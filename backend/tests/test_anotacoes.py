"""Anotações do Financeiro em três formatos: texto, lista e tabela
(05/10/2026). Só dados sintéticos."""
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.database import get_db
from app.main import app, prestador_atual_id

URL = "/api/financeiro/anotacoes"


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


def _tabela_recarga():
    return {
        "colunas": [
            {"nome": "Data", "tipo": "data"},
            {"nome": "Valor", "tipo": "valor"},
            {"nome": "Observação", "tipo": "texto"},
        ],
        "linhas": [["2026-10-01", 30, "Operadora A"], ["2026-10-15", "51626.61", ""]],
    }


def test_nota_de_texto_continua_como_antes(client):
    nota = client.post(URL, json={"titulo": "Lembretes"}).json()
    assert nota["formato"] == "texto" and nota["dados"] is None and nota["texto"] == ""
    r = client.patch(f"{URL}/{nota['id']}", json={"texto": "ligar pro contador"})
    assert r.status_code == 200
    assert r.json()["texto"] == "ligar pro contador" and r.json()["formato"] == "texto"
    # `dados` mandado numa nota de texto é ignorado
    r = client.patch(f"{URL}/{nota['id']}", json={"dados": {"itens": [{"texto": "x", "feito": False}]}})
    assert r.status_code == 200 and r.json()["dados"] is None


def test_nota_antiga_sem_formato_vira_texto(client, db, prestador_teste):
    """Linha gravada como antes da mudança (sem `formato` nem `dados`): o
    banco preenche "texto" e a API lista e edita normalmente."""
    nota_id = uuid.uuid4()
    db.execute(
        text("INSERT INTO anotacao (id, prestador_id, titulo, texto) VALUES (:id, :p, :t, :x)"),
        {"id": nota_id, "p": prestador_teste.id, "t": "Nota antiga", "x": "linha 1\nlinha 2"},
    )
    lista = client.get(URL).json()
    assert [(n["titulo"], n["formato"], n["dados"], n["texto"]) for n in lista] == [
        ("Nota antiga", "texto", None, "linha 1\nlinha 2")
    ]
    r = client.patch(f"{URL}/{nota_id}", json={"texto": "mudou"})
    assert r.status_code == 200 and r.json()["texto"] == "mudou" and r.json()["formato"] == "texto"


def test_criar_e_atualizar_lista(client):
    nota = client.post(URL, json={"titulo": "Compras", "formato": "lista"}).json()
    assert nota["formato"] == "lista" and nota["dados"] == {"itens": []}
    itens = [{"texto": "papel A4", "feito": False}, {"texto": "toner", "feito": True}]
    r = client.patch(f"{URL}/{nota['id']}", json={"dados": {"itens": itens}})
    assert r.status_code == 200 and r.json()["dados"] == {"itens": itens}
    # o que foi salvo é o que volta na listagem
    assert client.get(URL).json()[0]["dados"] == {"itens": itens}
    # mudar só o nome não mexe no conteúdo
    r = client.patch(f"{URL}/{nota['id']}", json={"titulo": "Compras do mês"})
    assert r.json()["titulo"] == "Compras do mês" and r.json()["dados"] == {"itens": itens}


def test_lista_limites(client):
    nota = client.post(URL, json={"titulo": "Lista", "formato": "lista"}).json()
    duzentos = [{"texto": f"item {i}", "feito": False} for i in range(200)]
    assert client.patch(f"{URL}/{nota['id']}", json={"dados": {"itens": duzentos}}).status_code == 200
    r = client.patch(f"{URL}/{nota['id']}", json={"dados": {"itens": duzentos + [{"texto": "a mais", "feito": False}]}})
    assert r.status_code == 422 and "200" in r.json()["detail"]
    # o que estava salvo não se perde quando o pedido é recusado
    assert len(client.get(URL).json()[0]["dados"]["itens"]) == 200
    # texto comprido é cortado; "feito" que não é verdadeiro vira falso
    r = client.patch(f"{URL}/{nota['id']}", json={"dados": {"itens": [{"texto": "x" * 900, "feito": "sim"}, {"texto": "ok"}]}})
    assert r.status_code == 200
    assert [(len(i["texto"]), i["feito"]) for i in r.json()["dados"]["itens"]] == [(500, False), (2, False)]


@pytest.mark.parametrize("dados", [{"itens": "nada"}, {"itens": ["solto"]}, {"itens": [{"texto": 5}]}])
def test_lista_malformada_e_recusada(client, dados):
    assert client.post(URL, json={"titulo": "Ruim", "formato": "lista", "dados": dados}).status_code == 422


def test_criar_e_atualizar_tabela(client):
    nota = client.post(URL, json={"titulo": "Controle de recarga de telefone", "formato": "tabela", "dados": _tabela_recarga()}).json()
    assert nota["formato"] == "tabela"
    assert [c["tipo"] for c in nota["dados"]["colunas"]] == ["data", "valor", "texto"]
    # dinheiro é guardado como número (mesmo quando chega como texto "51626.61")
    assert nota["dados"]["linhas"] == [["2026-10-01", 30.0, "Operadora A"], ["2026-10-15", 51626.61, ""]]
    assert all(isinstance(linha[1], float) for linha in nota["dados"]["linhas"])

    dados = _tabela_recarga()
    dados["colunas"].append({"nome": "Pago", "tipo": "texto"})
    dados["linhas"] = [["2026-11-01", 45.5, "Operadora B", "sim"], [None, None, None], ["", "", "linha curta"]]
    r = client.patch(f"{URL}/{nota['id']}", json={"dados": dados})
    assert r.status_code == 200
    # células vazias: data "", valor None, texto ""; linha curta é completada
    assert r.json()["dados"]["linhas"] == [
        ["2026-11-01", 45.5, "Operadora B", "sim"],
        ["", None, "", ""],
        ["", None, "linha curta", ""],
    ]


