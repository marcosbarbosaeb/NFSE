"""
Painel interno — Marco 5 (painel) + Marco 6 (motor de emissão) + Marco 10
(login multiusuário) do plano.

Login DE VERDADE a partir do Marco 10 (cookie de sessão assinado, via
Starlette SessionMiddleware — ver app/auth.py pro hash de senha e
app/services/usuarios.py pro login em si). Antes disso (Fase 1, Marco 5) o
painel operava sempre como um prestador fixo de config, sem sessão nenhuma
— ver histórico em app/config.py. A troca foi cirúrgica de propósito:
`prestador_atual_id` é a ÚNICA dependency que mudou (de ler config fixa pra
ler a sessão); toda rota que já dependia dela (direta ou via `db_sessao`)
ganhou autenticação de graça, sem precisar tocar em nenhuma outra rota — a
disciplina de RLS por trás continua exatamente a mesma, testada desde o
Marco 1.

A partir do Marco 6, gerar uma DPS aqui JÁ PERSISTE uma linha real em
`emissao`, passando pela máquina de estados formal (rascunho -> montado ->
assinado -> ...) em vez de só montar/assinar em memória — nDPS é atribuído
automaticamente pelo motor de emissão (nosso Postgres é a fonte de verdade
do sequencial, não a Sefin — ver app/services/motor_emissao.py).

Marco 16, item 7 (a pedido do Marcos: "conseguimos fazer a emissão e o
cancelamento funcionando real. Deixe tudo pronto, mais tarde carregarei o
certificado A1 e faremos o teste") — o painel agora EXPÕE submeter/cancelar
de verdade (POST /api/dps/{id}/submeter, POST /api/dps/{id}/cancelar),
chamando `app.fiscal.cliente_sefin.ClienteSefin` com o certificado
carregado, exatamente como os scripts em integracao/ já faziam. A ressalva
de sempre continua valendo: submissão de DPS pela série "1" (a dos 5
fornecedores) NUNCA foi validada contra a API real — só cancelamento foi
(nota emitida por outro canal, série 70000-79999). E este sandbox não
alcança gov.br de jeito nenhum (egress bloqueado por política da
organização, confirmado por curl direto) — então nada disso pode ser
testado ao vivo daqui, só depois de implantado em algum lugar com rede
aberta E com um certificado A1 de verdade carregado.
"""
import datetime
import io
import logging
import json
import zipfile
from urllib.parse import urlparse
import os
import re
from html import escape
import uuid
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlencode

from starlette.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse, Response
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from app.config import get_settings
from app.deps import MENSAGEM_DEMO, MODULOS, db_sessao, exige_modulo, exigir_conta_real, ler_upload as _ler_upload, modulos_da_empresa, prestador_atual_id  # noqa: F401
from app import eventos as integracao
from app.database import definir_prestador_atual, get_db
from app.fiscal.dps import DescricaoIncompletaError
from app.models import (
    AjusteEvento, Assinatura, Certificado, Emissao, Envio, LoteAcao, 
    Prestador, Usuario,
)
from app.schemas import (
    AjusteOcorrenciaRequest,
    AliquotaAtualizarRequest,
    AssinaturaResponse,
    CadastroRequest,
    CadastroResponse,
    CalendarioResponse,
    CancelarDpsRequest,
    CertificadoStatus,
    CheckoutSessaoResponse,
    ConfirmarEmailRequest,
    ConsultaCnpjResponse,
    DashboardResumoResponse,
    EmissaoListaLinha,
    ExclusaoVinculoResponse,
    EmissaoResponse,
    EnvioResponse,
    ErroResponse,
    EventoCalendarioResponse,
    EventoManualAtualizarRequest,
    EventoManualCriarRequest,
    GerarDpsRequest,
    ModulosRequest,
    OrigemNotaRequest,
    PreferenciasRequest,
    GeracaoShopeeResponse,
    OrdemAwinResponse,
    PreferenciasPrestadorRequest,
    PreviaEmailResponse,
    ModeloEmailPadraoResponse,
    PreviaShopeeResponse,
    EnviarGeralRequest,
    MoverNotaRequest,
    LimparImportadasRequest,
    IgnorarPendenciaRequest,
    BuscarNacionalRequest,
    ImportarNacionalRequest,
    ImportarNacionalResponse,
    PreviaNacionalResponse,
    MarcarEnviadaRequest,
    SolicitarCodigoRequest,
    EntrarComCodigoRequest,
    ContaResponse,
    ContaAtualizarRequest,
    SessaoResponse,
    EmpresaResponse,
    EmpresaCriarRequest,
    ExcluirRequest,
    EmitenteAtualizarRequest,
    CriarLoteRequest,
    LoteResponse,
    PreviaLoteResponse,
    ResumoEnviosResponse,
    WhatsappRequest,
    EnviarEmailRequest,
    IndicacaoResponse,
    CanaisSuporteResponse,
    MensagemSuporteRequest,
    ProximosResponse,
    GoogleOAuthUrlResponse,
    ImportacaoCsvResponse,
    LembreteAliquotaRequest,
    LimparDadosRequest,
    LimparDadosResponse,
    LoginRequest,
    MunicipioResponse,
    MensagemProntaResponse,
    NotaVisualResponse,
    OpcoesEnvioResponse,
    PrestadorResponse,
    ReenviarConfirmacaoRequest,
    RegistrarEnvioRequest,
    ServicoNacionalResponse,
    TomadorResponse,
    TrocarSenhaRequest,
    UsuarioResponse,
    VerificarDuplicataResponse,
    VinculoCriarRequest,
    VinculoAtualizarRequest,
    VinculoDetalheResponse,
    VinculoResumo,
    WhatsappLinkResponse,
)
from app.services.municipios import buscar_municipios, municipio_por_codigo
from app.services.billing import (
    AssinaturaNaoEncontradaError,
    BillingNaoConfiguradoError,
    WebhookInvalidoError,
    assinatura_esta_ativa,
    criar_sessao_checkout,
    criar_sessao_portal,
    processar_webhook,
)
from app.services.cnpj_lookup import (
    CnpjInvalidoError,
    CnpjNaoEncontradoError,
    ConsultaCnpjIndisponivelError,
    consultar_cnpj,
)
from app.services.certificados import (
    CertificadoNaoEncontradoError,
    carregar_certificado,
    certificado_vencido,
    salvar_certificado,
)
from app.services.calendario import (
    ajustar_ocorrencia,
    atualizar_evento_manual,
    buscar_evento_manual,
    criar_evento_manual,
    evento_manual_para_dict,
    eventos_calendario,
    excluir_evento_manual,
    remover_ajuste,
)
from app.services.dashboard import resumo_mes
from app.services.envios import (
    CanalInvalidoError,
    EmissaoSemConteudoError,
    buscar_envio,
    gerar_mensagem_pronta,
    listar_envios,
    marcar_enviado,
    marcar_falha,
    melhor_xml_disponivel,
    registrar_envio,
)
from app.limites import limitador, limite  # noqa: F401 — limitador: os testes zeram
from app.services import contas, importar_adn, lotes, mensagens
from app.services.indicacao import resumo as resumo_indicacao
from app.services.email import EmailEnvioError, get_email_sender
from app.services.dashboard import proximos as proximos_do_painel
from app.services.envio_direto import (
    EmailIndisponivelError,
    LinkInvalidoError,
    base_url,
    enviar_email,
    enviar_geral,
    marcar_enviada,
    previa_email,
    ler_token,
    link_whatsapp,
    nome_pdf,
    obter_danfse,
    opcoes_envio,
)
from app.services.demo import criar_conta_demo, eh_email_demo
from app.services.limpeza import limpar_dados
from app.services.ordem_awin import CNPJ_AWIN, OrdemAwinInvalidaError, ler_ordem_awin
from app.services.relatorio_shopee import RelatorioShopeeInvalidoError, documentos_ja_gerados, gerar_notas, ler_relatorio
from app.services.servicos_nacionais import buscar_servicos, listar_servicos, servico_por_codigo
from app.services.google_oauth import (
    GoogleOAuthFalhaError,
    GoogleOAuthNaoConfiguradoError,
    gerar_state,
    montar_url_autorizacao,
    trocar_code_por_usuario,
)
from app.services.importacao_csv import CsvInvalidoError, importar_csv
from app.services.listagens import listar_emissoes
from app.fiscal.cliente_sefin import ClienteSefin
from app.services.motor_emissao import (
    EmissaoJaExisteError,
    TransicaoInvalidaError,
    assinar as assinar_emissao,
    buscar_emissao_ativa,
    cancelar as cancelar_emissao,
    criar_rascunho,
    montar as montar_emissao,
    motivo_da_recusa,
    recusa_corrigivel,
    remontar as remontar_emissao,
    submeter as submeter_emissao,
)
from app.services import assistente_tomador
from app.services.nota_visual import montar_nota_visual
from app.services.tomadores import CnpjJaCadastradoError, buscar_tomador, criar_tomador, listar_catalogo
from app.services.cadastro import (
    EmailJaCadastradoError as CadastroEmailJaCadastradoError,
    PrestadorJaCadastradoError,
    TokenInvalidoOuExpiradoError,
    confirmar_email,
    criar_cadastro,
    reenviar_confirmacao,
)
from app.services.usuarios import SenhaAtualIncorretaError, autenticar, trocar_senha
from app.services.vinculos import (
    ApelidoJaExisteError,
    atualizar_vinculo,
    buscar_vinculo,
    criar_vinculo,
    emissoes_da_competencia,
    excluir_vinculo,
    listar_vinculos_ativos,
    listar_vinculos_da_tela,
    ordenar_para_tela,
)
from app.tempo import hoje as hoje_br

logger = logging.getLogger("agenteana.api")
app = FastAPI(title="Painel NFS-e — Raiana (Marco 5/6/9/10)")

# Rotas do EMISSOR só respondem pra empresa que tem o módulo (05/10/2026).
_SO_EMISSOR = Depends(exige_modulo("emissor"))
# same_site="lax": suficiente pro painel ser first-party (o próprio backend
# serve a página em /); https_only fica False aqui de propósito porque este
# ambiente de dev roda em http puro — LIGAR em produção atrás de HTTPS de
# verdade é obrigatório (cookie de sessão sem isso pode vazar em rede
# insegura).
_EM_HTTPS = get_settings().app_base_url.startswith("https://")
# Revisão de segurança (28/09/2026): em produção (APP_BASE_URL https) o
# cookie só trafega em HTTPS; sessão dura 14 dias.
app.add_middleware(
    SessionMiddleware, secret_key=get_settings().session_secret_key, same_site="lax",
    https_only=_EM_HTTPS, max_age=14 * 24 * 3600,
)

_METODOS_QUE_MUDAM = {"POST", "PUT", "PATCH", "DELETE"}


def _origem_confiavel(origem: str) -> bool:
    """Mesmo site do painel (notas.agenteana.com.br), o site institucional
    (agenteana.com.br) e o painel local em desenvolvimento."""
    host = urlparse(origem).hostname or ""
    base = urlparse(get_settings().app_base_url).hostname or ""
    return host == base or host == "agenteana.com.br" or host.endswith(".agenteana.com.br") or host in ("localhost", "127.0.0.1")


@app.middleware("http")
async def _seguranca(request: Request, call_next):
    """Defesa extra contra CSRF (pedido que muda dado vindo de outro site é
    recusado — o cookie é SameSite=Lax, isto cobre o resto) e cabeçalhos de
    segurança em toda resposta."""
    if request.method in _METODOS_QUE_MUDAM and request.url.path.startswith("/api/") and request.url.path != "/api/webhooks/stripe":
        origem = request.headers.get("origin")
        if origem and origem != "null" and not _origem_confiavel(origem):
            return JSONResponse(status_code=403, content={"detail": "Origem não permitida."})
    resposta = await call_next(request)
    resposta.headers.setdefault("X-Content-Type-Options", "nosniff")
    resposta.headers.setdefault("X-Frame-Options", "DENY")
    resposta.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    resposta.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if _EM_HTTPS:
        resposta.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
    return resposta


def _avisar_segredos_de_desenvolvimento() -> None:
    """Se o deploy subir sem SESSION_SECRET_KEY/CERT_MASTER_KEY próprias, os
    valores de desenvolvimento (que estão no git) estariam valendo — qualquer
    um forjaria sessão ou abriria certificados. Grita no log."""
    padrao = type(get_settings())
    s = get_settings()
    for campo in ("session_secret_key", "cert_master_key"):
        if getattr(s, campo) == padrao.model_fields[campo].default and os.environ.get("RAILWAY_ENVIRONMENT"):
            logger.critical("SEGURANÇA: %s está com o valor de desenvolvimento em produção — defina a variável no Railway.", campo.upper())


_avisar_segredos_de_desenvolvimento()




def _validar_nbs(codigo: str | None) -> str | None:
    """Código NBS: 9 dígitos (ex.: 1.1406.20.00). Vazio = sem NBS."""
    digitos = "".join(c for c in (codigo or "") if c.isdigit())
    if not digitos:
        return None
    if len(digitos) != 9:
        raise HTTPException(status_code=422, detail="Código NBS tem 9 dígitos (ex.: 1.1406.20.00).")
    return digitos


def _sessao_demo(request: Request, db: Session) -> bool:
    usuario_id = request.session.get("usuario_id")
    if not usuario_id:
        return False
    usuario = db.get(Usuario, uuid.UUID(usuario_id))
    return usuario is not None and eh_email_demo(usuario.email)


def _dados_oficiais_cnpj(cnpj: str):
    """Dados da Receita pro CNPJ, ou None se a consulta falhar (não trava o
    cadastro do tomador)."""
    try:
        return consultar_cnpj(cnpj)
    except Exception:  # noqa: BLE001 — indisponível/não achou: segue com o digitado
        return None


@app.post("/api/auth/login", response_model=UsuarioResponse, responses={401: {"model": ErroResponse}, 403: {"model": ErroResponse}}, dependencies=[Depends(limite("login", 20, 600))])
def api_login(req: LoginRequest, request: Request, db: Session = Depends(get_db)):
    """Desde o Marco 15 existem dois jeitos de uma conta nascer: administrativo
    (scripts/criar_usuario.py, já confirmado) ou cadastro público self-service
    (ver /api/cadastro abaixo, precisa confirmar e-mail antes de logar)."""
    usuario = autenticar(db, req.email, req.senha)
    if usuario is None:
        raise HTTPException(status_code=401, detail="E-mail ou senha inválidos.")
    if not usuario.email_confirmado:
        raise HTTPException(status_code=403, detail="Confirme seu e-mail antes de entrar — verifique sua caixa de entrada.")
    contas.iniciar_sessao(db, request, usuario)
    db.commit()
    return UsuarioResponse(email=usuario.email, prestador_id=usuario.prestador_id, nome=usuario.nome)


@app.post("/api/demo", response_model=UsuarioResponse, dependencies=[Depends(limite("demo", 6, 3600))])
def api_criar_demo(request: Request, db: Session = Depends(get_db)):
    """Ambiente de simulação — cria uma conta descartável com dados de
    exemplo e já entra nela (ver app/services/demo.py)."""
    usuario = criar_conta_demo(db)
    db.commit()
    contas.iniciar_sessao(db, request, usuario)
    db.commit()
    return UsuarioResponse(email=usuario.email, prestador_id=usuario.prestador_id, demo=True)


