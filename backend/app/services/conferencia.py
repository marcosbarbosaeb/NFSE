"""Conferência (05/10/2026): "precisamos criar controles para que o cadastro
dos tomadores e a NF da pessoa não saiam erradas e isso gere problemas".

A Ana confere o cadastro do tomador, a empresa e a nota ANTES de a nota ser
gerada/enviada, e conta o que achou em português simples, com o jeito de
consertar. Cada achado é um "ponto":

    {"nivel": "erro" | "aviso", "codigo": str, "campo": str | None,
     "mensagem": str, "como_corrigir": str | None,
     "onde": "tomador" | "empresa" | "nota"}

- "erro": a nota sairia errada ou seria recusada — trava a geração em
  `POST /api/dps` (só lá; `criar_rascunho` e a geração em lote da Shopee
  não passam por aqui, de propósito).
- "aviso": parece estranho, mas pode estar certo — a pessoa confirma.

Nada aqui fala com a rede nem grava no banco: só lê. Toda função presume
`definir_prestador_atual` já chamado na sessão (RLS).
"""
import datetime
import re
import statistics
import uuid
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.fiscal.dps import renderizar_descricao
from app.models import Certificado, Emissao, Prestador, PrestadorTomador
from app.services.envio_direto import formas_de_envio
from app.services.municipios import municipio_por_codigo
from app.services.paises import pais_valido
from app.services.servicos_nacionais import normalizar_codigo, servico_por_codigo
from app.tempo import hoje as hoje_br

# xDescServ é TSDesc2000 no esquema da DPS (integracao/schemas/
# tiposSimples_v1.00.xsd): passou disso, a Receita recusa.
LIMITE_DESCRICAO = 2000
DIAS_AVISO_CERTIFICADO = 30
# Quantas notas autorizadas olhar pra saber "o código de sempre".
_NOTAS_PARA_CODIGOS = 3
# Quantas notas olhar pra saber "o valor de costume".
_NOTAS_PARA_VALOR = 6

_ESTADOS_FORA_DO_HISTORICO = ("cancelada", "substituida")
# Nota que ainda não foi autorizada pela prefeitura (dá tempo de consertar).
ESTADOS_CONFERIVEIS = ("rascunho", "montado", "assinado", "erro")


def _ponto(nivel: str, codigo: str, mensagem: str, como_corrigir: str | None = None, *, campo: str | None = None, onde: str = "tomador") -> dict:
    return {"nivel": nivel, "codigo": codigo, "campo": campo, "mensagem": mensagem, "como_corrigir": como_corrigir, "onde": onde}


def resumo(pontos: list[dict]) -> dict:
    erros = sum(1 for p in pontos if p["nivel"] == "erro")
    return {"erros": erros, "avisos": len(pontos) - erros}


def _brl(valor) -> str:
    return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _digitos(texto) -> str:
    return "".join(c for c in str(texto or "") if c.isdigit())


# --- CNPJ / CPF --------------------------------------------------------------


def cnpj_valido(cnpj: str | None) -> bool:
    """Confere os dois dígitos verificadores. Aceita também o CNPJ com
    letras (alfanumérico, em uso desde julho/2026): a conta é a mesma, com
    cada caractere valendo o código dele menos 48."""
    bruto = re.sub(r"[.\-/\s]", "", str(cnpj or "")).upper()
    if not re.fullmatch(r"[0-9A-Z]{12}\d{2}", bruto) or len(set(bruto)) == 1:
        return False
    valores = [ord(c) - 48 for c in bruto]

    def dv(parte: list[int]) -> int:
        pesos = [((len(parte) - 1 - i) % 8) + 2 for i in range(len(parte))]
        resto = sum(v * p for v, p in zip(parte, pesos)) % 11
        return 0 if resto < 2 else 11 - resto

    return dv(valores[:12]) == valores[12] and dv(valores[:13]) == valores[13]


def cpf_valido(cpf: str | None) -> bool:
    digitos = _digitos(cpf)
    if len(digitos) != 11 or len(set(digitos)) == 1:
        return False
    numeros = [int(c) for c in digitos]
    for tamanho in (9, 10):
        resto = (sum(n * (tamanho + 1 - i) for i, n in enumerate(numeros[:tamanho])) * 10) % 11
        if (0 if resto == 10 else resto) != numeros[tamanho]:
            return False
    return True


# --- peças comuns (cadastro ao vivo e dados congelados na nota) --------------


