"""Importar emissor (05/10/2026): o "Importar do Emissor Nacional" virou um
jeito de cadastrar uma empresa nova — certificado A1 -> empresa -> notas e
tomadores. Só dados sintéticos: certificados autoassinados descartáveis (no
formato do CN/SAN da ICP-Brasil) e páginas do ADN simuladas. Nada de rede."""
import datetime
import logging

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID
from fastapi.testclient import TestClient

from app.database import definir_prestador_atual, get_db
from app.main import app
from app.models import Certificado, Emissao, Prestador, PrestadorTomador, UsuarioPrestador
from app.services import importar_adn
from app.services.certificados import CertificadoIlegivelError, cnpj_valido, ler_certificado
from app.services.usuarios import criar_usuario
from tests.test_importar_nacional import nfse

CNPJ_NOVO = "11444777000161"  # sintético, com dígitos verificadores válidos
CNPJ_OUTRO = "11222333000181"
SENHA = "senha-do-a1-sintetico"
OID_CNPJ = x509.ObjectIdentifier("2.16.76.1.3.3")


@pytest.fixture(scope="module")
def chave():
    # Uma chave só pro módulo todo: gerar RSA é a parte lenta.
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _pfx(chave, cn, *, san_cnpj=None, san_tag=0x13, senha=SENHA, vence_em_dias=365):
    """.pfx autoassinado descartável. `san_cnpj`: põe o otherName da
    ICP-Brasil (OID 2.16.76.1.3.3) com o CNPJ, na codificação `san_tag`
    (0x13 PrintableString, 0x04 OCTET STRING, 0x0c UTF8String)."""
    nome = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])
    agora = datetime.datetime.now(datetime.timezone.utc)
    fim = agora + datetime.timedelta(days=vence_em_dias)
    construtor = (
        x509.CertificateBuilder()
        .subject_name(nome)
        .issuer_name(nome)
        .public_key(chave.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(min(agora, fim) - datetime.timedelta(days=30))
        .not_valid_after(fim)
    )
    if san_cnpj:
        valor = bytes([san_tag, len(san_cnpj)]) + san_cnpj.encode()
        construtor = construtor.add_extension(
            x509.SubjectAlternativeName([x509.RFC822Name("contato@exemplo.com"), x509.OtherName(OID_CNPJ, valor)]), critical=False
        )
    cert = construtor.sign(chave, hashes.SHA256())
    return pkcs12.serialize_key_and_certificates(
        name=b"teste", key=chave, cert=cert, cas=None,
        encryption_algorithm=serialization.BestAvailableEncryption(senha.encode()),
    )


@pytest.fixture(scope="module")
def pfx_empresa(chave):
    return _pfx(chave, f"EMPRESA NOVA SINTETICA LTDA:{CNPJ_NOVO}", san_cnpj=CNPJ_NOVO)


@pytest.fixture
def cliente(db, prestador_teste):
    db.commit = db.flush

    def _get_db_override():
        yield db

    app.dependency_overrides[get_db] = _get_db_override
    usuario = criar_usuario(db, prestador_teste.id, "dono@empresa.com", "senha-forte-1")
    db.add(UsuarioPrestador(usuario_id=usuario.id, prestador_id=prestador_teste.id))
    db.flush()
    client = TestClient(app)
    r = client.post("/api/auth/login", json={"email": "dono@empresa.com", "senha": "senha-forte-1"})
    assert r.status_code == 200, r.text
    yield client
    app.dependency_overrides.pop(get_db, None)


def _arquivo(pfx):
    return {"pfx": ("certificado.pfx", pfx, "application/x-pkcs12")}


DADOS = {"cpf_cnpj": CNPJ_NOVO, "razao_social": "Empresa Nova Sintética LTDA", "cod_municipio": "3106200"}


def _criar(client, pfx, senha=SENHA, **dados):
    return client.post("/api/empresas/importar", files=_arquivo(pfx), data={"senha": senha, **{**DADOS, **dados}})


# --- ler o certificado (serviço) ------------------------------------------------


def test_le_razao_social_cnpj_e_validade_do_certificado_icp_brasil(chave, pfx_empresa):
    d = ler_certificado(pfx_empresa, SENHA)
    assert d["titular"] == "EMPRESA NOVA SINTETICA LTDA" and d["cnpj"] == CNPJ_NOVO
    assert d["pessoa_fisica"] is False and d["vencido"] is False
    assert d["valido_de"] < datetime.date.today() < d["valido_ate"]

    # só o CN "RAZAO:CNPJ" (sem o otherName) também serve
    so_cn = ler_certificado(_pfx(chave, f"LOJA EXEMPLO ME:{CNPJ_OUTRO}"), SENHA)
    assert so_cn["titular"] == "LOJA EXEMPLO ME" and so_cn["cnpj"] == CNPJ_OUTRO

    # o otherName manda quando o CN não tem o CNPJ — em qualquer codificação
    for tag in (0x13, 0x04, 0x0C):
        d = ler_certificado(_pfx(chave, "LOJA SEM NUMERO NO NOME", san_cnpj=CNPJ_OUTRO, san_tag=tag), SENHA)
        assert d["cnpj"] == CNPJ_OUTRO and d["titular"] == "LOJA SEM NUMERO NO NOME"
    # ...e quando os dois divergem
    assert ler_certificado(_pfx(chave, f"MATRIZ SA:{CNPJ_NOVO}", san_cnpj=CNPJ_OUTRO), SENHA)["cnpj"] == CNPJ_OUTRO


def test_certificado_sem_cnpj_nao_inventa(chave, certificado_teste):
    # certificado comum (o fixture de sempre): só o nome, sem CNPJ
    d = ler_certificado(certificado_teste["pfx_bytes"], certificado_teste["senha"])
    assert d["titular"] == "TESTE REGRESSAO NFSE" and d["cnpj"] is None and d["pessoa_fisica"] is False

    # e-CPF ("NOME:CPF"): pessoa física, sem CNPJ
    pf = ler_certificado(_pfx(chave, "FULANA DE TAL:12345678909"), SENHA)
    assert pf["cnpj"] is None and pf["pessoa_fisica"] is True and pf["titular"] == "FULANA DE TAL"

    # 14 números que não são um CNPJ (dígito verificador errado) ficam de fora
    errado = ler_certificado(_pfx(chave, "EMPRESA X:11444777000199", san_cnpj="11444777000199"), SENHA)
    assert errado["cnpj"] is None and errado["titular"] == "EMPRESA X"
    # dois pontos no meio do nome não confundem
    assert ler_certificado(_pfx(chave, "ACME: SOLUCOES"), SENHA)["titular"] == "ACME: SOLUCOES"

    assert cnpj_valido(CNPJ_NOVO) and cnpj_valido(CNPJ_OUTRO)
    assert not cnpj_valido("11444777000199") and not cnpj_valido("00000000000000") and not cnpj_valido("123")


def test_senha_errada_ou_arquivo_qualquer_da_erro_claro_sem_a_senha(pfx_empresa):
    for conteudo, senha in ((pfx_empresa, "senha-errada-123"), (b"isto nao e um pfx", SENHA)):
        with pytest.raises(CertificadoIlegivelError) as erro:
            ler_certificado(conteudo, senha)
        assert "senha" in str(erro.value) and senha not in str(erro.value)


# --- POST /api/certificado/ler ---------------------------------------------------


def test_rota_ler_certificado_nao_guarda_nada(cliente, db, prestador_teste, pfx_empresa):
    r = cliente.post("/api/certificado/ler", files=_arquivo(pfx_empresa), data={"senha": SENHA})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["titular"] == "EMPRESA NOVA SINTETICA LTDA" and d["cnpj"] == CNPJ_NOVO
    assert d["ja_cadastrada"] is False and d["vencido"] is False and d["valido_ate"] > str(datetime.date.today())
    assert SENHA not in r.text

    # nada foi guardado nem criado
    definir_prestador_atual(db, prestador_teste.id)
    assert db.query(Certificado).count() == 0
    assert cliente.get("/api/certificado/status").json()["carregado"] is False
    assert len(cliente.get("/api/empresas").json()) == 1


def test_rota_ler_certificado_senha_errada_422_sem_vazar_a_senha(cliente, pfx_empresa, caplog):
    caplog.set_level(logging.DEBUG)
    r = cliente.post("/api/certificado/ler", files=_arquivo(pfx_empresa), data={"senha": "senha-errada-xyz"})
    assert r.status_code == 422
    assert "senha está certa" in r.json()["detail"]
    assert "senha-errada-xyz" not in r.text and "senha-errada-xyz" not in caplog.text

    # com a senha certa também não aparece em log nenhum
    caplog.clear()
    assert cliente.post("/api/certificado/ler", files=_arquivo(pfx_empresa), data={"senha": SENHA}).status_code == 200
    assert SENHA not in caplog.text


def test_rota_ler_certificado_avisa_quando_a_empresa_ja_e_do_login(cliente, chave, prestador_teste):
    pfx = _pfx(chave, f"PRESTADOR DE TESTE:{prestador_teste.cpf_cnpj}", san_cnpj=prestador_teste.cpf_cnpj)
    d = cliente.post("/api/certificado/ler", files=_arquivo(pfx), data={"senha": SENHA}).json()
    assert d["cnpj"] == prestador_teste.cpf_cnpj and d["ja_cadastrada"] is True


def test_rotas_exigem_login(db, pfx_empresa):
    db.commit = db.flush
    app.dependency_overrides[get_db] = lambda: (yield db)
    try:
        client = TestClient(app)
        assert client.post("/api/certificado/ler", files=_arquivo(pfx_empresa), data={"senha": SENHA}).status_code == 401
        assert _criar(client, pfx_empresa).status_code == 401
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_simulacao_nao_le_nem_guarda_certificado(db, pfx_empresa):
    db.commit = db.flush
    app.dependency_overrides[get_db] = lambda: (yield db)
    try:
        client = TestClient(app)
        assert client.post("/api/demo").status_code == 200
        for r in (client.post("/api/certificado/ler", files=_arquivo(pfx_empresa), data={"senha": SENHA}), _criar(client, pfx_empresa)):
            assert r.status_code == 403 and "simulação" in r.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_db, None)