@app.post("/api/auth/google/iniciar", response_model=GoogleOAuthUrlResponse, responses={400: {"model": ErroResponse}}, dependencies=[Depends(limite("google", 30, 600))])
def api_iniciar_google_oauth(request: Request):
    """Marco 16, item 1 — primeiro passo do login/cadastro com Google (ver
    app/services/google_oauth.py). Rota pública: roda tanto pra quem já
    tem conta (login) quanto pra quem ainda não tem (o callback decide
    qual dos dois é o caso, olhando se o e-mail devolvido pela Google já
    tem Usuario). 400 enquanto GOOGLE_OAUTH_CLIENT_ID/SECRET forem
    placeholder — mesmo padrão de /api/assinatura/checkout com Stripe não
    configurado."""
    settings = get_settings()
    state = gerar_state()
    try:
        url = montar_url_autorizacao(settings, state)
    except GoogleOAuthNaoConfiguradoError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    request.session["google_oauth_state"] = state
    return GoogleOAuthUrlResponse(url=url)


@app.get("/api/auth/google/callback")
def api_callback_google_oauth(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
):
    """Volta da Google depois da pessoa autorizar (ou cancelar/negar). É a
    própria Google que navega o browser pra cá — por isso a resposta é
    SEMPRE um redirect de volta pro frontend (nunca JSON, não tem quem
    leia), com o resultado sinalizado só pela URL de destino:

    - conta já existe (e confirmada) → loga e manda pra /app;
    - conta já existe mas e-mail não confirmado → manda pra /entrar com um
      aviso (mesma trava do login por senha, ver api_login);
    - e-mail sem conta nenhuma → manda pro /cadastro público normal,
      pré-preenchido (não dá pra criar a conta só com o que a Google
      manda, falta CNPJ/razão social — ver docstring de
      app/services/google_oauth.py);
    - qualquer falha (state não bate, code ausente, Google recusou a
      troca) → manda pra /entrar com um erro genérico. `state` é
      comparado contra o que foi guardado na sessão em
      /api/auth/google/iniciar — protege contra um link de callback
      forjado que não veio de um fluxo que a gente mesmo iniciou."""
    settings = get_settings()
    base = settings.app_base_url
    state_esperado = request.session.pop("google_oauth_state", None)

    if error is not None or code is None or state is None or state != state_esperado:
        return RedirectResponse(f"{base}/entrar?erro=google")

    try:
        info = trocar_code_por_usuario(settings, code)
    except (GoogleOAuthNaoConfiguradoError, GoogleOAuthFalhaError):
        return RedirectResponse(f"{base}/entrar?erro=google")

    # Revisão de segurança (28/09/2026): só confia no e-mail que a Google
    # diz ter verificado, e uma conta já ligada a uma conta Google não aceita
    # outra com o mesmo e-mail.
    if not info.email_verificado:
        return RedirectResponse(f"{base}/entrar?erro=google")
    usuario = db.query(Usuario).filter_by(email=info.email, ativo=True).one_or_none()
    if usuario is not None and usuario.google_sub and usuario.google_sub != info.sub:
        return RedirectResponse(f"{base}/entrar?erro=google")
    if usuario is None:
        params = urlencode({"google_email": info.email, "google_nome": info.nome or ""})
        return RedirectResponse(f"{base}/cadastro?{params}")

    if not usuario.email_confirmado:
        return RedirectResponse(f"{base}/entrar?erro=confirme-email")

    if usuario.google_sub is None:
        usuario.google_sub = info.sub
    if not usuario.nome and info.nome:
        usuario.nome = info.nome[:120]
    contas.iniciar_sessao(db, request, usuario)
    db.commit()
    return RedirectResponse(f"{base}/app")


@app.get("/api/municipios", response_model=list[MunicipioResponse])
def api_buscar_municipios(q: str = "", uf: str | None = None):
    """Autocomplete de cidade (pedido do Marcos: esconder o código IBGE da
    pessoa). Público de propósito — o cadastro usa antes do login. Dado é a
    tabela oficial embutida, sem nada do prestador."""
    return buscar_municipios(q, uf=uf)


@app.get("/api/municipios/{codigo}", response_model=MunicipioResponse, responses={404: {"model": ErroResponse}})
def api_ver_municipio(codigo: str):
    m = municipio_por_codigo(codigo)
    if m is None:
        raise HTTPException(status_code=404, detail="Município não encontrado.")
    return m


@app.get("/api/cnpj/{cnpj}", response_model=ConsultaCnpjResponse, responses={404: {"model": ErroResponse}, 422: {"model": ErroResponse}, 503: {"model": ErroResponse}}, dependencies=[Depends(limite("cnpj", 60, 600))])
def api_consultar_cnpj(cnpj: str):
    """Marco 16 — autopreenchimento do cadastro público a partir do CNPJ
    (rota pública, sem sessão — é usada ANTES de existir conta). Nunca deve
    derrubar o cadastro: 503 quando a consulta externa está indisponível é
    o sinal pro frontend cair pro preenchimento manual (ver
    app/services/cnpj_lookup.py pra ressalva sobre o código de município
    devolvido aqui ser só uma sugestão)."""
    try:
        dados = consultar_cnpj(cnpj)
    except CnpjInvalidoError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except CnpjNaoEncontradoError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ConsultaCnpjIndisponivelError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return ConsultaCnpjResponse(
        razao_social=dados.razao_social, logradouro=dados.logradouro, numero=dados.numero,
        complemento=dados.complemento, bairro=dados.bairro, cep=dados.cep,
        municipio=dados.municipio, uf=dados.uf,
        cod_municipio_sugerido=dados.cod_municipio_sugerido, situacao_cadastral=dados.situacao_cadastral,
    )


@app.post("/api/cadastro", response_model=CadastroResponse, responses={409: {"model": ErroResponse}}, dependencies=[Depends(limite("cadastro", 10, 3600))])
def api_cadastro(req: CadastroRequest, db: Session = Depends(get_db)):
    """Marco 15 — cadastro público self-service (rota pública, sem sessão).
    Cria Prestador+Usuario de verdade (ver app/services/cadastro.py), mas o
    Usuario nasce sem `email_confirmado` — não dá pra logar até confirmar
    (ver /api/cadastro/confirmar abaixo)."""
    try:
        usuario = criar_cadastro(
            db, email=req.email, senha=req.senha, razao_social=req.razao_social,
            cpf_cnpj=req.cpf_cnpj, cod_municipio=req.cod_municipio,
            cep=req.cep, logradouro=req.logradouro, numero=req.numero,
            complemento=req.complemento, bairro=req.bairro, codigo_indicacao=req.codigo_indicacao,
            modo_teste=req.modo_teste,
            modulos={"emissor": ["emissor"], "financeiro": ["financeiro"], "ambos": ["emissor", "financeiro"]}[req.produto],
        )
    except CadastroEmailJaCadastradoError:
        raise HTTPException(status_code=409, detail="Já existe uma conta com este e-mail.")
    except PrestadorJaCadastradoError:
        raise HTTPException(status_code=409, detail="Já existe uma conta cadastrada com este CNPJ.")
    db.commit()
    return CadastroResponse(
        mensagem="Conta criada! Enviamos um link de confirmação pro seu e-mail — confira sua caixa de entrada.",
        email=usuario.email,
    )


@app.post("/api/cadastro/confirmar", response_model=UsuarioResponse, responses={400: {"model": ErroResponse}})
def api_confirmar_email(req: ConfirmarEmailRequest, request: Request, db: Session = Depends(get_db)):
    """Confirma o e-mail E já loga (mesma sessão) — evita o usuário ter que
    digitar a senha de novo logo depois de criar a conta."""
    try:
        usuario = confirmar_email(db, req.token)
    except TokenInvalidoOuExpiradoError:
        raise HTTPException(status_code=400, detail="Link de confirmação inválido ou expirado. Peça um novo.")
    contas.iniciar_sessao(db, request, usuario)
    db.commit()
    return UsuarioResponse(email=usuario.email, prestador_id=usuario.prestador_id, nome=usuario.nome)


@app.post("/api/cadastro/reenviar-confirmacao", dependencies=[Depends(limite("reenvio", 5, 3600))])
def api_reenviar_confirmacao(req: ReenviarConfirmacaoRequest, db: Session = Depends(get_db)):
    """Resposta sempre igual, exista o e-mail ou não (ver docstring de
    reenviar_confirmacao) — não dá pista pra quem está tentando adivinhar
    contas cadastradas."""
    reenviar_confirmacao(db, req.email)
    db.commit()
    return {"mensagem": "Se esse e-mail tiver um cadastro pendente de confirmação, reenviamos o link."}


@app.post("/api/auth/logout")
def api_logout(request: Request, db: Session = Depends(get_db)):
    usuario_id, sessao_id = request.session.get("usuario_id"), request.session.get("sessao_id")
    if usuario_id and sessao_id:
        try:
            contas.revogar_sessao(db, uuid.UUID(usuario_id), uuid.UUID(sessao_id))
            db.commit()
        except ValueError:
            pass
    request.session.clear()
    return {"ok": True}


@app.get("/api/auth/me", response_model=UsuarioResponse, responses={401: {"model": ErroResponse}})
def api_auth_me(request: Request, db: Session = Depends(get_db)):
    usuario_id = request.session.get("usuario_id")
    if usuario_id is None:
        raise HTTPException(status_code=401, detail="Não autenticado.")
    usuario = db.query(Usuario).filter_by(id=uuid.UUID(usuario_id), ativo=True).one_or_none()
    if usuario is None:
        raise HTTPException(status_code=401, detail="Sessão inválida.")
    if not contas.validar_sessao(db, request, usuario):
        request.session.clear()
        raise HTTPException(status_code=401, detail="Sessão encerrada neste aparelho.")
    ativa = contas.empresa_ativa(db, request, usuario)
    definir_prestador_atual(db, ativa)
    teste = bool(db.query(Prestador.modo_teste).filter(Prestador.id == ativa).scalar())
    return UsuarioResponse(
        email=usuario.email, prestador_id=ativa, demo=eh_email_demo(usuario.email), nome=usuario.nome, teste=teste,
        modulos=modulos_da_empresa(db, ativa),
    )


@app.put("/api/empresa/modulos")
def api_definir_modulos(req: ModulosRequest, db: Session = Depends(db_sessao), prestador_id: uuid.UUID = Depends(prestador_atual_id)):
    """Liga/desliga os produtos da empresa ativa (Empresa › Módulos). Desligar
    não apaga nada: os dados do módulo ficam guardados e voltam quando ele
    for ligado de novo. (Enquanto não há cobrança por módulo, quem liga é a
    própria pessoa.)"""
    prestador = db.get(Prestador, prestador_id)
    prestador.modulos = [m for m in MODULOS if m in req.modulos]
    resposta = {"modulos": list(prestador.modulos)}
    db.commit()
    return resposta


# --- Conta, sessões e empresas (29/09/2026, ver app/services/contas.py) ---


def _usuario_logado(request: Request, db: Session) -> Usuario:
    usuario_id = request.session.get("usuario_id")
    usuario = db.get(Usuario, uuid.UUID(usuario_id)) if usuario_id else None
    if usuario is None or not usuario.ativo or not contas.validar_sessao(db, request, usuario):
        request.session.clear()
        raise HTTPException(status_code=401, detail="Não autenticado — faça login.")
    return usuario


@app.post("/api/auth/codigo", dependencies=[Depends(limite("codigo", 5, 900))])
def api_pedir_codigo(req: SolicitarCodigoRequest, db: Session = Depends(get_db)):
    """Login sem senha: manda um código de 6 dígitos pro e-mail. Responde
    igual com ou sem conta (não revela quem é cliente)."""
    gerado = contas.gerar_codigo(db, req.email)
    if gerado is not None:
        usuario, codigo = gerado
        db.commit()
        s = get_settings()
        texto = (
            f"Seu código de acesso à Agente Ana: {codigo}\n\n"
            "Ele vale por 10 minutos. Se não foi você que pediu, ignore este e-mail."
        )
        html = (
            "<div style='font-family:Arial,sans-serif;font-size:15px;color:#1e293b'>"
            "<p>Seu código de acesso à Agente Ana:</p>"
            f"<p style='font-size:28px;font-weight:bold;letter-spacing:6px'>{codigo}</p>"
            "<p style='color:#64748b;font-size:13px'>Vale por 10 minutos. Se não foi você que pediu, ignore este e-mail.</p></div>"
        )
        try:
            get_email_sender().enviar(
                destinatario=usuario.email, assunto=f"{codigo} é o seu código da Agente Ana",
                corpo_texto=texto, corpo_html=html, responder_para=s.email_suporte,
            )
        except EmailEnvioError:
            logger.exception("Falha ao enviar código de login")
    return {"ok": True}


@app.post("/api/auth/codigo/entrar", response_model=UsuarioResponse, responses={401: {"model": ErroResponse}}, dependencies=[Depends(limite("codigo-entrar", 15, 900))])
def api_entrar_com_codigo(req: EntrarComCodigoRequest, request: Request, db: Session = Depends(get_db)):
    usuario = contas.entrar_com_codigo(db, req.email, req.codigo)
    if usuario is None:
        db.commit()  # guarda a tentativa errada
        raise HTTPException(status_code=401, detail="Código inválido ou vencido. Peça um novo.")
    contas.iniciar_sessao(db, request, usuario)
    db.commit()
    return UsuarioResponse(email=usuario.email, prestador_id=usuario.prestador_id, nome=usuario.nome)


@app.get("/api/conta", response_model=ContaResponse)
def api_conta(request: Request, db: Session = Depends(get_db)):
    u = _usuario_logado(request, db)
    return {
        "nome": u.nome, "email": u.email, "demo": eh_email_demo(u.email),
        "tem_senha": bool(u.senha_hash), "google_conectado": bool(u.google_sub),
    }


@app.patch("/api/conta", response_model=ContaResponse)
def api_atualizar_conta(req: ContaAtualizarRequest, request: Request, db: Session = Depends(get_db)):
    u = _usuario_logado(request, db)
    if req.nome is not None:
        u.nome = req.nome.strip()[:120] or None
    db.commit()
    return api_conta(request, db)


@app.get("/api/conta/sessoes", response_model=list[SessaoResponse])
def api_sessoes(request: Request, db: Session = Depends(get_db)):
    u = _usuario_logado(request, db)
    return contas.listar_sessoes(db, u.id, request.session.get("sessao_id"))


@app.delete("/api/conta/sessoes/{sessao_id}")
def api_desconectar_sessao(sessao_id: uuid.UUID, request: Request, db: Session = Depends(get_db)):
    u = _usuario_logado(request, db)
    if not contas.revogar_sessao(db, u.id, sessao_id):
        raise HTTPException(status_code=404, detail="Aparelho não encontrado.")
    db.commit()
    return {"ok": True}


@app.post("/api/conta/sessoes/sair-das-outras")
def api_sair_das_outras(request: Request, db: Session = Depends(get_db)):
    u = _usuario_logado(request, db)
    quantas = contas.revogar_outras(db, u.id, request.session.get("sessao_id"))
    db.commit()
    return {"desconectadas": quantas}


@app.delete("/api/conta", dependencies=[Depends(exigir_conta_real)])
def api_excluir_conta(req: ExcluirRequest, request: Request, db: Session = Depends(get_db)):
    """Apaga o login e as empresas em que ele é o único usuário. Confirmação:
    digitar EXCLUIR."""
    u = _usuario_logado(request, db)
    if req.confirmacao.strip().upper() != "EXCLUIR":
        raise HTTPException(status_code=422, detail="Digite EXCLUIR pra confirmar.")
    contas.apagar_conta(db, u)
    db.commit()
    request.session.clear()
    return {"ok": True}


@app.get("/api/empresas", response_model=list[EmpresaResponse])
def api_empresas(request: Request, db: Session = Depends(get_db)):
    u = _usuario_logado(request, db)
    ativa = contas.empresa_ativa(db, request, u)
    return [{**e, "ativa": e["id"] == ativa} for e in contas.listar_empresas(db, u)]