def test_tabela_sem_dados_nasce_com_uma_coluna(client):
    nota = client.post(URL, json={"titulo": "Vazia", "formato": "tabela"}).json()
    assert nota["dados"] == {"colunas": [{"nome": "Anotação", "tipo": "texto"}], "linhas": []}


def test_tabela_limites(client):
    nota = client.post(URL, json={"titulo": "Tabela", "formato": "tabela"}).json()
    url = f"{URL}/{nota['id']}"
    coluna = {"nome": "Valor", "tipo": "valor"}

    oito = {"colunas": [coluna] * 8, "linhas": [[1] * 8] * 300}
    assert client.patch(url, json={"dados": oito}).status_code == 200
    assert client.patch(url, json={"dados": {"colunas": [coluna] * 9, "linhas": []}}).status_code == 422
    assert client.patch(url, json={"dados": {"colunas": [], "linhas": []}}).status_code == 422
    assert client.patch(url, json={"dados": {"colunas": [coluna], "linhas": [[1]] * 301}}).status_code == 422
    # recusou: continua o que estava salvo
    salvo = client.get(URL).json()[0]["dados"]
    assert len(salvo["colunas"]) == 8 and len(salvo["linhas"]) == 300

    # nome de coluna e texto de célula são cortados; célula sobrando é descartada
    r = client.patch(url, json={"dados": {"colunas": [{"nome": "n" * 100, "tipo": "texto"}], "linhas": [["t" * 900, "sobra"]]}})
    assert r.status_code == 200
    assert len(r.json()["dados"]["colunas"][0]["nome"]) == 40
    assert [len(c) for c in r.json()["dados"]["linhas"][0]] == [500]


@pytest.mark.parametrize(
    "colunas, linhas",
    [
        ([{"nome": "X", "tipo": "numero"}], []),               # tipo de coluna desconhecido
        ([{"nome": "V", "tipo": "valor"}], [["trinta"]]),      # dinheiro que não é número
        ([{"nome": "V", "tipo": "valor"}], [[True]]),          # booleano não é dinheiro
        ([{"nome": "V", "tipo": "valor"}], [["NaN"]]),
        ([{"nome": "V", "tipo": "valor"}], [[1e15]]),          # grande demais
        ([{"nome": "D", "tipo": "data"}], [["01/10/2026"]]),   # data fora do padrão
        ([{"nome": "D", "tipo": "data"}], [["2026-02-30"]]),   # data que não existe
        ([{"nome": "T", "tipo": "texto"}], [[{"a": 1}]]),
        ([{"nome": "T", "tipo": "texto"}], ["linha solta"]),
        ("colunas", []),
    ],
)
def test_tabela_malformada_e_recusada(client, colunas, linhas):
    r = client.post(URL, json={"titulo": "Ruim", "formato": "tabela", "dados": {"colunas": colunas, "linhas": linhas}})
    assert r.status_code == 422
    assert client.get(URL).json() == []


def test_valor_e_arredondado_pra_centavos(client):
    dados = {"colunas": [{"nome": "V", "tipo": "valor"}], "linhas": [[10.129], [-5], ["  7.5 "], [0]]}
    nota = client.post(URL, json={"titulo": "Valores", "formato": "tabela", "dados": dados}).json()
    assert nota["dados"]["linhas"] == [[10.13], [-5.0], [7.5], [0.0]]


def test_formato_desconhecido_e_recusado(client):
    assert client.post(URL, json={"titulo": "X", "formato": "planilha"}).status_code == 422
    assert client.get(URL).json() == []
    nota = client.post(URL, json={"titulo": "X"}).json()
    r = client.patch(f"{URL}/{nota['id']}", json={"formato": "desenho"})
    assert r.status_code == 422
    assert client.get(URL).json()[0]["formato"] == "texto"


def test_mudar_de_formato(client):
    nota = client.post(URL, json={"titulo": "Muda", "texto": "pão\nleite"}).json()
    url = f"{URL}/{nota['id']}"

    # texto -> lista (a tela manda o conteúdo já convertido e limpa o texto)
    itens = [{"texto": "pão", "feito": False}, {"texto": "leite", "feito": False}]
    r = client.patch(url, json={"formato": "lista", "dados": {"itens": itens}, "texto": ""}).json()
    assert (r["formato"], r["dados"], r["texto"]) == ("lista", {"itens": itens}, "")

    # lista -> tabela
    tabela = {"colunas": [{"nome": "Anotação", "tipo": "texto"}], "linhas": [["pão"], ["leite"]]}
    r = client.patch(url, json={"formato": "tabela", "dados": tabela}).json()
    assert (r["formato"], r["dados"]) == ("tabela", tabela)

    # dados de lista numa nota que agora é tabela não passam
    assert client.patch(url, json={"dados": {"colunas": "x"}}).status_code == 422

    # tabela -> texto: `dados` some
    r = client.patch(url, json={"formato": "texto", "texto": "pão\nleite"}).json()
    assert (r["formato"], r["dados"], r["texto"]) == ("texto", None, "pão\nleite")

    # mudar o formato sem mandar conteúdo começa vazio
    assert client.patch(url, json={"formato": "lista"}).json()["dados"] == {"itens": []}
    # repetir o mesmo formato sem conteúdo não apaga nada
    client.patch(url, json={"dados": {"itens": itens}})
    assert client.patch(url, json={"formato": "lista"}).json()["dados"] == {"itens": itens}