# --- POST /api/empresas/importar + a importação de sempre -------------------------


def _paginas(monkeypatch, paginas):
    """ADN simulado: cada chamada devolve a próxima página."""
    def pagina_falsa(cliente_sefin, cnpj, nsu):
        assert cnpj == CNPJ_NOVO  # a leitura é da empresa NOVA
        pagina = paginas.pop(0)
        return pagina, (max(d["nsu"] for d in pagina) if pagina else None)

    monkeypatch.setattr(importar_adn, "PAUSA_S", 0)
    monkeypatch.setattr(importar_adn, "ler_pagina", pagina_falsa)


def _notas_sinteticas():
    xmls = [
        nfse(1, CNPJ_OUTRO, "Loja Exemplo LTDA", "2026-08", "100.00", desc="Comissão de vendas - AGOSTO/2026", prest=CNPJ_NOVO),
        nfse(2, CNPJ_OUTRO, "Loja Exemplo LTDA", "2026-09", "150.00", desc="Comissão de vendas - SETEMBRO/2026", prest=CNPJ_NOVO),
        nfse(3, "12345678909", "Cliente Pessoa Física", "2026-09", "40.00", tipo="CPF", desc="Consultoria avulsa", prest=CNPJ_NOVO),
        nfse(4, "44555666000199", "Cliente Antigo SA", "2026-02", "80.00", desc="Serviço fixo", prest=CNPJ_NOVO),
    ]
    return [{"nsu": i, "tipo": "NFSE", "xml": xml} for i, (xml, _chave) in enumerate(xmls, start=1)]


