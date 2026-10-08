"""Link de assinatura do calendário e Pasta do mês (08/10/2026). Dados
sintéticos; login de verdade (como em test_contador.py), porque o lado de
quem fala (empresa/contador) mora na sessão."""
import datetime
import uuid

from app.models import EventoManual, LancamentoBancario
from app.services import agenda_ics, pasta
from tests.test_contador import _convidar_e_aceitar, _entrar, api, cenario  # noqa: F401 (fixtures)


# --- link de assinatura -----------------------------------------------------------


def test_ics_tem_um_evento_por_dia_com_titulo_valor_e_link():
    eventos = [
        {"data": datetime.date(2026, 10, 15), "tipo": "prazo_emissao", "titulo": "Dia de gerar a nota — Loja", "apelido": "Loja; Filial, Centro",
         "valor": None, "chave": "abc:2026-10", "vinculo_id": "v1"},
        {"data": datetime.date(2026, 10, 20), "tipo": "recebimento_previsto", "titulo": "Previsão", "apelido": "Loja", "valor": 1234.5,
         "chave": "n1", "vinculo_id": "v1"},
        {"data": datetime.date(2026, 10, 21), "tipo": "manual", "titulo": "Reunião com o contador " + "x" * 80, "id": "m1",
         "descricao": "levar\nos papéis", "valor": None},
    ]
    ics = agenda_ics.montar_ics(eventos, nome_empresa="Minha Empresa", agora=datetime.datetime(2026, 10, 8, tzinfo=datetime.timezone.utc))
    assert ics.startswith("BEGIN:VCALENDAR\r\n") and ics.endswith("END:VCALENDAR\r\n")
    assert ics.count("BEGIN:VEVENT") == 3
    assert "DTSTART;VALUE=DATE:20261015" in ics and "DTEND;VALUE=DATE:20261016" in ics
    assert "SUMMARY:Gerar nota — Loja\; Filial\\, Centro" in ics
    assert "Previsão de recebimento — Loja (R$ 1.234\\,50)" in ics
    assert "levar\\nos papéis" in ics
    # nenhuma linha passa de 75 bytes (as compridas continuam na de baixo, com espaço)
    assert all(len(linha.encode("utf-8")) <= 75 for linha in ics.split("\r\n"))
    # o mesmo evento tem o mesmo UID sempre (o Google atualiza em vez de duplicar)
    assert ics == agenda_ics.montar_ics(eventos, nome_empresa="Minha Empresa", agora=datetime.datetime(2026, 10, 8, tzinfo=datetime.timezone.utc))


def test_link_da_agenda_abre_sem_login_e_trocar_desliga_o_antigo(db, api, cenario):  # noqa: F811
    dona = _entrar(api, "dona@cliente.example")
    url = dona.get("/api/calendario/assinatura").json()["url"]
    assert url.endswith(".ics") and "/api/agenda/" in url
    assert dona.get("/api/calendario/assinatura").json()["url"] == url  # o mesmo até trocar
    caminho = url[url.index("/api/agenda/"):]

    db.add(EventoManual(
        id=uuid.uuid4(), prestador_id=cenario["cliente"].id, data=datetime.date.today() + datetime.timedelta(days=3),
        titulo="Lembrete sintético", categoria="lembrete",
    ))
    db.flush()
    anonimo = api()  # sem login
    r = anonimo.get(caminho)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/calendar")
    assert "SUMMARY:Lembrete sintético" in r.text and "CLIENTE LTDA" in r.text

    r = dona.post("/api/calendario/assinatura/novo")
    assert r.status_code == 200, r.text
    novo = r.json()["url"]
    assert novo != url
    assert anonimo.get(caminho).status_code == 404
    assert anonimo.get(novo[novo.index("/api/agenda/"):]).status_code == 200
    assert anonimo.get("/api/agenda/nao-existe.ics").status_code == 404


# --- pasta do mês -----------------------------------------------------------------


