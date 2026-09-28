// Textos e regras das ações em lote (29/09/2026) — ver components/LotePainel.tsx.
import type { AcaoLote, Lote } from "./types"

/** Nome da ação num título ("Envio à prefeitura"). */
export const NOME_ACAO: Record<AcaoLote, string> = {
  assinar: "Assinatura",
  submeter: "Envio à prefeitura",
  email: "Envio ao fornecedor por e-mail",
  email_geral: "Envio aos e-mails gerais",
}

/** Verbo da ação numa frase ("prontas para enviar à prefeitura"). */
export const VERBO_ACAO: Record<AcaoLote, string> = {
  assinar: "assinar",
  submeter: "enviar à prefeitura",
  email: "enviar ao fornecedor por e-mail",
  email_geral: "enviar aos e-mails gerais",
}

export const POR_QUE_NENHUMA: Record<AcaoLote, string> = {
  assinar: "Só dá pra assinar notas emitidas que ainda não foram assinadas.",
  submeter: "Só vão à prefeitura notas já assinadas (ou que voltaram com erro). Assine antes.",
  email:
    "Só vão por e-mail notas autorizadas pela prefeitura (ou de teste) que ainda não foram enviadas, de tomadores que recebem por e-mail.",
  email_geral: "Só vão notas autorizadas pela prefeitura (ou de teste) que ainda não foram enviadas aos e-mails gerais.",
}

export const LOTE_RODANDO = (l: Lote) => l.status === "fila" || l.status === "executando"