def _checar_pessoa(
    *, tipo: str, documento: str | None, nome: str | None, endereco: dict, onde: str,
    conferir_digitos: bool = True, como_corrigir: str, como_documento: str | None = None,
) -> list[dict]:
    """Quem recebe a nota: documento, nome e endereço do jeito que vão pro
    XML (ver `_pessoa` em app/fiscal/dps.py)."""
    pontos: list[dict] = []
    documento = (documento or "").strip()
    como_documento = como_documento or como_corrigir
    if tipo == "NIF":
        if not documento:
            pontos.append(_ponto("erro", "documento_vazio", "Falta o número de identificação (NIF) de quem recebe a nota.", como_documento, campo="cnpj", onde=onde))
    elif not documento:
        pontos.append(_ponto("erro", "documento_vazio", f"Falta o {tipo} de quem recebe a nota.", como_documento, campo="cnpj", onde=onde))
    elif conferir_digitos and not (cpf_valido(documento) if tipo == "CPF" else cnpj_valido(documento)):
        pontos.append(_ponto(
            "erro", "documento_invalido",
            f"O {tipo} {documento} não existe: os números não fecham. Deve ter um dígito trocado ou faltando.",
            f"Confira o {tipo} com o tomador (ou numa nota antiga dele). {como_documento}", campo="cnpj", onde=onde,
        ))
    if not (nome or "").strip():
        pontos.append(_ponto("erro", "razao_social_vazia", "Falta o nome (razão social) de quem recebe a nota.", como_corrigir, campo="razao_social", onde=onde))

    cidade = str(endereco.get("cMun") or "").strip()
    if not cidade:
        return pontos  # sem cidade o endereço não vai na nota (vendedor estrangeiro / não reconhecido)
    if municipio_por_codigo(cidade) is None:
        pontos.append(_ponto("erro", "cidade_invalida", "A cidade do endereço de quem recebe a nota não foi reconhecida.", como_corrigir, campo="cod_municipio", onde=onde))
    cep = str(endereco.get("CEP") or "").strip()
    faltando = [rotulo for chave, rotulo in (("xLgr", "rua"), ("nro", "número"), ("xBairro", "bairro")) if not str(endereco.get(chave) or "").strip()]
    if not cep:
        faltando.insert(0, "CEP")
    elif not re.fullmatch(r"\d{8}", cep):
        pontos.append(_ponto("erro", "cep_invalido", f"O CEP “{cep}” está errado: precisa ter 8 números.", como_corrigir, campo="cep", onde=onde))
    if faltando:
        lista = faltando[0] if len(faltando) == 1 else ", ".join(faltando[:-1]) + " e " + faltando[-1]
        pontos.append(_ponto(
            "aviso", "endereco_incompleto",
            f"O endereço está pela metade: falta {lista}. Assim a nota sai sem o endereço de quem recebe.",
            f"Pra o endereço ir na nota ele precisa estar inteiro (CEP, rua, número e bairro). {como_corrigir}",
            campo="endereco", onde=onde,
        ))
    return pontos


def _checar_servico(*, cod_local: str | None, cod_nacional: str | None, cod_nbs: str | None, onde: str, como_corrigir: str) -> list[dict]:
    pontos: list[dict] = []
    if servico_por_codigo(cod_nacional) is None:
        pontos.append(_ponto(
            "erro", "servico_invalido",
            f"O código do serviço ({cod_nacional or 'vazio'}) não existe na lista oficial de serviços.",
            f"Escolha o serviço pela busca, sem digitar o número. {como_corrigir}", campo="cod_trib_nacional", onde=onde,
        ))
    if cod_nbs and len(_digitos(cod_nbs)) != 9:
        pontos.append(_ponto(
            "erro", "nbs_invalido", f"O código NBS “{cod_nbs}” está errado: ele tem sempre 9 números.",
            f"Corrija o NBS ou deixe em branco. {como_corrigir}", campo="cod_nbs", onde=onde,
        ))
    if municipio_por_codigo(cod_local) is None:
        pontos.append(_ponto(
            "erro", "local_prestacao_invalido", "A cidade onde o serviço é prestado não foi reconhecida.",
            f"Escolha a cidade de novo na lista. {como_corrigir}", campo="cod_local_prestacao", onde=onde,
        ))
    return pontos


def campos_desconhecidos(template: str) -> list[str]:
    """Campos automáticos ({...}) que a Ana não sabe preencher. Pergunta ao
    próprio renderizador (em vez de repetir a lista dele aqui): o que ele
    devolve do jeito que recebeu, ele não conhece."""
    desconhecidos = []
    for nome in dict.fromkeys(re.findall(r"\{(\w+)\}", template or "")):
        marcador = "{" + nome + "}"
        if renderizar_descricao(marcador, "2026-01", ordem="1") == marcador:
            desconhecidos.append(marcador)
    return desconhecidos


def _comparavel(campo: str, valor) -> str:
    """Código num formato que dá pra comparar ('17.06.01' == '170601')."""
    if valor is None:
        return ""
    if campo == "cTribNac":
        return normalizar_codigo(str(valor))
    if campo == "cNBS":
        return _digitos(valor)
    texto = str(valor).strip()
    return texto.lstrip("0") or ("0" if texto else "")


_CODIGOS_COMPARADOS = (
    ("cTribNac", "cod_trib_nacional", "servico_diferente", "código do serviço"),
    ("cTribMun", "cod_trib_municipal", "cod_municipal_diferente", "código de tributação municipal"),
    ("cNBS", "cod_nbs", "nbs_diferente", "código NBS"),
)


