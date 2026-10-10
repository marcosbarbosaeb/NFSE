"""Conferência (app/services/conferencia.py): os controles pra que o cadastro
do tomador e a nota não saiam errados. Dados sintéticos, Postgres real com
rollback (mesmo padrão das outras suítes)."""
import datetime
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event

from app.database import get_db
from app.main import app, prestador_atual_id
from app.models import Certificado, Emissao, PrestadorTomador, Tomador
from app.services import conferencia
from app.services.conferencia import (
    campos_desconhecidos, cnpj_valido, conferir_emissao, conferir_empresa, conferir_nota, conferir_vinculo,
    conferir_vinculos, cpf_valido,
)
from app.services.motor_emissao import criar_rascunho, montar
from app.services.relatorio_shopee import ler_relatorio, gerar_notas
from app.tempo import hoje as hoje_br


@pytest.fixture
def client(db, prestador_teste):
    db.commit = db.flush

    def _get_db_override():
        yield db

    app.dependency_overrides[get_db] = _get_db_override
    app.dependency_overrides[prestador_atual_id] = lambda: prestador_teste.id
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(prestador_atual_id, None)


def _codigos(pontos, nivel=None):
    return {p["codigo"] for p in pontos if nivel is None or p["nivel"] == nivel}


def _competencia(meses_atras: int = 0) -> str:
    hoje = hoje_br()
    total = hoje.year * 12 + hoje.month - 1 - meses_atras
    return f"{total // 12:04d}-{total % 12 + 1:02d}"


def _certificado(db, prestador, dias: int = 200):
    db.add(Certificado(
        id=uuid.uuid4(), prestador_id=prestador.id, pfx_criptografado=b"x", senha_criptografada=b"x",
        validade=hoje_br() + datetime.timedelta(days=dias),
    ))
    db.flush()


def _nota(db, vinculo, competencia, valor, estado="confirmado", codigos=None):
    """Uma nota antiga deste tomador, direto no banco."""
    e = Emissao(
        id=uuid.uuid4(), prestador_tomador_id=vinculo.id, prestador_id=vinculo.prestador_id, competencia=competencia,
        valor=valor, serie="9", n_dps=int(uuid.uuid4().int % 10**9), estado=estado,
        tomador_snapshot={"codigo_servico_usado": codigos or {
            "cLocPrestacao": vinculo.cod_local_prestacao, "cTribNac": vinculo.cod_trib_nacional,
            "cTribMun": vinculo.cod_trib_municipal, "cNBS": vinculo.cod_nbs,
        }},
    )
    db.add(e)
    db.flush()
    return e


# --- dígitos verificadores -------------------------------------------------------


def test_cnpj_e_cpf_digitos_verificadores():
    assert cnpj_valido("11222333000181") and cnpj_valido("11.222.333/0001-81")
    assert cnpj_valido("12ABC34501DE35")  # CNPJ com letras (exemplo oficial do Serpro)
    assert not cnpj_valido("11222333000182")
    assert not cnpj_valido("11111111111111") and not cnpj_valido("123") and not cnpj_valido(None)
    assert cpf_valido("529.982.247-25") and not cpf_valido("52998224724") and not cpf_valido("00000000000")


def test_campos_desconhecidos_segue_o_renderizador():
    assert campos_desconhecidos("Comissão {mes_nome_upper}/{ano} {competencia_mm_aaaa} {mes} ordem {ordem}") == []
    assert campos_desconhecidos("Comissão {cliente} de {mes} {valor} {cliente}") == ["{cliente}", "{valor}"]


# --- tomador -----------------------------------------------------------------------


def test_cadastro_certo_nao_tem_erro(db, vinculo_teste):
    vinculo_teste.email_contato = "financeiro@exemplo.com.br"
    assert conferir_vinculo(db, vinculo_teste) == []


def test_erros_do_cadastro_do_tomador(db, vinculo_teste):
    t = vinculo_teste.tomador
    t.cnpj, t.razao_social, t.cod_municipio, t.cep, t.bairro = "11222333000182", "  ", "9999999", "0131100", None
    vinculo_teste.cod_trib_nacional = "999999"
    vinculo_teste.cod_nbs = "1.1406"
    vinculo_teste.cod_local_prestacao = "1234567"
    vinculo_teste.template_descricao = "Comissão {cliente} {mes}"
    pontos = conferir_vinculo(db, vinculo_teste)
    assert _codigos(pontos, "erro") == {
        "documento_invalido", "razao_social_vazia", "cidade_invalida", "cep_invalido",
        "servico_invalido", "nbs_invalido", "local_prestacao_invalido", "descricao_campo_desconhecido",
    }
    for p in pontos:
        assert p["onde"] == "tomador" and p["mensagem"] and p["como_corrigir"]
    endereco = next(p for p in pontos if p["codigo"] == "endereco_incompleto")
    assert "bairro" in endereco["mensagem"] and "CEP" not in endereco["mensagem"]

    vinculo_teste.template_descricao = "   "
    assert "descricao_vazia" in _codigos(conferir_vinculo(db, vinculo_teste), "erro")


