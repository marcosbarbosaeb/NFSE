/** Nome de marca dos tomadores mais comuns (08/10/2026): no catálogo eles
 * estão com a razão social ("SHPS SERVICOS ADMINISTRATIVOS"), e quem procura
 * digita "Shopee". A marca entra no texto da busca e vira o apelido sugerido. */
export const MARCA_POR_CNPJ: Record<string, string> = {
  "35635824000112": "Shopee",
  "03007331000141": "Mercado Livre",
  "15436940000103": "Amazon",
  "47960950000121": "Magalu",
  "14182871000188": "Awin",
  "06990590000123": "Google",
  "11137051080945": "Boticário",
  "01239313000160": "Época Cosméticos",
}

export function marcaDe(cnpj: string | null | undefined): string | null {
  return (cnpj && MARCA_POR_CNPJ[cnpj.replace(/\D/g, "")]) || null
}

/** "Shopee · SHPS SERVICOS ADMINISTRATIVOS LTDA." (ou só a razão social). */
export function nomeComMarca(razaoSocial: string, cnpj: string | null | undefined): string {
  const marca = marcaDe(cnpj)
  return marca ? `${marca} · ${razaoSocial}` : razaoSocial
}
