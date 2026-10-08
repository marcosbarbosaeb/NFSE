"""Uso da plataforma e passeio de novidades (08/10/2026). Dados sintéticos."""
import uuid

from app import novidades
from app.config import get_settings
from app.models import EventoUso, Usuario
from app.services import uso

from tests.test_contador import _conta, _entrar, api  # noqa: F401 (fixtures)


def test_tela_e_normalizada_sem_ids_nem_consulta():
    um = "7b0e6a52-1c1d-4f6e-9d0a-2f6b1c2d3e4f"
    assert uso.normalizar_tela(f"/app/nfse/{um}?pagamento=abc") == "/app/nfse/:id"
    assert uso.normalizar_tela("/app/empresa?aba=notas&x=1") == "/app/empresa?aba=notas"
    assert uso.normalizar_tela("/app/") == "/app"
    assert uso.normalizar_tela("/parceira/segredo") is None and uso.normalizar_tela("https://outro.site") is None


def test_o_que_e_anotado():
    assert uso.interessa("POST", "/api/dps", 200) == "acao"
    assert uso.interessa("GET", "/api/dps", 200) is None            # leitura não conta
    assert uso.interessa("POST", "/api/dps", 409) == "erro"
    assert uso.interessa("GET", "/api/dps/x", 500) == "erro"
    assert uso.interessa("POST", "/api/dps", 401) is None            # sessão vencida não é erro de uso
    assert uso.interessa("POST", "/api/auth/login", 401) is None and uso.interessa("POST", "/api/uso/tela", 200) is None
    assert uso.interessa("GET", "/app/nfse", 200) is None


def test_painel_de_uso_so_pra_gestao_com_funil_e_sugestoes(db, api, monkeypatch):
    _conta(db, "00000000000434", "gestor@plataforma.example", nome="PLATAFORMA")
    cliente, dona = _conta(db, "00000000000272", "dona@cliente.example", nome="CLIENTE")
    monkeypatch.setattr(get_settings(), "admin_emails", "gestor@plataforma.example")
    for tipo, nome, detalhe, vezes in (
        ("tela", "/app/nfse", None, 5), ("tela", "/app/empresa?aba=notas", None, 2),
        ("acao", "POST /api/dps", None, 4), ("acao", "POST /api/dps/{emissao_id}/assinar", None, 3),
        ("erro", "POST /api/dps", "409", 3),
    ):
        for _ in range(vezes):
            db.add(EventoUso(id=uuid.uuid4(), usuario_id=dona.id, prestador_id=cliente.id, tipo=tipo, nome=nome, detalhe=detalhe))
    db.flush()

    assert _entrar(api, "dona@cliente.example").get("/api/gestao/uso").status_code == 403
    d = _entrar(api, "gestor@plataforma.example").get("/api/gestao/uso").json()
    assert (d["eventos"], d["pessoas"]) == (17, 1)
    assert [(t["titulo"], t["vezes"]) for t in d["telas"]] == [("NFS-e (lista)", 5), ("Empresa › aba notas", 2)]
    assert [(a["titulo"], a["vezes"]) for a in d["acoes"]] == [("Criou uma nota", 4), ("Assinou uma nota", 3)]
    assert [(e["titulo"], e["status"], e["vezes"]) for e in d["erros"]] == [("Criou uma nota", "409", 3)]
    # o caminho até a primeira nota: cada etapa tem no máximo as contas da anterior
    contas = [e["contas"] for e in d["funil"]]
    assert [e["etapa"] for e in d["funil"]][0] == "Criaram a conta" and d["funil"][-1]["etapa"] == "Emitiram a primeira nota"
    assert contas[0] >= 2 and contas == sorted(contas, reverse=True)
    tipos = [s["tipo"] for s in d["sugestoes"]]
    assert "erro" in tipos
    # nada de conteúdo: só nomes de rota e contagens
    assert "dona@cliente.example" not in str(d)


def test_conta_nova_nao_ve_passeio_e_conta_antiga_ve_so_a_ultima_versao(db, api):
    # conta de antes das novidades (sem nada guardado): só a versão mais nova é "nova"
    _conta(db, "00000000000272", "antiga@cliente.example", nome="ANTIGA")
    d = _entrar(api, "antiga@cliente.example").get("/api/novidades").json()
    assert d["novas"] == 1 and [v["versao"] for v in d["versoes"] if v["nova"]] == [novidades.VERSAO]

    # conta criada agora: já nasce em dia
    cliente = api()
    r = cliente.post("/api/cadastro", json={
        "email": "nova@cliente.example", "senha": "SenhaDeTeste123!", "whatsapp": "92999990000",
        "razao_social": "NOVA LTDA", "cpf_cnpj": "00000000000787", "cod_municipio": "3106200",
    })
    assert r.status_code == 200, r.text
    nova = db.query(Usuario).filter_by(email="nova@cliente.example").one()
    assert nova.preferencias["novidades"] == {"vista": novidades.VERSAO}
    assert novidades.para({"empresa"}, nova.preferencias["novidades"]["vista"])["novas"] == 0


def test_funil_e_sugestao_da_maior_queda():
    conta = lambda **k: {"demo": False, "so_contador": False, "modulos": ["emissor"], "email_confirmado": True, "ultimo_acesso": "x", "certificado": "ok", "tomadores": 1, "notas_total": 1, **k}  # noqa: E731
    contas = [conta(), conta(certificado="falta"), conta(certificado="falta"), conta(tomadores=0, notas_total=0), conta(demo=True), conta(modulos=["financeiro"])]
    etapas = uso.funil(contas)
    assert [e["contas"] for e in etapas] == [4, 4, 4, 2, 1, 1]
    dicas = uso.sugestoes({"erros": [], "pessoas": 0, "telas_sem_visita": [], "dias": 30, "eventos": 5}, etapas)
    assert dicas[0]["tipo"] == "funil" and "2 de 4 contas param antes de “enviaram o certificado”" in dicas[0]["titulo"]
