import type { PerguntaFaq } from "./faq"

/** "Conciliação" → "conciliacao": a busca ignora acento e maiúscula. */
export function semAcento(texto: string): string {
  return texto.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase()
}

export function palavrasDaBusca(texto: string): string[] {
  return semAcento(texto).split(/\s+/).filter(Boolean)
}

/** Todas as palavras precisam aparecer (na pergunta, na resposta ou no nome
 * do tema), em qualquer ordem. Mesma regra da tela Ajuda e do "Fale com o
 * suporte". */
export function combina(p: PerguntaFaq, palavras: string[], tituloTema = ""): boolean {
  if (palavras.length === 0) return true
  const texto = `${semAcento(p.pergunta)} ${semAcento(p.resposta)} ${semAcento(tituloTema)}`
  return palavras.every((palavra) => texto.includes(palavra))
}

/** Pra uma dúvida escrita do jeito da pessoa ("como cancelo uma nota"):
 * primeiro tenta com todas as palavras; se não achar nada, aceita as
 * perguntas que têm a maioria das palavras com 4 letras ou mais. */
export function buscarDuvida(perguntas: PerguntaFaq[], texto: string, maximo = 5): PerguntaFaq[] {
  const palavras = palavrasDaBusca(texto)
  if (palavras.length === 0) return []
  const exatas = perguntas.filter((p) => combina(p, palavras))
  if (exatas.length) return exatas.slice(0, maximo)
  const fortes = palavras.filter((w) => w.length >= 4).map((w) => (w.length > 5 ? w.slice(0, w.length - 2) : w))
  if (fortes.length === 0) return []
  return perguntas
    .map((p) => {
      const t = `${semAcento(p.pergunta)} ${semAcento(p.resposta)}`
      return { p, n: fortes.filter((w) => t.includes(w)).length }
    })
    .filter((x) => x.n >= Math.max(1, Math.ceil(fortes.length * 0.6)))
    .sort((a, b) => b.n - a.n)
    .slice(0, maximo)
    .map((x) => x.p)
}
