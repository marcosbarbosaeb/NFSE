"""Pontos de integração entre os módulos (05/10/2026).

O emissor e o financeiro são produtos separados: um não importa o código do
outro. Quando algo que acontece num módulo interessa ao outro, quem faz
PUBLICA um evento aqui e quem se interessa OUVE — sem que o primeiro saiba
quem está ouvindo (ou se há alguém).

Eventos de hoje (publicados pelo emissor):

- ``nota_criada(db, emissao, origem)`` — uma nota foi gerada. `origem` é um
  texto opaco que veio de quem pediu a nota (ex.: ``"fin:pagamento:<id>"``
  quando o financeiro pede a nota de um recebimento).
- ``antes_de_trocar_nota(db, emissao)`` — uma nota que não tinha sido
  enviada vai ser apagada e trocada por outra. Quem ouve pode devolver uma
  função ``f(nova)``: o emissor chama cada uma depois que a nota nova
  existe (ex.: o financeiro passa o recebimento da antiga pra nova).

Perguntas (quem responde devolve verdadeiro/falso):

- ``tomador_em_uso(db, vinculo_id)`` — algum módulo tem dados ligados a esse
  tomador (ex.: recebimentos)? O emissor pergunta antes de apagar um tomador
  que só existia por causa de notas importadas.

Coletas (cada ouvinte devolve uma lista):

- ``agenda(db, prestador_id, inicio, fim, vinculos)`` — eventos que o módulo
  quer mostrar no calendário.

A lista é curta de propósito: cada item novo é uma decisão de integração.
"""
from collections.abc import Callable

_ouvintes: dict[str, list[Callable]] = {}


def ouvir(evento: str, funcao: Callable) -> Callable:
    lista = _ouvintes.setdefault(evento, [])
    if funcao not in lista:
        lista.append(funcao)
    return funcao


def publicar(evento: str, db, **dados) -> None:
    for funcao in _ouvintes.get(evento, []):
        funcao(db, **dados)


def perguntar(evento: str, db, **dados) -> bool:
    """Verdadeiro se algum módulo respondeu que sim."""
    return any(funcao(db, **dados) for funcao in _ouvintes.get(evento, []))


def coletar(evento: str, db, **dados) -> list:
    """O que cada ouvinte devolveu (sem os vazios)."""
    return [r for r in (funcao(db, **dados) for funcao in _ouvintes.get(evento, [])) if r is not None]


class RecusaDeIntegracao(Exception):
    """Um módulo recusou o que o outro pediu (ex.: a nota é de um recebimento
    que não existe). Quem publicou devolve a mensagem pra tela."""