def test_endereco_sem_cep_entra_como_incompleto(db, vinculo_teste):
    vinculo_teste.tomador.cep = None
    pontos = conferir_vinculo(db, vinculo_teste)
    # Endereço pela metade é aviso: a nota sai sem o endereço do tomador.
    assert "endereco_incompleto" in _codigos(pontos, "aviso") and "cep_invalido" not in _codigos(pontos)


def test_avisos_do_tomador_email_e_descricao_longa(db, vinculo_teste):
    assert _codigos(conferir_vinculo(db, vinculo_teste)) == {"sem_email"}
    vinculo_teste.envio_canal = "whatsapp"
    assert conferir_vinculo(db, vinculo_teste) == []
    vinculo_teste.envio_canal, vinculo_teste.email_para = "email", "nf@exemplo.com.br"
    assert conferir_vinculo(db, vinculo_teste) == []
    vinculo_teste.template_descricao = "x" * 2001
    pontos = conferir_vinculo(db, vinculo_teste)
    assert _codigos(pontos, "aviso") == {"descricao_longa"} and not _codigos(pontos, "erro")


def test_codigo_diferente_das_ultimas_notas_autorizadas(db, vinculo_teste):
    vinculo_teste.email_contato = "a@exemplo.com.br"
    vinculo_teste.cod_nbs = "114062000"
    _nota(db, vinculo_teste, _competencia(1), 100, codigos={"cTribNac": "17.06.01", "cTribMun": "1", "cNBS": "1.1406.20.00"})
    # nota que não foi autorizada não ensina nada
    _nota(db, vinculo_teste, _competencia(0), 100, estado="erro", codigos={"cTribNac": "010101", "cTribMun": "777", "cNBS": "999999999"})
    assert conferir_vinculo(db, vinculo_teste) == []  # mesmo código, escrito de outro jeito

    vinculo_teste.cod_trib_nacional, vinculo_teste.cod_trib_municipal, vinculo_teste.cod_nbs = "010101", None, "123456789"
    pontos = conferir_vinculo(db, vinculo_teste)
    assert _codigos(pontos, "aviso") == {"servico_diferente", "cod_municipal_diferente", "nbs_diferente"}
    assert not _codigos(pontos, "erro")
    assert "17.06.01" in next(p for p in pontos if p["codigo"] == "servico_diferente")["mensagem"]


def test_so_controle_de_recebimento_nao_confere_nota(db, vinculo_teste):
    t = vinculo_teste.tomador
    t.cnpj, t.status, t.cep, t.logradouro = "X" + uuid.uuid4().hex[:13].upper(), "interno", None, None
    vinculo_teste.cod_trib_nacional, vinculo_teste.sem_nota = "000000", True
    assert conferir_vinculo(db, vinculo_teste) == []
    vinculo_teste.sem_nota = False
    erros = _codigos(conferir_vinculo(db, vinculo_teste), "erro")
    assert {"documento_vazio", "servico_invalido"} <= erros and "documento_invalido" not in erros


def test_simulacao_nao_reclama_do_cnpj_de_mentira(db, vinculo_teste, prestador_teste):
    vinculo_teste.tomador.cnpj = "11222333000199"
    vinculo_teste.email_contato = "a@exemplo.com.br"
    assert "documento_invalido" in _codigos(conferir_vinculo(db, vinculo_teste))
    prestador_teste.demo = True
    db.flush()
    assert conferir_vinculo(db, vinculo_teste) == []
    assert conferir_empresa(db, prestador_teste.id) == []