@app.post("/api/empresas", response_model=EmpresaResponse, responses={409: {"model": ErroResponse}}, dependencies=[Depends(exigir_conta_real)])
def api_adicionar_empresa(req: EmpresaCriarRequest, request: Request, db: Session = Depends(get_db)):
    """Mais um CNPJ no mesmo login — já entra ativo."""
    u = _usuario_logado(request, db)
    # A empresa nova começa com os mesmos módulos da que está aberta.
    ativa = contas.empresa_ativa(db, request, u)
    definir_prestador_atual(db, ativa)
    herdados = modulos_da_empresa(db, ativa)
    try:
        prestador = contas.adicionar_empresa(db, u, modulos=herdados, **req.model_dump())
    except contas.ContaError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.commit()
    request.session["prestador_id"] = str(prestador.id)
    return {"id": prestador.id, "razao_social": prestador.razao_social, "nome_fantasia": prestador.nome_fantasia, "cnpj": prestador.cpf_cnpj, "ativa": True}


@app.post("/api/empresas/{prestador_id}/ativar", response_model=EmpresaResponse)
def api_ativar_empresa(prestador_id: uuid.UUID, request: Request, db: Session = Depends(get_db)):
    u = _usuario_logado(request, db)
    if prestador_id != u.prestador_id and not contas.tem_acesso(db, u.id, prestador_id):
        raise HTTPException(status_code=404, detail="Empresa não encontrada.")
    request.session["prestador_id"] = str(prestador_id)
    u.prestador_id = prestador_id  # abre nela da próxima vez
    db.commit()
    definir_prestador_atual(db, prestador_id)
    p = db.get(Prestador, prestador_id)
    return {"id": p.id, "razao_social": p.razao_social, "nome_fantasia": p.nome_fantasia, "cnpj": p.cpf_cnpj, "ativa": True}


@app.delete("/api/empresa", dependencies=[Depends(exigir_conta_real)])
def api_excluir_empresa(
    req: ExcluirRequest, request: Request,
    db: Session = Depends(get_db), prestador_id: uuid.UUID = Depends(prestador_atual_id),
):
    """Apaga a empresa ativa e todo o histórico dela aqui. Confirmação: o
    CNPJ (só números). Se era a única empresa do login, a conta vai junto."""
    u = _usuario_logado(request, db)
    definir_prestador_atual(db, prestador_id)
    p = db.get(Prestador, prestador_id)
    if p is None or "".join(c for c in req.confirmacao if c.isdigit()) != p.cpf_cnpj:
        raise HTTPException(status_code=422, detail="Digite o CNPJ da empresa pra confirmar.")
    usuario_id = u.id
    contas.apagar_empresa(db, prestador_id)
    db.commit()
    restante = db.get(Usuario, usuario_id)
    if restante is None:
        request.session.clear()
        return {"ok": True, "conta_excluida": True}
    request.session["prestador_id"] = str(restante.prestador_id)
    return {"ok": True, "conta_excluida": False}


@app.patch("/api/prestador", response_model=PrestadorResponse)
def api_atualizar_emitente(
    req: EmitenteAtualizarRequest, db: Session = Depends(db_sessao), prestador_id: uuid.UUID = Depends(prestador_atual_id),
):
    """Dados do emitente (tela Empresa › Emitente)."""
    prestador = db.get(Prestador, prestador_id)
    if prestador is None:
        raise HTTPException(status_code=404, detail="Prestador não encontrado.")
    for campo, valor in req.model_dump(exclude_unset=True).items():
        if isinstance(valor, str):
            valor = valor.strip()
            if campo == "cep":
                valor = "".join(c for c in valor if c.isdigit())
        if campo == "razao_social" and not valor:
            continue
        setattr(prestador, campo, valor or None)
    db.commit()
    return prestador


@app.get("/api/indicacao", response_model=IndicacaoResponse)
def api_indicacao(db: Session = Depends(db_sessao), prestador_id: uuid.UUID = Depends(prestador_atual_id)):
    """Programa de indicação: link, indicados e desconto (10% por indicado
    ativo, até 100% — ver app/services/indicacao.py)."""
    dados = resumo_indicacao(db, prestador_id)
    db.commit()
    return dados


@app.get("/api/suporte", response_model=CanaisSuporteResponse)
def api_canais_suporte():
    s = get_settings()
    return {
        "email": s.email_suporte,
        "whatsapp": re.sub(r"\D", "", s.suporte_whatsapp) or None,
        "formulario": bool(s.resend_api_key),
    }


@app.post("/api/suporte", responses={400: {"model": ErroResponse}, 503: {"model": ErroResponse}}, dependencies=[Depends(limite("suporte", 5, 600))])
def api_mensagem_suporte(req: MensagemSuporteRequest, request: Request, db: Session = Depends(get_db)):
    """Manda a mensagem pro e-mail do suporte (que o Cloudflare encaminha
    pro Gmail), com "responder para" = quem escreveu."""
    if req.site:
        return {"ok": True}  # robô: finge que foi
    usuario = None
    usuario_id = request.session.get("usuario_id")
    if usuario_id:
        usuario = db.query(Usuario).filter_by(id=uuid.UUID(usuario_id), ativo=True).one_or_none()
    responder = usuario.email if usuario and not eh_email_demo(usuario.email) else (req.email or "").strip()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", responder or ""):
        raise HTTPException(status_code=400, detail="Informe um e-mail válido pra gente te responder.")
    s = get_settings()
    if not s.resend_api_key:
        raise HTTPException(status_code=503, detail=f"O formulário ainda não está ativo — escreva para {s.email_suporte}.")
    linhas = [
        f"De: {req.nome or '-'} <{responder}>",
        f"Conta: {usuario.email if usuario else 'não logado'}",
        f"Página: {req.pagina or '-'}",
        "",
        req.mensagem.strip(),
    ]
    texto = "\n".join(linhas)
    html = "<div style='font-family:Arial,sans-serif;font-size:14px'>" + "<br>".join(escape(l) for l in linhas) + "</div>"
    try:
        get_email_sender().enviar(
            destinatario=s.email_suporte,
            assunto=f"[Suporte] {req.assunto.strip()}",
            corpo_texto=texto,
            corpo_html=html,
            responder_para=responder,
        )
    except EmailEnvioError as exc:
        raise HTTPException(status_code=503, detail=f"Não deu pra enviar agora — escreva para {s.email_suporte}.") from exc
    return {"ok": True}


@app.post("/api/auth/trocar-senha", responses={400: {"model": ErroResponse}, 401: {"model": ErroResponse}}, dependencies=[Depends(exigir_conta_real)])
def api_trocar_senha(req: TrocarSenhaRequest, request: Request, db: Session = Depends(get_db)):
    """Marco 15 — tela de Configurações. Usa `get_db` puro (não `db_sessao`)
    porque `usuario` não tem RLS, mesmo motivo de `prestador_atual_id`
    acima."""
    usuario_id = request.session.get("usuario_id")
    if usuario_id is None:
        raise HTTPException(status_code=401, detail="Não autenticado.")
    try:
        trocar_senha(db, uuid.UUID(usuario_id), req.senha_atual, req.senha_nova)
    except SenhaAtualIncorretaError:
        raise HTTPException(status_code=400, detail="Senha atual incorreta.")
    # Senha nova derruba os outros aparelhos logados.
    contas.revogar_outras(db, uuid.UUID(usuario_id), request.session.get("sessao_id"))
    db.commit()
    return {"ok": True}


# --- Marco 15 (item 4): assinatura/cobrança (ver app/services/billing.py) ---


@app.get("/api/assinatura", response_model=AssinaturaResponse)
def api_ver_assinatura(prestador_id: uuid.UUID = Depends(prestador_atual_id), db: Session = Depends(get_db)):
    """`get_db` puro (não `db_sessao`): `assinatura` TEM RLS, mas
    `prestador_atual_id` já resolveu quem está logado sem precisar setar a
    variável de sessão só pra este SELECT — setamos abaixo, direto."""
    definir_prestador_atual(db, prestador_id)
    assinatura = db.query(Assinatura).filter_by(prestador_id=prestador_id).one_or_none()
    return AssinaturaResponse(
        status=assinatura.status if assinatura else "trial",
        ativa=assinatura_esta_ativa(assinatura),
        trial_termina_em=assinatura.trial_termina_em if assinatura else None,
        tem_assinatura_stripe=bool(assinatura and assinatura.stripe_subscription_id),
    )


@app.post("/api/assinatura/checkout", response_model=CheckoutSessaoResponse, responses={400: {"model": ErroResponse}}, dependencies=[Depends(exigir_conta_real)])
def api_criar_checkout(
    request: Request, prestador_id: uuid.UUID = Depends(prestador_atual_id), db: Session = Depends(get_db)
):
    definir_prestador_atual(db, prestador_id)
    usuario_id = request.session.get("usuario_id")
    if usuario_id is None:
        raise HTTPException(status_code=401, detail="Não autenticado.")
    usuario = db.get(Usuario, uuid.UUID(usuario_id))
    try:
        url = criar_sessao_checkout(db, prestador_id, usuario.email)
    except BillingNaoConfiguradoError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    db.commit()
    return CheckoutSessaoResponse(url=url)


@app.post("/api/assinatura/portal", response_model=CheckoutSessaoResponse, responses={400: {"model": ErroResponse}}, dependencies=[Depends(exigir_conta_real)])
def api_criar_portal(prestador_id: uuid.UUID = Depends(prestador_atual_id), db: Session = Depends(get_db)):
    definir_prestador_atual(db, prestador_id)
    try:
        url = criar_sessao_portal(db, prestador_id)
    except (BillingNaoConfiguradoError, AssinaturaNaoEncontradaError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return CheckoutSessaoResponse(url=url)


@app.post("/api/webhooks/stripe")
async def api_webhook_stripe(request: Request, db: Session = Depends(get_db)):
    """Rota pública (sem sessão) — quem autentica isto é a assinatura
    criptográfica no header `stripe-signature`, verificada dentro de
    `processar_webhook` (nunca confia no corpo sem essa checagem passar
    antes). Usa `get_db` puro porque não há prestador_id resolvido pela
    sessão aqui — `processar_webhook` descobre e SETA o prestador_id certo
    internamente (a partir do metadata que a própria Stripe devolve,
    gravado por nós no Checkout) antes de tocar em `assinatura`, que tem
    RLS — ver docstring de `_resolver_prestador_id_do_evento`."""
    payload = await request.body()
    assinatura_header = request.headers.get("stripe-signature", "")

    def _processar():
        tipo = processar_webhook(db, payload, assinatura_header)
        db.commit()
        return tipo

    # Banco + chamadas ao Stripe são bloqueantes: fora do event loop, senão
    # todo o resto do app espera junto.
    try:
        tipo = await run_in_threadpool(_processar)
    except WebhookInvalidoError:
        raise HTTPException(status_code=400, detail="Assinatura de webhook inválida.")
    except BillingNaoConfiguradoError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"recebido": True, "tipo": tipo}


@app.get("/api/vinculos", response_model=list[VinculoResumo])
def api_listar_vinculos(todos: bool = False, competencia: str | None = None, db: Session = Depends(db_sessao)):
    """Sem parâmetros: só os ativos (dropdowns de emissão/recebimento).
    `todos=true` (aba Tomadores, 28/09/2026): ativos e inativos, ordenados
    por dia de emissão com os inativos no fim, cada um com a nota da
    `competencia` (AAAA-MM, padrão = mês atual) se já foi gerada."""
    if competencia is not None and not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", competencia):
        raise HTTPException(status_code=422, detail="competencia deve estar no formato AAAA-MM")
    if todos:
        vinculos = ordenar_para_tela(listar_vinculos_da_tela(db))
        hoje = hoje_br()
        emissoes = emissoes_da_competencia(db, competencia or f"{hoje.year:04d}-{hoje.month:02d}")
    else:
        vinculos = listar_vinculos_ativos(db)
        emissoes = {}
    resposta = []
    for v in vinculos:
        emissao = emissoes.get(v.id)
        resposta.append(VinculoResumo(
            id=v.id, apelido=v.apelido, tomador_razao_social=v.tomador.razao_social,
            tomador_cnpj="" if v.tomador.status == "interno" else v.tomador.cnpj, serie=v.serie, template_descricao=v.template_descricao,
            requer_revisao=v.requer_revisao, ativo=v.ativo, tomador_id=v.tomador_id,
            cod_trib_nacional=v.cod_trib_nacional, cod_local_prestacao=v.cod_local_prestacao,
            dia_limite_emissao=v.dia_limite_emissao, dias_para_recebimento=v.dias_para_recebimento,
            emissao_id=emissao["id"] if emissao else None, emissao_estado=emissao["estado"] if emissao else None,
            emissao_valor=round(emissao["valor"], 2) if emissao else None,
            emissao_quantidade=emissao["quantidade"] if emissao else 0,
            metodo_captura_valor=v.metodo_captura_valor, sem_nota=v.sem_nota,
        ))
    return resposta


@app.delete("/api/vinculos/{vinculo_id}", response_model=ExclusaoVinculoResponse, responses={404: {"model": ErroResponse}})
def api_excluir_vinculo(vinculo_id: uuid.UUID, db: Session = Depends(db_sessao)):
    """"Excluir o tomador e aí sim ele suma" (28/09/2026) — sem notas, apaga
    de verdade; com notas, arquiva (as notas continuam íntegras)."""
    vinculo = buscar_vinculo(db, vinculo_id)
    if vinculo is None or vinculo.excluido_em is not None:
        raise HTTPException(status_code=404, detail="Tomador não encontrado.")
    apelido = vinculo.apelido
    resultado = excluir_vinculo(db, vinculo)
    db.commit()
    if resultado == "apagado":
        mensagem = f"{apelido} foi excluído."
    else:
        mensagem = f"{apelido} foi excluído da sua lista. As notas já emitidas pra ele continuam guardadas na aba NFS-e."
    return ExclusaoVinculoResponse(resultado=resultado, mensagem=mensagem)


def _validar_codigo_servico(codigo: str | None) -> str | None:
    """"Não criar códigos novos": só aceita código da lista oficial."""
    if codigo is None:
        return None
    servico = servico_por_codigo(codigo)
    if servico is None:
        raise HTTPException(
            status_code=422,
            detail=f"Código de serviço {codigo} não existe na lista nacional — escolha um na busca.",
        )
    return servico["codigo"]


@app.get("/api/servicos-nacionais", response_model=list[ServicoNacionalResponse])
def api_servicos_nacionais(q: str | None = None, limite: int = 400):
    """Lista oficial de códigos de tributação nacional (cTribNac), com busca
    por código ou palavra. Pública: é tabela do governo, não dado de conta."""
    if q:
        return buscar_servicos(q, limite=min(limite, 400))
    return listar_servicos()[: min(limite, 400)]


@app.get("/api/vinculos/{vinculo_id}", response_model=VinculoDetalheResponse, responses={404: {"model": ErroResponse}})
def api_ver_vinculo(vinculo_id: uuid.UUID, db: Session = Depends(db_sessao)):
    """Marco 13 — tela de detalhe do tomador ('Regras de emissão')."""
    vinculo = buscar_vinculo(db, vinculo_id)
    if vinculo is None:
        raise HTTPException(status_code=404, detail="Vínculo não encontrado (ou não pertence ao prestador ativo)")
    return vinculo


# --- Cadastro assistido de tomador (05/10/2026) ---


