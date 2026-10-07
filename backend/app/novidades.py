"""Versões e novidades (08/10/2026).

Rotina combinada com o Marcos pra "não dar erros": tudo sobe primeiro pro
ambiente de teste, ganha um número de versão e uma lista do que mudou — "até
para informarmos aos usuários". Duas camadas:

- **Aqui**: o que o USUÁRIO percebe, em linguagem de leigo, por perfil
  ("novidades por perfil"): `todos`, `empresa` (quem emite nota / usa o
  financeiro) ou `contador`. Aparece na tela Novidades e no sino.
- **CHANGELOG.md** (raiz do repositório): o registro técnico, com o que o
  usuário não vê (migração, variável nova, o que conferir ao publicar).

Como numerar: `ano.mês.sequência` (2026.10.1, 2026.10.2...). A versão mais
nova vai SEMPRE no topo da lista; o número que o painel mostra no rodapé é o
dela. Publicar no real sem acrescentar a versão aqui = publicar sem número.
"""
from __future__ import annotations

PERFIS = ("todos", "empresa", "contador")

# A mais nova primeiro.
VERSOES: list[dict] = [
    {
        "versao": "2026.10.2",
        "data": "2026-10-08",
        "resumo": "Painel do contador, importação mais fácil de escolher e menos coisa obrigatória pra começar.",
        "itens": [
            {"perfil": "todos", "titulo": "Novidades e número da versão",
             "texto": "Esta tela: a cada atualização eu conto aqui o que mudou. O número da versão fica no rodapé do menu."},
            {"perfil": "contador", "titulo": "Painel da carteira", "link": "/app/atendimentos",
             "texto": "Em “Empresas que atendo”: notas e faturamento do mês de todas as empresas, o que pede atenção (certificado vencendo, "
                      "nota recusada, limite do MEI ou do Simples chegando) e o raio-x de cada uma, sem entrar em nenhuma."},
            {"perfil": "contador", "titulo": "Baixar as notas do mês de cada cliente", "link": "/app/atendimentos",
             "texto": "Um arquivo .zip com os XMLs e PDFs do mês, direto do painel. O dono da empresa vê no histórico que você baixou."},
            {"perfil": "empresa", "titulo": "Menos coisa obrigatória pra começar",
             "texto": "Dos dados da empresa, só o regime tributário é obrigatório — e eu busco na Receita pelo CNPJ. Endereço e alíquota "
                      "ficam opcionais: se deixar em branco, não trava nada."},
            {"perfil": "empresa", "titulo": "Importação: buscar, ordenar e marcar",
             "texto": "Ao trazer notas do Emissor Nacional dá pra buscar pelo nome, ordenar por valor, quantidade ou data e marcar de uma vez o que apareceu na busca."},
            {"perfil": "empresa", "titulo": "Notas em lote: guardar os arquivos é opcional", "link": "/app/nfse/lote",
             "texto": "Não vai baixar nem compartilhar agora? Marque a etapa como concluída e o mês fica fechado."},
            {"perfil": "empresa", "titulo": "Visão geral mais direta", "link": "/app",
             "texto": "Nos próximos passos, as notas do dia que vence primeiro já aparecem abertas; as dos dias seguintes ficam recolhidas. "
                      "E a linha das notas de vendedores mostra quantas já foram enviadas."},
        ],
    },
    {
        "versao": "2026.10.1",
        "data": "2026-10-07",
        "resumo": "Contador com acesso próprio, dados da empresa pelo CNPJ e desfazer importação.",
        "itens": [
            {"perfil": "empresa", "titulo": "Convide o seu contador", "link": "/app/empresa?aba=contador",
             "texto": "No menu do seu nome, “Convidar meu contador”: ele entra com o login dele e você escolhe o que ele pode fazer."},
            {"perfil": "empresa", "titulo": "Dados da empresa pelo CNPJ", "link": "/app/empresa",
             "texto": "O botão “Preencher pelo CNPJ” busca na Receita o endereço e o regime e preenche só o que estiver em branco."},
            {"perfil": "empresa", "titulo": "Desfazer uma importação",
             "texto": "Importou o extrato errado ou notas demais? Em Financeiro › Conciliação e em Empresa › Notas e e-mails tem "
                      "“Importações feitas”, com o botão Desfazer."},
            {"perfil": "empresa", "titulo": "Tela Empresa mais simples", "link": "/app/empresa",
             "texto": "De oito abas pra cinco: Dados da empresa, Notas e e-mails, Certificado, Contador e Mais opções."},
            {"perfil": "contador", "titulo": "Conta de contador, grátis", "link": "/app/atendimentos",
             "texto": "Sem CNPJ e sem mensalidade: você entra nas empresas dos clientes que te convidarem e vê as pendências de cada uma."},
            {"perfil": "contador", "titulo": "Bonificação", "link": "/app/atendimentos",
             "texto": "Você recebe uma parte da mensalidade de cada cliente que atende, enquanto atender."},
        ],
    },
]

VERSAO: str = VERSOES[0]["versao"]


def _numero(versao: str) -> tuple[int, ...]:
    return tuple(int(p) for p in versao.split(".") if p.isdigit())


def para(perfis: set[str], vista: str | None = None) -> dict:
    """As versões com o que interessa a quem está logado. `vista` = a última
    versão que a pessoa já abriu (pra bolinha do sino)."""
    quero = perfis | {"todos"}
    versoes = []
    for v in VERSOES:
        itens = [i for i in v["itens"] if i["perfil"] in quero]
        if itens:
            versoes.append({**v, "itens": itens, "nova": vista is None or _numero(v["versao"]) > _numero(vista)})
    return {"versao": VERSAO, "versoes": versoes, "novas": sum(1 for v in versoes if v["nova"])}
