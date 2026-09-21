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
import datetime
import uuid
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from app.config import get_settings
from app.database import definir_prestador_atual, get_db
from app.fiscal.dps import DescricaoIncompletaError
from app.models import Certificado, Emissao, Prestador, Usuario
from app.schemas import (
    CalendarioResponse,
    CertificadoStatus,
    DashboardResumoResponse,
    DespesaResponse,
    EmissaoListaLinha,
    EmissaoResponse,
    EnvioResponse,
    ErroResponse,
    GerarDpsRequest,
    ImportacaoCsvResponse,
    LoginRequest,
    MensagemProntaResponse,
    NotaVisualResponse,
    PagamentoResponse,
    PainelStatusResponse,
    PrestadorResponse,
    RegistrarDespesaRequest,
    RegistrarEnvioRequest,
    RegistrarPagamentoRequest,
    TomadorResponse,
    TrocarSenhaRequest,
    UsuarioResponse,
    VinculoCriarRequest,
    VinculoAtualizarRequest,
    VinculoDetalheResponse,
    VinculoResumo,
)
from app.services.certificados import (
    CertificadoNaoEncontradoError,
    carregar_certificado,
    certificado_vencido,
    salvar_certificado,
)
from app.services.calendario import eventos_calendario
from app.services.dashboard import resumo_mes
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
from app.services.listagens import listar_despesas, listar_emissoes, listar_pagamentos
from app.services.motor_emissao import (
    EmissaoJaExisteError,
    TransicaoInvalidaError,
    assinar as assinar_emissao,
    criar_rascunho,
    montar as montar_emissao,
)
from app.services.nota_visual import montar_nota_visual
from app.services.pagamentos import registrar_pagamento
from app.services.painel_status import painel_status_completo
from app.services.tomadores import CnpjJaCadastradoError, buscar_tomador, criar_tomador, listar_catalogo
from app.services.usuarios import SenhaAtualIncorretaError, autenticar, trocar_senha
from app.services.vinculos import (
    ApelidoJaExisteError,
    atualizar_vinculo,
    buscar_vinculo,
    criar_vinculo,
    listar_vinculos_ativos,
)

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


@app.post("/api/auth/trocar-senha", responses={400: {"model": ErroResponse}, 401: {"model": ErroResponse}})
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
    db.commit()
    return {"ok": True}


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


@app.get("/api/vinculos/{vinculo_id}", response_model=VinculoDetalheResponse, responses={404: {"model": ErroResponse}})
def api_ver_vinculo(vinculo_id: uuid.UUID, db: Session = Depends(db_sessao)):
    """Marco 13 — tela de detalhe do tomador ('Regras de emissão')."""
    vinculo = buscar_vinculo(db, vinculo_id)
    if vinculo is None:
        raise HTTPException(status_code=404, detail="Vínculo não encontrado (ou não pertence ao prestador ativo)")
    return vinculo


@app.post("/api/vinculos", response_model=VinculoDetalheResponse, responses={404: {"model": ErroResponse}, 409: {"model": ErroResponse}})
def api_criar_vinculo(req: VinculoCriarRequest, db: Session = Depends(db_sessao), prestador_id: uuid.UUID = Depends(prestador_atual_id)):
    """Marco 13 — 'usar um tomador pré-cadastrado' ou 'cadastrar meu
    próprio tomador' (ver VinculoCriarRequest) chegam aqui pela mesma
    rota; a diferença é só qual dos dois campos veio preenchido."""
    if req.novo_tomador is not None:
        try:
            tomador = criar_tomador(db, **req.novo_tomador.model_dump())
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
        )
    except ApelidoJaExisteError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
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
    try:
        vinculo = atualizar_vinculo(db, vinculo, **req.model_dump(exclude_unset=True))
    except ApelidoJaExisteError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.commit()
    return vinculo


@app.get("/api/tomadores", response_model=list[TomadorResponse])
def api_listar_tomadores(
    apenas_meus: bool = False,
    db: Session = Depends(db_sessao),
    prestador_id: uuid.UUID = Depends(prestador_atual_id),
):
    """Marco 13 — catálogo pra tela de Tomadores: 'Meus tomadores'
    (apenas_meus=true, só quem já tem vínculo ativo) ou 'Todos os
    tomadores' (catálogo compartilhado inteiro)."""
    return listar_catalogo(db, prestador_id=prestador_id, apenas_meus=apenas_meus)


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
    eventos = eventos_calendario(db, prestador_id, data_inicio, data_fim)
    return {"inicio": data_inicio, "fim": data_fim, "eventos": eventos}


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