@app.get("/api/vinculos/{vinculo_id}/ultima-nota", dependencies=[_SO_EMISSOR])
def api_ultima_nota_do_vinculo(vinculo_id: uuid.UUID, db: Session = Depends(db_sessao)):
    """O que dá pra aproveitar da última nota deste tomador (emitida aqui ou
    importada) pra configurar a emissão: códigos e a descrição, com o que
    muda todo mês já trocado por campo automático."""
    if buscar_vinculo(db, vinculo_id) is None:
        raise HTTPException(status_code=404, detail="Tomador não encontrado.")
    return {"nota": assistente_tomador.ultima_nota_do_vinculo(db, vinculo_id)}


@app.post("/api/tomadores/ler-nota", dependencies=[_SO_EMISSOR], responses={422: {"model": ErroResponse}})
def api_ler_nota_antiga(
    arquivo: UploadFile = File(...), db: Session = Depends(db_sessao), prestador_id: uuid.UUID = Depends(prestador_atual_id),
):
    """Cadastro assistido: a pessoa manda uma nota que já emitiu pra este
    cliente (XML, ou o PDF — aí a Ana busca o XML na Receita pela chave de
    acesso impressa nele) e o cadastro vem preenchido."""
    conteudo = _ler_upload(arquivo, 5)
    if conteudo[:5] == b"%PDF-":
        chave = assistente_tomador.chave_no_pdf(conteudo)
        if not chave:
            raise HTTPException(status_code=422, detail="Não achei a chave de acesso nesse PDF. Se tiver o XML da nota, envie ele.")
        try:
            private_key, cert = carregar_certificado(db, prestador_id, get_settings().cert_master_key)
        except CertificadoNaoEncontradoError as exc:
            raise HTTPException(
                status_code=422,
                detail="Pra ler a nota pelo PDF eu preciso do seu certificado digital (Empresa › Certificado). Sem ele, envie o XML da nota.",
            ) from exc
        try:
            resposta = ClienteSefin(private_key, cert, "1", timeout=15).consultar_nfse(chave)
            conteudo = ClienteSefin.extrair_nfse_xml(resposta) if resposta.ok else None
        except Exception as exc:  # noqa: BLE001 — rede/Receita fora do ar
            raise HTTPException(status_code=422, detail="Não consegui buscar essa nota na Receita agora. Tente de novo ou envie o XML.") from exc
        if not conteudo:
            raise HTTPException(
                status_code=422,
                detail="A Receita não devolveu essa nota — ela precisa ter sido emitida pelo CNPJ desta empresa. Se tiver o XML, envie ele.",
            )
    try:
        return assistente_tomador.ler_xml(conteudo)
    except assistente_tomador.NotaIlegivelError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/servicos/codigos-usados", dependencies=[_SO_EMISSOR])
def api_codigos_usados(cod_trib_nacional: str | None = Query(default=None, max_length=10), db: Session = Depends(db_sessao)):
    """Códigos de tributação municipal e NBS que já saíram nas notas desta
    empresa (com a descrição da Receita) — pra escolher numa lista."""
    return assistente_tomador.codigos_usados(db, cod_trib_nacional or None)


@app.post("/api/vinculos", response_model=VinculoDetalheResponse, responses={404: {"model": ErroResponse}, 409: {"model": ErroResponse}})
def api_criar_vinculo(
    req: VinculoCriarRequest, request: Request,
    db: Session = Depends(db_sessao), prestador_id: uuid.UUID = Depends(prestador_atual_id),
):
    """Marco 13 — 'usar um tomador pré-cadastrado' ou 'cadastrar meu
    próprio tomador' (ver VinculoCriarRequest) chegam aqui pela mesma
    rota; a diferença é só qual dos dois campos veio preenchido.

    O catálogo de tomadores é compartilhado entre as contas, então um
    tomador novo (revisão de segurança, 28/09/2026):
    - de conta REAL: nome e endereço oficiais da Receita (BrasilAPI) ganham
      do que foi digitado, quando a consulta responde — ninguém consegue
      "plantar" dados falsos pra um CNPJ que outras contas vão usar;
    - de conta de SIMULAÇÃO: fica pendente (só pra ela, fora do catálogo) e
      some junto com a conta."""
    req.cod_trib_nacional = _validar_codigo_servico(req.cod_trib_nacional)
    if req.novo_tomador is not None:
        dados = req.novo_tomador.model_dump()
        if _sessao_demo(request, db):
            dados["status"] = "pendente"
        else:
            oficial = _dados_oficiais_cnpj(dados["cnpj"])
            if oficial is not None:
                dados.update(
                    razao_social=oficial.razao_social[:200] or dados["razao_social"],
                    cod_municipio=oficial.cod_municipio_sugerido or dados["cod_municipio"],
                    cep=oficial.cep or dados.get("cep"), logradouro=oficial.logradouro or dados.get("logradouro"),
                    numero=oficial.numero or dados.get("numero"), complemento=oficial.complemento or dados.get("complemento"),
                    bairro=oficial.bairro or dados.get("bairro"),
                )
        try:
            tomador = criar_tomador(db, **dados)
        except CnpjJaCadastradoError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        tomador_id = tomador.id
    else:
        tomador = buscar_tomador(db, req.tomador_id)
        if tomador is None:
            raise HTTPException(status_code=404, detail="Tomador não encontrado no catálogo.")
        tomador_id = tomador.id

    try:
        vinculo = criar_vinculo(
            db, prestador_id=prestador_id, tomador_id=tomador_id, apelido=req.apelido,
            cod_local_prestacao=req.cod_local_prestacao, cod_trib_nacional=req.cod_trib_nacional,
            cod_trib_municipal=req.cod_trib_municipal, template_descricao=req.template_descricao,
            metodo_captura_valor=req.metodo_captura_valor, serie=req.serie, requer_revisao=req.requer_revisao,
            dia_limite_emissao=req.dia_limite_emissao, dias_para_recebimento=req.dias_para_recebimento,
            email_contato=req.email_contato, whatsapp_contato=req.whatsapp_contato,
        )
    except ApelidoJaExisteError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    for campo in ("email_assunto", "email_mensagem", "email_anexos", "email_copia", "email_para"):
        setattr(vinculo, campo, (getattr(req, campo) or "").strip() or None)
    vinculo.cod_nbs = _validar_nbs(req.cod_nbs)
    vinculo.incluir_intermediario = bool(req.incluir_intermediario)
    vinculo.envio_canal = req.envio_canal
    vinculo.portal_url = (req.portal_url or "").strip() or None
    vinculo.sem_nota = bool(req.sem_nota)
    db.commit()
    return vinculo


@app.patch("/api/vinculos/{vinculo_id}", response_model=VinculoDetalheResponse, responses={404: {"model": ErroResponse}, 409: {"model": ErroResponse}})
def api_atualizar_vinculo(vinculo_id: uuid.UUID, req: VinculoAtualizarRequest, db: Session = Depends(db_sessao)):
    """Marco 13 — edita as 'regras de emissão' de um vínculo já existente
    (o padrão que fica valendo pras próximas notas — não reescreve notas
    já emitidas, que usam o snapshot congelado no rascunho)."""
    vinculo = buscar_vinculo(db, vinculo_id)
    if vinculo is None:
        raise HTTPException(status_code=404, detail="Vínculo não encontrado (ou não pertence ao prestador ativo)")
    campos = req.model_dump(exclude_unset=True)
    for campo in ("email_assunto", "email_mensagem", "email_anexos", "email_copia", "email_para"):
        if campo in campos:
            campos[campo] = (campos[campo] or "").strip() or None
    if "cod_nbs" in campos:
        campos["cod_nbs"] = _validar_nbs(campos["cod_nbs"])
    if campos.get("incluir_intermediario") is None:
        campos.pop("incluir_intermediario", None)
    if campos.get("sem_nota") is None:
        campos.pop("sem_nota", None)
    if "portal_url" in campos:
        campos["portal_url"] = (campos["portal_url"] or "").strip() or None
    if campos.get("cod_trib_nacional") is not None and campos["cod_trib_nacional"] != vinculo.cod_trib_nacional:
        campos["cod_trib_nacional"] = _validar_codigo_servico(campos["cod_trib_nacional"])
    try:
        vinculo = atualizar_vinculo(db, vinculo, **campos)
    except ApelidoJaExisteError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.commit()
    return vinculo


@app.get("/api/tomadores", response_model=list[TomadorResponse])
def api_listar_tomadores(
    request: Request,
    apenas_meus: bool = False,
    db: Session = Depends(db_sessao),
    prestador_id: uuid.UUID = Depends(prestador_atual_id),
):
    """Marco 13 — catálogo pra tela de Tomadores: 'Meus tomadores'
    (apenas_meus=true, só quem já tem vínculo ativo) ou 'Todos os
    tomadores' (catálogo compartilhado inteiro)."""
    tomadores = listar_catalogo(db, prestador_id=prestador_id, apenas_meus=apenas_meus)
    if _sessao_demo(request, db):
        # Simulação é anônima: vê o catálogo, mas não as sugestões (modelo de
        # descrição, código, prazos) que vêm do uso das contas reais.
        return [
            TomadorResponse.model_validate(t).model_copy(update={
                "sug_cod_trib_nacional": None, "sug_template_descricao": None,
                "sug_dia_emissao": None, "sug_dias_recebimento": None,
            })
            for t in tomadores
        ]
    return tomadores


@app.get("/api/calendario", response_model=CalendarioResponse, responses={422: {"model": ErroResponse}})
def api_calendario(
    inicio: str,
    fim: str,
    db: Session = Depends(db_sessao),
    prestador_id: uuid.UUID = Depends(prestador_atual_id),
):
    """Marco 13 — eventos de prazo/previsão de recebimento pro calendário
    (ver app/services/calendario.py). `inicio`/`fim` em AAAA-MM-DD,
    inclusivos. GET puro, sem efeito colateral."""
    try:
        data_inicio = datetime.date.fromisoformat(inicio)
        data_fim = datetime.date.fromisoformat(fim)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="inicio/fim devem estar no formato AAAA-MM-DD") from exc
    if data_fim < data_inicio:
        raise HTTPException(status_code=422, detail="fim não pode ser anterior a inicio")
    if (data_fim - data_inicio).days > 400 or not (2000 <= data_inicio.year <= 2100):
        raise HTTPException(status_code=422, detail="intervalo muito grande (máximo de 13 meses)")
    eventos = eventos_calendario(db, prestador_id, data_inicio, data_fim)
    return {"inicio": data_inicio, "fim": data_fim, "eventos": eventos}


def _vinculo_do_evento(db: Session, vinculo_id: uuid.UUID | None):
    """Fornecedor opcional de um evento manual — RLS garante que só acha
    vínculo do próprio prestador."""
    if vinculo_id is None:
        return None
    vinculo = buscar_vinculo(db, vinculo_id)
    if vinculo is None:
        raise HTTPException(status_code=404, detail="Fornecedor não encontrado.")
    return vinculo


@app.post("/api/calendario/eventos", response_model=EventoCalendarioResponse)
def api_criar_evento_manual(
    req: EventoManualCriarRequest,
    db: Session = Depends(db_sessao),
    prestador_id: uuid.UUID = Depends(prestador_atual_id),
):
    """Eventos criados à mão pelo usuário (Marco 15) — desde o Marco 17 com
    categoria: lembrete, previsão de recebimento (valor/fornecedor) ou
    prazo, diferente dos tipos calculados que /api/calendario também
    devolve (ver app/services/calendario.py)."""
    _vinculo_do_evento(db, req.vinculo_id)
    evento = criar_evento_manual(
        db, prestador_id, data=req.data, titulo=req.titulo, descricao=req.descricao,
        categoria=req.categoria, valor=req.valor, prestador_tomador_id=req.vinculo_id,
    )
    # monta a resposta ANTES do commit: ela consulta o vínculo, e depois do
    # commit a variável de RLS (SET LOCAL) já não existe mais.
    resposta = evento_manual_para_dict(db, evento)
    db.commit()
    return resposta


@app.patch("/api/calendario/eventos/{evento_id}", response_model=EventoCalendarioResponse, responses={404: {"model": ErroResponse}})
def api_atualizar_evento_manual(
    evento_id: uuid.UUID, req: EventoManualAtualizarRequest, db: Session = Depends(db_sessao),
):
    evento = buscar_evento_manual(db, evento_id)
    if evento is None:
        raise HTTPException(status_code=404, detail="Evento não encontrado (ou não pertence ao prestador ativo).")
    campos = req.model_dump(exclude_unset=True)
    if "vinculo_id" in campos:
        _vinculo_do_evento(db, campos["vinculo_id"])
        campos["prestador_tomador_id"] = campos.pop("vinculo_id")
    evento = atualizar_evento_manual(db, evento, **campos)
    resposta = evento_manual_para_dict(db, evento)  # antes do commit (RLS)
    db.commit()
    return resposta


@app.put("/api/calendario/ajustes", responses={422: {"model": ErroResponse}})
def api_ajustar_ocorrencia(
    req: AjusteOcorrenciaRequest,
    db: Session = Depends(db_sessao),
    prestador_id: uuid.UUID = Depends(prestador_atual_id),
):
    """Marco 17 — move ou oculta SÓ esta ocorrência de um alerta calculado
    (a regra dos outros meses continua igual)."""
    try:
        ajustar_ocorrencia(db, prestador_id, tipo=req.tipo, chave=req.chave, nova_data=req.nova_data, oculto=req.oculto)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.commit()
    return {"ok": True}


@app.delete("/api/calendario/ajustes")
def api_remover_ajuste(tipo: str, chave: str, db: Session = Depends(db_sessao)):
    """Volta a ocorrência pra data calculada pela regra."""
    removido = remover_ajuste(db, tipo=tipo, chave=chave)
    db.commit()
    return {"ok": True, "removido": removido}


@app.delete("/api/calendario/eventos/{evento_id}", responses={404: {"model": ErroResponse}})
def api_excluir_evento_manual(evento_id: uuid.UUID, db: Session = Depends(db_sessao)):
    evento = buscar_evento_manual(db, evento_id)
    if evento is None:
        raise HTTPException(status_code=404, detail="Evento não encontrado (ou não pertence ao prestador ativo).")
    excluir_evento_manual(db, evento)
    db.commit()
    return {"ok": True}


@app.get("/api/prestador", response_model=PrestadorResponse)
def api_ver_prestador(db: Session = Depends(db_sessao), prestador_id: uuid.UUID = Depends(prestador_atual_id)):
    """Marco 14 — tela 'Configurações': dados básicos do prestador, somente
    leitura (edição é administrativa por enquanto, ver DEPLOY.md). `prestador`
    tem RLS própria (isolada por `id`, ver migração 5af6e092d5e1), então
    `db_sessao` já garante que só o prestador logado é visível."""
    prestador = db.query(Prestador).filter_by(id=prestador_id).one_or_none()
    if prestador is None:
        raise HTTPException(status_code=404, detail="Prestador não encontrado.")
    return prestador


@app.patch("/api/prestador/preferencias", response_model=PrestadorResponse, responses={404: {"model": ErroResponse}})
def api_preferencias_prestador(
    req: PreferenciasPrestadorRequest, db: Session = Depends(db_sessao), prestador_id: uuid.UUID = Depends(prestador_atual_id),
):
    """Ambiente das notas novas e modelo padrão do e-mail da nota (28/09/2026)."""
    prestador = db.query(Prestador).filter_by(id=prestador_id).one_or_none()
    if prestador is None:
        raise HTTPException(status_code=404, detail="Prestador não encontrado.")
    for campo, valor in req.model_dump(exclude_unset=True).items():
        if campo == "tp_amb_padrao":
            if valor and not prestador.modo_teste:
                prestador.tp_amb_padrao = valor
        else:
            setattr(prestador, campo, (valor or "").strip() or None)
    db.commit()
    return prestador


