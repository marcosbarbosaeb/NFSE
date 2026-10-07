import { AlertTriangle, CheckCircle2, FileSpreadsheet, Info } from "lucide-react"
import { type FormEvent, type ReactNode, useEffect, useId, useState } from "react"
import { api } from "../../lib/api"
import { classeCampo, classeCheckbox, mensagemErro } from "../../lib/financeiro"
import { formatBRL } from "../../lib/format"
import type { EscolhasPlanilha, PreviaPlanilha, ResultadoPlanilha, VinculoResumo } from "../../lib/types"
import { Button } from "../ui/Button"
import { Modal } from "../ui/Modal"

// Importar a planilha de controle financeiro (.xlsx) — 28/09/2026.
// 1) arquivo + ano → prévia (nada gravado); 2) revisar: qual tomador é cada
// linha de receita, mês do pagamento x mês da nota, o que mais importar;
// 3) importa (reenvia o MESMO arquivo com as escolhas) e mostra o resumo.

const ANO_ATUAL = new Date().getFullYear()
const ANOS = [ANO_ATUAL, ANO_ATUAL - 1, ANO_ATUAL - 2]

interface EscolhaReceita {
  /** "v:<id do tomador>" | "novo" | "ignorar" */
  destino: string
  deslocamento: 0 | 1
}

function Secao({
  marcado,
  onMarcar,
  titulo,
  resumo,
  desabilitado,
  children,
}: {
  marcado: boolean
  onMarcar: (v: boolean) => void
  titulo: string
  resumo: ReactNode
  desabilitado?: boolean
  children?: ReactNode
}) {
  return (
    <div className={`rounded-lg border border-slate-200 p-3 dark:border-slate-700 ${desabilitado ? "opacity-60" : ""}`}>
      <label className="flex cursor-pointer items-start gap-3">
        <input type="checkbox" checked={marcado} disabled={desabilitado} onChange={(e) => onMarcar(e.target.checked)} className={`${classeCheckbox} mt-0.5`} />
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-medium text-slate-800 dark:text-slate-200">{titulo}</span>
          <span className="block text-xs text-slate-500 dark:text-slate-400">{resumo}</span>
        </span>
      </label>
      {children && (
        <details className="mt-2 pl-7">
          <summary className="cursor-pointer text-xs font-medium text-primary-600 hover:text-primary-700 dark:text-primary-300">Ver itens</summary>
          <div className="mt-2 max-h-48 overflow-y-auto">{children}</div>
        </details>
      )}
    </div>
  )
}

function ListaItens({ itens }: { itens: { chave: string; nome: string; valor: ReactNode }[] }) {
  return (
    <ul className="divide-y divide-slate-100 text-xs dark:divide-slate-700/60">
      {itens.map((i) => (
        <li key={i.chave} className="flex items-baseline justify-between gap-3 py-1.5">
          <span className="min-w-0 truncate text-slate-700 dark:text-slate-200">{i.nome}</span>
          <span className="shrink-0 tabular-nums text-slate-500 dark:text-slate-400">{i.valor}</span>
        </li>
      ))}
    </ul>
  )
}

