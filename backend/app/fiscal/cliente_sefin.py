"""
Cliente HTTP (mTLS) para a API Sefin Nacional — porta de integracao/
submit_dps.py, consultar_dps.py, consultar_nfse.py e cancelar_nfse.py.

Os quatro scripts originais repetiam, cada um à sua maneira: o dict BASES
(URL de homologação/produção), a extração do .pfx pra PEM temporário, e a
montagem de requests com `cert=(cert_path, key_path)`. Consolidado aqui numa
classe única — reduz a chance de um deles ficar com uma URL desatualizada
ou um timeout diferente sem os outros acompanharem.

IMPORTANTE — nada disso foi tocado, só copiado com o mesmo comportamento:
- submit_dps.py está documentado como "AINDA NÃO TESTADO contra a API de
  verdade" — `submeter_dps` aqui carrega essa mesma incerteza. Não passou a
  ser "testado" só por ter sido portado.
- cancelar_nfse.py FOI testado e usado de verdade (ver
  output/CANCELAMENTO_..._112223684.xml) — `enviar_evento_cancelamento`
  aqui replica exatamente o payload/URL que funcionou.
- consultar_dps.py fazia uma varredura sequencial pra achar o próximo nDPS
  livre. Isso é mantido aqui só como ferramenta de RECONCILIAÇÃO/diagnóstico
  (`proximo_ndps_livre_por_varredura`) — não é mais a fonte de verdade do
  próximo nDPS: essa fonte é o nosso Postgres (UNIQUE(prestador,serie,nDPS),
  ver app/models.py e a correção feita na revisão do Opus sobre nDPS não
  ser "reservado" pela Sefin).

Nenhum teste de regressão bate de verdade na rede — ver
backend/tests/test_cliente_sefin.py, que verifica a CONSTRUÇÃO da
requisição (URL, corpo, gzip+base64) com `requests` mockado.
"""
import base64
import gzip
from dataclasses import dataclass

import requests

from app.fiscal.certificado import pem_temporario

BASES = {
    "2": "https://sefin.producaorestrita.nfse.gov.br/API/SefinNacional",  # homologação
    "1": "https://sefin.nfse.gov.br/SefinNacional",  # produção
}

URL_SUBMISSAO = {
    "2": f"{BASES['2']}/nfse",
    "1": f"{BASES['1']}/nfse",
}

ADN_BASES = {
    "2": "https://adn.producaorestrita.nfse.gov.br",
    "1": "https://adn.nfse.gov.br",
}


@dataclass
class RespostaSefin:
    status_code: int
    dados: dict | None
    texto_bruto: str | None = None

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 300


