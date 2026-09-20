#!/usr/bin/env python3
"""
Marco 1, último passo: migra os 5 fornecedores hoje hardcoded em
`integracao/build_dps.py` (FORNECEDORES) para linhas reais no banco —
1 Prestador (a Raiana, compartilhado pelos 5), 4 Tomadores distintos
(AWIN e AWIN Rchlo são o MESMO tomador, CNPJ 14182871000188 — ver nota em
app/models.py) e 5 vínculos PrestadorTomador (um por fornecedor_key).

Idempotente: pode rodar de novo sem duplicar (upsert por CNPJ/apelido).

Sobre a conexão: este é um script administrativo de seed/migração, não uma
requisição de aplicação — por isso conecta como o role `postgres`
(superusuário local, bypassa RLS por natureza), e não como `nfse_dev` (o
role de runtime da aplicação, restrito por RLS — ver alembic/versions/*_rls).
Rodar um script assim pelo role de runtime exigiria descobrir o UUID do
prestador ANTES de ele existir só pra poder setar
`app.current_prestador_id`, o que não faz sentido para uma carga inicial.
Em produção, esse mesmo padrão vale: seed/admin roda com um role
privilegiado à parte; a aplicação nunca ganha bypass de RLS.

Uso:
    python3 scripts/migrar_fornecedores.py [--database-url postgresql://postgres:...]
"""
import argparse
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/ -> app...
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "integracao"))  # onde mora build_dps.py (dentro do repo)

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import Prestador, PrestadorTomador, Tomador  # noqa: E402

from build_dps import FORNECEDORES  # noqa: E402

DEFAULT_ADMIN_DATABASE_URL = "postgresql+psycopg://postgres:postgres_dev_local@localhost:5432/nfse_saas"


def _only_digits(s: str) -> str:
    return "".join(c for c in s if c.isdigit())


def _endereco_kwargs(pessoa: dict) -> dict:
    return {
        "cod_municipio": pessoa["cMun"],
        "cep": pessoa.get("CEP"),
        "logradouro": pessoa.get("xLgr"),
        "numero": pessoa.get("nro"),
        "complemento": pessoa.get("xCpl"),
        "bairro": pessoa.get("xBairro"),
    }


def migrar(db: Session) -> None:
    # --- 1) Prestador (um só, compartilhado pelos 5 fornecedores) ---
    # Todos os `prest` em FORNECEDORES são idênticos (mesma Raiana) — pega o
    # primeiro como referência e confirma que os outros batem, pra não
    # mascarar um dado divergente que a gente não previu.
    primeiro_prest = next(iter(FORNECEDORES.values()))["prest"]
    for chave, cfg in FORNECEDORES.items():
        if cfg["prest"]["CNPJ"] != primeiro_prest["CNPJ"]:
            raise ValueError(
                f"Fornecedor '{chave}' tem um prestador com CNPJ diferente do esperado — "
                "a suposição de 'prestador único compartilhado' não vale mais, revisar o script."
            )

    cnpj_prest = _only_digits(primeiro_prest["CNPJ"])
    prestador = db.query(Prestador).filter_by(cpf_cnpj=cnpj_prest).one_or_none()
    if prestador is None:
        prestador = Prestador(
            id=uuid.uuid4(),
            cpf_cnpj=cnpj_prest,
            inscricao_municipal=primeiro_prest.get("IM"),
            razao_social=primeiro_prest["xNome"],
            telefone=primeiro_prest.get("fone"),
            email=primeiro_prest.get("email"),
            op_simples_nacional=primeiro_prest.get("opSimpNac"),
            regime_apuracao_sn=primeiro_prest.get("regApTribSN"),
            regime_especial_trib=primeiro_prest.get("regEspTrib"),
            **_endereco_kwargs(primeiro_prest),
        )
        db.add(prestador)
        db.flush()
        print(f"  + Prestador criado: {prestador.razao_social} ({prestador.id})")
    else:
        print(f"  = Prestador já existia: {prestador.razao_social} ({prestador.id})")

    # --- 2) Tomadores (catálogo central, um por CNPJ distinto) ---
    tomadores_por_cnpj: dict[str, Tomador] = {}
    for chave, cfg in FORNECEDORES.items():
        toma = cfg["toma"]
        cnpj_toma = _only_digits(toma["CNPJ"])
        if cnpj_toma in tomadores_por_cnpj:
            continue
        tomador = db.query(Tomador).filter_by(cnpj=cnpj_toma).one_or_none()
        if tomador is None:
            tomador = Tomador(
                id=uuid.uuid4(),
                cnpj=cnpj_toma,
                razao_social=toma["xNome"],
                status="aprovado",
                **_endereco_kwargs(toma),
            )
            db.add(tomador)
            db.flush()
            print(f"  + Tomador criado: {tomador.razao_social} ({tomador.cnpj})")
        else:
            print(f"  = Tomador já existia: {tomador.razao_social} ({tomador.cnpj})")
        tomadores_por_cnpj[cnpj_toma] = tomador

    # --- 3) Vínculos prestador_tomador (um por fornecedor_key) ---
    for chave, cfg in FORNECEDORES.items():
        apelido = cfg["nome_curto"]
        vinculo = (
            db.query(PrestadorTomador)
            .filter_by(prestador_id=prestador.id, apelido=apelido)
            .one_or_none()
        )
        if vinculo is not None:
            print(f"  = Vínculo já existia: {apelido}")
            continue

        serv = cfg["serv"]
        descricao = serv["descricao_template"]
        if cfg.get("dados_bancarios"):
            # Mesma regra de montagem do build_dps.py: concatenado com " - ",
            # sem quebra de linha (a API normaliza quebras e invalida a
            # assinatura — ver comentário original). Guardamos o template já
            # com o trecho bancário embutido, pra Marco 3 reusar sem precisar
            # reimplementar essa concatenação a partir de uma coluna separada
            # que este schema não tem.
            descricao = descricao + " - " + cfg["dados_bancarios"]

        tomador = tomadores_por_cnpj[_only_digits(cfg["toma"]["CNPJ"])]
        vinculo = PrestadorTomador(
            id=uuid.uuid4(),
            prestador_id=prestador.id,
            tomador_id=tomador.id,
            apelido=apelido,
            cod_local_prestacao=serv["cLocPrestacao"],
            cod_trib_nacional=serv["cTribNac"],
            cod_trib_municipal=serv.get("cTribMun"),
            template_descricao=descricao,
            metodo_captura_valor="manual",
            serie=cfg["serie"],
            requer_revisao=True,
            ativo=True,
        )
        db.add(vinculo)
        db.flush()
        print(f"  + Vínculo criado: {apelido} -> {tomador.razao_social}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=DEFAULT_ADMIN_DATABASE_URL)
    args = parser.parse_args()

    engine = create_engine(args.database_url, future=True)
    with Session(engine) as db:
        print(f"Migrando {len(FORNECEDORES)} fornecedores de integracao/build_dps.py...")
        migrar(db)
        db.commit()
        print("OK — commit feito.")

        totais = {
            "prestador": db.query(Prestador).count(),
            "tomador": db.query(Tomador).count(),
            "prestador_tomador": db.query(PrestadorTomador).count(),
        }
        print(f"Totais no banco agora: {totais}")


if __name__ == "__main__":
    main()