def test_importar_emissor_do_certificado_ate_o_resumo(cliente, db, prestador_teste, pfx_empresa, monkeypatch):
    r = _criar(cliente, pfx_empresa, nome_fantasia="Nova", cep="30.140-093", logradouro="Rua Exemplo", numero="10")
    assert r.status_code == 200, r.text
    corpo = r.json()
    nova_id = corpo["empresa"]["id"]
    assert corpo["empresa"]["cnpj"] == CNPJ_NOVO and corpo["empresa"]["ativa"] is True
    assert corpo["certificado"]["carregado"] is True and corpo["certificado"]["vencido"] is False
    assert SENHA not in r.text

    # a empresa nova é a ativa, com o certificado dela guardado (cifrado) e o módulo de notas
    assert cliente.get("/api/auth/me").json()["prestador_id"] == nova_id
    empresas = cliente.get("/api/empresas").json()
    assert len(empresas) == 2 and next(e for e in empresas if e["id"] == nova_id)["ativa"]
    assert cliente.get("/api/certificado/status").json()["carregado"] is True
    prestador = cliente.get("/api/prestador").json()
    assert prestador["razao_social"] == DADOS["razao_social"] and prestador["cep"] == "30140093"
    definir_prestador_atual(db, nova_id)
    guardado = db.query(Certificado).one()
    assert str(guardado.prestador_id) == nova_id and pfx_empresa[:20] not in guardado.pfx_criptografado
    assert SENHA.encode() not in guardado.senha_criptografada
    assert "emissor" in db.get(Prestador, nova_id).modulos

    # a importação de sempre roda na empresa nova, com o certificado guardado
    docs = _notas_sinteticas()
    _paginas(monkeypatch, [docs[:2], docs[2:], []])
    r = cliente.post("/api/importar/nacional/buscar", json={"desde_inicio": True, "desde": "2026-01"})
    assert r.status_code == 200, r.text
    previa = r.json()
    assert previa["terminou"] and previa["total_notas"] == 4 and all(g["sugestao"] == "novo" for g in previa["grupos"])

    mapeamento = [{"documento": g["documento"], "acao": "novo"} for g in previa["grupos"]]
    r = cliente.post("/api/importar/nacional", json={"mapeamento": mapeamento, "ajustar_modelos": True})
    assert r.status_code == 200, r.text
    resumo = r.json()
    assert resumo["importadas"] == 4 and resumo["vinculos_criados"] == 3 and resumo["puladas"] == []
    por_nome = {t["apelido"]: t for t in resumo["tomadores"]}
    assert len(por_nome) == 3

    loja = por_nome["Loja Exemplo LTDA"]
    assert loja["notas"] == 2 and loja["documento"] == CNPJ_OUTRO and loja["ativo"] and not loja["sem_nota"]
    assert loja["modelo_ajustado"] is True and loja["pendencia"] is None
    vinculo = db.get(PrestadorTomador, loja["id"])
    # pronto pra próxima nota: o mês virou campo automático (não repete "SETEMBRO/2026")
    assert vinculo.template_descricao == "Comissão de vendas - {mes_nome_upper}/{ano}"
    assert vinculo.cod_trib_nacional == "100101" and vinculo.cod_local_prestacao == "3106200"

    pessoa = por_nome["Cliente Pessoa Física"]
    assert pessoa["sem_nota"] is True and pessoa["notas"] == 1 and pessoa["modelo_ajustado"] is False
    antigo = por_nome["Cliente Antigo SA"]
    assert antigo["ativo"] is False and antigo["modelo_ajustado"] is False  # sem nota recente; descrição fixa fica como era
    assert db.get(PrestadorTomador, antigo["id"]).template_descricao == "Serviço fixo"

    assert db.query(Emissao).filter(Emissao.origem == "importada").count() == 4
    assert len(cliente.get("/api/vinculos?todos=true").json()) == 3

    # a empresa que já existia continua do jeito que estava
    cliente.post(f"/api/empresas/{prestador_teste.id}/ativar")
    assert cliente.get("/api/vinculos?todos=true").json() == []
    assert cliente.get("/api/certificado/status").json()["carregado"] is False


