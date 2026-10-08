"""Cliente que nasceu "só controle" vira tomador de verdade (05/10/2026).

"Lancei um recebimento de controle do GOOGLE ADSENSE e agora na aba de
tomador não tem a opção de eu inserir ele como tomador para poder gerar
notas." O cliente criado pelo financeiro (ou por importação sem CNPJ) aponta
pra um tomador interno, sem documento (ver `criar_tomador_interno` em
app/services/vinculos.py). Aqui a pessoa conta QUEM ele é:

- empresa do Brasil: o vínculo passa a apontar pro tomador do catálogo com
  aquele CNPJ (o que já existe, ou um novo) — o MESMO vínculo, então
  recebimentos, notas importadas, calendário e regras continuam nele;
- empresa de fora: o próprio tomador interno ganha país + identificação
  fiscal estrangeira (NIF), e a nota sai como as dos vendedores estrangeiros
  da Shopee (ver app/services/motor_emissao.py).

Nada aqui liga a emissão (`sem_nota` continua como estava): isso é o passo
seguinte da tela, quando a pessoa confere o código do serviço e a descrição.
Toda função presume `definir_prestador_atual` já chamado (RLS).
"""
import re

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import PrestadorTomador, Tomador
from app.services.conferencia import cnpj_valido
from app.services.municipios import municipio_por_codigo
from app.services.paises import pais_valido
from app.services.tomadores import criar_tomador


class IdentificacaoError(Exception):
    """Não deu pra identificar — a mensagem já vem pronta pra tela."""

    def __init__(self, mensagem: str, status: int = 422):
        super().__init__(mensagem)
        self.status = status


def _limpo(texto: str | None, tamanho: int) -> str | None:
    return re.sub(r"\s+", " ", texto or "").strip()[:tamanho] or None


def _exigir_interno(vinculo: PrestadorTomador) -> Tomador:
    tomador = vinculo.tomador
    if tomador is None or tomador.status != "interno":
        raise IdentificacaoError(
            "Este tomador já tem CNPJ, e o CNPJ de um tomador não pode ser trocado. "
            "Se o CNPJ está errado, cadastre o tomador de novo com o certo (Tomadores › Adicionar tomador).",
            status=409,
        )
    return tomador


def _apagar_se_orfao(db: Session, tomador: Tomador) -> bool:
    """O tomador interno que ficou sem ninguém apontando pra ele some. Só
    tomador interno, e só se nada mais o usa: os vínculos desta conta são
    conferidos aqui; os de outra conta (a RLS não deixa ver) seguram a
    exclusão pela chave estrangeira — aí ele simplesmente fica."""
    if tomador.status != "interno":
        return False
    if db.query(PrestadorTomador.id).filter(PrestadorTomador.tomador_id == tomador.id).first() is not None:
        return False
    try:
        with db.begin_nested():
            db.delete(tomador)
            db.flush()
    except IntegrityError:
        return False
    return True