def test_varios_tomadores_sem_uma_consulta_por_tomador(db, prestador_teste, vinculo_teste):
    from app.services.vinculos import listar_vinculos_ativos

    for i in range(12):
        db.add(PrestadorTomador(
            id=uuid.uuid4(), prestador_id=prestador_teste.id, tomador_id=vinculo_teste.tomador_id, apelido=f"Programa {i}",
            cod_local_prestacao="3106200", cod_trib_nacional="170601" if i % 2 else "999999",
            template_descricao="Comissão {mes}/{ano}", email_contato="a@exemplo.com.br", ativo=True,
        ))
    db.flush()
    _nota(db, vinculo_teste, _competencia(1), 100)
    vinculos = listar_vinculos_ativos(db)
    assert len(vinculos) == 13

    consultas = []
    conexao = db.connection()
    ouvinte = lambda *a: consultas.append(a[2])  # noqa: E731
    event.listen(conexao, "before_cursor_execute", ouvinte)
    try:
        resultado = conferir_vinculos(db, vinculos)
    finally:
        event.remove(conexao, "before_cursor_execute", ouvinte)
    assert len(consultas) <= 3, consultas
    assert len(resultado) == 13
    assert sum(1 for pontos in resultado.values() if "servico_invalido" in _codigos(pontos)) == 6


# --- empresa -----------------------------------------------------------------------


def test_empresa_certificado_ambiente_e_aliquota(db, prestador_teste):
    prestador_teste.aliquota_atual = None  # a fixture já vem com regime e alíquota
    prestador_teste.op_simples_nacional = None
    pontos = conferir_empresa(db, prestador_teste.id)
    assert _codigos(pontos, "erro") == {"sem_certificado"} and all(p["onde"] == "empresa" for p in pontos)
    assert _codigos(conferir_empresa(db, prestador_teste.id, certificado_trava=False), "aviso") == {"sem_certificado"}

    _certificado(db, prestador_teste, dias=-1)
    assert _codigos(conferir_empresa(db, prestador_teste.id), "erro") == {"certificado_vencido"}
    registro = db.query(Certificado).filter_by(prestador_id=prestador_teste.id).one()
    registro.validade = hoje_br() + datetime.timedelta(days=29)
    db.flush()
    assert _codigos(conferir_empresa(db, prestador_teste.id)) == {"certificado_vencendo"}
    assert conferir_empresa(db, prestador_teste.id)[0]["nivel"] == "aviso"
    registro.validade = hoje_br() + datetime.timedelta(days=30)
    db.flush()
    assert conferir_empresa(db, prestador_teste.id) == []

    prestador_teste.tp_amb_padrao, prestador_teste.op_simples_nacional = "2", "3"
    db.flush()
    assert _codigos(conferir_empresa(db, prestador_teste.id), "aviso") == {"ambiente_teste", "aliquota_nao_definida"}
    prestador_teste.aliquota_atual, prestador_teste.modo_teste = 6, True
    db.flush()
    assert conferir_empresa(db, prestador_teste.id) == []


# --- nota (antes de gerar) ---------------------------------------------------------


def test_nota_certa_so_avisa_do_certificado(db, vinculo_teste):
    pontos = conferir_nota(db, vinculo_teste, 100.0, hoje_br(), None, None)
    assert _codigos(pontos) == {"sem_certificado"} and pontos[0]["nivel"] == "aviso"  # sem_email fica só no cadastro


def test_nota_erros_de_valor_data_e_ordem(db, vinculo_teste, prestador_teste):
    _certificado(db, prestador_teste)
    vinculo_teste.template_descricao = "Comissão ordem {ordem}"
    amanha = hoje_br() + datetime.timedelta(days=1)
    pontos = conferir_nota(db, vinculo_teste, 0, amanha, " ", None)
    assert _codigos(pontos, "erro") == {"valor_invalido", "competencia_futura", "ordem_faltando"}
    assert all(p["onde"] == "nota" for p in pontos)
    assert conferir_nota(db, vinculo_teste, 10, hoje_br(), "123", None) == []
    assert "valor_invalido" in _codigos(conferir_nota(db, vinculo_teste, None, hoje_br(), "123", None))

    vinculo_teste.template_descricao = "x" * 1995 + " {ordem}"
    assert _codigos(conferir_nota(db, vinculo_teste, 10, hoje_br(), "1234567890", None), "erro") == {"descricao_longa"}


def test_nota_leva_os_erros_do_cadastro(db, vinculo_teste, prestador_teste):
    _certificado(db, prestador_teste)
    vinculo_teste.tomador.cnpj = "11222333000182"
    pontos = conferir_nota(db, vinculo_teste, 10, hoje_br(), None, None)
    assert _codigos(pontos) == {"documento_invalido"} and pontos[0]["onde"] == "tomador"


