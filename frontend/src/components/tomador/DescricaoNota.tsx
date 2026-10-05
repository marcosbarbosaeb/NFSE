import { useState } from "react"
import { competenciaAtual } from "../../lib/format"

/** Descrição do serviço na nota, pra quem não é da área (05/10/2026): a
 * pessoa escreve o texto normal e marca o que muda todo mês. O "modelo" com
 * códigos entre chaves continua existindo por baixo — fica em "editar o
 * texto completo", pra quem precisa de algo fora do padrão. */

const MESES = ["JANEIRO", "FEVEREIRO", "MARÇO", "ABRIL", "MAIO", "JUNHO", "JULHO", "AGOSTO", "SETEMBRO", "OUTUBRO", "NOVEMBRO", "DEZEMBRO"]

export function previaDescricao(modelo: string, ordem = "123456"): string {
  const [ano, mes] = competenciaAtual().split("-")
  return modelo
    .replaceAll("{competencia_mm_aaaa}", `${mes}/${ano}`)
    .replaceAll("{mes_nome_upper}", MESES[Number(mes) - 1])
    .replaceAll("{ano}", ano)
    .replaceAll("{mes}", mes)
    .replaceAll("{ordem}", ordem)
}

type Periodo = "nenhum" | "nome" | "numero"

interface Partes {
  texto: string
  periodo: Periodo
  ordem: boolean
}

const TOKEN_PERIODO: Record<Exclude<Periodo, "nenhum">, string> = { nome: "{mes_nome_upper}/{ano}", numero: "{competencia_mm_aaaa}" }
const TEXTO_ORDEM = "Ordem de pagamento {ordem}"

function montar(p: Partes): string {
  return [p.texto.trim(), p.periodo === "nenhum" ? "" : TOKEN_PERIODO[p.periodo], p.ordem ? TEXTO_ORDEM : ""].filter(Boolean).join(" - ")
}

/** Modelo -> partes simples; null quando o modelo não cabe no jeito simples. */
function desmontar(modelo: string): Partes | null {
  let resto = modelo.trim()
  let ordem = false
  let periodo: Periodo = "nenhum"
  const fim = (sufixo: string) => {
    if (!resto.endsWith(sufixo)) return false
    resto = resto.slice(0, -sufixo.length).replace(/\s*-\s*$/, "").trimEnd()
    return true
  }
  if (fim(TEXTO_ORDEM)) ordem = true
  if (fim(TOKEN_PERIODO.nome)) periodo = "nome"
  else if (fim(TOKEN_PERIODO.numero)) periodo = "numero"
  if (/[{}]/.test(resto)) return null
  return { texto: resto, periodo, ordem }
}

const classeInput =
  "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"

export function DescricaoNota({ modelo, onChange }: { modelo: string; onChange: (modelo: string) => void }) {
  const partes = desmontar(modelo)
  // Modelo fora do padrão abre direto no texto completo.
  const [completo, setCompleto] = useState(partes === null)
  const [ano, mes] = competenciaAtual().split("-")
  const p = partes ?? { texto: modelo, periodo: "nenhum" as Periodo, ordem: false }
  const mudar = (novo: Partial<Partes>) => onChange(montar({ ...p, ...novo }))

  return (
    <div data-tour="form-descricao">
      <p className="mb-1 text-sm font-medium text-slate-700 dark:text-slate-300">O que vai escrito na nota</p>

      {completo || partes === null ? (
        <>
          <textarea
            required
            aria-label="Texto completo da descrição"
            value={modelo}
            onChange={(e) => onChange(e.target.value)}
            rows={3}
            className={classeInput}
          />
          <p className="mt-1.5 text-xs text-slate-500 dark:text-slate-400">
            Os códigos entre chaves são trocados sozinhos todo mês: <code>{"{mes_nome_upper}"}</code> = {MESES[Number(mes) - 1]},{" "}
            <code>{"{ano}"}</code> = {ano}, <code>{"{competencia_mm_aaaa}"}</code> = {mes}/{ano}, <code>{"{ordem}"}</code> = o número da
            ordem de pagamento que você informa ao gerar.
          </p>
          {partes !== null && (
            <button type="button" onClick={() => setCompleto(false)} className="mt-1 text-xs font-semibold text-primary-600 hover:underline">
              ← voltar pro jeito simples
            </button>
          )}
        </>
      ) : (
        <>
          <input
            required
            aria-label="Texto da descrição"
            value={p.texto}
            onChange={(e) => mudar({ texto: e.target.value })}
            placeholder="Ex.: Comissão de vendas"
            className={classeInput}
          />
          <fieldset className="mt-3 rounded-lg border border-slate-200 px-3 py-2.5 dark:border-slate-700">
            <legend className="px-1 text-xs font-semibold text-slate-500 dark:text-slate-400">O que muda todo mês? Eu preencho sozinha.</legend>
            <div className="flex flex-col gap-2 text-sm text-slate-700 dark:text-slate-200">
              <label className="flex flex-wrap items-center gap-2">
                <input type="checkbox" checked={p.periodo !== "nenhum"} onChange={(e) => mudar({ periodo: e.target.checked ? "nome" : "nenhum" })} />
                O mês e o ano da nota
                {p.periodo !== "nenhum" && (
                  <select
                    aria-label="Formato do mês"
                    value={p.periodo}
                    onChange={(e) => mudar({ periodo: e.target.value as Periodo })}
                    className="rounded-md border border-slate-300 bg-white px-2 py-1 text-xs text-slate-800 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
                  >
                    <option value="nome">
                      {MESES[Number(mes) - 1]}/{ano}
                    </option>
                    <option value="numero">
                      {mes}/{ano}
                    </option>
                  </select>
                )}
              </label>
              <label className="flex items-start gap-2">
                <input type="checkbox" className="mt-0.5" checked={p.ordem} onChange={(e) => mudar({ ordem: e.target.checked })} />
                <span>
                  O número da ordem de pagamento
                  <span className="block text-xs text-slate-400 dark:text-slate-500">Eu peço esse número toda vez que você gerar a nota.</span>
                </span>
              </label>
            </div>
          </fieldset>
          <button type="button" onClick={() => setCompleto(true)} className="mt-1.5 text-xs text-slate-400 hover:text-primary-600 hover:underline">
            Preciso de um texto diferente (editar o texto completo)
          </button>
        </>
      )}

      <div className="mt-3 rounded-lg border border-primary-100 bg-primary-50/60 px-3 py-2.5 dark:border-primary-900/40 dark:bg-primary-900/20">
        <p className="text-[11px] font-semibold uppercase tracking-wide text-primary-600 dark:text-primary-300">Na nota deste mês vai sair assim</p>
        <p className="mt-0.5 text-sm text-slate-800 dark:text-slate-100">{modelo ? previaDescricao(modelo) : <span className="text-slate-400">—</span>}</p>
      </div>
    </div>
  )
}