def _checar_codigos_de_costume(atuais: dict, ultimas: list[dict], *, onde: str, como_corrigir: str) -> list[dict]:
    """`ultimas`: os códigos das últimas notas AUTORIZADAS deste tomador
    (mais nova primeiro). Avisa quando o de agora não é nenhum dos que a
    prefeitura já aceitou pra ele."""
    pontos: list[dict] = []
    for chave, campo, codigo, rotulo in _CODIGOS_COMPARADOS:
        usados = [str(u.get(chave)).strip() for u in ultimas if isinstance(u, dict) and str(u.get(chave) or "").strip()]
        if not usados:
            continue
        agora = atuais.get(chave)
        if _comparavel(chave, agora) in {_comparavel(chave, u) for u in usados}:
            continue
        agora_txt = f"“{agora}”" if str(agora or "").strip() else "vazio"
        pontos.append(_ponto(
            "aviso", codigo,
            f"O {rotulo} está diferente do das últimas notas autorizadas deste tomador: agora está {agora_txt}, antes era “{usados[0]}”.",
            f"Se você mudou de propósito, tudo bem. Se não, volte para “{usados[0]}”. {como_corrigir}", campo=campo, onde=onde,
        ))
    return pontos


def _codigos_das_ultimas(db: Session, vinculo_ids: list[uuid.UUID], *, ignorar_id: uuid.UUID | None = None) -> dict[uuid.UUID, list[dict]]:
    """Códigos usados nas últimas notas autorizadas (estado 'confirmado') de
    cada vínculo — lidos do retrato guardado na nota (`codigo_servico_usado`,
    que existe nas emitidas aqui e nas importadas). Uma consulta só pra
    todos os vínculos."""
    if not vinculo_ids:
        return {}
    posicao = func.row_number().over(
        partition_by=Emissao.prestador_tomador_id, order_by=(Emissao.competencia.desc(), Emissao.criado_em.desc())
    ).label("posicao")
    consulta = db.query(
        Emissao.prestador_tomador_id.label("vinculo_id"), Emissao.tomador_snapshot["codigo_servico_usado"].label("codigos"),
        Emissao.competencia.label("competencia"), Emissao.criado_em.label("criado_em"), posicao,
    ).filter(
        Emissao.prestador_tomador_id.in_(vinculo_ids), Emissao.estado == "confirmado", Emissao.tomador_documento.is_(None),
    )
    if ignorar_id is not None:
        consulta = consulta.filter(Emissao.id != ignorar_id)
    sub = consulta.subquery()
    linhas = (
        db.query(sub.c.vinculo_id, sub.c.codigos)
        .filter(sub.c.posicao <= _NOTAS_PARA_CODIGOS)
        .order_by(sub.c.vinculo_id, sub.c.posicao)
    )
    resultado: dict[uuid.UUID, list[dict]] = {}
    for vinculo_id, codigos in linhas:
        if isinstance(codigos, dict):
            resultado.setdefault(vinculo_id, []).append(codigos)
    return resultado


# --- tomador (vínculo + catálogo) ----------------------------------------------

_CORRIGIR_NO_TOMADOR = "Corrija no cadastro do tomador."
# Nome, CNPJ e endereço são do catálogo de tomadores (compartilhado entre as
# contas) e NÃO têm edição na tela — o remédio de verdade hoje é este.
_TROCAR_CNPJ = "O CNPJ de um tomador já cadastrado não pode ser trocado: cadastre o tomador de novo com o CNPJ certo (Tomadores › Adicionar tomador) e exclua este."
_DADOS_DE_FORA = "Preencha em Tomadores › abrir o tomador › “Dados do tomador”."
_DADOS_DO_CATALOGO = "Corrija em Tomadores › abrir o tomador › “Dados do tomador” (dá pra puxar da Receita ou buscar o CEP pelo endereço)."