def test_nota_valor_fora_do_costume(db, vinculo_teste, prestador_teste):
    _certificado(db, prestador_teste)
    for i, valor in enumerate([1000, 1200, 1300, 1234.56, 1250], start=1):
        _nota(db, vinculo_teste, _competencia(i), valor)
    _nota(db, vinculo_teste, _competencia(6), 99999, estado="cancelada")  # cancelada não conta
    assert conferir_nota(db, vinculo_teste, 1500, hoje_br(), None, None) == []
    alto = conferir_nota(db, vinculo_teste, 12345.60, hoje_br(), None, None)
    assert _codigos(alto) == {"valor_fora_do_costume"} and alto[0]["nivel"] == "aviso"
    assert "R$ 1.234,56" in alto[0]["mensagem"] and "R$ 12.345,60" in alto[0]["mensagem"]
    assert _codigos(conferir_nota(db, vinculo_teste, 123.45, hoje_br(), None, None)) == {"valor_fora_do_costume"}
    assert conferir_nota(db, vinculo_teste, 411.60, hoje_br(), None, None) == []  # 1/3 de 1.234,56 = 411,52


def test_nota_mesmo_valor_de_outra_recente(db, vinculo_teste, prestador_teste):
    _certificado(db, prestador_teste)
    _nota(db, vinculo_teste, _competencia(1), 850.40)
    _nota(db, vinculo_teste, _competencia(2), 700)
    repetida = conferir_nota(db, vinculo_teste, 850.40, hoje_br(), None, None)
    assert _codigos(repetida) == {"possivel_duplicada"} and repetida[0]["nivel"] == "aviso"
    assert conferir_nota(db, vinculo_teste, 850.41, hoje_br(), None, None) == []
    # valor fixo todo mês (mensalidade) não é sinal de nota repetida
    _nota(db, vinculo_teste, _competencia(3), 850.40)
    assert conferir_nota(db, vinculo_teste, 850.40, hoje_br(), None, None) == []


def test_nota_de_mes_antigo(db, vinculo_teste, prestador_teste):
    _certificado(db, prestador_teste)
    hoje = hoje_br()
    assert conferir_nota(db, vinculo_teste, 10, None, None, None, competencia=_competencia(2)) == []
    antiga = conferir_nota(db, vinculo_teste, 10, None, None, None, competencia=_competencia(3))
    assert _codigos(antiga) == {"competencia_antiga"} and antiga[0]["nivel"] == "aviso"
    assert _codigos(conferir_nota(db, vinculo_teste, 10, hoje - datetime.timedelta(days=125), None, None)) == {"competencia_antiga"}
    assert _codigos(conferir_nota(db, vinculo_teste, 10, hoje, None, 80)) == {"aliquota_fora_do_normal"}


# --- nota que já existe -------------------------------------------------------------


def test_emissao_nao_se_compara_com_ela_mesma(db, vinculo_teste, prestador_teste):
    _certificado(db, prestador_teste)
    vinculo_teste.email_contato = "a@exemplo.com.br"
    emissao = montar(db, criar_rascunho(db, vinculo_teste, competencia=_competencia(0), valor=500.0, tpAmb="1"))
    assert conferir_emissao(db, emissao) == []

    _nota(db, vinculo_teste, _competencia(1), 5000)
    assert _codigos(conferir_emissao(db, emissao)) == {"valor_fora_do_costume"}


def test_emissao_usa_o_que_esta_guardado_na_nota(db, vinculo_teste, prestador_teste):
    emissao = montar(db, criar_rascunho(db, vinculo_teste, competencia=_competencia(0), valor=500.0, tpAmb="2"))
    snap = dict(emissao.tomador_snapshot)
    snap.update(cnpj="11222333000182", descricao_renderizada="Comissão {cliente}", dcompet=(hoje_br() + datetime.timedelta(days=3)).isoformat())
    snap["endereco"] = {**snap["endereco"], "CEP": "123", "xBairro": ""}
    snap["codigo_servico_usado"] = {**snap["codigo_servico_usado"], "cTribNac": "999999"}
    emissao.tomador_snapshot = snap
    db.flush()
    pontos = conferir_emissao(db, emissao)
    assert _codigos(pontos, "erro") == {
        "documento_invalido", "cep_invalido", "servico_invalido", "descricao_campo_desconhecido",
        "competencia_futura", "sem_certificado",
    }
    # o cadastro (certo) ficou diferente do que a nota guardou; e a nota é de teste
    assert _codigos(pontos, "aviso") == {"cadastro_mudou", "ambiente_teste", "endereco_incompleto"}
    assert "gere a nota de novo" in next(p for p in pontos if p["codigo"] == "documento_invalido")["como_corrigir"]