def test_pasta_da_empresa_pedidos_arquivos_e_extrato_que_conta_sozinho(db, api, cenario):  # noqa: F811
    dona = _entrar(api, "dona@cliente.example")
    r = dona.get("/api/pasta?competencia=2026-09").json()
    assert r["papel"] == "empresa" and r["mes"]["itens"] == [] and r["tem_contador"] is False

    assert dona.post("/api/pasta/pedidos/sugestoes").json()["pedidos"] == 3
    assert dona.post("/api/pasta/pedidos/sugestoes").json()["pedidos"] == 3  # não duplica
    itens = dona.get("/api/pasta?competencia=2026-09").json()["mes"]["itens"]
    assert [i["situacao"] for i in itens] == ["pendente"] * 3
    extrato, tomadas, comprovantes = itens

    # extrato importado no Financeiro em setembro: o item conta como entregue
    db.add(LancamentoBancario(
        id=uuid.uuid4(), prestador_id=cenario["cliente"].id, data=datetime.date(2026, 9, 10), descricao="PIX SINTETICO",
        valor=10, credito=True, chave="pix-sintetico",
    ))
    db.flush()
    # arquivo de um pedido
    r = dona.post("/api/pasta/arquivos", data={"competencia": "2026-09", "pedido_id": tomadas["id"]},
                  files={"arquivo": ("nota tomada.pdf", b"%PDF-1.4 sintetico", "application/pdf")})
    assert r.status_code == 200, r.text
    arquivo_id = r.json()["id"]
    # não teve comprovante neste mês
    assert dona.post("/api/pasta/marcar", json={"pedido_id": comprovantes["id"], "competencia": "2026-09", "situacao": "nao_tem"}).status_code == 200
    # "conferido" é só do contador
    assert dona.post("/api/pasta/marcar", json={"pedido_id": tomadas["id"], "competencia": "2026-09", "situacao": "conferido"}).status_code == 403

    mes = dona.get("/api/pasta?competencia=2026-09").json()["mes"]
    assert [i["situacao"] for i in mes["itens"]] == ["entregue", "entregue", "nao_tem"]
    assert mes["itens"][0]["extrato_linhas"] == 1 and mes["resumo"] == {"itens": 3, "pendentes": 0, "prontos": 3}
    # outro mês continua pendente
    assert [i["situacao"] for i in dona.get("/api/pasta?competencia=2026-08").json()["mes"]["itens"]] == ["pendente"] * 3

    baixado = dona.get(f"/api/pasta/arquivos/{arquivo_id}")
    assert baixado.status_code == 200 and baixado.content == b"%PDF-1.4 sintetico"
    assert "nota%20tomada.pdf" in baixado.headers["content-disposition"]

    # tipo de arquivo e tamanho
    assert dona.post("/api/pasta/arquivos", data={"competencia": "2026-09"}, files={"arquivo": ("virus.exe", b"MZ", "application/x-msdownload")}).status_code == 422
    grande = b"0" * (pasta.LIMITE_ARQUIVO + 1)
    assert dona.post("/api/pasta/arquivos", data={"competencia": "2026-09"}, files={"arquivo": ("grande.pdf", grande, "application/pdf")}).status_code == 413

    # tirar um pedido: some dos meses, o arquivo enviado continua (como avulso)
    assert dona.delete(f"/api/pasta/pedidos/{tomadas['id']}").status_code == 200
    mes = dona.get("/api/pasta?competencia=2026-09").json()["mes"]
    assert [i["titulo"] for i in mes["itens"]] == ["Extrato do banco", "Comprovantes de pagamento"]
    assert [a["nome"] for a in mes["avulsos"]] == ["nota tomada.pdf"]
    assert dona.delete(f"/api/pasta/arquivos/{arquivo_id}").status_code == 200


def test_conversa_e_contador_pelo_painel_sem_entrar_na_empresa(db, api, cenario):  # noqa: F811
    dona, contadora = _convidar_e_aceitar(db, api, cenario, permissoes=[])
    acesso_id = contadora.get("/api/contador/atendimentos").json()["clientes"][0]["id"]
    painel = f"/api/contador/atendimentos/{acesso_id}/pasta"

    # a contadora monta a lista pelo painel dela
    r = contadora.post(f"{painel}/pedidos", json={"titulo": "Folha de pagamento", "descricao": "Holerites do mês"})
    assert r.status_code == 200, r.text
    pedido_id = r.json()["id"]
    assert contadora.post(f"{painel}/mensagens", json={"texto": "Oi! Me manda a folha de setembro?", "competencia": "2026-09"}).status_code == 200

    # a dona vê o pedido e a mensagem como novidade
    vista = dona.get("/api/pasta?competencia=2026-09").json()
    assert vista["tem_contador"] is True and [i["titulo"] for i in vista["mes"]["itens"]] == ["Folha de pagamento"]
    assert vista["novidades"] == {"mensagens": 1, "arquivos": 0}
    assert [(m["papel"], m["texto"]) for m in vista["mensagens"]] == [("contador", "Oi! Me manda a folha de setembro?")]
    assert dona.post("/api/pasta/lido").status_code == 200
    assert dona.get("/api/pasta").json()["novidades"] == {"mensagens": 0, "arquivos": 0}

    # a dona manda o arquivo e responde; a contadora vê no painel e confere
    assert dona.post("/api/pasta/arquivos", data={"competencia": "2026-09", "pedido_id": pedido_id},
                     files={"arquivo": ("folha.pdf", b"%PDF folha", "application/pdf")}).status_code == 200
    assert dona.post("/api/pasta/mensagens", json={"texto": "Enviei!", "competencia": "2026-09"}).status_code == 200
    cliente = contadora.get("/api/contador/atendimentos").json()["clientes"][0]
    assert cliente["pasta"]["novidades"] == {"mensagens": 1, "arquivos": 1}
    do_painel = contadora.get(f"{painel}?competencia=2026-09").json()
    assert do_painel["papel"] == "contador" and do_painel["mes"]["itens"][0]["situacao"] == "entregue"
    arquivo_id = do_painel["mes"]["itens"][0]["arquivos"][0]["id"]
    assert contadora.get(f"{painel}/arquivos/{arquivo_id}").content == b"%PDF folha"
    assert contadora.post(f"{painel}/marcar", json={"pedido_id": pedido_id, "competencia": "2026-09", "situacao": "conferido"}).status_code == 200
    assert dona.get("/api/pasta?competencia=2026-09").json()["mes"]["itens"][0]["situacao"] == "conferido"

    # a contadora que entrou na empresa fala como contador
    assert contadora.get("/api/pasta").json()["papel"] == "contador"

    # outra pessoa não chega no painel desta empresa
    assert dona.get(f"{painel}").status_code == 404


def test_pasta_de_uma_empresa_nao_aparece_na_outra(db, api, cenario):  # noqa: F811
    dona = _entrar(api, "dona@cliente.example")
    dona.post("/api/pasta/pedidos", json={"titulo": "Só da cliente"})
    dona.post("/api/pasta/mensagens", json={"texto": "segredo da cliente"})
    escritorio = _entrar(api, "contadora@escritorio.example")  # a empresa dela mesma, sem acesso à cliente
    r = escritorio.get("/api/pasta").json()
    assert r["mes"]["itens"] == [] and r["mensagens"] == []
