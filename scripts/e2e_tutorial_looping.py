"""Reprodução do looping do tutorial (observações de teste, 10/10/2026).

Roda contra um servidor local (`uvicorn app.main:app --port 8765`, com o
frontend buildado) e uma conta sintética criada por `--semear`. Confere:
concluir o passeio "o que mudou", pular as dicas, sair e entrar de novo,
recarregar, trocar de empresa e abrir em outro navegador — e que nenhum balão
aparece de novo depois de concluído (o looping).

    python3 scripts/e2e_tutorial_looping.py --semear   # cria/zera a conta de teste
    python3 scripts/e2e_tutorial_looping.py            # roda o roteiro

Antes da correção: o passeio voltava ao convite depois do 4º item, sem fim.
"""
import datetime
import sys
import uuid

BASE = "http://127.0.0.1:8765"
EMAIL = "tutorial.e2e@exemplo.com.br"
SENHA = "senha-boa-123"
CONVITE = "Tem novidade desde a sua última visita"


def semear():
    sys.path.insert(0, "backend")
    from app.auth import hash_senha
    from app.database import SessionLocal, definir_prestador_atual
    from app.models import Prestador, Usuario, UsuarioPrestador
    from app.services.billing import criar_assinatura_trial

    db = SessionLocal()
    u = db.query(Usuario).filter_by(email=EMAIL).first()
    if u:
        u.preferencias = {"novidades": {"vista": "2026.10.6"}}
        db.commit()
        return
    ids = []
    for nome in ("EMPRESA TUTORIAL E2E", "SEGUNDA EMPRESA E2E"):
        pid = uuid.uuid4()
        definir_prestador_atual(db, pid)
        db.add(Prestador(id=pid, cpf_cnpj="9" + uuid.uuid4().int.__str__()[:13], razao_social=nome, cod_municipio="3106200",
                         op_simples_nacional="3", regime_apuracao_sn="1", regime_especial_trib="0", modulos=["emissor", "financeiro"],
                         perfis=["avulso"], perfil_respondido_em=datetime.datetime.now(datetime.timezone.utc)))
        db.flush()
        criar_assinatura_trial(db, pid)
        ids.append(pid)
    u = Usuario(id=uuid.uuid4(), prestador_id=ids[0], email=EMAIL, senha_hash=hash_senha(SENHA), email_confirmado=True,
                telefone="31999990000", preferencias={"novidades": {"vista": "2026.10.6"}})
    db.add(u)
    db.flush()
    for pid in ids:
        db.add(UsuarioPrestador(usuario_id=u.id, prestador_id=pid))
    db.commit()


def roteiro():
    from playwright.sync_api import sync_playwright

    falhas, log = [], []

    def dialogo(pg, espera=2500):
        pg.wait_for_timeout(espera)
        d = pg.locator("[role=dialog]")
        return d.first if d.count() else None

    def entrar(pg):
        pg.goto(BASE + "/entrar")
        pg.fill("input[type=email]", EMAIL)
        pg.fill("input[type=password]", SENHA)
        pg.get_by_role("button", name="Entrar", exact=True).click()
        pg.wait_for_url("**/app**")

    def clicar(d, *nomes):
        for nome in nomes:
            b = d.get_by_role("button", name=nome, exact=True)
            if b.count():
                b.first.evaluate("e => e.click()")
                return nome
        return None

    with sync_playwright() as p:
        br = p.chromium.launch()
        ctx = br.new_context(viewport={"width": 1280, "height": 900})
        pg = ctx.new_page()
        entrar(pg)
        # 1. boas-vindas: pular
        d = dialogo(pg)
        if d is None or d.get_attribute("aria-label") != "Oi! Eu sou a Ana.":
            falhas.append("boas-vindas não abriu na primeira entrada")
        else:
            clicar(d, "Pular")
        if dialogo(pg) is not None:
            falhas.append("depois de pular, outro balão abriu na Visão geral")
        # 2. vai pra Tomadores: dicas da tela (concluir) e depois o convite das novidades
        pg.get_by_role("link", name="Tomadores").first.click()
        vistos = {}
        for _ in range(30):
            d = dialogo(pg)
            if d is None:
                break
            titulo = d.get_attribute("aria-label")
            vistos[titulo] = vistos.get(titulo, 0) + 1
            log.append(f"{pg.url.replace(BASE, '')} :: {titulo}")
            if vistos[titulo] > 1:
                falhas.append(f"LOOPING: “{titulo}” apareceu de novo")
                break
            clicar(d, "Ver o que mudou", "Próximo", "Entendi")
        else:
            falhas.append("o passeio não terminou em 30 passos")
        if not any(t == CONVITE for t in vistos):
            # o convite só vem numa tela já vista: volta pra Visão geral
            pg.get_by_role("link", name="Visão geral").first.click()
            for _ in range(15):
                d = dialogo(pg)
                if d is None:
                    break
                titulo = d.get_attribute("aria-label")
                vistos[titulo] = vistos.get(titulo, 0) + 1
                log.append(f"{pg.url.replace(BASE, '')} :: {titulo}")
                if vistos[titulo] > 1:
                    falhas.append(f"LOOPING: “{titulo}” apareceu de novo")
                    break
                clicar(d, "Ver o que mudou", "Próximo", "Entendi")
        if CONVITE not in vistos:
            falhas.append("o convite das novidades não apareceu")
        # 3. nada reaparece: Visão geral, recarregar, sair e entrar, trocar de empresa
        for nome, acao in (
            ("Visão geral", lambda: pg.goto(BASE + "/app")),
            ("recarregar", lambda: pg.reload()),
            ("Tomadores de novo", lambda: pg.goto(BASE + "/app/tomadores")),
        ):
            acao()
            d = dialogo(pg)
            if d is not None:
                falhas.append(f"{nome}: reapareceu “{d.get_attribute('aria-label')}”")
        pg.evaluate("fetch('/api/auth/logout', {method: 'POST'})")
        entrar(pg)
        d = dialogo(pg)
        if d is not None:
            falhas.append(f"sair e entrar: reapareceu “{d.get_attribute('aria-label')}”")
        outra = pg.evaluate("fetch('/api/empresas').then(r => r.json()).then(l => (l.empresas || l).find(e => !e.ativa))")
        if outra:
            pg.evaluate(f"fetch('/api/empresas/{outra['id']}/ativar', {{method: 'POST'}})")
            pg.goto(BASE + "/app")
            d = dialogo(pg)
            if d is not None:
                falhas.append(f"trocar de empresa: reapareceu “{d.get_attribute('aria-label')}”")
        else:
            falhas.append("não achei a segunda empresa para trocar")
        ctx.close()
        # 4. outro navegador (sem nada guardado): as dicas vistas vêm da conta
        ctx2 = br.new_context(viewport={"width": 1280, "height": 900})
        pg2 = ctx2.new_page()
        entrar(pg2)
        for caminho in ("/app", "/app/tomadores"):
            pg2.goto(BASE + caminho)
            d = dialogo(pg2, 3000)
            if d is not None:
                falhas.append(f"outro navegador {caminho}: reapareceu “{d.get_attribute('aria-label')}”")
        br.close()
    print("\n".join(log))
    print("FALHAS:" if falhas else "OK: sem looping e nada reaparece.", *falhas, sep="\n- ")
    return 1 if falhas else 0


if __name__ == "__main__":
    if "--semear" in sys.argv:
        semear()
        print("conta de teste pronta")
    else:
        sys.exit(roteiro())