def test_emissao_de_vendedor_da_shopee_nao_quebra(db, vinculo_teste, prestador_teste):
    _certificado(db, prestador_teste)
    _nota(db, vinculo_teste, _competencia(1), 1)  # o "costume" do vínculo não vale pro vendedor
    avulso = {
        "documento": "52998224725", "tipo_documento": "CPF", "razao_social": "VENDEDORA EXEMPLO",
        "endereco": {"cMun": "3550308", "CEP": "01311000", "xLgr": "Rua A", "nro": "1", "xBairro": "Centro"},
    }
    emissao = montar(db, criar_rascunho(db, vinculo_teste, competencia=_competencia(0), valor=90000.0, tpAmb="1", tomador_avulso=avulso))
    assert emissao.tomador_documento == "52998224725"
    assert conferir_emissao(db, emissao) == []

    ruim = {"documento": "52998224724", "tipo_documento": "CPF", "razao_social": "OUTRO VENDEDOR", "endereco": {"cMun": "9999999", "CEP": "1234", "xLgr": "Rua B", "nro": "2", "xBairro": "Centro"}}
    emissao2 = criar_rascunho(db, vinculo_teste, competencia=_competencia(0), valor=10.0, tpAmb="1", tomador_avulso=ruim)
    pontos = conferir_emissao(db, emissao2)
    assert _codigos(pontos) == {"documento_invalido", "cidade_invalida", "cep_invalido"}
    assert all(p["onde"] == "nota" for p in pontos)

    # sem endereço reconhecido (não vai na nota) e estrangeiro com NIF: nada a reclamar
    sem_endereco = {"documento": "11222333000181", "tipo_documento": "CNPJ", "razao_social": "LOJA SEM ENDERECO", "endereco": None}
    emissao3 = criar_rascunho(db, vinculo_teste, competencia=_competencia(0), valor=10.0, tpAmb="1", tomador_avulso=sem_endereco)
    assert conferir_emissao(db, emissao3) == []
    estrangeiro = {"documento": "NIF-123", "tipo_documento": "NIF", "razao_social": "SELLER LTD", "endereco": None, "pais": "CN"}
    emissao4 = criar_rascunho(db, vinculo_teste, competencia=_competencia(0), valor=10.0, tpAmb="1", tomador_avulso=estrangeiro)
    assert conferir_emissao(db, emissao4) == []

    # retrato estragado/antigo não derruba
    emissao4.tomador_snapshot = {"avulso": True}
    db.flush()
    assert "razao_social_vazia" in _codigos(conferir_emissao(db, emissao4))


def test_lote_da_shopee_nao_passa_pela_trava(db, vinculo_teste, prestador_teste):
    """A geração em lote continua gerando mesmo com o cadastro do vínculo
    com erro (a trava é só de POST /api/dps) — e cada nota gerada pode ser
    conferida depois, pelo retrato do vendedor."""
    _certificado(db, prestador_teste)
    vinculo_teste.tomador.cnpj = "11222333000182"  # travaria POST /api/dps
    csv = (
        "\ufeffMês de conclusão,Nome da loja,ID da Loja,Comissão Total do Vendedor,CNPJ do Vendedor,CPF do Vendedor,"
        "Identificação Fiscal Estrangeira,Razão social do vendedor,Endereço do Vendedor,País do Vendedor,Inscrição Estadual,E-mail\n"
        'Aug 2026,Loja Um,1,"R$7,14",11222333000181,,,LOJA UM LTDA,"R Exemplo, 425, Sala 2 - Centro, Hortolândia - São Paulo, 13186642",BR,1,um@exemplo.com\n'
        'Aug 2026,Pessoa Física,3,"R$1,00",,52998224724,,FULANA DE TAL,"R Dois, 74 - Vila Nova, Jandira - São Paulo, 06636030",BR,,f@exemplo.com\n'
    ).encode("utf-8")
    resultado = gerar_notas(db, vinculo_teste, ler_relatorio(csv), competencia="2026-08", dcompet=hoje_br().isoformat(), tpAmb="1")
    assert resultado.geradas == 2 and not resultado.erros
    notas = {n.tomador_documento: n for n in db.query(Emissao).filter_by(prestador_tomador_id=vinculo_teste.id)}
    assert conferir_emissao(db, notas["11222333000181"]) == []
    assert _codigos(conferir_emissao(db, notas["52998224724"])) == {"documento_invalido"}


