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
        "versao": "2026.10.4",
        "data": "2026-10-08",
        "resumo": "Eu te mostro o que mudou desde a sua última visita.",
        "itens": [
            {"perfil": "todos", "titulo": "Passeio pelas novidades", "alvo": "novidades-sino",
             "texto": "Quando sair uma atualização, eu aviso ao entrar e ofereço um passeio rápido pelo que mudou. Não quer agora? É só fechar: "
                      "o sino aqui em cima guarda tudo."},
        ],
    },
    {
        "versao": "2026.10.3",
        "data": "2026-10-08",
        "resumo": "Painel próprio do contador, cara nova da Ana e WhatsApp no cadastro.",
        "itens": [
            {"perfil": "contador", "titulo": "Painel do contador, refeito", "link": "/app/atendimentos", "alvo": "contador-abas",
             "texto": "Três telas em volta da sua rotina: “Hoje” (uma fila só com o que fazer, do mais urgente pro menos), “Fechamento do mês” "
                      "(as empresas em colunas: falta conferir, aguardando pagamento, fechado) e “Empresas” (a carteira com os números)."},
            {"perfil": "contador", "titulo": "Ficha de cada empresa, sem entrar nela", "link": "/app/atendimentos", "alvo": "contador-busca",
             "texto": "Escolha a empresa no topo do painel e veja o que te interessa: notas mês a mês, limite do regime, fechamento, certificado, "
                      "o que tem pra fazer e o contato do responsável. “Entrar na empresa” continua lá pra quando for trabalhar nela."},
            {"perfil": "todos", "titulo": "A Ana de cara nova", "alvo": "marca",
             "texto": "Saiu a ilustração e ficou só o “A” da marca, no painel e nos e-mails. Clicar na marca, no topo do menu, volta pro começo."},
            {"perfil": "todos", "titulo": "WhatsApp no cadastro e no perfil", "link": "/app/conta", "alvo": "conta-whatsapp",
             "texto": "Agora o cadastro pede o seu WhatsApp, pra nossa equipe conseguir falar com você. Quem já tem conta pode informar em Minha conta › Perfil."},
            {"perfil": "empresa", "titulo": "Depois do teste grátis", "link": "/app/conta?aba=assinatura",
             "texto": "Nesta fase não há cobrança pelo painel: quando o teste termina, você pede a liberação em Minha conta › Assinatura "
                      "(um clique) e a nossa equipe autoriza o uso."},
        ],
    },
    {
        "versao": "2026.10.2",
        "data": "2026-10-08",
        "resumo": "Painel do contador, importação mais fácil de escolher e menos coisa obrigatória pra começar.",
        "itens": [
            {"perfil": "todos", "titulo": "Novidades e número da versão",
             "texto": "Esta tela: a cada atualização eu conto aqui o que mudou. O número da versão fica no rodapé do menu."},
            {"perfil": "contador", "titulo": "Painel da carteira", "link": "/app/atendimentos",
             "texto": "Em “Painel do contador”: notas e faturamento do mês de todas as empresas, o que pede atenção (certificado vencendo, "
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
    versão que a pessoa já viu (pra bolinha do sino e pro passeio "o que
    mudou desde a sua última visita"). Quem nunca abriu as novidades (conta de
    antes de existir a tela) é tratado como quem viu até a penúltima: só a
    versão mais nova aparece como nova. Conta nova já nasce em dia
    (`marcar_em_dia`) — pra ela vale o tutorial normal."""
    if vista is None and len(VERSOES) > 1:
        vista = VERSOES[1]["versao"]
    quero = perfis | {"todos"}
    versoes = []
    for v in VERSOES:
        itens = [i for i in v["itens"] if i["perfil"] in quero]
        if itens:
            versoes.append({**v, "itens": itens, "nova": vista is None or _numero(v["versao"]) > _numero(vista)})
    return {"versao": VERSAO, "versoes": versoes, "novas": sum(1 for v in versoes if v["nova"])}


def marcar_em_dia(preferencias: dict | None) -> dict:
    """Preferências de quem acabou de criar a conta: nada é "novidade" pra
    quem está chegando agora."""
    return {**(preferencias or {}), "novidades": {"vista": VERSAO}}