def _conferir_vinculo(vinculo: PrestadorTomador, ultimas: list[dict], *, demo: bool) -> list[dict]:
    tomador = vinculo.tomador
    interno = tomador.status == "interno"  # só desta conta, sem CNPJ (ver criar_tomador_interno)
    pontos: list[dict] = []

    if vinculo.sem_nota:
        # Só controle de recebimento: nada de nota, só o básico.
        if not (tomador.razao_social or "").strip():
            pontos.append(_ponto("erro", "razao_social_vazia", "Este tomador está sem nome.", _DADOS_DO_CATALOGO, campo="razao_social"))
        return pontos

    if tomador.de_fora:
        # Empresa de fora do Brasil: não tem CNPJ nem endereço daqui. A nota
        # sai com a identificação fiscal de lá (NIF) e o país — precisa dos dois.
        if not (tomador.razao_social or "").strip():
            pontos.append(_ponto("erro", "razao_social_vazia", "Falta o nome da empresa que recebe a nota.", _DADOS_DE_FORA, campo="razao_social"))
        pais = (tomador.pais or "").strip().upper()
        if not pais or pais == "BR":
            pontos.append(_ponto(
                "erro", "pais_vazio", "Falta o país desta empresa de fora do Brasil.", _DADOS_DE_FORA, campo="pais",
            ))
        elif not pais_valido(pais):
            pontos.append(_ponto("erro", "pais_invalido", f"Não reconheci o país “{pais}” desta empresa.", _DADOS_DE_FORA, campo="pais"))
        if not (tomador.nif or "").strip():
            pontos.append(_ponto(
                "erro", "documento_vazio", "Falta o número fiscal desta empresa no país dela (NIF). Sem ele a nota não pode ser emitida.",
                f"Ele aparece no contrato ou no extrato de pagamento (às vezes como “Tax ID” ou “VAT number”). {_DADOS_DE_FORA}", campo="nif",
            ))
    else:
        if interno:
            pontos.append(_ponto(
                "erro", "documento_vazio", "Ainda não sei quem é este cliente: ele está sem CNPJ, e sem isso a nota não pode ser emitida.",
                "Abra o tomador e responda em “Quer emitir nota pra este cliente?” (o CNPJ dele, ou os dados da empresa se ela for de fora "
                "do Brasil) — ou marque “só controle de recebimento” se você não emite nota pra ele.", campo="cnpj",
            ))
        documento = "" if interno else tomador.cnpj
        tipo = "CPF" if len(documento or "") == 11 and (documento or "").isdigit() else "CNPJ"
        pontos += [
            p for p in _checar_pessoa(
                tipo=tipo, documento=documento, nome=tomador.razao_social,
                endereco={"cMun": tomador.cod_municipio, "CEP": tomador.cep, "xLgr": tomador.logradouro, "nro": tomador.numero, "xBairro": tomador.bairro},
                # Simulação: os tomadores de exemplo têm CNPJ inválido de propósito (ver app/services/demo.py).
                onde="tomador", conferir_digitos=not demo, como_corrigir=_DADOS_DO_CATALOGO, como_documento=_TROCAR_CNPJ,
            )
            if not (interno and p["codigo"] == "documento_vazio")
        ]
        if not (tomador.cod_municipio or "").strip():
            pontos.append(_ponto("erro", "cidade_invalida", "Falta a cidade do tomador.", _DADOS_DO_CATALOGO, campo="cod_municipio"))

    pontos += _checar_servico(
        cod_local=vinculo.cod_local_prestacao, cod_nacional=vinculo.cod_trib_nacional, cod_nbs=vinculo.cod_nbs,
        onde="tomador", como_corrigir=_CORRIGIR_NO_TOMADOR,
    )

    template = (vinculo.template_descricao or "").strip()
    if not template:
        pontos.append(_ponto(
            "erro", "descricao_vazia", "Falta a descrição do serviço que vai escrita na nota.",
            "Escreva a descrição no cadastro do tomador (pode copiar de uma nota antiga).", campo="template_descricao",
        ))
    else:
        desconhecidos = campos_desconhecidos(template)
        if desconhecidos:
            pontos.append(_ponto(
                "erro", "descricao_campo_desconhecido",
                f"A descrição da nota tem um campo automático que eu não conheço: {', '.join(desconhecidos)}. Ele sairia escrito assim mesmo na nota.",
                "Apague esse trecho ou troque por um dos campos automáticos da lista, no cadastro do tomador.", campo="template_descricao",
            ))
        hoje = hoje_br()
        # Estimativa: FEVEREIRO é o mês de nome mais comprido.
        exemplo = renderizar_descricao(template, f"{hoje.year:04d}-02", ordem="0" * 12)
        if len(exemplo) > LIMITE_DESCRICAO:
            pontos.append(_ponto(
                "aviso", "descricao_longa",
                f"A descrição da nota está comprida demais: tem {len(exemplo)} letras e a prefeitura aceita até {LIMITE_DESCRICAO}.",
                "Encurte a descrição no cadastro do tomador.", campo="template_descricao",
            ))

    if "email" in formas_de_envio(vinculo) and not (vinculo.email_para or "").strip() and not (vinculo.email_contato or "").strip():
        pontos.append(_ponto(
            "aviso", "sem_email", "Este tomador recebe a nota por e-mail, mas não tem e-mail cadastrado.",
            "Preencha o e-mail do tomador — ou escolha outra forma de envio.", campo="email",
        ))

    pontos += _checar_codigos_de_costume(
        {"cTribNac": vinculo.cod_trib_nacional, "cTribMun": vinculo.cod_trib_municipal, "cNBS": vinculo.cod_nbs},
        ultimas, onde="tomador", como_corrigir=_CORRIGIR_NO_TOMADOR,
    )
    return pontos


def _eh_demo(db: Session, prestador_id: uuid.UUID) -> bool:
    return bool(db.query(Prestador.demo).filter(Prestador.id == prestador_id).scalar())