@app.get("/api/email-modelo", response_model=ModeloEmailPadraoResponse, dependencies=[_SO_EMISSOR])
def api_modelo_email_padrao():
    """Texto de sempre do e-mail da nota e os códigos que dá pra usar."""
    return {
        "assunto": mensagens.ASSUNTO_PADRAO,
        "mensagem": mensagens.MENSAGEM_PADRAO,
        "codigos": [{"codigo": c, "descricao": d, "exemplo": e} for c, d, e in mensagens.CODIGOS_MODELO],
    }


@app.patch("/api/prestador/aliquota", response_model=PrestadorResponse, responses={404: {"model": ErroResponse}})
def api_atualizar_aliquota(
    req: AliquotaAtualizarRequest, db: Session = Depends(db_sessao), prestador_id: uuid.UUID = Depends(prestador_atual_id)
):
    """Marco 16, item 5 — a única edição própria de Prestador (o resto
    continua administrativo, ver docstring de PrestadorResponse). Grava
    `aliquota_atualizada_em = hoje` junto, pra dashboard/calendário saberem
    que ela já foi revisada neste mês (ver app/services/dashboard.py e
    app/services/calendario.py) — mesmo que o VALOR não tenha mudado: o
    ponto é a CONFIRMAÇÃO mensal, não só a mudança de número."""
    prestador = db.query(Prestador).filter_by(id=prestador_id).one_or_none()
    if prestador is None:
        raise HTTPException(status_code=404, detail="Prestador não encontrado.")
    prestador.aliquota_atual = Decimal(str(req.aliquota))
    prestador.aliquota_atualizada_em = hoje_br()
    db.commit()
    # SEM db.refresh() de propósito: a sessão usa expire_on_commit=False
    # (ver app/database.py) — `prestador` já tem os valores que acabou de
    # setar. Um refresh forçaria um SELECT numa transação NOVA, onde a
    # variável de sessão da RLS (SET LOCAL, só vale durante a transação do
    # commit) já não existe mais — foi exatamente isso que quebrou aqui
    # (RLS rejeitando com "invalid input syntax for type uuid: ''"),
    # mesmo padrão que api_atualizar_vinculo já evita.
    return prestador


@app.patch("/api/prestador/lembrete-aliquota", response_model=PrestadorResponse, responses={404: {"model": ErroResponse}})
def api_atualizar_lembrete_aliquota(
    req: LembreteAliquotaRequest, db: Session = Depends(db_sessao), prestador_id: uuid.UUID = Depends(prestador_atual_id)
):
    """Marco 17 — regra do lembrete mensal de alíquota no calendário (dia do
    mês). Mesmo cuidado de api_atualizar_aliquota: sem db.refresh() depois
    do commit (RLS)."""
    prestador = db.query(Prestador).filter_by(id=prestador_id).one_or_none()
    if prestador is None:
        raise HTTPException(status_code=404, detail="Prestador não encontrado.")
    prestador.dia_lembrete_aliquota = req.dia
    db.commit()
    return prestador


@app.get("/api/certificado/status", response_model=CertificadoStatus, dependencies=[_SO_EMISSOR])
def api_status_certificado(db: Session = Depends(db_sessao), prestador_id: uuid.UUID = Depends(prestador_atual_id)):
    registro = db.query(Certificado).filter_by(prestador_id=prestador_id).one_or_none()
    if registro is None:
        return CertificadoStatus(carregado=False)
    return CertificadoStatus(carregado=True, validade=registro.validade, vencido=certificado_vencido(registro))


@app.post("/api/certificado", response_model=CertificadoStatus, dependencies=[_SO_EMISSOR, Depends(exigir_conta_real)])
def api_salvar_certificado(
    pfx: UploadFile = File(...), senha: str = Form(...),
    db: Session = Depends(db_sessao), prestador_id: uuid.UUID = Depends(prestador_atual_id),
):
    settings = get_settings()
    pfx_bytes = _ler_upload(pfx, 2)
    try:
        registro = salvar_certificado(db, prestador_id, pfx_bytes, senha, settings.cert_master_key)
    except Exception as exc:
        logger.warning("Certificado recusado: %s", type(exc).__name__)
        raise HTTPException(
            status_code=400,
            detail="Não foi possível abrir o certificado — confira se o arquivo é o .pfx/.p12 do A1 e se a senha está certa.",
        ) from exc
    db.commit()
    return CertificadoStatus(carregado=True, validade=registro.validade, vencido=certificado_vencido(registro))


def _para_resposta(emissao: Emissao) -> EmissaoResponse:
    snap = emissao.tomador_snapshot or {}
    return EmissaoResponse(
        id=emissao.id, estado=emissao.estado, n_dps=emissao.n_dps, serie=emissao.serie,
        competencia=emissao.competencia, valor=float(emissao.valor),
        apelido=snap.get("apelido", ""), tomador=snap.get("razao_social", ""),
        descricao=snap.get("descricao_renderizada", ""),
        xml=emissao.xml_assinado or emissao.xml_dps,
        chave_acesso=emissao.chave_acesso, erro_detalhe=motivo_da_recusa(emissao.erro_detalhe),
        erro_corrigivel=emissao.estado == "erro" and recusa_corrigivel(emissao.erro_detalhe),
        atualizado_em=emissao.atualizado_em, origem=emissao.origem or "ana", vinculo_id=emissao.prestador_tomador_id,
        avulsa=bool(emissao.tomador_documento),
    )


@app.get("/api/dps/verificar-duplicata", response_model=VerificarDuplicataResponse, dependencies=[_SO_EMISSOR])
def api_verificar_duplicata(vinculo_id: uuid.UUID, competencia: str, db: Session = Depends(db_sessao)):
    """Marco 16 — a tela de 'Nova emissão' chama isso assim que
    fornecedor+competência ficam preenchidos, pra avisar de uma possível
    duplicata ANTES do usuário tentar gerar a nota (não substitui a checagem
    de `POST /api/dps`, que continua sendo a fonte de verdade — isto aqui é
    só pra UX, GET puro sem efeito colateral)."""
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", competencia):
        raise HTTPException(status_code=422, detail="competencia deve estar no formato AAAA-MM")
    existente = buscar_emissao_ativa(db, vinculo_id, competencia)
    if existente is None:
        return VerificarDuplicataResponse(existe=False)
    return VerificarDuplicataResponse(
        existe=True, emissao_id=existente.id, estado=existente.estado, valor=float(existente.valor),
        pode_substituir=existente.estado in ESTADOS_SUBSTITUIVEIS,
    )


# Nota que ainda não foi pra prefeitura: pode ser apagada ou trocada por outra.
ESTADOS_SUBSTITUIVEIS = ("rascunho", "montado", "assinado", "erro")


def _tp_amb_da_conta(db: Session, prestador_id: uuid.UUID) -> str:
    prestador = db.get(Prestador, prestador_id)
    if prestador is not None and prestador.modo_teste:
        return "2"  # conta de teste: sempre homologação
    return (prestador.tp_amb_padrao if prestador else None) or "1"


def _tp_amb_da_nota(db: Session, prestador_id: uuid.UUID, pedido: str | None) -> str:
    """Conta de teste é sempre homologação, mesmo se pedirem produção."""
    prestador = db.get(Prestador, prestador_id)
    if prestador is not None and prestador.modo_teste:
        return "2"
    return pedido or _tp_amb_da_conta(db, prestador_id)


@app.post("/api/dps", response_model=EmissaoResponse, responses={404: {"model": ErroResponse}, 409: {"model": ErroResponse}, 422: {"model": ErroResponse}}, dependencies=[_SO_EMISSOR])
def api_criar_dps(req: GerarDpsRequest, db: Session = Depends(db_sessao)):
    """Cria e monta (rascunho -> montado) — persiste de verdade, com nDPS
    atribuído automaticamente. Essa é a 'caixa de revisão' antes de assinar."""
    vinculo = buscar_vinculo(db, req.vinculo_id)
    if vinculo is None:
        raise HTTPException(status_code=404, detail="Vínculo não encontrado (ou não pertence ao prestador ativo)")
    if vinculo.sem_nota:
        raise HTTPException(status_code=422, detail=f"{vinculo.apelido} está como 'só controle de recebimento' — a Ana não gera nota pra ele. Mude em Tomadores › editar.")

    competencia = req.competencia
    if req.data_competencia is not None:
        competencia = f"{req.data_competencia.year:04d}-{req.data_competencia.month:02d}"
    # De onde veio o pedido da nota, quando veio de outro módulo (texto
    # opaco pro emissor — ex.: "fin:pagamento:<id>", ver app/eventos.py).
    origem = req.origem or (f"fin:pagamento:{req.pagamento_id}" if req.pagamento_id else None)

    depois_da_troca: list = []
    # Tudo num ponto de retorno: se o outro módulo recusar o pedido (origem
    # que ele não reconhece), nada do que foi feito aqui fica.
    ponto = db.begin_nested()
    existente = buscar_emissao_ativa(db, vinculo.id, competencia)
    if existente is not None:
        mes = f"{competencia[5:7]}/{competencia[:4]}"
        valor_br = f"R$ {float(existente.valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        if existente.estado not in ESTADOS_SUBSTITUIVEIS:
            raise HTTPException(status_code=409, detail=(
                f"{vinculo.apelido} já tem uma nota emitida em {mes} ({valor_br}). Pra gerar outra, escolha uma data de "
                "competência de outro mês — ou cancele a nota existente."
            ))
        if not req.substituir:
            raise HTTPException(status_code=409, detail=(
                f"{vinculo.apelido} já tem uma nota de {mes} que ainda não foi enviada ({valor_br}). "
                "Abra essa nota pra continuar, ou gere esta no lugar dela."
            ))
        # Troca: a nota que não saiu é apagada; o que outros módulos tinham
        # ligado a ela passa pra nova.
        depois_da_troca = integracao.coletar("antes_de_trocar_nota", db, emissao=existente)
        db.query(Envio).filter(Envio.emissao_id == existente.id).delete(synchronize_session=False)
        db.delete(existente)
        db.flush()
    try:
        emissao = criar_rascunho(
            db, vinculo, competencia=competencia, valor=req.valor,
            ordem=req.ordem, aliq_sn=req.aliq_sn, tpAmb=_tp_amb_da_nota(db, vinculo.prestador_id, req.tpAmb),
            dcompet=req.data_competencia.isoformat() if req.data_competencia else None,
        )
        emissao = montar_emissao(db, emissao)
    except EmissaoJaExisteError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except DescricaoIncompletaError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    try:
        for passar_pra_nova in depois_da_troca:
            passar_pra_nova(emissao)
        integracao.publicar("nota_criada", db, emissao=emissao, origem=origem)
    except integracao.RecusaDeIntegracao as exc:
        ponto.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    ponto.commit()
    db.flush()
    resposta = _para_resposta(emissao)  # antes do commit (RLS vale só na transação)
    db.commit()
    return resposta


@app.post("/api/dps/{emissao_id}/origem", response_model=EmissaoResponse, responses={404: {"model": ErroResponse}, 422: {"model": ErroResponse}}, dependencies=[_SO_EMISSOR])
def api_ligar_origem(emissao_id: uuid.UUID, req: OrigemNotaRequest, db: Session = Depends(db_sessao)):
    """A nota que JÁ existe atende um pedido que veio de outro módulo (ex.: o
    financeiro pediu a nota de um recebimento e ela já estava gerada) — o
    emissor só avisa, como se a nota tivesse acabado de ser criada."""
    emissao = _emissao_ou_404(db, emissao_id)
    try:
        integracao.publicar("nota_criada", db, emissao=emissao, origem=req.origem)
    except integracao.RecusaDeIntegracao as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.flush()
    resposta = _para_resposta(emissao)
    db.commit()
    return resposta


@app.get("/api/dps", response_model=list[EmissaoListaLinha], dependencies=[_SO_EMISSOR])
def api_listar_dps(
    ano: str | None = None,
    vinculo_id: uuid.UUID | None = None,
    estado: str | None = None,
    grupo: str | None = Query(default=None, pattern=r"^(notas|vendedores)$"),
    db: Session = Depends(db_sessao),
):
    """Marco 14 — tela 'NFS-e': lista completa (todas as competências),
    diferente de /api/painel/resumo-mes (só o mês corrente, pro dashboard).
    Todos os filtros são opcionais. GET puro, sem efeito colateral."""
    if ano is not None and (len(ano) != 4 or not ano.isdigit()):
        raise HTTPException(status_code=422, detail="ano deve estar no formato AAAA")
    return listar_emissoes(db, ano=ano, vinculo_id=vinculo_id, estado=estado, grupo=grupo)


@app.post("/api/dps/importar-csv", response_model=ImportacaoCsvResponse, responses={400: {"model": ErroResponse}}, dependencies=[_SO_EMISSOR])
def api_importar_csv(arquivo: UploadFile = File(...), db: Session = Depends(db_sessao)):
    """Marco 7 — gera várias emissões de uma vez a partir de um CSV
    (colunas: apelido, competencia, valor[, ordem][, aliq_sn]). Cada linha
    roda isolada (savepoint) — uma linha ruim vira erro naquela linha, sem
    derrubar as demais. Só dá commit se pelo menos uma linha deu certo."""
    bruto = _ler_upload(arquivo, 5)
    try:
        conteudo = bruto.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            conteudo = bruto.decode("latin-1")  # Excel pt-BR às vezes salva assim
        except UnicodeDecodeError as exc:
            raise HTTPException(status_code=400, detail="Não foi possível ler o arquivo como texto (utf-8/latin-1).") from exc

    try:
        resultados = importar_csv(db, conteudo=conteudo)
    except CsvInvalidoError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    sucesso = sum(1 for r in resultados if r.ok)
    if sucesso:
        db.commit()
    return ImportacaoCsvResponse(
        total=len(resultados), sucesso=sucesso, erro=len(resultados) - sucesso,
        linhas=[
            {"linha": r.linha, "apelido": r.apelido, "ok": r.ok, "mensagem": r.mensagem, "emissao_id": r.emissao_id, "n_dps": r.n_dps}
            for r in resultados
        ],
    )


# --- Ações em lote (29/09/2026, ver app/services/lotes.py) ---


def _ids_do_lote(db: Session, req: CriarLoteRequest) -> list[uuid.UUID]:
    if req.emissao_ids is None and req.vinculo_id is None and req.competencia is None:
        raise HTTPException(status_code=422, detail="Selecione notas ou um filtro (tomador/competência).")
    try:
        return lotes.selecionar(
            db, req.acao, emissao_ids=req.emissao_ids, vinculo_id=req.vinculo_id,
            competencia=req.competencia, reenviar=req.reenviar,
        )
    except lotes.LoteInvalidoError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/lotes/previa", response_model=PreviaLoteResponse, dependencies=[_SO_EMISSOR])
def api_previa_lote(req: CriarLoteRequest, db: Session = Depends(db_sessao)):
    """Quantas notas a ação vai pegar (pra tela confirmar antes)."""
    return {"acao": req.acao, "quantidade": len(_ids_do_lote(db, req))}


@app.post("/api/lotes", response_model=LoteResponse, responses={422: {"model": ErroResponse}}, dependencies=[_SO_EMISSOR, Depends(exigir_conta_real)])
def api_criar_lote(
    req: CriarLoteRequest, request: Request,
    db: Session = Depends(db_sessao), prestador_id: uuid.UUID = Depends(prestador_atual_id),
):
    ids = _ids_do_lote(db, req)
    if not ids:
        raise HTTPException(status_code=422, detail="Nenhuma nota selecionada está pronta pra essa ação.")
    try:
        lote = lotes.criar_lote(db, prestador_id, req.acao, ids)
    except lotes.LoteInvalidoError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.commit()
    lotes.iniciar(lote.id, prestador_id, base_url(str(request.base_url)))
    return lotes.resumo(lote)