@app.get("/api/dps", response_model=list[EmissaoListaLinha])
def api_listar_dps(
    ano: str | None = None,
    vinculo_id: uuid.UUID | None = None,
    estado: str | None = None,
    db: Session = Depends(db_sessao),
):
    """Marco 14 — tela 'NFS-e': lista completa (todas as competências),
    diferente de /api/painel/resumo-mes (só o mês corrente, pro dashboard).
    Todos os filtros são opcionais. GET puro, sem efeito colateral."""
    if ano is not None and (len(ano) != 4 or not ano.isdigit()):
        raise HTTPException(status_code=422, detail="ano deve estar no formato AAAA")
    return listar_emissoes(db, ano=ano, vinculo_id=vinculo_id, estado=estado)


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


@app.get("/api/dps/{emissao_id}/nota", response_model=NotaVisualResponse, responses={404: {"model": ErroResponse}})
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


@app.get("/api/pagamentos", response_model=list[PagamentoResponse])
def api_listar_pagamentos(
    ano: str | None = None,
    vinculo_id: uuid.UUID | None = None,
    db: Session = Depends(db_sessao),
):
    """Marco 14 — tela 'Recebimentos'. GET puro, sem efeito colateral."""
    if ano is not None and (len(ano) != 4 or not ano.isdigit()):
        raise HTTPException(status_code=422, detail="ano deve estar no formato AAAA")
    return listar_pagamentos(db, ano=ano, vinculo_id=vinculo_id)


@app.post("/api/despesas", response_model=DespesaResponse)
def api_registrar_despesa(req: RegistrarDespesaRequest, db: Session = Depends(db_sessao), prestador_id: uuid.UUID = Depends(prestador_atual_id)):
    """Marco 8 — registro manual de uma despesa (por categoria, não por
    fornecedor — ver seção 'Despesas' da planilha real)."""
    despesa = registrar_despesa(db, prestador_id, categoria=req.categoria, competencia=req.competencia, valor=req.valor)
    db.commit()
    return DespesaResponse(id=despesa.id, categoria=despesa.categoria, competencia=despesa.competencia, valor=float(despesa.valor))


@app.get("/api/despesas", response_model=list[DespesaResponse])
def api_listar_despesas(ano: str | None = None, db: Session = Depends(db_sessao)):
    """Marco 14 — tela 'Despesas'. GET puro, sem efeito colateral."""
    if ano is not None and (len(ano) != 4 or not ano.isdigit()):
        raise HTTPException(status_code=422, detail="ano deve estar no formato AAAA")
    return listar_despesas(db, ano=ano)


@app.get("/api/painel/status", response_model=PainelStatusResponse)
def api_painel_status(ano: str, db: Session = Depends(db_sessao), prestador_id: uuid.UUID = Depends(prestador_atual_id)):
    """Marco 8 — 'painel de status, seria notas geradas e notas recebidas...
    igual a esta planilha' (item #7 da lista original). `ano` é obrigatório
    e no formato AAAA (o painel mostra um ano de cada vez, como a aba única
    da planilha real hoje mostra 2026)."""
    if len(ano) != 4 or not ano.isdigit():
        raise HTTPException(status_code=422, detail="ano deve estar no formato AAAA")
    return painel_status_completo(db, prestador_id, ano)


@app.get("/api/painel/resumo-mes", response_model=DashboardResumoResponse)
def api_painel_resumo_mes(
    competencia: str | None = None,
    db: Session = Depends(db_sessao),
    prestador_id: uuid.UUID = Depends(prestador_atual_id),
):
    """Marco 12 — dados da tela 'Visão geral' do novo frontend (ver
    app/services/dashboard.py pro porquê de cada campo e as aproximações
    assumidas). `competencia` é opcional (AAAA-MM); sem ela, usa o mês
    corrente. GET puro, sem efeito colateral."""
    if competencia is not None and (len(competencia) != 7 or competencia[4] != "-"):
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
    return FileResponse(indice)


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
        return FileResponse(candidato)
    return _index_html()