def conferir_vinculo(db: Session, vinculo: PrestadorTomador) -> list[dict]:
    """O cadastro de UM tomador (como a pessoa vê: o vínculo + o tomador do
    catálogo)."""
    ultimas = {} if vinculo.sem_nota else _codigos_das_ultimas(db, [vinculo.id])
    return _conferir_vinculo(vinculo, ultimas.get(vinculo.id, []), demo=_eh_demo(db, vinculo.prestador_id))


def conferir_vinculos(db: Session, vinculos: list[PrestadorTomador]) -> dict[uuid.UUID, list[dict]]:
    """Vários tomadores de uma vez (a lista da aba Tomadores), com duas
    consultas no total — não uma por tomador. Espera os vínculos já com o
    tomador carregado (ver `listar_vinculos_ativos`)."""
    if not vinculos:
        return {}
    ultimas = _codigos_das_ultimas(db, [v.id for v in vinculos if not v.sem_nota])
    demo = _eh_demo(db, vinculos[0].prestador_id)
    return {v.id: _conferir_vinculo(v, ultimas.get(v.id, []), demo=demo) for v in vinculos}


# --- empresa -------------------------------------------------------------------


def conferir_empresa(db: Session, prestador_id: uuid.UUID, *, certificado_trava: bool = True) -> list[dict]:
    """Certificado, alíquota e ambiente. `certificado_trava=False`: a falta
    de certificado vira aviso (dá pra GERAR a nota sem ele; só não dá pra
    assinar e enviar)."""
    prestador = db.get(Prestador, prestador_id)
    if prestador is None:
        return []
    pontos: list[dict] = []
    nivel_cert = "erro" if certificado_trava else "aviso"
    # Simulação nunca assina nem envia nada: certificado e ambiente não se aplicam.
    if not prestador.demo:
        registro = db.query(Certificado).filter_by(prestador_id=prestador_id).one_or_none()
        hoje = hoje_br()
        if registro is None:
            pontos.append(_ponto(
                nivel_cert, "sem_certificado", "Sua empresa ainda não tem o certificado digital guardado aqui. Sem ele eu não consigo assinar nem enviar a nota.",
                "Envie o arquivo do certificado A1 (.pfx) em Empresa › Certificado.", campo="certificado", onde="empresa",
            ))
        elif registro.validade is not None and registro.validade < hoje:
            pontos.append(_ponto(
                nivel_cert, "certificado_vencido", f"O certificado digital venceu em {registro.validade:%d/%m/%Y}. A Receita recusa nota assinada com certificado vencido.",
                "Compre um certificado A1 novo e envie em Empresa › Certificado.", campo="certificado", onde="empresa",
            ))
        elif registro.validade is not None and (registro.validade - hoje).days < DIAS_AVISO_CERTIFICADO:
            dias = (registro.validade - hoje).days
            quando = "vence hoje" if dias == 0 else ("vence amanhã" if dias == 1 else f"vence em {dias} dias")
            pontos.append(_ponto(
                "aviso", "certificado_vencendo", f"O certificado digital {quando} ({registro.validade:%d/%m/%Y}). Depois disso não dá pra enviar notas.",
                "Renove o certificado A1 e envie o novo em Empresa › Certificado.", campo="certificado", onde="empresa",
            ))
        if not prestador.modo_teste and prestador.tp_amb_padrao == "2":
            pontos.append(_ponto(
                "aviso", "ambiente_teste", "Sua conta está no ambiente de teste: as notas saem sem valor fiscal (não valem de verdade).",
                "Para emitir notas de verdade, mude para “Produção” em Empresa › Notas.", campo="ambiente", onde="empresa",
            ))
    if not prestador.demo:
        from app.services.compatibilidade import usa_emissor_nacional

        if usa_emissor_nacional(prestador.cod_municipio) is False:
            pontos.append(_ponto(
                "aviso", "prefeitura_sem_emissor_nacional",
                "Pela lista da Receita, a prefeitura da sua cidade emite nota por sistema próprio, não pelo Emissor Nacional — o envio da nota pode ser recusado.",
                "Confirme com a prefeitura (ou o contador) se a sua empresa pode emitir pelo Emissor Nacional da NFS-e.",
                campo="cod_municipio", onde="empresa",
            ))
    # "3" = ME/EPP do Simples Nacional: é quem informa a alíquota na nota.
    if prestador.op_simples_nacional == "3" and prestador.aliquota_atual is None:
        pontos.append(_ponto(
            "aviso", "aliquota_nao_definida", "A alíquota do Simples Nacional da sua empresa não está informada.",
            "Informe a alíquota em Empresa › Alíquotas (o seu contador sabe o número).", campo="aliquota", onde="empresa",
        ))
    return pontos


# --- nota ------------------------------------------------------------------------


