"""Detalhe do "Mês a mês" (05/10/2026): o que está por trás de cada total.

Pedido do Marcos: "devo poder consultar quanto um tomador me pagou mês a mês
ou quanto eu gastei mês a mês com alguma coisa". O resumo
(`contas_mes.resumo_anual`) dá só o total de cada mês; aqui cada linha
daquela tabela abre em quem/o quê:

- recebido  → uma linha por cliente;
- faturado  → uma linha por cliente (notas confirmadas);
- despesas  → uma linha por categoria, e cada categoria abre nas suas
  coisas (a descrição do lançamento / nome da conta fixa);
- retiradas → idem (categoria → descrição).

REGRA DE OURO: os filtros são os MESMOS de `resumo_anual` — mês de
competência, nota só "confirmado", despesa separada de retirada pelo `tipo`,
e nenhum outro corte (nem pago/a pagar, nem origem). Assim a soma das linhas
de um mês bate com o total que a tela já mostra
(tests/test_mes_a_mes.py confere mês a mês). Mudou a regra lá, muda aqui.
"""
from collections import Counter
from decimal import Decimal

from sqlalchemy.orm import Session

from app.financeiro.contas_mes import MESES
from app.models import Despesa, Emissao, PagamentoRecebido, PrestadorTomador

_SEM_NOME = "Cliente sem nome"


class _Linha:
    """Soma por mês de uma linha (um cliente, uma categoria, uma coisa)."""

    def __init__(self) -> None:
        self.somas = [Decimal(0)] * 12
        self.nomes: Counter[str] = Counter()

    def somar(self, competencia: str, valor, nome: str) -> None:
        self.somas[int(competencia[5:7]) - 1] += valor or 0
        self.nomes[nome] += 1

    def nome(self) -> str:
        # Mesma coisa escrita de dois jeitos ("Internet", "internet"): fica a
        # grafia mais usada (empate: ordem alfabética, pra ser sempre igual).
        return sorted(self.nomes.items(), key=lambda x: (-x[1], x[0]))[0][0]

    def valores(self) -> list[float]:
        return [round(float(v), 2) for v in self.somas]

    def total(self) -> float:
        return round(float(sum(self.somas, Decimal(0))), 2)

    def vazia(self) -> bool:
        return not any(self.somas)


def _chave(texto: str) -> str:
    return " ".join(texto.split()).casefold()


def _ordenar(linhas: list[dict]) -> list[dict]:
    return sorted(linhas, key=lambda x: (-abs(x["total"]), x["nome"].casefold()))


def _por_cliente(consulta) -> list[dict]:
    """`consulta` devolve (vinculo_id, apelido, competencia, valor)."""
    clientes: dict[str, _Linha] = {}
    for vinculo_id, apelido, competencia, valor in consulta:
        clientes.setdefault(str(vinculo_id), _Linha()).somar(competencia, valor, apelido or _SEM_NOME)
    return _ordenar([
        {"id": vid, "nome": l.nome(), "valores": l.valores(), "total": l.total()}
        for vid, l in clientes.items() if not l.vazia()
    ])


def _por_categoria(despesas: list[Despesa]) -> list[dict]:
    categorias: dict[str, _Linha] = {}
    itens: dict[str, dict[str, _Linha]] = {}
    for d in despesas:
        # A categoria agrupa pelo texto exato, igual ao "Para onde vai o
        # dinheiro" do resumo; a coisa, sem ligar pra maiúscula/espaço.
        categorias.setdefault(d.categoria, _Linha()).somar(d.competencia, d.valor, d.categoria)
        nome = " ".join((d.descricao or "").split()) or d.categoria
        itens.setdefault(d.categoria, {}).setdefault(_chave(nome), _Linha()).somar(d.competencia, d.valor, nome)
    return _ordenar([
        {
            "nome": categoria, "valores": l.valores(), "total": l.total(),
            "itens": _ordenar([
                {"nome": i.nome(), "valores": i.valores(), "total": i.total()}
                for i in itens[categoria].values() if not i.vazia()
            ]),
        }
        for categoria, l in categorias.items() if not l.vazia()
    ])


def detalhe_anual(db: Session, ano: str) -> dict:
    """As linhas por trás de cada total de `resumo_anual` (só leitura)."""
    # Join de fora: mesmo que o cliente não apareça, o dinheiro continua na
    # conta — o resumo soma tudo, então aqui também.
    faturado = _por_cliente(
        db.query(Emissao.prestador_tomador_id, PrestadorTomador.apelido, Emissao.competencia, Emissao.valor)
        .outerjoin(PrestadorTomador, Emissao.prestador_tomador_id == PrestadorTomador.id)
        .filter(Emissao.competencia.like(f"{ano}-%"), Emissao.estado == "confirmado")
    )
    recebido = _por_cliente(
        db.query(
            PagamentoRecebido.prestador_tomador_id, PrestadorTomador.apelido,
            PagamentoRecebido.competencia, PagamentoRecebido.valor,
        )
        .outerjoin(PrestadorTomador, PagamentoRecebido.prestador_tomador_id == PrestadorTomador.id)
        .filter(PagamentoRecebido.competencia.like(f"{ano}-%"))
    )
    despesas_ano = db.query(Despesa).filter(Despesa.competencia.like(f"{ano}-%")).all()
    return {
        "ano": ano,
        "meses": MESES,
        "faturado": faturado,
        "recebido": recebido,
        "despesas": _por_categoria([d for d in despesas_ano if d.tipo == "despesa"]),
        "retiradas": _por_categoria([d for d in despesas_ano if d.tipo == "retirada"]),
    }