@app.get("/api/lotes", response_model=list[LoteResponse], dependencies=[_SO_EMISSOR])
def api_listar_lotes(db: Session = Depends(db_sessao)):
    recentes = db.query(LoteAcao).order_by(LoteAcao.criado_em.desc()).limit(10).all()
    for lote in recentes:
        lotes.atualizar_parado(db, lote)
    db.commit()
    return [lotes.resumo(l) for l in recentes]


def _lote_ou_404(db: Session, lote_id: uuid.UUID) -> LoteAcao:
    lote = db.get(LoteAcao, lote_id)
    if lote is None:
        raise HTTPException(status_code=404, detail="Lote não encontrado.")
    return lote


@app.get("/api/lotes/{lote_id}", response_model=LoteResponse, dependencies=[_SO_EMISSOR])
def api_ver_lote(lote_id: uuid.UUID, db: Session = Depends(db_sessao)):
    lote = lotes.atualizar_parado(db, _lote_ou_404(db, lote_id))
    db.commit()
    return lotes.resumo(lote)


@app.post("/api/lotes/{lote_id}/cancelar", response_model=LoteResponse, dependencies=[_SO_EMISSOR])
def api_cancelar_lote(lote_id: uuid.UUID, db: Session = Depends(db_sessao)):
    lote = _lote_ou_404(db, lote_id)
    if lote.status in ("fila", "executando", "interrompido"):
        lote.status = "cancelado"
        db.commit()
    return lotes.resumo(lote)


@app.post("/api/lotes/{lote_id}/retomar", response_model=LoteResponse, dependencies=[_SO_EMISSOR, Depends(exigir_conta_real)])
def api_retomar_lote(
    lote_id: uuid.UUID, request: Request,
    db: Session = Depends(db_sessao), prestador_id: uuid.UUID = Depends(prestador_atual_id),
):
    lote = lotes.atualizar_parado(db, _lote_ou_404(db, lote_id))
    if lote.status != "interrompido":
        raise HTTPException(status_code=409, detail="Só dá pra retomar um lote interrompido.")
    lote.status = "fila"
    db.commit()
    lotes.iniciar(lote.id, prestador_id, base_url(str(request.base_url)))
    return lotes.resumo(lote)


@app.post("/api/lotes/{lote_id}/refazer-falhas", response_model=LoteResponse, dependencies=[_SO_EMISSOR, Depends(exigir_conta_real)])
def api_refazer_falhas(
    lote_id: uuid.UUID, request: Request,
    db: Session = Depends(db_sessao), prestador_id: uuid.UUID = Depends(prestador_atual_id),
):
    """Novo lote só com as notas que falharam."""
    lote = _lote_ou_404(db, lote_id)
    ids = [uuid.UUID(e["emissao_id"]) for e in lote.erros]
    ids = lotes.selecionar(db, lote.acao, emissao_ids=ids, reenviar=False)
    try:
        novo = lotes.criar_lote(db, prestador_id, lote.acao, ids)
    except lotes.LoteInvalidoError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.commit()
    lotes.iniciar(novo.id, prestador_id, base_url(str(request.base_url)))
    return lotes.resumo(novo)