def test_importacao_normal_continua_sem_mexer_na_descricao(cliente, db, pfx_empresa, monkeypatch):
    """Sem `ajustar_modelos` (tela antiga de importação) nada muda: a
    descrição entra como veio — e o resultado ganha a lista de tomadores."""
    assert _criar(cliente, pfx_empresa).status_code == 200
    docs = _notas_sinteticas()
    _paginas(monkeypatch, [docs, []])
    previa = cliente.post("/api/importar/nacional/buscar", json={"desde": "2026-01"}).json()
    r = cliente.post("/api/importar/nacional", json={"mapeamento": [{"documento": g["documento"], "acao": "novo"} for g in previa["grupos"]]})
    assert r.status_code == 200, r.text
    loja = next(t for t in r.json()["tomadores"] if t["apelido"] == "Loja Exemplo LTDA")
    assert loja["modelo_ajustado"] is False
    assert db.get(PrestadorTomador, loja["id"]).template_descricao == "Comissão de vendas - AGOSTO/2026"


def test_senha_errada_nao_cria_empresa(cliente, pfx_empresa):
    r = _criar(cliente, pfx_empresa, senha="senha-errada-abc")
    assert r.status_code == 422 and "senha está certa" in r.json()["detail"]
    assert "senha-errada-abc" not in r.text
    assert len(cliente.get("/api/empresas").json()) == 1


