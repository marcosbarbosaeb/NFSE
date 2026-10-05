import { nomeDoPais } from "./paises"

export function soDigitos(texto: string | null | undefined): string {
  return (texto ?? "").replace(/\D/g, "")
}

/** O documento de um tomador, como a pessoa lê: CNPJ com máscara ou, pra
 * empresa de fora do Brasil, "NIF 123 · Irlanda". Vazio = sem identificação
 * (cliente só de controle). */
export function documentoDoTomador(t: { cnpj?: string | null; nif?: string | null; pais?: string | null }): string {
  if (t.cnpj) return formatarDocumento(t.cnpj)
  return [t.nif ? `NIF ${t.nif}` : "", t.pais ? nomeDoPais(t.pais) : ""].filter(Boolean).join(" · ")
}

/** 12345678000190 -> 12.345.678/0001-90 (CPF: 123.456.789-01). Outro tamanho volta como veio. */
export function formatarDocumento(doc: string | null | undefined): string {
  const d = soDigitos(doc)
  if (d.length === 14) return d.replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/, "$1.$2.$3/$4-$5")
  if (d.length === 11) return d.replace(/^(\d{3})(\d{3})(\d{3})(\d{2})$/, "$1.$2.$3-$4")
  return doc ?? ""
}

/** Máscara enquanto digita (até 14 dígitos). */
export function mascararCnpj(texto: string): string {
  const d = soDigitos(texto).slice(0, 14)
  return d
    .replace(/^(\d{2})(\d)/, "$1.$2")
    .replace(/^(\d{2})\.(\d{3})(\d)/, "$1.$2.$3")
    .replace(/\.(\d{3})(\d)/, ".$1/$2")
    .replace(/(\d{4})(\d)/, "$1-$2")
}

/** Máscara de CEP (00000-000). */
export function mascararCep(texto: string): string {
  const d = soDigitos(texto).slice(0, 8)
  return d.length > 5 ? `${d.slice(0, 5)}-${d.slice(5)}` : d
}