# --- rotas ---------------------------------------------------------------------------


def test_rotas_de_conferencia(client, db, vinculo_teste, prestador_teste):
    r = client.get(f"/api/vinculos/{vinculo_teste.id}/conferencia")
    assert r.status_code == 200, r.text
    assert r.json()["erros"] == 0 and r.json()["avisos"] == 1 and r.json()["pontos"][0]["codigo"] == "sem_email"
    assert client.get(f"/api/vinculos/{uuid.uuid4()}/conferencia").status_code == 404

    vinculo_teste.tomador.cep = "123"
    db.flush()
    r = client.get("/api/conferencia/tomadores")
    assert r.status_code == 200 and r.json() == {str(vinculo_teste.id): {"erros": 1, "avisos": 1}}

    corpo = {"vinculo_id": str(vinculo_teste.id), "valor": 100, "data_competencia": hoje_br().isoformat(), "ordem": None, "aliq_sn": None}
    r = client.post("/api/dps/conferir", json=corpo)
    assert r.status_code == 200, r.text
    assert {p["codigo"] for p in r.json()["pontos"]} == {"cep_invalido", "sem_certificado"}
    assert client.post("/api/dps/conferir", json={**corpo, "vinculo_id": str(uuid.uuid4())}).status_code == 404
    # ainda sem valor digitado: responde (com o erro de valor), não quebra
    r = client.post("/api/dps/conferir", json={"vinculo_id": str(vinculo_teste.id)})
    assert r.status_code == 200 and "valor_invalido" in {p["codigo"] for p in r.json()["pontos"]}


def test_post_dps_recusa_com_erro_e_gera_com_aviso(client, db, vinculo_teste):
    vinculo_teste.tomador.cnpj = "11222333000182"
    db.flush()
    corpo = {"vinculo_id": str(vinculo_teste.id), "competencia": _competencia(0), "valor": 100.0}
    r = client.post("/api/dps", json=corpo)
    assert r.status_code == 422
    assert r.json()["detail"].startswith("Não gerei a nota") and "11222333000182" in r.json()["detail"]
    assert db.query(Emissao).filter_by(prestador_tomador_id=vinculo_teste.id).count() == 0

    vinculo_teste.tomador.cnpj = "11222333000181"
    db.flush()
    # só avisos (sem certificado, mês antigo): gera
    r = client.post("/api/dps", json={**corpo, "competencia": _competencia(5)})
    assert r.status_code == 200, r.text
    emissao_id = r.json()["id"]

    r = client.get(f"/api/dps/{emissao_id}/conferencia")
    assert r.status_code == 200, r.text
    assert {p["codigo"] for p in r.json()["pontos"]} == {"sem_certificado", "competencia_antiga"}
    assert client.get(f"/api/dps/{uuid.uuid4()}/conferencia").status_code == 404

    emissao = db.get(Emissao, uuid.UUID(emissao_id))
    emissao.estado = "confirmado"
    db.flush()
    assert client.get(f"/api/dps/{emissao_id}/conferencia").json() == {"pontos": []}


def test_post_dps_recusa_data_no_futuro(client, vinculo_teste):
    amanha = hoje_br() + datetime.timedelta(days=1)
    r = client.post("/api/dps", json={
        "vinculo_id": str(vinculo_teste.id), "competencia": f"{amanha.year:04d}-{amanha.month:02d}", "valor": 10,
        "data_competencia": amanha.isoformat(),
    })
    assert r.status_code == 422 and "ainda não chegou" in r.json()["detail"]


def test_rotas_so_para_quem_tem_o_emissor(client, db, vinculo_teste, prestador_teste):
    prestador_teste.modulos = ["financeiro"]
    db.flush()
    assert client.get("/api/conferencia/tomadores").status_code == 403
    assert client.get(f"/api/vinculos/{vinculo_teste.id}/conferencia").status_code == 403
    assert client.post("/api/dps/conferir", json={"vinculo_id": str(vinculo_teste.id)}).status_code == 403


def test_frase_de_recusa_resume_os_erros():
    pontos = [conferencia._ponto("erro", f"e{i}", f"Problema {i}.", "Conserte.") for i in range(5)] + [conferencia._ponto("aviso", "a", "Aviso.")]
    frase = conferencia.frase_de_recusa(pontos)
    assert "5 problemas" in frase and "Problema 2." in frase and "Problema 3." not in frase and "e mais 2" in frase and "Aviso" not in frase