def test_certificado_de_outro_cnpj_ou_vencido_nao_cria_empresa(cliente, chave):
    de_outro = _pfx(chave, f"OUTRA EMPRESA LTDA:{CNPJ_OUTRO}", san_cnpj=CNPJ_OUTRO)
    r = _criar(cliente, de_outro)
    assert r.status_code == 422 and "11.222.333/0001-81" in r.json()["detail"]

    vencido = _pfx(chave, f"EMPRESA NOVA SINTETICA LTDA:{CNPJ_NOVO}", san_cnpj=CNPJ_NOVO, vence_em_dias=-3)
    lido = cliente.post("/api/certificado/ler", files=_arquivo(vencido), data={"senha": SENHA}).json()
    assert lido["vencido"] is True
    r = _criar(cliente, vencido)
    assert r.status_code == 422 and "venceu" in r.json()["detail"]

    assert _criar(cliente, _pfx(chave, f"X:{CNPJ_NOVO}"), cpf_cnpj="123").status_code == 422  # CNPJ incompleto
    assert len(cliente.get("/api/empresas").json()) == 1


def test_filial_usa_o_certificado_da_matriz_e_certificado_sem_cnpj_aceita_o_digitado(cliente, chave, certificado_teste):
    # mesma raiz de CNPJ (8 primeiros números): matriz 0001 e filial 0002
    matriz = _pfx(chave, f"EMPRESA NOVA SINTETICA LTDA:{CNPJ_NOVO}", san_cnpj=CNPJ_NOVO)
    assert _criar(cliente, matriz, cpf_cnpj="11444777000242").status_code == 200
    # certificado de onde não deu pra tirar o CNPJ: vale o que a pessoa digitou
    r = cliente.post(
        "/api/empresas/importar", files=_arquivo(certificado_teste["pfx_bytes"]),
        data={"senha": certificado_teste["senha"], **DADOS, "cpf_cnpj": "55.666.777/0001-81"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["empresa"]["cnpj"] == "55666777000181"
    assert len(cliente.get("/api/empresas").json()) == 3


def test_cnpj_que_ja_existe_da_o_erro_amigavel_de_sempre(cliente, pfx_empresa, prestador_teste):
    assert _criar(cliente, pfx_empresa).status_code == 200
    cliente.post(f"/api/empresas/{prestador_teste.id}/ativar")
    r = _criar(cliente, pfx_empresa)
    assert r.status_code == 409 and r.json()["detail"] == "Esse CNPJ já está cadastrado na Agente Ana."
    # igual ao caminho manual
    manual = cliente.post("/api/empresas", json=DADOS)
    assert manual.status_code == 409 and manual.json()["detail"] == r.json()["detail"]
    assert len(cliente.get("/api/empresas").json()) == 2
    # a empresa aberta não ganhou certificado de tabela
    assert cliente.get("/api/certificado/status").json()["carregado"] is False


def test_importacao_indisponivel_mantem_empresa_e_certificado_e_da_pra_tentar_depois(cliente, pfx_empresa, monkeypatch):
    nova_id = _criar(cliente, pfx_empresa).json()["empresa"]["id"]

    def fora_do_ar(cliente_sefin, cnpj, nsu):
        raise importar_adn.ImportacaoAdnError("Não consegui falar com o Emissor Nacional agora. Tente de novo em alguns minutos.")

    monkeypatch.setattr(importar_adn, "ler_pagina", fora_do_ar)
    r = cliente.post("/api/importar/nacional/buscar", json={"desde_inicio": True})
    assert r.status_code == 502 and "Emissor Nacional" in r.json()["detail"]

    # o que já foi feito continua feito
    empresas = cliente.get("/api/empresas").json()
    assert len(empresas) == 2 and next(e for e in empresas if e["id"] == nova_id)["ativa"]
    assert cliente.get("/api/certificado/status").json()["carregado"] is True
    assert cliente.get("/api/vinculos?todos=true").json() == []

    # mais tarde (Empresa › Notas e e-mails › Importar do Emissor Nacional) funciona
    docs = _notas_sinteticas()
    _paginas(monkeypatch, [docs, []])
    previa = cliente.post("/api/importar/nacional/buscar", json={"desde": "2026-01"}).json()
    assert previa["terminou"] and previa["total_notas"] == 4
    r = cliente.post("/api/importar/nacional", json={"mapeamento": [{"documento": g["documento"], "acao": "novo"} for g in previa["grupos"]]})
    assert r.status_code == 200 and r.json()["importadas"] == 4


def test_cadastrar_do_zero_continua_funcionando(cliente):
    r = cliente.post("/api/empresas", json=DADOS)
    assert r.status_code == 200, r.text
    assert r.json()["cnpj"] == CNPJ_NOVO and r.json()["ativa"] is True
    assert cliente.get("/api/auth/me").json()["prestador_id"] == r.json()["id"]
    assert cliente.get("/api/certificado/status").json()["carregado"] is False