export function ImportarPlanilhaModal({ onClose, onImportado }: { onClose: () => void; onImportado: () => void }) {
  const [etapa, setEtapa] = useState<1 | 2 | 3>(1)
  const [arquivo, setArquivo] = useState<File | null>(null)
  const [ano, setAno] = useState(String(ANO_ATUAL))
  const [previa, setPrevia] = useState<PreviaPlanilha | null>(null)
  const [vinculos, setVinculos] = useState<VinculoResumo[]>([])
  const [receitas, setReceitas] = useState<Record<number, EscolhaReceita>>({})
  const [despesas, setDespesas] = useState(true)
  const [recorrentes, setRecorrentes] = useState(true)
  const [retiradas, setRetiradas] = useState(true)
  const [rotinas, setRotinas] = useState(true)
  const [resultado, setResultado] = useState<ResultadoPlanilha | null>(null)
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const idArquivo = useId()
  const idAno = useId()

  useEffect(() => {
    api
      .get<VinculoResumo[]>("/vinculos?todos=true")
      .then(setVinculos)
      .catch(() => {})
  }, [])

  function fechar() {
    if (resultado) onImportado()
    onClose()
  }

  function formulario(): FormData {
    const form = new FormData()
    if (arquivo) form.append("arquivo", arquivo)
    form.append("ano", ano)
    return form
  }

  async function lerPrevia(e: FormEvent) {
    e.preventDefault()
    if (!arquivo) {
      setErro("Escolha o arquivo .xlsx da planilha.")
      return
    }
    setErro(null)
    setEnviando(true)
    try {
      const p = await api.postForm<PreviaPlanilha>("/importar/planilha/previa", formulario())
      setPrevia(p)
      setReceitas(
        Object.fromEntries(
          p.receitas.map((r) => [r.linha, { destino: r.acao === "vinculo" && r.vinculo_id ? `v:${r.vinculo_id}` : "novo", deslocamento: r.deslocamento }]),
        ),
      )
      setDespesas(p.despesas.length > 0)
      setRecorrentes(p.despesas.some((d) => d.recorrente))
      setRetiradas(p.retiradas.length > 0)
      setRotinas(p.rotinas.length > 0)
      setEtapa(2)
    } catch (err) {
      setErro(mensagemErro(err))
    } finally {
      setEnviando(false)
    }
  }

  async function importar() {
    if (!previa) return
    const escolhas: EscolhasPlanilha = {
      receitas: previa.receitas.map((r) => {
        const e = receitas[r.linha] ?? { destino: "ignorar", deslocamento: r.deslocamento }
        if (e.destino.startsWith("v:")) return { linha: r.linha, acao: "vinculo", vinculo_id: e.destino.slice(2), deslocamento: e.deslocamento }
        return { linha: r.linha, acao: e.destino === "novo" ? "novo" : "ignorar", deslocamento: e.deslocamento }
      }),
      despesas,
      recorrentes: despesas && recorrentes,
      retiradas,
      rotinas,
    }
    const form = formulario()
    form.append("escolhas", JSON.stringify(escolhas))
    setErro(null)
    setEnviando(true)
    try {
      setResultado(await api.postForm<ResultadoPlanilha>("/importar/planilha", form))
      setEtapa(3)
    } catch (err) {
      setErro(mensagemErro(err))
    } finally {
      setEnviando(false)
    }
  }

  function mudarReceita(linha: number, mudanca: Partial<EscolhaReceita>) {
    setReceitas((atual) => ({ ...atual, [linha]: { ...atual[linha], ...mudanca } }))
  }

  const passos = ["Arquivo", "Revisar", "Pronto"]
  const idsVinculos = new Set(vinculos.map((v) => v.id))
  const vinculosOrdenados = [...vinculos].sort((a, b) => a.apelido.localeCompare(b.apelido, "pt-BR"))

  const totalDe = (lista: { total: number }[]) => lista.reduce((s, x) => s + x.total, 0)
  const aImportar = previa ? previa.receitas.filter((r) => receitas[r.linha]?.destino !== "ignorar") : []
  const fixas = previa ? previa.despesas.filter((d) => d.recorrente) : []

  return (
    <Modal titulo="Importar planilha de controle" onClose={fechar} largura="max-w-3xl">
      <ol className="mb-5 flex items-center gap-2 text-xs" aria-label="Etapas">
        {passos.map((p, i) => {
          const n = i + 1
          const atual = n === etapa
          const feito = n < etapa
          return (
            <li key={p} className="flex items-center gap-2" aria-current={atual ? "step" : undefined}>
              <span
                className={`flex h-5 w-5 items-center justify-center rounded-full text-[11px] font-semibold ${
                  atual ? "bg-primary-600 text-white" : feito ? "bg-success-600 text-white" : "bg-slate-100 text-slate-400 dark:bg-slate-700 dark:text-slate-400"
                }`}
              >
                {feito ? "✓" : n}
              </span>
              <span className={atual ? "font-medium text-slate-800 dark:text-slate-200" : "text-slate-400 dark:text-slate-500"}>{p}</span>
              {n < passos.length && <span className="h-px w-6 bg-slate-200 dark:bg-slate-700" aria-hidden />}
            </li>
          )
        })}
      </ol>

      {erro && (
        <p className="mb-4 rounded-lg bg-danger-50 px-4 py-3 text-sm text-danger-700 dark:bg-danger-900/40 dark:text-danger-300" role="alert">
          {erro}
        </p>
      )}

      {etapa === 1 && (
        <form onSubmit={lerPrevia} className="flex flex-col gap-4">
          <p className="text-sm text-slate-500 dark:text-slate-400">
            A planilha com os meses (JAN..DEZ) nas colunas e os blocos “Pagamentos recebidos”, “NF geradas”, “Despesas”, distribuição de lucros e o quadro de
            conferências. Nada é gravado antes da revisão.
          </p>
          <p className="flex items-start gap-2 rounded-lg bg-primary-50 px-3 py-2 text-xs text-primary-700 dark:bg-primary-900/30 dark:text-primary-300">
            <Info size={14} className="mt-0.5 shrink-0" />
            Importe primeiro as notas do Emissor Nacional (tela NFS-e) pra os recebimentos baterem com as notas.
          </p>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <label className="block sm:col-span-2" htmlFor={idArquivo}>
              <span className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Arquivo (.xlsx)</span>
              <input
                id={idArquivo}
                type="file"
                required
                accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                onChange={(e) => setArquivo(e.target.files?.[0] ?? null)}
                className="block w-full text-sm text-slate-600 file:mr-3 file:rounded-lg file:border-0 file:bg-slate-100 file:px-3 file:py-2 file:text-sm file:font-medium file:text-slate-700 hover:file:bg-slate-200 dark:text-slate-300 dark:file:bg-slate-700 dark:file:text-slate-200"
              />
            </label>
            <label className="block" htmlFor={idAno}>
              <span className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Ano da planilha</span>
              <select id={idAno} value={ano} onChange={(e) => setAno(e.target.value)} className={classeCampo}>
                {ANOS.map((a) => (
                  <option key={a} value={a}>
                    {a}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <Button type="button" variant="outline" onClick={fechar}>
              Cancelar
            </Button>
            <Button type="submit" variant="accent" disabled={enviando || !arquivo}>
              <FileSpreadsheet size={16} /> {enviando ? "Lendo..." : "Ler planilha"}
            </Button>
          </div>
        </form>
      )}

      {etapa === 2 && previa && (
        <div className="flex flex-col gap-5">
          <p className="flex items-start gap-2 rounded-lg bg-primary-50 px-3 py-2 text-xs text-primary-700 dark:bg-primary-900/30 dark:text-primary-300">
            <Info size={14} className="mt-0.5 shrink-0" />
            Importe primeiro as notas do Emissor Nacional (tela NFS-e) pra os recebimentos baterem com as notas.
          </p>

          <section aria-labelledby="titulo-receitas">
            <div className="mb-1 flex flex-wrap items-baseline justify-between gap-2">
              <h3 id="titulo-receitas" className="text-sm font-semibold text-slate-800 dark:text-slate-200">
                Recebimentos ({previa.receitas.length} fontes)
              </h3>
              <span className="text-xs text-slate-500 dark:text-slate-400">
                {aImportar.length} a importar · {formatBRL(totalDe(aImportar))}
              </span>
            </div>
            <p className="mb-3 text-xs text-slate-500 dark:text-slate-400">
              Diga a qual tomador cada linha pertence. Em “Mês do pagamento”: algumas fontes pagam antes da nota — ex.: no Mercado Livre o que
              caiu em janeiro é a nota de fevereiro, então o recebimento entra junto da nota de fevereiro. A Ana compara com as “NF geradas” da
              planilha e já sugere; confira.
            </p>
            {previa.receitas.length === 0 ? (
              <p className="py-3 text-center text-sm text-slate-400 dark:text-slate-500">Nenhuma linha de recebimento encontrada.</p>
            ) : (
              <ul className="flex flex-col gap-2">
                {previa.receitas.map((r) => {
                  const e = receitas[r.linha] ?? { destino: "ignorar", deslocamento: r.deslocamento }
                  const ignorada = e.destino === "ignorar"
                  const meses = r.valores.filter((v) => v && v > 0).length
                  const sugeridoForaDaLista = !!r.vinculo_id && !idsVinculos.has(r.vinculo_id)
                  return (
                    <li key={r.linha} className={`rounded-lg border border-slate-200 p-3 dark:border-slate-700 ${ignorada ? "bg-slate-50 dark:bg-slate-900/40" : ""}`}>
                      <div className="flex items-baseline justify-between gap-3">
                        <p className={`min-w-0 truncate text-sm font-medium ${ignorada ? "text-slate-400 line-through dark:text-slate-500" : "text-slate-800 dark:text-slate-200"}`}>
                          {r.nome}
                        </p>
                        <span className="shrink-0 text-sm tabular-nums text-slate-700 dark:text-slate-200">{formatBRL(r.total)}</span>
                      </div>
                      <p className="text-xs text-slate-400 dark:text-slate-500">
                        {meses} {meses === 1 ? "mês" : "meses"} com valor{r.nf_nome ? ` · comparado com a NF “${r.nf_nome}”` : " · sem linha de NF correspondente"}
                      </p>
                      <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2">
                        <label className="block">
                          <span className="mb-0.5 block text-xs text-slate-500 dark:text-slate-400">Lançar em</span>
                          <select value={e.destino} onChange={(ev) => mudarReceita(r.linha, { destino: ev.target.value })} className={`${classeCampo} py-1.5`}>
                            <optgroup label="Tomador existente">
                              {sugeridoForaDaLista && <option value={`v:${r.vinculo_id}`}>Tomador sugerido</option>}
                              {vinculosOrdenados.map((v) => (
                                <option key={v.id} value={`v:${v.id}`}>
                                  {v.apelido}
                                  {v.sem_nota ? " (sem nota)" : ""}
                                  {v.ativo === false ? " (inativo)" : ""}
                                </option>
                              ))}
                            </optgroup>
                            <option value="novo">Criar como fonte só de controle (sem nota)</option>
                            <option value="ignorar">Não importar</option>
                          </select>
                        </label>
                        <label className="block">
                          <span className="mb-0.5 block text-xs text-slate-500 dark:text-slate-400">Mês do pagamento</span>
                          <select
                            value={e.deslocamento}
                            disabled={ignorada}
                            onChange={(ev) => mudarReceita(r.linha, { deslocamento: ev.target.value === "1" ? 1 : 0 })}
                            className={`${classeCampo} py-1.5 disabled:opacity-50`}
                          >
                            <option value={0}>Mesmo mês da nota</option>
                            <option value={1}>Paga antes — é a nota do mês seguinte</option>
                          </select>
                        </label>
                      </div>
                    </li>
                  )
                })}
              </ul>
            )}
          </section>

          <section aria-labelledby="titulo-mais" className="flex flex-col gap-2">
            <h3 id="titulo-mais" className="text-sm font-semibold text-slate-800 dark:text-slate-200">
              O que mais importar
            </h3>
            <Secao
              marcado={despesas}
              onMarcar={setDespesas}
              desabilitado={previa.despesas.length === 0}
              titulo="Despesas"
              resumo={`${previa.despesas.length} linha(s) · ${formatBRL(totalDe(previa.despesas))} no ano. Meses futuros entram como “a pagar”.`}
            >
              {previa.despesas.length > 0 && <ListaItens itens={previa.despesas.map((d) => ({ chave: d.nome, nome: d.nome, valor: formatBRL(d.total) }))} />}
            </Secao>
            <Secao
              marcado={despesas && recorrentes}
              onMarcar={setRecorrentes}
              desabilitado={!despesas || fixas.length === 0}
              titulo="Criar contas fixas"
              resumo={
                fixas.length === 0
                  ? "Nenhuma despesa se repete nos últimos meses."
                  : `${fixas.length} despesa(s) que se repetem viram contas fixas, pra ticar todo mês.`
              }
            >
              {fixas.length > 0 && (
                <ListaItens
                  itens={fixas.map((d) => ({
                    chave: d.nome,
                    nome: d.nome,
                    valor: d.valor_padrao ? formatBRL(d.valor_padrao) : <span className="text-slate-400 dark:text-slate-500">varia</span>,
                  }))}
                />
              )}
            </Secao>
            <Secao
              marcado={retiradas}
              onMarcar={setRetiradas}
              desabilitado={previa.retiradas.length === 0}
              titulo="Retiradas (distribuição de lucros)"
              resumo={
                previa.retiradas.length === 0
                  ? "Nenhuma linha de distribuição de lucros encontrada."
                  : `${previa.retiradas.length} conta(s) · ${formatBRL(totalDe(previa.retiradas))} no ano.`
              }
            >
              {previa.retiradas.length > 0 && (
                <ListaItens itens={previa.retiradas.map((r) => ({ chave: r.nome, nome: r.conta && r.conta !== r.nome ? `${r.nome} (${r.conta})` : r.nome, valor: formatBRL(r.total) }))} />
              )}
            </Secao>
            <Secao
              marcado={rotinas}
              onMarcar={setRotinas}
              desabilitado={previa.rotinas.length === 0}
              titulo="Rotina de fechamento"
              resumo={
                previa.rotinas.length === 0
                  ? "Nenhum quadro de conferências encontrado."
                  : `${previa.rotinas.length} item(ns), com os meses já marcados com X.`
              }
            >
              {previa.rotinas.length > 0 && (
                <ListaItens itens={previa.rotinas.map((r) => ({ chave: r.nome, nome: r.nome, valor: `${r.feitos.length} ${r.feitos.length === 1 ? "mês" : "meses"} ✓` }))} />
              )}
            </Secao>
          </section>

          <div className="flex flex-wrap justify-between gap-3 pt-2">
            <Button type="button" variant="outline" onClick={() => setEtapa(1)} disabled={enviando}>
              Voltar
            </Button>
            <Button type="button" variant="accent" onClick={importar} disabled={enviando}>
              {enviando ? "Importando..." : "Importar"}
            </Button>
          </div>
        </div>
      )}

      {etapa === 3 && resultado && (
        <div className="flex flex-col gap-4">
          <p className="flex items-center gap-2 text-sm font-medium text-success-700 dark:text-success-300">
            <CheckCircle2 size={18} /> Planilha importada.
          </p>
          <dl className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            {[
              ["Recebimentos lançados", resultado.pagamentos],
              ["Recebimentos que já existiam", resultado.pagamentos_existentes],
              ["Fontes criadas (sem nota)", resultado.tomadores_criados],
              ["Despesas", resultado.despesas],
              ["Contas fixas", resultado.contas_fixas],
              ["Retiradas", resultado.retiradas],
              ["Itens da rotina", resultado.rotinas],
            ].map(([rotulo, n]) => (
              <div key={rotulo} className="rounded-lg bg-slate-50 px-3 py-2 dark:bg-slate-900/40">
                <dt className="text-xs text-slate-500 dark:text-slate-400">{rotulo}</dt>
                <dd className="text-lg font-semibold tabular-nums text-slate-900 dark:text-slate-100">{n}</dd>
              </div>
            ))}
          </dl>
          {resultado.avisos.length > 0 && (
            <div className="rounded-lg bg-warning-50 px-4 py-3 text-sm text-warning-700 dark:bg-warning-900/40 dark:text-warning-300">
              <p className="mb-1 flex items-center gap-2 font-medium">
                <AlertTriangle size={16} /> Avisos
              </p>
              <ul className="list-disc pl-5 text-xs">
                {resultado.avisos.map((a, i) => (
                  <li key={i}>{a}</li>
                ))}
              </ul>
            </div>
          )}
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Não era isso? Dá pra desfazer esta importação inteira em Financeiro › Conciliação › Importações feitas.
          </p>
          <div className="flex justify-end pt-2">
            <Button variant="accent" onClick={fechar}>
              Concluir
            </Button>
          </div>
        </div>
      )}
    </Modal>
  )
}
