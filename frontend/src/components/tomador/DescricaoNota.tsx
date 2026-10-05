import { useRef, useState } from "react"
import { competenciaAtual } from "../../lib/format"

/** Descrição do serviço na nota, pra quem não é da área. A pessoa escreve
 * o texto e ESCOLHE em campos simples o que muda todo mês (05/10/2026: "essa
 * explicação está mais confundindo do que ajudando; temos que deixar campos
 * simples pra pessoa selecionar"): se o mês aparece, QUAL mês (o da nota, o
 * anterior, dois antes...) e como ele é escrito. O modelo com códigos entre
 * chaves continua existindo por baixo; em "texto livre" os códigos entram
 * por botões, sem precisar decorar nada. */

const MESES = ["JANEIRO", "FEVEREIRO", "MARÇO", "ABRIL", "MAIO", "JUNHO", "JULHO", "AGOSTO", "SETEMBRO", "OUTUBRO", "NOVEMBRO", "DEZEMBRO"]

/** AAAA-MM menos N meses. */
export function mesDeReferencia(competencia: string, mesesAtras = 0): [string, string] {
  const [ano, mes] = competencia.split("-").map(Number)
  const total = ano * 12 + (mes - 1) - mesesAtras
  return [String(Math.floor(total / 12)), String((total % 12) + 1).padStart(2, "0")]
}