def identificar_com_cnpj(
    db: Session, vinculo: PrestadorTomador, *, cnpj: str, digitado: dict, oficial=None, demo: bool = False,
) -> str | None:
    """Empresa do Brasil. `digitado`: razao_social, cod_municipio, cep,
    logradouro, numero, complemento, bairro (o que a pessoa preencheu quando a
    consulta à Receita não respondeu). `oficial`: o que a Receita devolveu
    (app.services.cnpj_lookup), ou None. Devolve um aviso pra pessoa, se
    houver (ex.: já existe outro cliente seu com este CNPJ)."""
    antigo = _exigir_interno(vinculo)
    numeros = re.sub(r"[.\-/\s]", "", cnpj or "")
    if not re.fullmatch(r"\d{14}", numeros):
        raise IdentificacaoError("O CNPJ tem 14 números. Confira se não faltou ou sobrou algum.")
    # Simulação: os tomadores de exemplo têm CNPJ inválido de propósito.
    if not demo and not cnpj_valido(numeros):
        raise IdentificacaoError(
            "Esse CNPJ não existe: os números não fecham. Deve ter um dígito trocado — confira no contrato ou numa nota antiga."
        )

    existente = db.query(Tomador).filter_by(cnpj=numeros).one_or_none()
    if existente is not None and (existente.status == "aprovado" or demo):
        novo = existente  # já está no catálogo: usa o cadastro de lá, sem mexer nele
    else:
        dados = {
            "razao_social": _limpo(digitado.get("razao_social"), 200), "cod_municipio": (digitado.get("cod_municipio") or "").strip() or None,
            "cep": re.sub(r"\D", "", digitado.get("cep") or "") or None, "logradouro": _limpo(digitado.get("logradouro"), 200),
            "numero": _limpo(digitado.get("numero"), 20), "complemento": _limpo(digitado.get("complemento"), 100),
            "bairro": _limpo(digitado.get("bairro"), 100),
        }
        if oficial is not None:
            # Mesma regra de POST /api/vinculos: o catálogo é compartilhado, então
            # nome e endereço oficiais ganham do que foi digitado.
            dados.update(
                razao_social=(oficial.razao_social or "")[:200] or dados["razao_social"],
                cod_municipio=oficial.cod_municipio_sugerido or dados["cod_municipio"],
                cep=oficial.cep or dados["cep"], logradouro=oficial.logradouro or dados["logradouro"],
                numero=oficial.numero or dados["numero"], complemento=oficial.complemento or dados["complemento"],
                bairro=oficial.bairro or dados["bairro"],
            )
        if not dados["razao_social"] or len(dados["razao_social"]) < 2:
            raise IdentificacaoError("Não consegui buscar os dados desse CNPJ na Receita agora. Escreva o nome (razão social) da empresa.")
        if municipio_por_codigo(dados["cod_municipio"]) is None:
            raise IdentificacaoError("Falta a cidade da empresa. Escolha pela busca.")
        if dados["cep"] is not None and len(dados["cep"]) != 8:
            raise IdentificacaoError("O CEP precisa ter 8 números (ou deixe em branco).")
        novo = criar_tomador(db, cnpj=numeros, status="pendente" if demo else "aprovado", **dados)

    aviso = None
    irmaos = [
        apelido for (apelido,) in db.query(PrestadorTomador.apelido).filter(
            PrestadorTomador.tomador_id == novo.id, PrestadorTomador.id != vinculo.id, PrestadorTomador.excluido_em.is_(None),
        ).order_by(PrestadorTomador.apelido)
    ]
    if irmaos:
        nomes = "“" + "”, “".join(irmaos[:3]) + "”" + (" e outros" if len(irmaos) > 3 else "")
        aviso = (
            f"Você já tem outro cliente com este mesmo CNPJ: {nomes}. Tudo bem ter os dois (a mesma empresa pode ser "
            "faturada em programas separados) — só confira se não é o mesmo cliente cadastrado duas vezes."
        )

    vinculo.tomador = novo
    db.flush()
    _apagar_se_orfao(db, antigo)
    return aviso


def identificar_do_exterior(
    db: Session, vinculo: PrestadorTomador, *, razao_social: str, pais: str, nif: str, endereco: str | None = None,
    motivo_sem_nif: str | None = None,
) -> None:
    """Empresa de fora do Brasil: nome, país e a identificação fiscal de lá
    ficam no tomador interno desta conta. `endereco` (cidade/endereço lá
    fora) é só pra consulta — a nota sai só com o país, como nas notas pra
    estrangeiros que a Receita já autorizou."""
    tomador = _exigir_interno(vinculo)
    nome = _limpo(razao_social, 200)
    if not nome or len(nome) < 2:
        raise IdentificacaoError("Escreva o nome da empresa, do jeito que aparece no contrato ou no extrato de pagamento.")
    codigo = (pais or "").strip().upper()
    if codigo == "BR":
        raise IdentificacaoError("Empresa do Brasil tem CNPJ: use a opção “Empresa do Brasil”.")
    if not pais_valido(codigo):
        raise IdentificacaoError("Escolha o país da empresa na lista.")
    numero = _limpo(nif, 40)
    # Sem número fiscal (08/10/2026): a nota aceita, desde que diga o motivo.
    motivo = motivo_sem_nif if motivo_sem_nif in ("1", "2") and not numero else None
    if not numero and not motivo:
        raise IdentificacaoError(
            "Falta o número fiscal da empresa no país dela (NIF). Ele aparece no contrato ou no extrato de pagamento — "
            "às vezes como “Tax ID” ou “VAT number”. Se ela não tem esse número, marque “Esta empresa não tem número fiscal”."
        )
    tomador.razao_social, tomador.pais, tomador.nif, tomador.motivo_sem_nif = nome, codigo, numero or None, motivo
    # Endereço no Brasil não se aplica a quem é de fora.
    tomador.cep = tomador.numero = tomador.complemento = tomador.bairro = None
    tomador.logradouro = _limpo(endereco, 200)
    db.flush()