def _historico(db: Session, vinculo_id: uuid.UUID, *, ignorar_id: uuid.UUID | None = None) -> list[tuple[str, Decimal]]:
    """(competência, valor) das últimas notas deste tomador que não foram
    canceladas — mais nova primeiro. Notas de vendedores da Shopee (avulsas)
    não contam: são de outra pessoa."""
    consulta = db.query(Emissao.competencia, Emissao.valor).filter(
        Emissao.prestador_tomador_id == vinculo_id, Emissao.tomador_documento.is_(None),
        Emissao.estado.notin_(_ESTADOS_FORA_DO_HISTORICO),
    )
    if ignorar_id is not None:
        consulta = consulta.filter(Emissao.id != ignorar_id)
    return [(c, v) for c, v in consulta.order_by(Emissao.competencia.desc(), Emissao.criado_em.desc()).limit(_NOTAS_PARA_VALOR)]


def _competencia_menos(competencia: str, meses: int) -> str:
    ano, mes = int(competencia[:4]), int(competencia[5:7])
    total = ano * 12 + (mes - 1) - meses
    return f"{total // 12:04d}-{total % 12 + 1:02d}"


def _checar_valor_e_datas(
    *, valor, data_competencia: datetime.date | None, competencia: str | None, historico: list[tuple[str, Decimal]] | None,
) -> list[dict]:
    """`historico=None`: não compara com o costume (nota de vendedor da Shopee)."""
    pontos: list[dict] = []
    hoje = hoje_br()
    valor_ok = valor is not None and float(valor) > 0
    if not valor_ok:
        pontos.append(_ponto("erro", "valor_invalido", "O valor da nota precisa ser maior que zero.", "Digite o valor do serviço.", campo="valor", onde="nota"))

    if data_competencia is not None and data_competencia > hoje:
        pontos.append(_ponto(
            "erro", "competencia_futura",
            f"A data de competência ({data_competencia:%d/%m/%Y}) ainda não chegou. A Receita não aceita nota com data no futuro.",
            "Escolha a data de hoje ou uma data que já passou.", campo="data_competencia", onde="nota",
        ))
    mes_nota = f"{data_competencia.year:04d}-{data_competencia.month:02d}" if data_competencia is not None else competencia
    if mes_nota and re.fullmatch(r"\d{4}-\d{2}", mes_nota):
        atraso = (hoje.year * 12 + hoje.month) - (int(mes_nota[:4]) * 12 + int(mes_nota[5:7]))
        if atraso > 2:
            pontos.append(_ponto(
                "aviso", "competencia_antiga",
                f"A competência da nota é {mes_nota[5:7]}/{mes_nota[:4]}, de {atraso} meses atrás. Nota de mês antigo pode gerar multa e juros no imposto.",
                "Confira se a data é essa mesmo. Na dúvida, pergunte ao seu contador.", campo="data_competencia", onde="nota",
            ))

    if not valor_ok or not historico:
        return pontos
    valor_dec = Decimal(str(valor)).quantize(Decimal("0.01"))
    valores = [Decimal(v) for _, v in historico if v is not None and Decimal(v) > 0]
    if valores:
        costume = Decimal(str(statistics.median(valores)))
        if valor_dec > costume * 3 or valor_dec * 3 < costume:
            quantas = "a última nota deste tomador ficou em" if len(valores) == 1 else "as últimas notas deste tomador ficaram em torno de"
            pontos.append(_ponto(
                "aviso", "valor_fora_do_costume",
                f"Valor bem diferente do costume: {quantas} {_brl(costume)} e esta é de {_brl(valor_dec)}.",
                "Confira se não faltou ou sobrou um número (ou a vírgula) no valor.", campo="valor", onde="nota",
            ))
    if mes_nota and re.fullmatch(r"\d{4}-\d{2}", mes_nota):
        meses_vizinhos = {_competencia_menos(mes_nota, 1), _competencia_menos(mes_nota, 2)}
        iguais = [c for c, v in historico if v is not None and Decimal(v) == valor_dec]
        # Valor fixo todo mês (mensalidade) repete sempre: aí não é sinal de nota repetida.
        if len(iguais) == 1 and iguais[0] in meses_vizinhos:
            pontos.append(_ponto(
                "aviso", "possivel_duplicada",
                f"Este tomador já tem uma nota com este mesmo valor ({_brl(valor_dec)}) em {iguais[0][5:7]}/{iguais[0][:4]}. Pode ser a mesma nota de novo.",
                "Confira se este serviço já não foi cobrado na outra nota.", campo="valor", onde="nota",
            ))
    return pontos


def _checar_aliquota(aliq_sn) -> list[dict]:
    if aliq_sn is None or 0 < float(aliq_sn) <= 33:
        return []
    return [_ponto(
        "aviso", "aliquota_fora_do_normal", f"A alíquota do Simples informada ({float(aliq_sn):g}%) está fora do normal (costuma ficar entre 4% e 20%).",
        "Confira o número com o seu contador.", campo="aliq_sn", onde="nota",
    )]