class ClienteSefin:
    """Uma instância por (private_key, cert, tpAmb) — reaproveitável para
    várias chamadas (o PEM temporário é recriado a cada chamada, já que o
    original também recriava a cada execução de script; não guardamos
    segredo em disco além do tempo de uma requisição)."""

    def __init__(self, private_key, cert, tpAmb: str, timeout: int = 40):
        if tpAmb not in ("1", "2"):
            raise ValueError("tpAmb precisa ser '1' (produção) ou '2' (homologação)")
        self.private_key = private_key
        self.cert = cert
        self.tpAmb = tpAmb
        self.timeout = timeout

    @property
    def base(self) -> str:
        return BASES[self.tpAmb]

    def _post(self, url: str, json_body: dict) -> RespostaSefin:
        with pem_temporario(self.private_key, self.cert) as (cert_path, key_path):
            resp = requests.post(url, json=json_body, cert=(cert_path, key_path), timeout=self.timeout)
        return self._para_resposta(resp)

    def _get(self, url: str, headers: dict | None = None) -> requests.Response:
        with pem_temporario(self.private_key, self.cert) as (cert_path, key_path):
            return requests.get(url, cert=(cert_path, key_path), timeout=self.timeout, headers=headers)

    @staticmethod
    def _para_resposta(resp: requests.Response) -> RespostaSefin:
        try:
            return RespostaSefin(status_code=resp.status_code, dados=resp.json())
        except ValueError:
            return RespostaSefin(status_code=resp.status_code, dados=None, texto_bruto=resp.text)

    # --- submissão (integracao/submit_dps.py) ---
    def submeter_dps(self, xml_assinado: bytes) -> RespostaSefin:
        """POST {base}/nfse com {"dpsXmlGZipB64": ...}. Sucesso (201): dados
        traz chaveAcesso e nfseXmlGZipB64 (gzip+base64 da NFS-e gerada)."""
        b64 = base64.b64encode(gzip.compress(xml_assinado)).decode("ascii")
        return self._post(URL_SUBMISSAO[self.tpAmb], {"dpsXmlGZipB64": b64})

    @staticmethod
    def extrair_nfse_xml(resposta: RespostaSefin) -> bytes | None:
        if not resposta.dados:
            return None
        b64 = resposta.dados.get("nfseXmlGZipB64")
        return gzip.decompress(base64.b64decode(b64)) if b64 else None

    # --- consulta de DPS por Id (integracao/consultar_dps.py) ---
    def consultar_dps_existe(self, id_dps: str) -> int:
        """GET {base}/dps/{IdDPS} -> devolve o status HTTP (200 = existe NFS-e
        pra essa DPS, 404 = não existe)."""
        resp = self._get(f"{self.base}/dps/{id_dps}")
        return resp.status_code

    def proximo_ndps_livre_por_varredura(self, montar_id_dps_fn, max_tentativas: int = 50) -> int | None:
        """Ferramenta de RECONCILIAÇÃO/diagnóstico — varre nDPS=1..max até
        achar um 404. `montar_id_dps_fn(n) -> str` monta o Id pra cada n
        testado (normalmente app.fiscal.dps.montar_id_dps parcialmente
        aplicado). NÃO é a fonte de verdade do próximo nDPS (essa é o
        Postgres) — usar só pra conferir se o banco e a Sefin concordam."""
        for n in range(1, max_tentativas + 1):
            status = self.consultar_dps_existe(montar_id_dps_fn(n))
            if status == 404:
                return n
            if status != 200:
                return None
        return None

    # --- consulta de NFS-e emitida (integracao/consultar_nfse.py) ---
    def consultar_nfse(self, chave: str) -> RespostaSefin:
        """GET {base}/nfse/{chaveAcesso}."""
        resp = self._get(f"{self.base}/nfse/{chave}")
        return self._para_resposta(resp)

    def baixar_danfse(self, chave: str) -> bytes | None:
        """Tenta, em ordem, os endpoints conhecidos de DANFSe (o /DANFSe da
        própria Sefin devolve 501 — o serviço é do ADN, não da Sefin).
        Devolve os bytes do PDF, ou None se nenhum candidato respondeu."""
        candidatos = [
            f"{ADN_BASES[self.tpAmb]}/danfse/{chave}",
            f"{ADN_BASES[self.tpAmb]}/contribuintes/danfse/{chave}",
            f"{ADN_BASES[self.tpAmb]}/contribuintes/DANFSe/{chave}",
            f"{ADN_BASES[self.tpAmb]}/danfse/nfse/{chave}",
            f"{self.base}/DANFSe/{chave}",
        ]
        for url in candidatos:
            try:
                resp = self._get(url, headers={"Accept": "application/pdf, */*"})
            except requests.exceptions.RequestException:
                continue
            if resp.status_code == 200 and resp.content[:4] == b"%PDF":
                return resp.content
            if resp.status_code == 200 and "json" in (resp.headers.get("content-type") or ""):
                try:
                    data = resp.json()
                except ValueError:
                    continue
                for v in data.values():
                    if isinstance(v, str) and len(v) > 1000:
                        raw = base64.b64decode(v)
                        if raw[:4] == b"%PDF":
                            return raw
        return None

    # --- evento de cancelamento (integracao/cancelar_nfse.py) ---
    def enviar_evento_cancelamento(self, chave: str, xml_assinado: bytes) -> RespostaSefin:
        """POST {base}/nfse/{chaveAcesso}/eventos com
        {"pedidoRegistroEventoXmlGZipB64": ...}. Sucesso (201): dados pode
        trazer eventoXmlGZipB64 e "alertas"."""
        b64 = base64.b64encode(gzip.compress(xml_assinado)).decode("ascii")
        url = f"{self.base}/nfse/{chave}/eventos"
        return self._post(url, {"pedidoRegistroEventoXmlGZipB64": b64})