@app.get("/api/envios/resumo", response_model=ResumoEnviosResponse, dependencies=[_SO_EMISSOR])
def api_resumo_envios(
    ano: str | None = Query(default=None, pattern=r"^\d{4}$"), vinculo_id: uuid.UUID | None = None,
    competencia: str | None = Query(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$"), db: Session = Depends(db_sessao),
):
    """E-mails/WhatsApp entregues x falhas (último status de cada nota), como
    o "757 entregues · 35 falhas" do MandaNotas."""
    query = db.query(Emissao.id).filter(Emissao.estado != "cancelada")
    if ano:
        query = query.filter(Emissao.competencia.like(f"{ano}-%"))
    if competencia:
        query = query.filter(Emissao.competencia == competencia)
    if vinculo_id:
        query = query.filter(Emissao.prestador_tomador_id == vinculo_id)
    ids = [i for (i,) in query]
    ultimo: dict[uuid.UUID, str] = {}
    if ids:
        for emissao_id, status in (
            db.query(Envio.emissao_id, Envio.status)
            .filter(Envio.emissao_id.in_(ids), Envio.canal.in_(("email", "whatsapp", "direto_fornecedor")))
            .order_by(Envio.criado_em)
        ):
            if ultimo.get(emissao_id) != "enviado":
                ultimo[emissao_id] = status
    enviados = sum(1 for v in ultimo.values() if v == "enviado")
    falhas = sum(1 for v in ultimo.values() if v == "falha")
    return {"enviados": enviados, "falhas": falhas, "notas_sem_envio": len(ids) - enviados - falhas}


@app.get("/api/dps/zip", responses={404: {"model": ErroResponse}}, dependencies=[_SO_EMISSOR])
def api_zip_notas(
    ids: str | None = None, competencia: str | None = None, vinculo_id: uuid.UUID | None = None,
    db: Session = Depends(db_sessao),
):
    """XMLs (e os PDFs oficiais já baixados) de várias notas num .zip — a
    seleção da tela (`ids` separados por vírgula) ou um mês inteiro."""
    query = db.query(Emissao).filter(Emissao.estado != "cancelada")
    if ids:
        try:
            lista = [uuid.UUID(i) for i in ids.split(",") if i.strip()][:3000]
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="ids inválidos") from exc
        query = query.filter(Emissao.id.in_(lista))
    elif competencia:
        if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", competencia):
            raise HTTPException(status_code=422, detail="competencia deve estar no formato AAAA-MM")
        query = query.filter(Emissao.competencia == competencia)
        if vinculo_id:
            query = query.filter(Emissao.prestador_tomador_id == vinculo_id)
    else:
        raise HTTPException(status_code=422, detail="Informe as notas ou a competência.")
    buffer = io.BytesIO()
    quantos = 0
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for emissao in query.order_by(Emissao.n_dps).limit(3000):
            try:
                nome, conteudo = melhor_xml_disponivel(emissao)
            except EmissaoSemConteudoError:
                continue
            zf.writestr(f"xml/{nome}", conteudo)
            if emissao.estado == "confirmado" and emissao.danfse_pdf:
                zf.writestr(f"pdf/{nome_pdf(emissao)}", emissao.danfse_pdf)
            quantos += 1
    if not quantos:
        raise HTTPException(status_code=404, detail="Nenhuma nota com XML nessa seleção.")
    nome_zip = f"notas_{competencia or 'selecao'}.zip"
    return Response(content=buffer.getvalue(), media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="{nome_zip}"'})


@app.delete("/api/dps/{emissao_id}", responses={404: {"model": ErroResponse}, 409: {"model": ErroResponse}}, dependencies=[_SO_EMISSOR])
def api_apagar_dps(emissao_id: uuid.UUID, db: Session = Depends(db_sessao)):
    """Apaga uma nota que nunca virou NFS-e (rascunho, montada, assinada ou
    recusada) — ex.: as notas de teste. Autorizada/enviada não: essa se
    cancela."""
    emissao = _emissao_ou_404(db, emissao_id)
    if emissao.estado not in ("rascunho", "montado", "assinado", "erro"):
        raise HTTPException(status_code=409, detail="Só dá pra apagar nota que não foi autorizada pela prefeitura. Essa precisa ser cancelada.")
    db.query(Envio).filter(Envio.emissao_id == emissao.id).delete(synchronize_session=False)
    db.delete(emissao)
    db.commit()
    return {"ok": True}


@app.patch("/api/dps/{emissao_id}/tomador", response_model=EmissaoResponse, responses={404: {"model": ErroResponse}, 409: {"model": ErroResponse}}, dependencies=[_SO_EMISSOR])
def api_mover_nota(emissao_id: uuid.UUID, req: MoverNotaRequest, db: Session = Depends(db_sessao)):
    """Muda o tomador (vínculo) de uma nota importada do Emissor Nacional —
    ex.: AWIN x AWIN Rchlo, mesmo CNPJ. Notas geradas pela Ana não mudam."""
    emissao = _emissao_ou_404(db, emissao_id)
    if emissao.origem != "importada":
        raise HTTPException(status_code=409, detail="Só notas importadas do Emissor Nacional mudam de tomador.")
    vinculo = buscar_vinculo(db, req.vinculo_id)
    if vinculo is None:
        raise HTTPException(status_code=404, detail="Tomador não encontrado.")
    emissao.prestador_tomador_id = vinculo.id
    emissao.tomador_snapshot = {**(emissao.tomador_snapshot or {}), "apelido": vinculo.apelido}
    db.flush()
    resposta = _para_resposta(emissao)  # antes do commit (RLS vale só na transação)
    db.commit()
    return resposta


@app.get("/api/dps/{emissao_id}", response_model=EmissaoResponse, responses={404: {"model": ErroResponse}}, dependencies=[_SO_EMISSOR])
def api_ver_dps(emissao_id: uuid.UUID, db: Session = Depends(db_sessao)):
    emissao = db.query(Emissao).filter_by(id=emissao_id).one_or_none()
    if emissao is None:
        raise HTTPException(status_code=404, detail="Emissão não encontrada (ou não pertence ao prestador ativo)")
    return _para_resposta(emissao)


@app.get("/api/dps/{emissao_id}/nota", response_model=NotaVisualResponse, responses={404: {"model": ErroResponse}}, dependencies=[_SO_EMISSOR])
def api_nota_visual(emissao_id: uuid.UUID, db: Session = Depends(db_sessao)):
    """Marco 11 — a mesma emissão de /api/dps/{id}, mas com os campos já
    lidos e rotulados em português pra o painel desenhar uma 'nota' de
    verdade (cabeçalho, prestador/tomador, serviço, valores) em vez do
    JSON de resumo + XML cru que ele mostrava até aqui — ver docstring de
    app/services/nota_visual.py pro porquê disso ter virado necessário (a
    Raiana não conseguia conferir uma nota olhando aquilo). GET puro, sem
    efeito colateral."""
    emissao = db.query(Emissao).filter_by(id=emissao_id).one_or_none()
    if emissao is None:
        raise HTTPException(status_code=404, detail="Emissão não encontrada (ou não pertence ao prestador ativo)")
    return montar_nota_visual(emissao)


@app.post("/api/dps/{emissao_id}/assinar", response_model=EmissaoResponse, responses={404: {"model": ErroResponse}, 409: {"model": ErroResponse}}, dependencies=[_SO_EMISSOR, Depends(exigir_conta_real)])
def api_assinar_dps(emissao_id: uuid.UUID, db: Session = Depends(db_sessao), prestador_id: uuid.UUID = Depends(prestador_atual_id)):
    """montado -> assinado, com o certificado carregado (Marco 4). Não
    envia pra Sefin (ver docstring do módulo)."""
    emissao = db.query(Emissao).filter_by(id=emissao_id).one_or_none()
    if emissao is None:
        raise HTTPException(status_code=404, detail="Emissão não encontrada (ou não pertence ao prestador ativo)")

    settings = get_settings()
    try:
        private_key, cert = carregar_certificado(db, prestador_id, settings.cert_master_key)
    except CertificadoNaoEncontradoError as exc:
        raise HTTPException(status_code=409, detail="Nenhum certificado carregado — envie o .pfx antes de assinar.") from exc

    try:
        emissao = assinar_emissao(db, emissao, private_key, cert)
    except TransicaoInvalidaError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.commit()
    return _para_resposta(emissao)


@app.post("/api/dps/{emissao_id}/submeter", response_model=EmissaoResponse, responses={404: {"model": ErroResponse}, 409: {"model": ErroResponse}}, dependencies=[_SO_EMISSOR, Depends(exigir_conta_real)])
def api_submeter_dps(emissao_id: uuid.UUID, db: Session = Depends(db_sessao), prestador_id: uuid.UUID = Depends(prestador_atual_id)):
    """Marco 16, item 7 — assinado/erro -> submetido -> confirmado (ou ->
    erro de novo, retentável), chamando a Sefin DE VERDADE (ver
    app/services/motor_emissao.submeter). NUNCA foi validado contra a API
    real (rede bloqueada nesta sandbox, ver docstring do módulo) — fica
    pronto pra quando Marcos carregar um certificado A1 de verdade num
    ambiente com rede aberta. Uma recusa da Sefin não levanta erro HTTP:
    a emissão volta com estado='erro' e `erro_detalhe` preenchido (200),
    porque não é um erro do NOSSO lado — é resposta de negócio da Sefin,
    e a pessoa pode tentar de novo depois de corrigir o que for."""
    emissao = db.query(Emissao).filter_by(id=emissao_id).one_or_none()
    if emissao is None:
        raise HTTPException(status_code=404, detail="Emissão não encontrada (ou não pertence ao prestador ativo)")

    settings = get_settings()
    try:
        private_key, cert = carregar_certificado(db, prestador_id, settings.cert_master_key)
    except CertificadoNaoEncontradoError as exc:
        raise HTTPException(status_code=409, detail="Nenhum certificado carregado — envie o .pfx antes de submeter.") from exc

    tpAmb = (emissao.tomador_snapshot or {}).get("tpAmb", "2")
    cliente = ClienteSefin(private_key, cert, tpAmb)
    try:
        emissao = submeter_emissao(db, emissao, cliente)
    except TransicaoInvalidaError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    resposta = _para_resposta(emissao)  # antes do commit (RLS vale só na transação)
    db.commit()
    return resposta


@app.post("/api/dps/{emissao_id}/corrigir-reenviar", response_model=EmissaoResponse, responses={404: {"model": ErroResponse}, 409: {"model": ErroResponse}}, dependencies=[_SO_EMISSOR, Depends(exigir_conta_real)])
def api_corrigir_e_reenviar(emissao_id: uuid.UUID, db: Session = Depends(db_sessao), prestador_id: uuid.UUID = Depends(prestador_atual_id)):
    """Nota recusada por causa da hora de emissão (E0008): remonta com a
    hora de agora (mesmo número de DPS, mesmos dados), assina e envia de
    novo — um clique no aviso de recusa, sem refazer a nota (05/10/2026)."""
    emissao = db.query(Emissao).filter_by(id=emissao_id).one_or_none()
    if emissao is None:
        raise HTTPException(status_code=404, detail="Emissão não encontrada (ou não pertence ao prestador ativo)")
    try:
        private_key, cert = carregar_certificado(db, prestador_id, get_settings().cert_master_key)
    except CertificadoNaoEncontradoError as exc:
        raise HTTPException(status_code=409, detail="Nenhum certificado carregado — envie o .pfx antes de reenviar.") from exc
    try:
        remontar_emissao(db, emissao)
        assinar_emissao(db, emissao, private_key, cert)
        tpAmb = (emissao.tomador_snapshot or {}).get("tpAmb", "2")
        emissao = submeter_emissao(db, emissao, ClienteSefin(private_key, cert, tpAmb))
    except TransicaoInvalidaError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    resposta = _para_resposta(emissao)  # antes do commit (RLS vale só na transação)
    db.commit()
    return resposta


@app.post("/api/dps/{emissao_id}/cancelar", response_model=EmissaoResponse, responses={400: {"model": ErroResponse}, 404: {"model": ErroResponse}, 409: {"model": ErroResponse}, 422: {"model": ErroResponse}}, dependencies=[_SO_EMISSOR, Depends(exigir_conta_real)])
def api_cancelar_dps(
    emissao_id: uuid.UUID,
    req: CancelarDpsRequest,
    db: Session = Depends(db_sessao),
    prestador_id: uuid.UUID = Depends(prestador_atual_id),
):
    """Marco 16, item 7 — confirmado -> cancelada, chamando a Sefin DE
    VERDADE com a MESMA receita já validada em produção uma vez (ver
    app/services/motor_emissao.cancelar e integracao/cancelar_nfse.py).
    Ao contrário de submeter(): uma recusa da Sefin aqui LEVANTA erro
    (400) — cancelamento é uma ação que a pessoa pediu explicitamente
    (diferente de 'tentar emitir'), então uma recusa merece aparecer como
    falha da ação, não só ficar registrada silenciosamente na emissão."""
    emissao = db.query(Emissao).filter_by(id=emissao_id).one_or_none()
    if emissao is None:
        raise HTTPException(status_code=404, detail="Emissão não encontrada (ou não pertence ao prestador ativo)")

    settings = get_settings()
    try:
        private_key, cert = carregar_certificado(db, prestador_id, settings.cert_master_key)
    except CertificadoNaoEncontradoError as exc:
        raise HTTPException(status_code=409, detail="Nenhum certificado carregado — envie o .pfx antes de cancelar.") from exc

    tpAmb = (emissao.tomador_snapshot or {}).get("tpAmb", "2")
    cliente = ClienteSefin(private_key, cert, tpAmb)
    cnpj_autor = emissao.vinculo.prestador.cpf_cnpj
    try:
        emissao = cancelar_emissao(
            db, emissao, private_key, cert, cliente,
            cnpj_autor=cnpj_autor, cmotivo=req.cmotivo, xmotivo=req.xmotivo,
        )
    except TransicaoInvalidaError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        db.commit()  # erro_detalhe já foi gravado por cancelar() antes de levantar
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return _para_resposta(emissao)


@app.get("/api/dps/{emissao_id}/mensagem-pronta", response_model=MensagemProntaResponse, responses={404: {"model": ErroResponse}, 409: {"model": ErroResponse}}, dependencies=[_SO_EMISSOR])
def api_mensagem_pronta(emissao_id: uuid.UUID, db: Session = Depends(db_sessao)):
    """Marco 9 — texto pronto pra copiar/colar (WhatsApp, e-mail, ...).
    GET puro, sem efeito colateral — não registra tentativa de envio
    sozinho (ver POST /api/dps/{id}/envios pra isso)."""
    emissao = db.query(Emissao).filter_by(id=emissao_id).one_or_none()
    if emissao is None:
        raise HTTPException(status_code=404, detail="Emissão não encontrada (ou não pertence ao prestador ativo)")
    try:
        return MensagemProntaResponse(mensagem=gerar_mensagem_pronta(emissao))
    except EmissaoSemConteudoError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/api/dps/{emissao_id}/download", responses={404: {"model": ErroResponse}, 409: {"model": ErroResponse}}, dependencies=[_SO_EMISSOR])
def api_download_xml(emissao_id: uuid.UUID, db: Session = Depends(db_sessao)):
    """Marco 9 — baixa o melhor XML disponível pro estado atual da emissão
    (NÃO é o DANFSE oficial — ver ressalva em app/services/envios.py).
    GET puro, sem efeito colateral."""
    emissao = db.query(Emissao).filter_by(id=emissao_id).one_or_none()
    if emissao is None:
        raise HTTPException(status_code=404, detail="Emissão não encontrada (ou não pertence ao prestador ativo)")
    try:
        nome, conteudo = melhor_xml_disponivel(emissao)
    except EmissaoSemConteudoError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return Response(content=conteudo, media_type="application/xml", headers={"Content-Disposition": f'attachment; filename="{nome}"'})


def _emissao_ou_404(db: Session, emissao_id: uuid.UUID) -> Emissao:
    emissao = db.query(Emissao).filter_by(id=emissao_id).one_or_none()
    if emissao is None:
        raise HTTPException(status_code=404, detail="Emissão não encontrada (ou não pertence ao prestador ativo)")
    return emissao


@app.get("/api/dps/{emissao_id}/envio-opcoes", response_model=OpcoesEnvioResponse, responses={404: {"model": ErroResponse}}, dependencies=[_SO_EMISSOR])
def api_opcoes_envio(emissao_id: uuid.UUID, request: Request, db: Session = Depends(db_sessao)):
    """Marco 17 — o que dá pra usar no card 'Envio ao fornecedor' desta nota
    (e-mail direto ligado/desligado e por quê, WhatsApp, link público)."""
    emissao = _emissao_ou_404(db, emissao_id)
    return opcoes_envio(db, emissao, base_url(str(request.base_url)))


@app.post("/api/dps/{emissao_id}/enviar-geral", response_model=EnvioResponse, responses={400: {"model": ErroResponse}}, dependencies=[_SO_EMISSOR, Depends(exigir_conta_real)])
def api_enviar_geral(
    emissao_id: uuid.UUID, request: Request, req: EnviarGeralRequest | None = None,
    db: Session = Depends(db_sessao), prestador_id: uuid.UUID = Depends(prestador_atual_id),
):
    """Manda a nota pros e-mails gerais (contador, você) — 29/09/2026."""
    emissao = _emissao_ou_404(db, emissao_id)
    try:
        envio = enviar_geral(
            db, emissao, prestador_id, base_url(str(request.base_url)),
            para=req.para if req else None, assunto=req.assunto if req else None, texto=req.texto if req else None,
        )
    except EmailIndisponivelError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except EmissaoSemConteudoError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.commit()
    return envio


@app.post("/api/dps/{emissao_id}/marcar-enviada", response_model=EnvioResponse, dependencies=[_SO_EMISSOR])
def api_marcar_enviada(emissao_id: uuid.UUID, req: MarcarEnviadaRequest, db: Session = Depends(db_sessao)):
    """"Já mandei" — pelo portal do tomador ou outro jeito fora daqui."""
    emissao = _emissao_ou_404(db, emissao_id)
    envio = marcar_enviada(db, emissao, req.forma)
    db.commit()
    return envio


@app.get("/api/dps/{emissao_id}/email-previa", response_model=PreviaEmailResponse, responses={404: {"model": ErroResponse}}, dependencies=[_SO_EMISSOR])
def api_previa_email(emissao_id: uuid.UUID, request: Request, db: Session = Depends(db_sessao)):
    """Como o e-mail desta nota vai sair (destino, assunto, texto, anexos)."""
    emissao = _emissao_ou_404(db, emissao_id)
    return previa_email(db, emissao, base_url(str(request.base_url)))


@app.post("/api/dps/{emissao_id}/enviar-email", response_model=EnvioResponse, responses={400: {"model": ErroResponse}, 404: {"model": ErroResponse}, 409: {"model": ErroResponse}}, dependencies=[_SO_EMISSOR, Depends(exigir_conta_real)])
def api_enviar_email(
    emissao_id: uuid.UUID, request: Request, req: EnviarEmailRequest | None = None,
    db: Session = Depends(db_sessao), prestador_id: uuid.UUID = Depends(prestador_atual_id),
):
    """Marco 17 — manda a nota pro e-mail do fornecedor saindo do endereço
    da Agente Ana (PDF oficial + XML em anexo, resposta volta pro e-mail do
    prestador). Falha do provedor volta como envio com status 'falha'."""
    emissao = _emissao_ou_404(db, emissao_id)
    try:
        envio = enviar_email(
            db, emissao, prestador_id, base_url(str(request.base_url)),
            para=req.para if req else None, copia=req.copia if req else None,
            assunto=req.assunto if req else None, texto=req.texto if req else None,
            salvar_padrao=bool(req and req.salvar_padrao),
        )
    except EmailIndisponivelError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except EmissaoSemConteudoError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.commit()
    return envio


@app.post("/api/dps/{emissao_id}/whatsapp", response_model=WhatsappLinkResponse, responses={404: {"model": ErroResponse}, 409: {"model": ErroResponse}}, dependencies=[_SO_EMISSOR])
def api_link_whatsapp(
    emissao_id: uuid.UUID, request: Request, req: WhatsappRequest | None = None, db: Session = Depends(db_sessao),
):
    """Marco 17 — link do WhatsApp com a mensagem pronta (e o número do
    fornecedor, se cadastrado). Registra o envio como pendente."""
    emissao = _emissao_ou_404(db, emissao_id)
    if not (emissao.xml_resposta or emissao.xml_assinado or emissao.xml_dps):
        raise HTTPException(status_code=409, detail="Esta nota ainda não tem conteúdo pra enviar.")
    url, envio = link_whatsapp(
        db, emissao, base_url(str(request.base_url)),
        numero=req.numero if req else None, texto=req.texto if req else None,
        salvar_padrao=bool(req and req.salvar_padrao),
    )
    db.commit()
    return {"url": url, "envio": envio}


@app.get("/api/dps/{emissao_id}/pdf", responses={404: {"model": ErroResponse}}, dependencies=[_SO_EMISSOR])
def api_baixar_pdf(
    emissao_id: uuid.UUID, db: Session = Depends(db_sessao), prestador_id: uuid.UUID = Depends(prestador_atual_id),
):
    """Marco 17 — PDF oficial (DANFSe) da nota confirmada, baixado do ADN
    na primeira vez e guardado."""
    emissao = _emissao_ou_404(db, emissao_id)
    pdf = obter_danfse(db, emissao, prestador_id)
    if not pdf:
        raise HTTPException(status_code=404, detail="O PDF oficial só fica disponível depois que a prefeitura confirma a nota.")
    db.commit()
    return Response(content=pdf, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{nome_pdf(emissao)}"'})


@app.get("/api/publico/nota/{token}", responses={404: {"model": ErroResponse}})
def api_nota_publica(token: str, db: Session = Depends(get_db)):
    """Marco 17 — link que vai pro fornecedor (WhatsApp/e-mail): baixa a
    nota SEM login. O token assinado diz qual emissão e de qual prestador —
    é daí (nunca de parâmetro solto) que sai o prestador da RLS. PDF oficial
    quando existir, senão o XML."""
    try:
        emissao_id, prestador_id = ler_token(token)
    except LinkInvalidoError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    definir_prestador_atual(db, prestador_id)
    emissao = db.query(Emissao).filter_by(id=emissao_id).one_or_none()
    if emissao is None or emissao.estado == "cancelada":
        raise HTTPException(status_code=404, detail="Nota não encontrada ou cancelada.")
    pdf = obter_danfse(db, emissao, prestador_id)
    if pdf:
        db.commit()
        return Response(content=pdf, media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{nome_pdf(emissao)}"'})
    try:
        nome, conteudo = melhor_xml_disponivel(emissao)
    except EmissaoSemConteudoError as exc:
        raise HTTPException(status_code=404, detail="Nota ainda sem conteúdo.") from exc
    return Response(content=conteudo, media_type="application/xml", headers={"Content-Disposition": f'attachment; filename="{nome}"'})


@app.post("/api/dps/{emissao_id}/envios", response_model=EnvioResponse, responses={404: {"model": ErroResponse}, 409: {"model": ErroResponse}, 422: {"model": ErroResponse}}, dependencies=[_SO_EMISSOR])
def api_registrar_envio(emissao_id: uuid.UUID, req: RegistrarEnvioRequest, db: Session = Depends(db_sessao)):
    """Marco 9 — registra uma tentativa de entrega. 'download'/'mensagem_pronta'
    já nascem 'enviado' (o próprio app gerou o conteúdo); os outros canais
    ('email','whatsapp','direto_fornecedor') não são automatizados neste
    sandbox (sem rede/credenciais) — ficam 'pendente' até a Raiana confirmar
    manualmente com marcar-enviado/marcar-falha."""
    emissao = db.query(Emissao).filter_by(id=emissao_id).one_or_none()
    if emissao is None:
        raise HTTPException(status_code=404, detail="Emissão não encontrada (ou não pertence ao prestador ativo)")
    try:
        envio = registrar_envio(db, emissao, req.canal)
    except EmissaoSemConteudoError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except CanalInvalidoError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.commit()
    return envio


@app.get("/api/dps/{emissao_id}/envios", response_model=list[EnvioResponse], responses={404: {"model": ErroResponse}}, dependencies=[_SO_EMISSOR])
def api_listar_envios(emissao_id: uuid.UUID, db: Session = Depends(db_sessao)):
    emissao = db.query(Emissao).filter_by(id=emissao_id).one_or_none()
    if emissao is None:
        raise HTTPException(status_code=404, detail="Emissão não encontrada (ou não pertence ao prestador ativo)")
    return listar_envios(db, emissao)


@app.post("/api/envios/{envio_id}/marcar-enviado", response_model=EnvioResponse, responses={404: {"model": ErroResponse}}, dependencies=[_SO_EMISSOR])
def api_marcar_envio_enviado(envio_id: uuid.UUID, db: Session = Depends(db_sessao)):
    envio = buscar_envio(db, envio_id)
    if envio is None:
        raise HTTPException(status_code=404, detail="Envio não encontrado (ou não pertence ao prestador ativo)")
    envio = marcar_enviado(db, envio)
    db.commit()
    return envio


@app.post("/api/envios/{envio_id}/marcar-falha", response_model=EnvioResponse, responses={404: {"model": ErroResponse}}, dependencies=[_SO_EMISSOR])
def api_marcar_envio_falha(envio_id: uuid.UUID, db: Session = Depends(db_sessao)):
    envio = buscar_envio(db, envio_id)
    if envio is None:
        raise HTTPException(status_code=404, detail="Envio não encontrado (ou não pertence ao prestador ativo)")
    envio = marcar_falha(db, envio)
    db.commit()
    return envio


# --- Conciliação do extrato (05/10/2026, ver app/services/conciliacao.py) ---


def _vinculo_shopee(db: Session, vinculo_id: uuid.UUID):
    vinculo = buscar_vinculo(db, vinculo_id)
    if vinculo is None or vinculo.excluido_em is not None:
        raise HTTPException(status_code=404, detail="Tomador não encontrado.")
    return vinculo


@app.post("/api/awin/ordem", response_model=OrdemAwinResponse, responses={400: {"model": ErroResponse}}, dependencies=[_SO_EMISSOR])
def api_ler_ordem_awin(
    arquivo: UploadFile = File(...), vinculo_id: uuid.UUID | None = Form(default=None),
    db: Session = Depends(db_sessao), prestador_id: uuid.UUID = Depends(prestador_atual_id),
):
    """Ordem de pagamento da Awin em PDF (28/09/2026) — devolve número da
    ordem, valor e competência sugerida pra tela preencher, com avisos se o
    PDF for de outro CNPJ ou se a ordem já tiver nota. Não grava nada (ver
    app/services/ordem_awin.py)."""
    try:
        ordem = ler_ordem_awin(_ler_upload(arquivo, 10), arquivo.filename)
    except OrdemAwinInvalidaError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    avisos: list[str] = []
    if not ordem.numero:
        avisos.append("Não achei o número da ordem de pagamento no PDF — digite no campo abaixo.")
    if not ordem.valor:
        avisos.append("Não achei o valor (Total Bruto) no PDF — digite no campo abaixo.")
    if ordem.moeda and ordem.moeda.upper() != "BRL":
        avisos.append(f"A ordem está em {ordem.moeda}, não em reais — confira o valor antes de gerar.")
    prestador = db.get(Prestador, prestador_id)
    if prestador and ordem.cnpj_beneficiario and ordem.cnpj_beneficiario != prestador.cpf_cnpj:
        avisos.append("Essa ordem de pagamento é pra outro CNPJ, não o da sua empresa — confira se é o arquivo certo.")
    if vinculo_id is not None:
        vinculo = buscar_vinculo(db, vinculo_id)
        if vinculo is not None and vinculo.tomador is not None and vinculo.tomador.cnpj != CNPJ_AWIN:
            avisos.append(f"{vinculo.apelido} não é a Awin — esse PDF é uma ordem de pagamento da Awin.")

    ja_usada = None
    if ordem.numero:
        emissao = (
            db.query(Emissao)
            .filter(Emissao.estado != "cancelada", Emissao.tomador_snapshot["ordem"].astext == ordem.numero)
            .order_by(Emissao.criado_em.desc())
            .first()
        )
        if emissao is not None:
            ja_usada = {
                "emissao_id": emissao.id, "apelido": (emissao.tomador_snapshot or {}).get("apelido") or "",
                "competencia": emissao.competencia, "estado": emissao.estado,
            }
    return {
        "numero": ordem.numero, "valor": float(ordem.valor) if ordem.valor else None, "data": ordem.data,
        "moeda": ordem.moeda, "competencia_sugerida": ordem.competencia_sugerida, "avisos": avisos, "ja_usada": ja_usada,
    }


@app.post("/api/shopee/previa", response_model=PreviaShopeeResponse, responses={400: {"model": ErroResponse}}, dependencies=[_SO_EMISSOR])
def api_previa_shopee(
    vinculo_id: uuid.UUID = Form(...), arquivo: UploadFile = File(...), db: Session = Depends(db_sessao),
):
    """Relatório mensal da Shopee (28/09/2026) — lê o arquivo e mostra, por
    mês, quantos vendedores e quanto dá, sem gravar nada (ver
    app/services/relatorio_shopee.py)."""
    vinculo = _vinculo_shopee(db, vinculo_id)
    try:
        relatorio = ler_relatorio(_ler_upload(arquivo, 15))
    except RelatorioShopeeInvalidoError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    ja = {
        (mes, documento)
        for mes in {v.competencia for v in relatorio.vendedores}
        for documento in documentos_ja_gerados(db, vinculo, mes, relatorio.vendedores)
    }
    vendedores, por_mes = [], {}
    for v in relatorio.vendedores:
        gerada = (v.competencia, v.documento) in ja
        vendedores.append({
            "competencia": v.competencia, "documento": v.documento, "tipo_documento": v.tipo_documento,
            "razao_social": v.razao_social, "lojas": v.lojas, "valor": float(v.valor),
            "cidade": (v.endereco or {}).get("cidade"), "uf": (v.endereco or {}).get("uf"),
            "estrangeiro": v.estrangeiro, "avisos": v.avisos, "ja_gerada": gerada,
        })
        m = por_mes.setdefault(v.competencia, {
            "competencia": v.competencia, "vendedores": 0, "total": 0.0, "estrangeiros": 0, "ja_geradas": 0,
            "total_estrangeiros": 0.0, "total_ja_geradas": 0.0,
        })
        m["vendedores"] += 1
        m["total"] += float(v.valor)
        m["estrangeiros"] += int(v.estrangeiro)
        m["ja_geradas"] += int(gerada)
        # Pra pessoa conferir com o total que a Shopee mostra no painel.
        m["total_estrangeiros"] += float(v.valor) if v.estrangeiro else 0.0
        m["total_ja_geradas"] += float(v.valor) if gerada else 0.0
    competencias = sorted(por_mes.values(), key=lambda m: m["competencia"], reverse=True)
    for m in competencias:
        for campo in ("total", "total_estrangeiros", "total_ja_geradas"):
            m[campo] = round(m[campo], 2)
    vendedores.sort(key=lambda v: (v["competencia"], -v["valor"]))
    return {
        "linhas_lidas": relatorio.linhas_lidas, "linhas_ignoradas": relatorio.linhas_ignoradas,
        "competencias": competencias, "vendedores": vendedores,
    }


@app.post("/api/shopee/gerar", response_model=GeracaoShopeeResponse, responses={400: {"model": ErroResponse}}, dependencies=[_SO_EMISSOR])
def api_gerar_shopee(
    vinculo_id: uuid.UUID = Form(...),
    competencia: str = Form(...),
    arquivo: UploadFile = File(...),
    valor_minimo: float = Form(0),
    incluir_estrangeiros: bool = Form(False),
    aliq_sn: float | None = Form(None),
    tpAmb: str | None = Form(None),
    data_competencia: str | None = Form(None),
    db: Session = Depends(db_sessao),
):
    """Gera uma nota por vendedor do mês escolhido — os vendedores NÃO viram
    tomadores cadastrados (pedido do Marcos): os dados de cada um vão só na
    própria nota. Reenviar o mesmo relatório não duplica."""
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", competencia):
        raise HTTPException(status_code=422, detail="competencia deve estar no formato AAAA-MM")
    if tpAmb is not None and tpAmb not in ("1", "2"):
        raise HTTPException(status_code=422, detail="tpAmb deve ser 1 ou 2")
    vinculo = _vinculo_shopee(db, vinculo_id)
    tpAmb = tpAmb or _tp_amb_da_conta(db, vinculo.prestador_id)
    dcompet = None
    if data_competencia:
        try:
            dcompet = datetime.date.fromisoformat(data_competencia).isoformat()
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="data_competencia deve estar no formato AAAA-MM-DD") from exc
    try:
        relatorio = ler_relatorio(_ler_upload(arquivo, 15))
    except RelatorioShopeeInvalidoError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    resultado = gerar_notas(
        db, vinculo, relatorio, competencia=competencia, dcompet=dcompet, valor_minimo=Decimal(str(valor_minimo)),
        incluir_estrangeiros=incluir_estrangeiros, aliq_sn=aliq_sn, tpAmb=tpAmb,
    )
    db.commit()
    return {
        "geradas": resultado.geradas, "ja_existiam": resultado.ja_existiam, "puladas": resultado.puladas,
        "total": float(resultado.total), "erros": resultado.erros,
    }


@app.post("/api/dados/limpar", response_model=LimparDadosResponse, responses={422: {"model": ErroResponse}})
def api_limpar_dados(
    req: LimparDadosRequest, db: Session = Depends(db_sessao), prestador_id: uuid.UUID = Depends(prestador_atual_id),
):
    """Configurações > Limpar dados (28/09/2026). Exige digitar LIMPAR —
    não tem desfazer. Notas já enviadas à Receita nunca são apagadas (ver
    app/services/limpeza.py)."""
    if req.confirmacao.strip().upper() != "LIMPAR":
        raise HTTPException(status_code=422, detail="Digite LIMPAR para confirmar.")
    try:
        removidos = limpar_dados(db, prestador_id, req.categorias)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.commit()
    return LimparDadosResponse(removidos=removidos)


def _cliente_producao(db: Session, prestador_id: uuid.UUID) -> ClienteSefin:
    try:
        private_key, cert = carregar_certificado(db, prestador_id, get_settings().cert_master_key)
    except CertificadoNaoEncontradoError as exc:
        raise HTTPException(status_code=409, detail="Carregue o certificado digital da empresa (Empresa › Certificado) pra importar do Emissor Nacional.") from exc
    return ClienteSefin(private_key, cert, "1")


@app.get("/api/importar/nacional", response_model=PreviaNacionalResponse, dependencies=[_SO_EMISSOR])
def api_previa_nacional(db: Session = Depends(db_sessao), prestador_id: uuid.UUID = Depends(prestador_atual_id)):
    return importar_adn.previa(db, db.get(Prestador, prestador_id))


@app.post(
    "/api/importar/nacional/buscar", response_model=PreviaNacionalResponse,
    responses={409: {"model": ErroResponse}, 502: {"model": ErroResponse}},
    dependencies=[Depends(exigir_conta_real), Depends(limite("adn", 60, 600))],
)
def api_buscar_nacional(
    req: BuscarNacionalRequest, db: Session = Depends(db_sessao), prestador_id: uuid.UUID = Depends(prestador_atual_id),
):
    """Lê mais um pedaço das notas da empresa no Emissor Nacional (a tela
    chama de novo enquanto `terminou` for falso)."""
    cliente = _cliente_producao(db, prestador_id)
    try:
        return importar_adn.buscar(
            db, db.get(Prestador, prestador_id), cliente, recomecar=req.recomecar, desde_inicio=req.desde_inicio,
            desde=req.desde or f"{hoje_br().year:04d}-01",
        )
    except importar_adn.ImportacaoAdnError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/importar/nacional/limpar", dependencies=[_SO_EMISSOR, Depends(exigir_conta_real)])
def api_limpar_importadas(req: LimparImportadasRequest, db: Session = Depends(db_sessao)):
    """Tira do controle as notas importadas antes de um mês (histórico que
    não vai ser acompanhado). Notas geradas pela Ana ficam."""
    resultado = importar_adn.remover_importadas(db, req.antes)
    db.commit()
    return resultado


@app.post(
    "/api/importar/nacional", response_model=ImportarNacionalResponse, responses={409: {"model": ErroResponse}},
    dependencies=[Depends(exigir_conta_real)],
)
def api_importar_nacional(
    req: ImportarNacionalRequest, db: Session = Depends(db_sessao), prestador_id: uuid.UUID = Depends(prestador_atual_id),
):
    try:
        resultado = importar_adn.importar(db, db.get(Prestador, prestador_id), [r.model_dump(mode="json") for r in req.mapeamento])
    except importar_adn.ImportacaoAdnError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.commit()
    return resultado


# --- Financeiro: resumo, contas do mês com check, contas fixas e rotina (28/09/2026) ---


_COMPETENCIA_RE = r"^\d{4}-(0[1-9]|1[0-2])$"


@app.get("/api/conta/preferencias")
def api_preferencias(request: Request, db: Session = Depends(get_db)):
    """Disposição dos cards (Financeiro, Visão geral) — da pessoa, não da empresa."""
    return _usuario_logado(request, db).preferencias or {}


@app.put("/api/conta/preferencias")
def api_salvar_preferencias(req: PreferenciasRequest, request: Request, db: Session = Depends(get_db)):
    usuario = _usuario_logado(request, db)
    usuario.preferencias = {**(usuario.preferencias or {}), req.tela: {"ordem": req.ordem, "fechados": req.fechados, "ocultos": req.ocultos}}
    resposta = dict(usuario.preferencias)
    db.commit()
    return resposta


# --- Importar a planilha de controle (28/09/2026) ---


@app.post("/api/painel/pendencias/ignorar")
def api_ignorar_pendencia(
    req: IgnorarPendenciaRequest, db: Session = Depends(db_sessao), prestador_id: uuid.UUID = Depends(prestador_atual_id),
):
    """"Ignorar este aviso" na Visão geral (atraso consciente) — some só
    aquela ocorrência (ex.: gerar a nota de X em 10/2026)."""
    ajuste = db.query(AjusteEvento).filter_by(tipo="pendencia", chave=req.chave).one_or_none()
    if req.ignorar and ajuste is None:
        db.add(AjusteEvento(id=uuid.uuid4(), prestador_id=prestador_id, tipo="pendencia", chave=req.chave, oculto=True))
    elif not req.ignorar and ajuste is not None:
        db.delete(ajuste)
    db.commit()
    return {"ok": True}


@app.get("/api/painel/proximos", response_model=ProximosResponse, dependencies=[_SO_EMISSOR])
def api_painel_proximos(db: Session = Depends(db_sessao), prestador_id: uuid.UUID = Depends(prestador_atual_id)):
    """O que fazer agora + agenda dos próximos 30 dias (Visão geral)."""
    return proximos_do_painel(db, prestador_id)


@app.get("/api/painel/resumo-mes", response_model=DashboardResumoResponse, dependencies=[_SO_EMISSOR])
def api_painel_resumo_mes(
    competencia: str | None = None,
    db: Session = Depends(db_sessao),
    prestador_id: uuid.UUID = Depends(prestador_atual_id),
):
    """Marco 12 — dados da tela 'Visão geral' do novo frontend (ver
    app/services/dashboard.py pro porquê de cada campo e as aproximações
    assumidas). `competencia` é opcional (AAAA-MM); sem ela, usa o mês
    corrente. GET puro, sem efeito colateral."""
    if competencia is not None and not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", competencia):
        raise HTTPException(status_code=422, detail="competencia deve estar no formato AAAA-MM")
    return resumo_mes(db, prestador_id, competencia)


# Frontend novo (React/Vite, Marco 12/13) — o build (`npm run build` em
# frontend/) é copiado pra frontend/dist pelo Dockerfile (estágio Node,
# separado da imagem final — não roda servidor Node em produção, só serve
# os arquivos estáticos gerados). Em dev local sem Docker, precisa rodar
# `npm run build` uma vez em frontend/ pra esta pasta existir; o fluxo de
# desenvolvimento normal usa `npm run dev` (proxy do Vite, ver
# frontend/vite.config.ts), que não passa por aqui.
#
# `parents[2]`: este arquivo é backend/app/main.py — dois níveis acima é a
# raiz do repo (onde mora frontend/), tanto localmente quanto na imagem
# Docker (que replica a mesma estrutura: /app/backend, /app/frontend).
_FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


def _index_html() -> FileResponse:
    indice = _FRONTEND_DIST / "index.html"
    if not indice.is_file():
        # Acontece em dev local sem Docker antes do primeiro `npm run
        # build` em frontend/ (ver comentário acima) — 500 com instrução
        # clara em vez de um FileNotFoundError cru.
        raise HTTPException(
            status_code=500,
            detail="Build do frontend não encontrado — rode `npm run build` em frontend/ (ou use o Dockerfile).",
        )
    # Sempre revalida o index.html (senão, depois de um deploy, o navegador
    # guarda a página velha apontando pra arquivos que não existem mais).
    return FileResponse(indice, headers={"Cache-Control": "no-cache"})


# --- Módulo financeiro: produto à parte, com as rotas dele (05/10/2026) ---
# Entra aqui (antes do catch-all do frontend) e registra o que ele ouve do
# emissor (app/eventos.py). O emissor não importa nada de app/financeiro.
from app.financeiro import integracao as _integracao_financeiro  # noqa: E402
from app.financeiro.rotas import rotas as _rotas_financeiro  # noqa: E402

_integracao_financeiro.registrar()
app.include_router(_rotas_financeiro)


@app.get("/", include_in_schema=False)
def frontend_raiz():
    return _index_html()


@app.get("/{caminho_completo:path}", include_in_schema=False)
def frontend_catch_all(caminho_completo: str):
    """Serve o SPA novo pra qualquer rota que não seja da API. Isso vem
    DEPOIS de toda rota /api/* no arquivo (a ordem de registro é o que
    decide qual rota o Starlette tenta primeiro — ver docstring do módulo
    sobre a disciplina de RLS: a mesma lógica de "a rota mais específica
    ganha por estar primeiro" vale aqui), então uma /api/rota-que-nao-existe
    nunca cai aqui por acidente — cai no 404 explícito abaixo.

    Pra tudo mais: se o caminho pedido é um arquivo real do build (JS, CSS,
    favicon.svg, ...), devolve ele; senão devolve index.html e deixa o
    react-router decidir no navegador — é isso que permite recarregar a
    página em /tomadores ou compartilhar link direto pra /calendario sem
    dar 404."""
    if caminho_completo.startswith("api/"):
        raise HTTPException(status_code=404, detail="Rota não encontrada.")
    candidato = (_FRONTEND_DIST / caminho_completo).resolve()
    if _FRONTEND_DIST.is_dir() and candidato.is_file() and _FRONTEND_DIST.resolve() in candidato.parents:
        # Arquivos do build com hash no nome nunca mudam: cache longo.
        if caminho_completo.startswith("assets/"):
            return FileResponse(candidato, headers={"Cache-Control": "public, max-age=31536000, immutable"})
        return FileResponse(candidato)
    return _index_html()