export function previaDescricao(modelo: string, ordem = "123456", mesesAtras = 0): string {
  const [ano, mes] = mesDeReferencia(competenciaAtual(), mesesAtras)
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
const classeSelect =
  "rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"

const QUAL_MES = [
  { valor: 0, rotulo: "O mês da nota" },
  { valor: 1, rotulo: "O mês anterior ao da nota" },
  { valor: 2, rotulo: "Dois meses antes" },
  { valor: 3, rotulo: "Três meses antes" },
]

export function DescricaoNota({
  modelo,
  onChange,
  mesesAtras = 0,
  onMesesAtras,
}: {
  modelo: string
  onChange: (modelo: string) => void
  /** Quantos meses antes do mês da nota é o mês que aparece na descrição. */
  mesesAtras?: number
  onMesesAtras?: (meses: number) => void
}) {
  const partes = desmontar(modelo)
  // Modelo fora do padrão abre direto no texto livre.
  const [livre, setLivre] = useState(partes === null)
  const refTexto = useRef<HTMLTextAreaElement>(null)
  const [anoNota, mesNota] = competenciaAtual().split("-")
  const [ano, mes] = mesDeReferencia(competenciaAtual(), mesesAtras)
  const p = partes ?? { texto: modelo, periodo: "nenhum" as Periodo, ordem: false }
  const mudar = (novo: Partial<Partes>) => onChange(montar({ ...p, ...novo }))
  const usaMes = /\{(mes_nome_upper|competencia_mm_aaaa|mes|ano)\}/.test(modelo)

  function inserir(codigo: string) {
    const campo = refTexto.current
    const ini = campo?.selectionStart ?? modelo.length
    const fim = campo?.selectionEnd ?? modelo.length
    onChange(`${modelo.slice(0, ini)}${codigo}${modelo.slice(fim)}`)
    requestAnimationFrame(() => {
      campo?.focus()
      campo?.setSelectionRange(ini + codigo.length, ini + codigo.length)
    })
  }

  const qualMes = onMesesAtras && (
    <label className="flex flex-col gap-1 text-sm text-slate-700 dark:text-slate-200">
      <span className="text-xs font-medium text-slate-500 dark:text-slate-400">Qual mês aparece?</span>
      <select aria-label="Qual mês aparece na descrição" value={mesesAtras} onChange={(e) => onMesesAtras(Number(e.target.value))} className={classeSelect}>
        {QUAL_MES.map((o) => {
          const [a, m] = mesDeReferencia(competenciaAtual(), o.valor)
          return (
            <option key={o.valor} value={o.valor}>
              {o.rotulo} (hoje: {MESES[Number(m) - 1].toLowerCase()}/{a})
            </option>
          )
        })}
      </select>
    </label>
  )

  return (
    <div data-tour="form-descricao">
      <p className="mb-1 text-sm font-medium text-slate-700 dark:text-slate-300">O que vai escrito na nota</p>

      {livre || partes === null ? (
        <>
          <textarea
            ref={refTexto}
            required
            aria-label="Texto da descrição"
            value={modelo}
            onChange={(e) => onChange(e.target.value)}
            rows={3}
            className={classeInput}
          />
          <p className="mb-1.5 mt-2 text-xs text-slate-500 dark:text-slate-400">Clique pra colocar no texto — eu troco pelo valor certo em cada nota:</p>
          <div className="flex flex-wrap gap-1.5">
            {[
              { codigo: "{mes_nome_upper}", rotulo: `Mês por extenso (${MESES[Number(mes) - 1]})` },
              { codigo: "{mes}", rotulo: `Mês em número (${mes})` },
              { codigo: "{ano}", rotulo: `Ano (${ano})` },
              { codigo: "{competencia_mm_aaaa}", rotulo: `Mês/ano (${mes}/${ano})` },
              { codigo: "{ordem}", rotulo: "Nº da ordem de pagamento" },
            ].map((c) => (
              <button
                key={c.codigo}
                type="button"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => inserir(c.codigo)}
                className="rounded-full border border-primary-200 bg-primary-50 px-2.5 py-0.5 text-xs font-medium text-primary-700 hover:bg-primary-100 dark:border-primary-800 dark:bg-primary-900/30 dark:text-primary-300"
              >
                + {c.rotulo}
              </button>
            ))}
          </div>
          {usaMes && qualMes && <div className="mt-3 max-w-sm">{qualMes}</div>}
          {partes !== null && (
            <button type="button" onClick={() => setLivre(false)} className="mt-2 text-xs font-semibold text-primary-600 hover:underline">
              ← voltar pros campos simples
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
          <fieldset className="mt-3 rounded-lg border border-slate-200 px-3 py-3 dark:border-slate-700">
            <legend className="px-1 text-xs font-semibold text-slate-500 dark:text-slate-400">O que muda de uma nota pra outra</legend>
            <div className="flex flex-col gap-3 text-sm text-slate-700 dark:text-slate-200">
              <div>
                <label className="flex items-center gap-2">
                  <input type="checkbox" checked={p.periodo !== "nenhum"} onChange={(e) => mudar({ periodo: e.target.checked ? "nome" : "nenhum" })} />
                  Colocar o mês e o ano no fim do texto
                </label>
                {p.periodo !== "nenhum" && (
                  <div className="mt-2 grid grid-cols-1 gap-3 pl-6 sm:grid-cols-2">
                    {qualMes}
                    <label className="flex flex-col gap-1">
                      <span className="text-xs font-medium text-slate-500 dark:text-slate-400">Escrito como?</span>
                      <select aria-label="Como o mês é escrito" value={p.periodo} onChange={(e) => mudar({ periodo: e.target.value as Periodo })} className={classeSelect}>
                        <option value="nome">
                          Por extenso — {MESES[Number(mes) - 1]}/{ano}
                        </option>
                        <option value="numero">
                          Em número — {mes}/{ano}
                        </option>
                      </select>
                    </label>
                  </div>
                )}
              </div>
              <label className="flex items-start gap-2">
                <input type="checkbox" className="mt-0.5" checked={p.ordem} onChange={(e) => mudar({ ordem: e.target.checked })} />
                <span>
                  Colocar o número da ordem de pagamento
                  <span className="block text-xs text-slate-400 dark:text-slate-500">Eu peço esse número toda vez que você gerar a nota.</span>
                </span>
              </label>
            </div>
          </fieldset>
          <button type="button" onClick={() => setLivre(true)} className="mt-1.5 text-xs text-slate-400 hover:text-primary-600 hover:underline">
            Preciso de um texto diferente (escrever livre)
          </button>
        </>
      )}

      <div className="mt-3 rounded-lg border border-primary-100 bg-primary-50/60 px-3 py-2.5 dark:border-primary-900/40 dark:bg-primary-900/20">
        <p className="text-[11px] font-semibold uppercase tracking-wide text-primary-600 dark:text-primary-300">
          Numa nota de {MESES[Number(mesNota) - 1].toLowerCase()}/{anoNota} vai sair assim
        </p>
        <p className="mt-0.5 text-sm text-slate-800 dark:text-slate-100">
          {modelo ? previaDescricao(modelo, "123456", mesesAtras) : <span className="text-slate-400">—</span>}
        </p>
      </div>
    </div>
  )
}
