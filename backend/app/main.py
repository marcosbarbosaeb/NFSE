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

O que o painel ainda NÃO faz, de propósito: não expõe um botão de
"submeter pra Sefin". `motor_emissao.submeter`/`cancelar` existem e têm
testes (com ClienteSefin mockado), mas a submissão de DPS nunca foi testada
contra a API real (ver integracao/submit_dps.py) e este sandbox não
alcança gov.br de qualquer forma — clicar em "assinar" aqui não é
reversível gratuitamente do jeito que "gerar" é, mas ainda é uma etapa
segura porque nada sai pra rede. Expor submissão de verdade no painel é
decisão para quando isso puder ser validado de um ambiente com rede
liberada — Marcos continua emitindo de verdade pelos scripts em
integracao/ até lá.
"""
import uuid

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from app.config import get_settings
from app.database import definir_prestador_atual, get_db
from app.fiscal.dps import DescricaoIncompletaError
from app.models import Certificado, Emissao, Usuario
from app.schemas import (
    CertificadoStatus,
    DespesaResponse,
    EmissaoResponse,
    EnvioResponse,
    ErroResponse,
    GerarDpsRequest,
    ImportacaoCsvResponse,
    LoginRequest,
    MensagemProntaResponse,
    PagamentoResponse,
    PainelStatusResponse,
    RegistrarDespesaRequest,
    RegistrarEnvioRequest,
    RegistrarPagamentoRequest,
    UsuarioResponse,
    VinculoResumo,
)
from app.services.certificados import (
    CertificadoNaoEncontradoError,
    carregar_certificado,
    certificado_vencido,
    salvar_certificado,
)
from app.services.despesas import registrar_despesa
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
from app.services.importacao_csv import CsvInvalidoError, importar_csv
from app.services.motor_emissao import (
    EmissaoJaExisteError,
    TransicaoInvalidaError,
    assinar as assinar_emissao,
    criar_rascunho,
    montar as montar_emissao,
)
from app.services.pagamentos import registrar_pagamento
from app.services.painel_status import painel_status_completo
from app.services.usuarios import autenticar
from app.services.vinculos import buscar_vinculo, listar_vinculos_ativos

app = FastAPI(title="Painel NFS-e — Raiana (Marco 5/6/9/10)")
# same_site="lax": suficiente pro painel ser first-party (o próprio backend
# serve a página em /); https_only fica False aqui de propósito porque este
# ambiente de dev roda em http puro — LIGAR em produção atrás de HTTPS de
# verdade é obrigatório (cookie de sessão sem isso pode vazar em rede
# insegura).
app.add_middleware(SessionMiddleware, secret_key=get_settings().session_secret_key, same_site="lax", https_only=False)


def prestador_atual_id(request: Request, db: Session = Depends(get_db)) -> uuid.UUID:
    """Marco 10 — resolve o prestador a partir da SESSÃO autenticada (não
    mais config fixa, ver docstring do módulo). `usuario` não tem RLS (ver
    docstring do modelo em app/models.py), por isso usa `get_db` puro aqui
    e não `db_sessao` — seria circular, já que `db_sessao` depende desta
    função. NUNCA aceita prestador_id vindo do cliente: é sempre resolvido
    no servidor, a partir de quem está logado — é essa garantia que mantém
    a disciplina de RLS válida com múltiplos usuários."""
    usuario_id = request.session.get("usuario_id")
    if usuario_id is None:
        raise HTTPException(status_code=401, detail="Não autenticado — faça login.")
    usuario = db.query(Usuario).filter_by(id=uuid.UUID(usuario_id), ativo=True).one_or_none()
    if usuario is None:
        request.session.clear()
        raise HTTPException(status_code=401, detail="Sessão inválida — faça login novamente.")
    return usuario.prestador_id


def db_sessao(db: Session = Depends(get_db), prestador_id: uuid.UUID = Depends(prestador_atual_id)) -> Session:
    """RLS continua valendo de verdade aqui — sem isso, toda query nas
    tabelas protegidas devolve vazio (falha fechada, ver migração de RLS)."""
    definir_prestador_atual(db, prestador_id)
    return db


@app.post("/api/auth/login", response_model=UsuarioResponse, responses={401: {"model": ErroResponse}})
def api_login(req: LoginRequest, request: Request, db: Session = Depends(get_db)):
    """Marco 10 — cadastro de usuário é administrativo (scripts/criar_usuario.py),
    não há self-service signup aqui de propósito."""
    usuario = autenticar(db, req.email, req.senha)
    if usuario is None:
        raise HTTPException(status_code=401, detail="E-mail ou senha inválidos.")
    request.session["usuario_id"] = str(usuario.id)
    return UsuarioResponse(email=usuario.email, prestador_id=usuario.prestador_id)


@app.post("/api/auth/logout")
def api_logout(request: Request):
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
    return UsuarioResponse(email=usuario.email, prestador_id=usuario.prestador_id)


@app.get("/api/vinculos", response_model=list[VinculoResumo])
def api_listar_vinculos(db: Session = Depends(db_sessao)):
    vinculos = listar_vinculos_ativos(db)
    return [
        VinculoResumo(
            id=v.id, apelido=v.apelido, tomador_razao_social=v.tomador.razao_social,
            tomador_cnpj=v.tomador.cnpj, serie=v.serie, template_descricao=v.template_descricao,
            requer_revisao=v.requer_revisao,
        )
        for v in vinculos
    ]


@app.get("/api/certificado/status", response_model=CertificadoStatus)
def api_status_certificado(db: Session = Depends(db_sessao), prestador_id: uuid.UUID = Depends(prestador_atual_id)):
    registro = db.query(Certificado).filter_by(prestador_id=prestador_id).one_or_none()
    if registro is None:
        return CertificadoStatus(carregado=False)
    return CertificadoStatus(carregado=True, validade=registro.validade, vencido=certificado_vencido(registro))


@app.post("/api/certificado", response_model=CertificadoStatus)
async def api_salvar_certificado(
    pfx: UploadFile = File(...), senha: str = Form(...),
    db: Session = Depends(db_sessao), prestador_id: uuid.UUID = Depends(prestador_atual_id),
):
    settings = get_settings()
    pfx_bytes = await pfx.read()
    try:
        registro = salvar_certificado(db, prestador_id, pfx_bytes, senha, settings.cert_master_key)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Não foi possível carregar o certificado: {exc}") from exc
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
        chave_acesso=emissao.chave_acesso, erro_detalhe=emissao.erro_detalhe,
        atualizado_em=emissao.atualizado_em,
    )


@app.post("/api/dps", response_model=EmissaoResponse, responses={404: {"model": ErroResponse}, 409: {"model": ErroResponse}, 422: {"model": ErroResponse}})
def api_criar_dps(req: GerarDpsRequest, db: Session = Depends(db_sessao)):
    """Cria e monta (rascunho -> montado) — persiste de verdade, com nDPS
    atribuído automaticamente. Essa é a 'caixa de revisão' antes de assinar."""
    vinculo = buscar_vinculo(db, req.vinculo_id)
    if vinculo is None:
        raise HTTPException(status_code=404, detail="Vínculo não encontrado (ou não pertence ao prestador ativo)")

    try:
        emissao = criar_rascunho(
            db, vinculo, competencia=req.competencia, valor=req.valor,
            ordem=req.ordem, aliq_sn=req.aliq_sn, tpAmb=req.tpAmb,
        )
        emissao = montar_emissao(db, emissao)
    except EmissaoJaExisteError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except DescricaoIncompletaError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.commit()
    return _para_resposta(emissao)


@app.post("/api/dps/importar-csv", response_model=ImportacaoCsvResponse, responses={400: {"model": ErroResponse}})
async def api_importar_csv(arquivo: UploadFile = File(...), db: Session = Depends(db_sessao)):
    """Marco 7 — gera várias emissões de uma vez a partir de um CSV
    (colunas: apelido, competencia, valor[, ordem][, aliq_sn]). Cada linha
    roda isolada (savepoint) — uma linha ruim vira erro naquela linha, sem
    derrubar as demais. Só dá commit se pelo menos uma linha deu certo."""
    bruto = await arquivo.read()
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


@app.get("/api/dps/{emissao_id}", response_model=EmissaoResponse, responses={404: {"model": ErroResponse}})
def api_ver_dps(emissao_id: uuid.UUID, db: Session = Depends(db_sessao)):
    emissao = db.query(Emissao).filter_by(id=emissao_id).one_or_none()
    if emissao is None:
        raise HTTPException(status_code=404, detail="Emissão não encontrada (ou não pertence ao prestador ativo)")
    return _para_resposta(emissao)


@app.post("/api/dps/{emissao_id}/assinar", response_model=EmissaoResponse, responses={404: {"model": ErroResponse}, 409: {"model": ErroResponse}})
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


@app.get("/api/dps/{emissao_id}/mensagem-pronta", response_model=MensagemProntaResponse, responses={404: {"model": ErroResponse}, 409: {"model": ErroResponse}})
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


@app.get("/api/dps/{emissao_id}/download", responses={404: {"model": ErroResponse}, 409: {"model": ErroResponse}})
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


@app.post("/api/dps/{emissao_id}/envios", response_model=EnvioResponse, responses={404: {"model": ErroResponse}, 409: {"model": ErroResponse}, 422: {"model": ErroResponse}})
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


@app.get("/api/dps/{emissao_id}/envios", response_model=list[EnvioResponse], responses={404: {"model": ErroResponse}})
def api_listar_envios(emissao_id: uuid.UUID, db: Session = Depends(db_sessao)):
    emissao = db.query(Emissao).filter_by(id=emissao_id).one_or_none()
    if emissao is None:
        raise HTTPException(status_code=404, detail="Emissão não encontrada (ou não pertence ao prestador ativo)")
    return listar_envios(db, emissao)


@app.post("/api/envios/{envio_id}/marcar-enviado", response_model=EnvioResponse, responses={404: {"model": ErroResponse}})
def api_marcar_envio_enviado(envio_id: uuid.UUID, db: Session = Depends(db_sessao)):
    envio = buscar_envio(db, envio_id)
    if envio is None:
        raise HTTPException(status_code=404, detail="Envio não encontrado (ou não pertence ao prestador ativo)")
    envio = marcar_enviado(db, envio)
    db.commit()
    return envio


@app.post("/api/envios/{envio_id}/marcar-falha", response_model=EnvioResponse, responses={404: {"model": ErroResponse}})
def api_marcar_envio_falha(envio_id: uuid.UUID, db: Session = Depends(db_sessao)):
    envio = buscar_envio(db, envio_id)
    if envio is None:
        raise HTTPException(status_code=404, detail="Envio não encontrado (ou não pertence ao prestador ativo)")
    envio = marcar_falha(db, envio)
    db.commit()
    return envio


@app.post("/api/pagamentos", response_model=PagamentoResponse, responses={404: {"model": ErroResponse}})
def api_registrar_pagamento(req: RegistrarPagamentoRequest, db: Session = Depends(db_sessao)):
    """Marco 8 — registro manual de um pagamento recebido (o lado 'recebi'
    do painel de status; o lado 'faturei' já é automático via /api/dps)."""
    vinculo = buscar_vinculo(db, req.vinculo_id)
    if vinculo is None:
        raise HTTPException(status_code=404, detail="Vínculo não encontrado (ou não pertence ao prestador ativo)")
    pagamento = registrar_pagamento(db, vinculo, competencia=req.competencia, valor=req.valor, data_recebimento=req.data_recebimento)
    db.commit()
    return PagamentoResponse(
        id=pagamento.id, apelido=vinculo.apelido, competencia=pagamento.competencia,
        valor=float(pagamento.valor), data_recebimento=pagamento.data_recebimento,
    )


@app.post("/api/despesas", response_model=DespesaResponse)
def api_registrar_despesa(req: RegistrarDespesaRequest, db: Session = Depends(db_sessao), prestador_id: uuid.UUID = Depends(prestador_atual_id)):
    """Marco 8 — registro manual de uma despesa (por categoria, não por
    fornecedor — ver seção 'Despesas' da planilha real)."""
    despesa = registrar_despesa(db, prestador_id, categoria=req.categoria, competencia=req.competencia, valor=req.valor)
    db.commit()
    return DespesaResponse(id=despesa.id, categoria=despesa.categoria, competencia=despesa.competencia, valor=float(despesa.valor))


@app.get("/api/painel/status", response_model=PainelStatusResponse)
def api_painel_status(ano: str, db: Session = Depends(db_sessao), prestador_id: uuid.UUID = Depends(prestador_atual_id)):
    """Marco 8 — 'painel de status, seria notas geradas e notas recebidas...
    igual a esta planilha' (item #7 da lista original). `ano` é obrigatório
    e no formato AAAA (o painel mostra um ano de cada vez, como a aba única
    da planilha real hoje mostra 2026)."""
    if len(ano) != 4 or not ano.isdigit():
        raise HTTPException(status_code=422, detail="ano deve estar no formato AAAA")
    return painel_status_completo(db, prestador_id, ano)


@app.get("/", response_class=HTMLResponse)
def painel():
    return _PAGINA_HTML


_PAGINA_HTML = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<title>Painel NFS-e — Raiana</title>
<style>
  body { font-family: -apple-system, system-ui, sans-serif; max-width: 780px; margin: 2rem auto; padding: 0 1rem; color: #1a1a1a; }
  h1 { font-size: 1.3rem; }
  fieldset { border: 1px solid #ddd; border-radius: 8px; padding: 1rem; margin-bottom: 1rem; }
  legend { font-weight: 600; padding: 0 .4rem; }
  label { display: block; margin: .5rem 0 .2rem; font-size: .9rem; }
  input, select { width: 100%; padding: .4rem; box-sizing: border-box; }
  button { margin-top: .8rem; padding: .5rem 1rem; cursor: pointer; }
  button:disabled { opacity: .5; cursor: default; }
  pre { background: #f5f5f5; padding: .8rem; border-radius: 6px; overflow-x: auto; font-size: .8rem; white-space: pre-wrap; }
  .aviso { background: #fff4e5; border: 1px solid #ffc266; border-radius: 6px; padding: .6rem .8rem; font-size: .85rem; }
  .erro { color: #b00020; background: #fdecea; border: 1px solid #f5b5ac; border-radius: 6px; padding: .5rem .7rem; font-size: .85rem; margin-top: .5rem; }
  .sucesso { color: #0a6b2b; background: #e6f4ea; border: 1px solid #8fd19e; border-radius: 6px; padding: .5rem .7rem; font-size: .85rem; margin-top: .5rem; }
  .status { font-size: .85rem; }
  .badge { display: inline-block; padding: .1rem .5rem; border-radius: 999px; background: #e5e5e5; font-size: .8rem; }
</style>
</head>
<body>
<h1>Painel NFS-e</h1>

<fieldset id="login-fieldset">
  <legend>Entrar</legend>
  <label>E-mail</label>
  <input id="login-email" type="email">
  <label>Senha</label>
  <input id="login-senha" type="password">
  <button onclick="login()">Entrar</button>
  <div id="login-resultado"></div>
</fieldset>

<div id="app" style="display:none;">
<p class="status">Logado como <strong id="usuario-email"></strong> — <a href="#" onclick="logout(); return false;">sair</a></p>
<p class="aviso">Gerar já cria e persiste a emissão (nDPS automático); assinar avança o estado dela. Não envia pra
Sefin — submissão continua manual via scripts, do computador com rede liberada pra gov.br.</p>

<fieldset>
  <legend>Certificado</legend>
  <div id="cert-status" class="status">carregando...</div>
  <label>Arquivo .pfx</label>
  <input type="file" id="cert-pfx">
  <label>Senha</label>
  <input type="password" id="cert-senha">
  <button id="btn-cert" onclick="enviarCertificado()">Carregar certificado</button>
  <div id="cert-resultado"></div>
</fieldset>

<fieldset>
  <legend>Nova DPS</legend>
  <label>Vínculo (fornecedor)</label>
  <select id="vinculo"></select>
  <label>Competência (AAAA-MM)</label>
  <input type="month" id="competencia">
  <label>Valor (R$)</label>
  <input id="valor" type="number" step="0.01">
  <label>Ordem de pagamento (só AWIN/AWIN Rchlo)</label>
  <input id="ordem">
  <label>Alíquota do Simples Nacional (%)</label>
  <input id="aliq_sn" type="number" step="0.01">
  <label>Ambiente</label>
  <select id="tpAmb">
    <option value="2">Homologação — ambiente de teste, NÃO vale como nota fiscal real</option>
    <option value="1">Produção — nota fiscal real, seria enviada de verdade à Receita</option>
  </select>
  <p class="aviso">Use sempre <strong>Homologação</strong> pra testar. "Produção" ainda não envia nada de verdade pra Sefin neste painel (isso é um passo futuro), mas já é a opção que vale pra quando enviar de verdade — não troque por engano.</p>
  <button onclick="gerar()">Gerar (cria + monta)</button>
  <button id="btn-assinar" onclick="assinar()" disabled>Assinar</button>
</fieldset>

<fieldset>
  <legend>Envio (nota atual)</legend>
  <p class="aviso">'Baixar XML' e 'Mensagem pronta' o app gera sozinho. E-mail/WhatsApp/direto ao fornecedor não são automáticos aqui (sem rede/credenciais neste ambiente) — marque manualmente depois de enviar por fora.</p>
  <button onclick="baixarXml()">Baixar XML</button>
  <button onclick="mostrarMensagemPronta()">Mensagem pronta</button>
  <button onclick="registrarEnvio('email')">Registrar envio: e-mail</button>
  <button onclick="registrarEnvio('whatsapp')">Registrar envio: WhatsApp</button>
  <button onclick="registrarEnvio('direto_fornecedor')">Registrar envio: direto ao fornecedor</button>
  <div id="envio-resultado"></div>
</fieldset>

<fieldset>
  <legend>Importar CSV (várias notas de uma vez)</legend>
  <p class="aviso">Colunas: <code>apelido, competencia, valor</code> (+ <code>ordem</code>, <code>aliq_sn</code> opcionais). Uma linha por nota — o apelido precisa bater com o vínculo cadastrado (ex.: ML/Ebazar, AWIN). Uma linha com problema vira erro só naquela linha, sem travar as outras.</p>
  <input type="file" id="csv-arquivo" accept=".csv,text/csv">
  <button onclick="importarCsv()">Importar</button>
  <div id="csv-resultado"></div>
</fieldset>

<div id="resultado"></div>

<fieldset>
  <legend>Registrar pagamento recebido</legend>
  <label>Vínculo (fornecedor)</label>
  <select id="pgto-vinculo"></select>
  <label>Competência (AAAA-MM)</label>
  <input type="month" id="pgto-competencia">
  <label>Valor (R$)</label>
  <input id="pgto-valor" type="number" step="0.01">
  <label>Data do recebimento (opcional)</label>
  <input id="pgto-data" type="date">
  <button onclick="registrarPagamento()">Registrar pagamento</button>
  <div id="pgto-resultado"></div>
</fieldset>

<fieldset>
  <legend>Registrar despesa</legend>
  <label>Categoria</label>
  <input id="desp-categoria" placeholder="Ex.: Pro Labore, Contabilidade...">
  <label>Competência (AAAA-MM)</label>
  <input type="month" id="desp-competencia">
  <label>Valor (R$)</label>
  <input id="desp-valor" type="number" step="0.01">
  <button onclick="registrarDespesa()">Registrar despesa</button>
  <div id="desp-resultado"></div>
</fieldset>

<fieldset>
  <legend>Painel de status (ano completo)</legend>
  <label>Ano</label>
  <input id="status-ano" value="2026" style="width: 120px; display: inline-block;">
  <button onclick="carregarStatus()">Carregar</button>
  <div id="status-resultado"></div>
</fieldset>
</div>

<script>
let emissaoAtualId = null;

// FastAPI devolve `detail` como texto simples nos erros que o backend levanta
// de proposito (ex.: HTTPException), mas como uma LISTA de objetos quando e o
// Pydantic validando o corpo automaticamente (422 de campo obrigatorio/formato
// errado) — sem isso, essas mensagens apareciam como "[object Object]" pro
// usuario, o que parecia "nao funciona" mesmo quando o erro era so, por
// exemplo, competencia em formato errado.
function formatarErro(detail) {
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail.map(e => {
      const campo = Array.isArray(e.loc) ? e.loc[e.loc.length - 1] : 'campo';
      return `${campo}: ${e.msg}`;
    }).join('; ');
  }
  return 'Erro inesperado (veja o console do navegador — F12).';
}

async function login() {
  const email = document.getElementById('login-email').value;
  const senha = document.getElementById('login-senha').value;
  const r = await fetch('/api/auth/login', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({email, senha}) });
  const dados = await r.json();
  if (!r.ok) { document.getElementById('login-resultado').innerHTML = `<p class="erro">${formatarErro(dados.detail)}</p>`; return; }
  document.getElementById('login-senha').value = '';
  await mostrarApp(dados);
}
async function logout() {
  await fetch('/api/auth/logout', { method: 'POST' });
  document.getElementById('app').style.display = 'none';
  document.getElementById('login-fieldset').style.display = '';
  document.getElementById('login-resultado').innerHTML = '';
}
async function mostrarApp(usuario) {
  document.getElementById('usuario-email').textContent = usuario.email;
  document.getElementById('login-fieldset').style.display = 'none';
  document.getElementById('app').style.display = '';
  carregarVinculos();
  carregarStatusCertificado();
}
async function verificarSessao() {
  const r = await fetch('/api/auth/me');
  if (r.ok) { await mostrarApp(await r.json()); }
}

async function carregarVinculos() {
  const r = await fetch('/api/vinculos');
  const vinculos = await r.json();
  const opcoes = vinculos.map(v => `<option value="${v.id}">${v.apelido} — ${v.tomador_razao_social}</option>`).join('');
  document.getElementById('vinculo').innerHTML = opcoes;
  const pgtoSel = document.getElementById('pgto-vinculo');
  if (pgtoSel) pgtoSel.innerHTML = opcoes;
}
async function carregarStatusCertificado() {
  const r = await fetch('/api/certificado/status');
  const s = await r.json();
  const el = document.getElementById('cert-status');
  if (!s.carregado) { el.textContent = 'Nenhum certificado carregado.'; return; }
  el.textContent = `Carregado. Validade: ${s.validade}` + (s.vencido ? ' — VENCIDO!' : '');
}
async function enviarCertificado() {
  const pfx = document.getElementById('cert-pfx').files[0];
  const senha = document.getElementById('cert-senha').value;
  const resultado = document.getElementById('cert-resultado');
  const btn = document.getElementById('btn-cert');
  resultado.innerHTML = '';
  if (!pfx || !senha) { resultado.innerHTML = '<p class="erro">Selecione o arquivo .pfx e informe a senha antes de carregar.</p>'; return; }
  const fd = new FormData();
  fd.append('pfx', pfx);
  fd.append('senha', senha);
  btn.disabled = true;
  btn.textContent = 'Carregando...';
  try {
    const r = await fetch('/api/certificado', { method: 'POST', body: fd });
    const dados = await r.json();
    if (!r.ok) { resultado.innerHTML = `<p class="erro">Erro: ${formatarErro(dados.detail)}</p>`; return; }
    document.getElementById('cert-senha').value = '';
    resultado.innerHTML = `<p class="sucesso">✓ Certificado carregado com sucesso. Validade: ${dados.validade}${dados.vencido ? ' — ATENÇÃO: VENCIDO' : ''}.</p>`;
    carregarStatusCertificado();
  } catch (e) {
    resultado.innerHTML = `<p class="erro">Falha de conexão ao enviar o certificado: ${e}. Tente de novo.</p>`;
  } finally {
    btn.disabled = false;
    btn.textContent = 'Carregar certificado';
  }
}
function mostrarEmissao(dados) {
  emissaoAtualId = dados.id;
  document.getElementById('btn-assinar').disabled = dados.estado !== 'montado';
  const div = document.getElementById('resultado');
  div.innerHTML = `
    <p><span class="badge">${dados.estado}</span> nDPS ${dados.n_dps} — série ${dados.serie}</p>
    <h3>Resumo</h3>
    <pre>${JSON.stringify({apelido: dados.apelido, tomador: dados.tomador, valor: dados.valor, descricao: dados.descricao, chave_acesso: dados.chave_acesso}, null, 2)}</pre>
    <h3>XML</h3>
    <pre>${(dados.xml || '').replace(/</g, '&lt;')}</pre>
  `;
  carregarEnvios();
}
async function gerar() {
  const div = document.getElementById('resultado');
  const vinculoId = document.getElementById('vinculo').value;
  const competencia = document.getElementById('competencia').value;
  const valor = parseFloat(document.getElementById('valor').value);
  if (!vinculoId) { div.innerHTML = '<p class="erro">Escolha um vinculo (fornecedor) na lista antes de gerar.</p>'; return; }
  if (!competencia) { div.innerHTML = '<p class="erro">Escolha o mes de competencia.</p>'; return; }
  if (!(valor > 0)) { div.innerHTML = '<p class="erro">Informe um valor maior que zero.</p>'; return; }
  const corpo = {
    vinculo_id: vinculoId,
    competencia: competencia,
    valor: valor,
    ordem: document.getElementById('ordem').value || null,
    aliq_sn: document.getElementById('aliq_sn').value ? parseFloat(document.getElementById('aliq_sn').value) : null,
    tpAmb: document.getElementById('tpAmb').value,
  };
  const r = await fetch('/api/dps', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(corpo) });
  const dados = await r.json();
  if (!r.ok) { div.innerHTML = `<p class="erro">Erro: ${formatarErro(dados.detail)}</p>`; return; }
  mostrarEmissao(dados);
}
async function assinar() {
  if (!emissaoAtualId) return;
  const r = await fetch(`/api/dps/${emissaoAtualId}/assinar`, { method: 'POST' });
  const dados = await r.json();
  if (!r.ok) { document.getElementById('resultado').innerHTML += `<p class="erro">Erro: ${formatarErro(dados.detail)}</p>`; return; }
  mostrarEmissao(dados);
}

async function importarCsv() {
  const arquivo = document.getElementById('csv-arquivo').files[0];
  if (!arquivo) { alert('Selecione um arquivo .csv.'); return; }
  const fd = new FormData();
  fd.append('arquivo', arquivo);
  const div = document.getElementById('csv-resultado');
  div.innerHTML = '<p>Importando...</p>';
  const r = await fetch('/api/dps/importar-csv', { method: 'POST', body: fd });
  const dados = await r.json();
  if (!r.ok) { div.innerHTML = `<p class="erro">Erro: ${formatarErro(dados.detail)}</p>`; return; }
  const linhasHtml = dados.linhas.map(l => `
    <tr>
      <td>${l.linha}</td>
      <td>${l.apelido}</td>
      <td>${l.ok ? '<span class="badge">ok — nDPS ' + l.n_dps + '</span>' : '<span class="erro">erro</span>'}</td>
      <td>${l.mensagem || ''}</td>
    </tr>`).join('');
  div.innerHTML = `
    <p><strong>${dados.sucesso}</strong> criada(s), <strong>${dados.erro}</strong> com erro, de ${dados.total} linha(s).</p>
    <table style="width:100%; border-collapse: collapse; font-size: .85rem;">
      <tr><th align="left">Linha</th><th align="left">Apelido</th><th align="left">Status</th><th align="left">Detalhe</th></tr>
      ${linhasHtml}
    </table>`;
  carregarVinculos();
}

async function carregarEnvios() {
  if (!emissaoAtualId) return;
  const r = await fetch(`/api/dps/${emissaoAtualId}/envios`);
  const envios = await r.json();
  const div = document.getElementById('envio-resultado');
  if (envios.length === 0) { div.innerHTML = ''; return; }
  const linhas = envios.map(e => `
    <tr>
      <td>${e.canal}</td>
      <td><span class="badge">${e.status}</span></td>
      <td>${e.tentativas}</td>
      <td>${e.status === 'pendente' ? `<button onclick="marcarEnvio('${e.id}','enviado')">Marcar enviado</button> <button onclick="marcarEnvio('${e.id}','falha')">Marcar falha</button>` : ''}</td>
    </tr>`).join('');
  div.innerHTML = `<table style="width:100%; border-collapse: collapse; font-size:.8rem; margin-top:.6rem;">
    <tr><th align="left">Canal</th><th align="left">Status</th><th align="left">Tentativas</th><th></th></tr>${linhas}</table>`;
}
async function marcarEnvio(envioId, tipo) {
  await fetch(`/api/envios/${envioId}/marcar-${tipo === 'enviado' ? 'enviado' : 'falha'}`, { method: 'POST' });
  carregarEnvios();
}
async function baixarXml() {
  if (!emissaoAtualId) { alert('Gere uma nota primeiro.'); return; }
  window.open(`/api/dps/${emissaoAtualId}/download`, '_blank');
  await fetch(`/api/dps/${emissaoAtualId}/envios`, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({canal: 'download'}) });
  carregarEnvios();
}
async function mostrarMensagemPronta() {
  if (!emissaoAtualId) { alert('Gere uma nota primeiro.'); return; }
  const r = await fetch(`/api/dps/${emissaoAtualId}/mensagem-pronta`);
  const dados = await r.json();
  if (!r.ok) { document.getElementById('envio-resultado').innerHTML = `<p class="erro">Erro: ${formatarErro(dados.detail)}</p>`; return; }
  await fetch(`/api/dps/${emissaoAtualId}/envios`, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({canal: 'mensagem_pronta'}) });
  document.getElementById('envio-resultado').innerHTML = `<pre>${dados.mensagem}</pre>`;
  carregarEnvios();
}
async function registrarEnvio(canal) {
  if (!emissaoAtualId) { alert('Gere uma nota primeiro.'); return; }
  const r = await fetch(`/api/dps/${emissaoAtualId}/envios`, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({canal}) });
  const dados = await r.json();
  if (!r.ok) { document.getElementById('envio-resultado').innerHTML = `<p class="erro">Erro: ${formatarErro(dados.detail)}</p>`; return; }
  carregarEnvios();
}

async function registrarPagamento() {
  const corpo = {
    vinculo_id: document.getElementById('pgto-vinculo').value,
    competencia: document.getElementById('pgto-competencia').value,
    valor: parseFloat(document.getElementById('pgto-valor').value),
    data_recebimento: document.getElementById('pgto-data').value || null,
  };
  const r = await fetch('/api/pagamentos', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(corpo) });
  const dados = await r.json();
  const div = document.getElementById('pgto-resultado');
  if (!r.ok) { div.innerHTML = `<p class="erro">Erro: ${formatarErro(dados.detail)}</p>`; return; }
  div.innerHTML = `<p>Registrado: ${dados.apelido} — ${dados.competencia} — R$ ${dados.valor.toFixed(2)}</p>`;
}
async function registrarDespesa() {
  const corpo = {
    categoria: document.getElementById('desp-categoria').value,
    competencia: document.getElementById('desp-competencia').value,
    valor: parseFloat(document.getElementById('desp-valor').value),
  };
  const r = await fetch('/api/despesas', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(corpo) });
  const dados = await r.json();
  const div = document.getElementById('desp-resultado');
  if (!r.ok) { div.innerHTML = `<p class="erro">Erro: ${formatarErro(dados.detail)}</p>`; return; }
  div.innerHTML = `<p>Registrada: ${dados.categoria} — ${dados.competencia} — R$ ${dados.valor.toFixed(2)}</p>`;
}
const MESES_ABREV = ['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez'];
function tabelaStatus(titulo, linhas) {
  if (linhas.length === 0) return `<h3>${titulo}</h3><p style="font-size:.85rem;color:#666;">Sem lançamentos neste ano.</p>`;
  const cabecalho = `<tr><th align="left">${titulo}</th>${MESES_ABREV.map(m => `<th align="right">${m}</th>`).join('')}<th align="right">Total</th></tr>`;
  const corpo = linhas.map(l => `<tr><td>${l.rotulo}</td>${l.meses.map(v => `<td align="right">${v ? v.toFixed(2) : '—'}</td>`).join('')}<td align="right"><strong>${l.total.toFixed(2)}</strong></td></tr>`).join('');
  return `<table style="width:100%; border-collapse: collapse; font-size: .78rem; margin-bottom: 1rem;">${cabecalho}${corpo}</table>`;
}
async function carregarStatus() {
  const ano = document.getElementById('status-ano').value;
  const div = document.getElementById('status-resultado');
  div.innerHTML = '<p>Carregando...</p>';
  const r = await fetch(`/api/painel/status?ano=${encodeURIComponent(ano)}`);
  const dados = await r.json();
  if (!r.ok) { div.innerHTML = `<p class="erro">Erro: ${formatarErro(dados.detail)}</p>`; return; }
  div.innerHTML =
    tabelaStatus('NF Geradas', dados.notas_geradas) +
    tabelaStatus('Pagamentos recebidos', dados.pagamentos_recebidos) +
    tabelaStatus('Despesas', dados.despesas);
}

verificarSessao();
</script>
</body>
</html>"""
