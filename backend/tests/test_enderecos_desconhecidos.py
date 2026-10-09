"""Endereços que não existem (09/10/2026): robôs pediam /.env, /.git/config,
/wp-json/... e recebiam 200 com a página do app (nenhum arquivo de verdade
saía — conferido em produção). Agora: 404 pra caminho com "." no começo de
um pedaço e pra tudo que não é tela do app nem arquivo do build."""
import pytest
from fastapi.testclient import TestClient

from app.main import app

cliente = TestClient(app)


@pytest.mark.parametrize("caminho", [
    "/.env", "/.git/config", "/backend/.env", "/.well-known/x", "/wp-json/", "/wp-json/gravitysmtp/v1/tests/mock-data",
    "/test/phpinfo.php", "/php-info.php", "/wp-login.php", "/admin", "/qualquer-coisa", "/entrar/x", "/assets/nao-existe.js",
    "/robots.txt", "/sitemap.xml",
])
def test_desconhecido_da_404(caminho):
    r = cliente.get(caminho, follow_redirects=False)
    assert r.status_code == 404, caminho
    assert 'id="root"' not in r.text  # não é a página do app


@pytest.mark.parametrize("caminho", [
    "/", "/app", "/app/nfse", "/app/nfse/0f8c6c2e-6e62-4c43-9c7b-6b7cfa3d7f11", "/app/tomadores/novo", "/app/qualquer",
    "/entrar", "/cadastro", "/simulacao", "/confirmar-email", "/privacidade", "/termos", "/parceira/abc123",
])
def test_telas_do_app_continuam_abrindo(caminho):
    r = cliente.get(caminho + ("?cenario=beleza&gravacao=1" if caminho == "/simulacao" else ""), follow_redirects=False)
    assert r.status_code == 200 and 'id="root"' in r.text, caminho


def test_arquivo_do_build_continua_saindo():
    assert cliente.get("/favicon.svg").status_code == 200


def test_endereco_antigo_do_painel_leva_pro_novo():
    r = cliente.get("/tomadores/novo", follow_redirects=False)
    assert r.status_code == 301 and r.headers["location"] == "/app/tomadores/novo"


def test_api_inexistente_continua_404_em_json():
    r = cliente.get("/api/nao-existe")
    assert r.status_code == 404 and r.json()["detail"]