def conferir_nota(
    db: Session, vinculo: PrestadorTomador, valor, data_competencia: datetime.date | None,
    ordem: str | None, aliq_sn, *, competencia: str | None = None,
) -> list[dict]:
    """Antes de GERAR a nota: os erros do cadastro do tomador + a empresa +
    o que foi digitado agora. `competencia` (AAAA-MM) só é usada quando não
    veio a data."""
    pontos = [p for p in conferir_vinculo(db, vinculo) if p["nivel"] == "erro"]
    empresa = conferir_empresa(db, vinculo.prestador_id, certificado_trava=False)
    if aliq_sn is not None:
        # A alíquota foi digitada nesta nota: a falta da de referência não importa.
        empresa = [p for p in empresa if p["codigo"] != "aliquota_nao_definida"]
    pontos += empresa

    template = vinculo.template_descricao or ""
    mes_nota = f"{data_competencia.year:04d}-{data_competencia.month:02d}" if data_competencia is not None else competencia
    if "{ordem}" in template and not (ordem or "").strip():
        pontos.append(_ponto(
            "erro", "ordem_faltando", "A descrição da nota deste tomador leva o número da ordem de pagamento, e ele não foi informado.",
            "Digite o número da ordem de pagamento.", campo="ordem", onde="nota",
        ))
    elif template.strip() and mes_nota and re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", mes_nota):
        tamanho = len(renderizar_descricao(template, mes_nota, ordem=ordem))
        if tamanho > LIMITE_DESCRICAO:
            pontos.append(_ponto(
                "erro", "descricao_longa", f"A descrição desta nota ficou com {tamanho} letras e a prefeitura aceita até {LIMITE_DESCRICAO}.",
                "Encurte a descrição no cadastro do tomador.", campo="template_descricao", onde="tomador",
            ))
    pontos += _checar_valor_e_datas(
        valor=valor, data_competencia=data_competencia, competencia=competencia,
        historico=None if vinculo.sem_nota else _historico(db, vinculo.id),
    )
    pontos += _checar_aliquota(aliq_sn)
    return pontos


def _data_ou_none(texto) -> datetime.date | None:
    try:
        return datetime.date.fromisoformat(str(texto)[:10]) if texto else None
    except ValueError:
        return None


def conferir_emissao(db: Session, emissao: Emissao) -> list[dict]:
    """Uma nota que já existe e ainda não foi autorizada: confere o que está
    GUARDADO nela (o retrato do tomador e do serviço tirado quando ela foi
    gerada — é isso que vai pra prefeitura), sem comparar a nota com ela
    mesma. Notas de vendedores da Shopee (`tomador_documento` preenchido)
    são conferidas pelo retrato do vendedor e não entram na comparação de
    valor de costume."""
    snap = emissao.tomador_snapshot if isinstance(emissao.tomador_snapshot, dict) else {}
    avulsa = bool(emissao.tomador_documento) or bool(snap.get("avulso"))
    endereco = snap.get("endereco") if isinstance(snap.get("endereco"), dict) else {}
    servico = snap.get("codigo_servico_usado") if isinstance(snap.get("codigo_servico_usado"), dict) else {}
    demo = _eh_demo(db, emissao.prestador_id)
    if avulsa:
        onde, como = "nota", "Confira os dados deste vendedor no relatório, apague esta nota e gere de novo com o dado certo."
    else:
        onde, como = "tomador", "Depois de acertar o cadastro do tomador, gere a nota de novo (a nova entra no lugar desta)."

    tipo = str(snap.get("tipo_documento") or "CNPJ").upper()
    if tipo not in ("CNPJ", "CPF", "NIF"):
        tipo = "CNPJ"
    pontos = _checar_pessoa(
        tipo=tipo, documento=snap.get("cnpj") or emissao.tomador_documento, nome=snap.get("razao_social"),
        endereco=endereco, onde=onde, conferir_digitos=not demo, como_corrigir=como,
    )
    pontos += _checar_servico(
        cod_local=servico.get("cLocPrestacao"), cod_nacional=servico.get("cTribNac"), cod_nbs=servico.get("cNBS"),
        onde="tomador", como_corrigir="Corrija no cadastro do tomador e gere a nota de novo (a nova entra no lugar desta).",
    )

    descricao = str(snap.get("descricao_renderizada") or "")
    corrigir_descricao = "Corrija a descrição no cadastro do tomador e gere a nota de novo (a nova entra no lugar desta)."
    if not descricao.strip():
        pontos.append(_ponto("erro", "descricao_vazia", "Esta nota está sem a descrição do serviço.", corrigir_descricao, campo="template_descricao"))
    else:
        sobras = list(dict.fromkeys(re.findall(r"\{\w+\}", descricao)))
        if sobras:
            pontos.append(_ponto(
                "erro", "descricao_campo_desconhecido",
                f"A descrição desta nota ficou com um campo automático sem preencher: {', '.join(sobras)}.", corrigir_descricao, campo="template_descricao",
            ))
        if len(descricao) > LIMITE_DESCRICAO:
            pontos.append(_ponto(
                "erro", "descricao_longa", f"A descrição desta nota tem {len(descricao)} letras e a prefeitura aceita até {LIMITE_DESCRICAO}.",
                corrigir_descricao, campo="template_descricao",
            ))

    empresa = conferir_empresa(db, emissao.prestador_id)
    # O ambiente que vale é o que ficou gravado NESTA nota, não o da conta hoje.
    empresa = [p for p in empresa if p["codigo"] != "ambiente_teste"]
    if snap.get("aliq_sn") is not None:
        empresa = [p for p in empresa if p["codigo"] != "aliquota_nao_definida"]
    pontos += empresa
    prestador = db.get(Prestador, emissao.prestador_id)
    if str(snap.get("tpAmb") or "") == "2" and prestador is not None and not prestador.demo and not prestador.modo_teste:
        pontos.append(_ponto(
            "aviso", "ambiente_teste", "Esta nota foi gerada no ambiente de teste: ela sai sem valor fiscal (não vale de verdade).",
            "Para valer, mude para “Produção” em Empresa › Notas e gere a nota de novo.", campo="ambiente", onde="empresa",
        ))

    historico = None if avulsa else _historico(db, emissao.prestador_tomador_id, ignorar_id=emissao.id)
    pontos += _checar_valor_e_datas(
        valor=emissao.valor, data_competencia=_data_ou_none(snap.get("dcompet")), competencia=emissao.competencia, historico=historico,
    )
    pontos += _checar_aliquota(snap.get("aliq_sn"))

    if not avulsa:
        ultimas = _codigos_das_ultimas(db, [emissao.prestador_tomador_id], ignorar_id=emissao.id).get(emissao.prestador_tomador_id, [])
        pontos += _checar_codigos_de_costume(
            servico, ultimas, onde="tomador",
            como_corrigir="Se precisar, corrija no cadastro do tomador e gere a nota de novo.",
        )
        pontos += _cadastro_mudou(emissao, snap, endereco, servico)
    return pontos


