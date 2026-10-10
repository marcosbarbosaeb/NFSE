import type { PermissaoContador, PermissaoInfo, Usuario } from "./types"

// Contador com permissões (06/10/2026). A lista vem do backend
// (app/services/acesso.py); esta é só a reserva pra tela nunca ficar sem nome.
export const PERMISSOES_PADRAO: PermissaoInfo[] = [
  { id: "emitir", nome: "Gerar e cancelar notas", descricao: "Criar, assinar, enviar à prefeitura e cancelar notas — uma a uma ou em lote." },
  { id: "enviar", nome: "Enviar notas aos clientes", descricao: "Mandar as notas por e-mail, WhatsApp ou Google Drive e marcar como enviadas." },
  { id: "tomadores", nome: "Cadastrar e editar tomadores", descricao: "Incluir, alterar e arquivar os clientes para quem a empresa emite." },
  { id: "financeiro", nome: "Lançar e conciliar no Financeiro", descricao: "Registrar recebimentos e despesas, importar extrato, conciliar e fechar o mês." },
  { id: "empresa", nome: "Alterar dados da empresa", descricao: "Dados cadastrais, alíquota, certificado A1 e preferências de emissão." },
  { id: "documentos", nome: "Documentos da empresa", descricao: "Ver, enviar e substituir os documentos da empresa (contrato social, documentos dos sócios, certidões). Apagar, só o dono." },
]

const CURTO: Record<PermissaoContador, string> = {
  emitir: "gerar notas",
  enviar: "enviar notas",
  tomadores: "tomadores",
  financeiro: "financeiro",
  empresa: "dados da empresa",
  documentos: "documentos da empresa",
}

export const nomeCurto = (p: PermissaoContador) => CURTO[p] ?? p

/** "ver, gerar notas e financeiro" */
export function resumoPermissoes(permissoes: PermissaoContador[]): string {
  const itens = ["ver tudo", ...permissoes.map(nomeCurto)]
  if (itens.length === 1) return "só ver"
  return `${itens.slice(0, -1).join(", ")} e ${itens[itens.length - 1]}`
}

export const ehContador = (u: Usuario | null | undefined) => u?.papel === "contador"

/** O login pode fazer isso na empresa ativa? (dono pode tudo) */
export const pode = (u: Usuario | null | undefined, permissao: PermissaoContador) =>
  !ehContador(u) || (u?.permissoes ?? []).includes(permissao)

export function quando(iso: string | null | undefined): string {
  if (!iso) return ""
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ""
  return d.toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" })
}