def _cadastro_mudou(emissao: Emissao, snap: dict, endereco: dict, servico: dict) -> list[dict]:
    """A nota guarda os dados do tomador do dia em que foi gerada. Se o
    cadastro foi corrigido depois, a correção NÃO entrou nela."""
    vinculo = emissao.vinculo
    if vinculo is None or vinculo.tomador is None or vinculo.excluido_em is not None:
        return []
    tomador = vinculo.tomador

    def igual(a, b) -> bool:
        return str(a or "").strip() == str(b or "").strip()

    mudou = []
    if tomador.de_fora:
        # De fora do Brasil: o documento da nota é o NIF, e ela não leva endereço daqui.
        if not igual(snap.get("cnpj"), tomador.nif) or not igual(str(snap.get("pais") or "").upper(), (tomador.pais or "").upper()) \
                or not igual(snap.get("razao_social"), tomador.razao_social):
            mudou.append("os dados do tomador")
        pares = ()
    else:
        if not igual(snap.get("cnpj"), tomador.cnpj) or not igual(snap.get("razao_social"), tomador.razao_social):
            mudou.append("os dados do tomador")
        pares = (("cMun", tomador.cod_municipio), ("CEP", tomador.cep), ("xLgr", tomador.logradouro), ("nro", tomador.numero), ("xCpl", tomador.complemento), ("xBairro", tomador.bairro))
    if any(not igual(endereco.get(chave), atual) for chave, atual in pares):
        mudou.append("o endereço")
    codigos = (("cLocPrestacao", vinculo.cod_local_prestacao), ("cTribNac", vinculo.cod_trib_nacional), ("cTribMun", vinculo.cod_trib_municipal), ("cNBS", vinculo.cod_nbs))
    if any(_comparavel(chave, servico.get(chave)) != _comparavel(chave, atual) for chave, atual in codigos):
        mudou.append("os códigos do serviço")
    if "template_descricao_usado" in snap and not igual(snap.get("template_descricao_usado"), vinculo.template_descricao):
        mudou.append("a descrição")
    if not mudou:
        return []
    lista = mudou[0] if len(mudou) == 1 else ", ".join(mudou[:-1]) + " e " + mudou[-1]
    return [_ponto(
        "aviso", "cadastro_mudou",
        f"O cadastro deste tomador mudou depois que esta nota foi gerada ({lista}). Esta nota ainda está com os dados antigos.",
        "Para a nota sair com os dados novos, gere a nota de novo (a nova entra no lugar desta).", onde="nota",
    )]


def frase_de_recusa(pontos: list[dict]) -> str:
    """Os erros numa frase só, pro 422 de `POST /api/dps`."""
    erros = [p for p in pontos if p["nivel"] == "erro"]
    partes = [" ".join(t for t in (p["mensagem"], p["como_corrigir"]) if t) for p in erros[:3]]
    resto = len(erros) - len(partes)
    texto = "Não gerei a nota porque encontrei " + ("um problema" if len(erros) == 1 else f"{len(erros)} problemas") + ": " + " | ".join(partes)
    if resto > 0:
        texto += f" | e mais {resto}."
    return texto
