import { MoedaField } from "./ui/CampoMoeda"
import { AlertTriangle, CheckCircle2, FileSpreadsheet, Globe2 } from "lucide-react"
import { type FormEvent, useEffect, useMemo, useState } from "react"
import { ApiError, api, formatarErro } from "../lib/api"
import { formatBRL, formatCompetenciaLonga, parseBRL } from "../lib/format"
import type { GeracaoShopee, Lote, PassoLote, PreviaShopee, VinculoResumo } from "../lib/types"
import { hojeLocal } from "../lib/datas"
import { CampoData } from "./CampoData"
import { Button } from "./ui/Button"
import { CampoPercentual } from "./ui/CampoPercentual"
import { Modal } from "./ui/Modal"

// Relatório mensal da Shopee (28/09/2026). Na Shopee a nota vai pra cada
// VENDEDOR que pagou comissão (centenas por mês). A Ana lê o relatório, mostra
// um resumo por mês e gera uma nota por vendedor — sem cadastrar nenhum deles
// como tomador (ver backend/app/services/relatorio_shopee.py).

function formatarDocumento(doc: string, tipo: string): string {
  if (tipo === "CNPJ" && doc.length === 14) return `${doc.slice(0, 2)}.${doc.slice(2, 5)}.${doc.slice(5, 8)}/${doc.slice(8, 12)}-${doc.slice(12)}`
  if (tipo === "CPF" && doc.length === 11) return `${doc.slice(0, 3)}.${doc.slice(3, 6)}.${doc.slice(6, 9)}-${doc.slice(9)}`
  return doc
}

// "Depois de gerar, a Ana também..." (05/10/2026): a sequência inteira roda
// em segundo plano; a escolha fica lembrada neste navegador.
interface Depois {
  assinar: boolean
  prefeitura: boolean
  email: boolean
}
const CHAVE_DEPOIS = "ana:shopee:depois"
function lerDepois(): Depois {
  try {
    const d = JSON.parse(localStorage.getItem(CHAVE_DEPOIS) ?? "null")
    if (d && typeof d.assinar === "boolean") {
      const prefeitura = d.assinar && d.prefeitura === true
      return { assinar: d.assinar, prefeitura, email: prefeitura && d.email === true }
    }
  } catch {
    // sem storage ou valor estragado: padrão
  }
  return { assinar: true, prefeitura: true, email: true }
}

export function ShopeeModal({
  vinculo,
  aliquotaReferencia,
  ambienteTeste = false,
  onClose,
  onGeradas,
  onVerNotas,
  onLote,
}: {
  ambienteTeste?: boolean
  /** A sequência em segundo plano começou — a tela mostra o andamento. */
  onLote?: (lote: Lote) => void
  vinculo: VinculoResumo
  aliquotaReferencia: number | null
  onClose: () => void
  onGeradas: () => void
  /** "Ver as notas na lista": filtra a lista pela Shopee + mês gerado. */
  onVerNotas?: (competencia: string) => void
}) {
  const [arquivo, setArquivo] = useState<File | null>(null)
  const [arrastando, setArrastando] = useState(false)
  const [previa, setPrevia] = useState<PreviaShopee | null>(null)
  const [competencia, setCompetencia] = useState("")
  const [valorMinimo, setValorMinimo] = useState("0")
  const [incluirEstrangeiros, setIncluirEstrangeiros] = useState(false)
  // Data de competência que vai em cada nota (29/09/2026); padrão hoje. A
  // competência da lista continua sendo o mês do relatório.
  const [dataCompetencia, setDataCompetencia] = useState(hojeLocal)
  const [aliqSn, setAliqSn] = useState<number | null>(aliquotaReferencia)
  // A referência pode chegar depois do modal abrir.
  useEffect(() => {
    if (aliquotaReferencia != null) setAliqSn((atual) => atual ?? aliquotaReferencia)
  }, [aliquotaReferencia])
  // Ambiente: o da conta (Configurações › Ambiente das notas) — o backend
  // aplica quando não vem tpAmb.
  const [carregando, setCarregando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const [resultado, setResultado] = useState<GeracaoShopee | null>(null)
  const [verTodos, setVerTodos] = useState(false)
  const [depois, setDepois] = useState<Depois>(lerDepois)
  function mudarDepois(passo: keyof Depois, ligado: boolean) {
    // Cada passo depende do anterior.
    const novo: Depois = ligado
      ? { assinar: true, prefeitura: passo !== "assinar" ? true : depois.prefeitura, email: passo === "email" ? true : depois.email }
      : { assinar: passo === "assinar" ? false : depois.assinar, prefeitura: passo === "email" ? depois.prefeitura : false, email: false }
    setDepois(novo)
    try {
      localStorage.setItem(CHAVE_DEPOIS, JSON.stringify(novo))
    } catch {
      // sem storage: vale só nesta vez
    }
  }
  const passos: PassoLote[] = [depois.assinar && "assinar", depois.prefeitura && "submeter", depois.email && "email"].filter(Boolean) as PassoLote[]

  async function lerArquivo(e: FormEvent) {
    e.preventDefault()
    if (!arquivo) return
    setErro(null)
    setCarregando(true)
    try {
      const form = new FormData()
      form.append("vinculo_id", vinculo.id)
      form.append("arquivo", arquivo)
      const resp = await api.postForm<PreviaShopee>("/shopee/previa", form)
      setPrevia(resp)
      setCompetencia(resp.competencias[0]?.competencia ?? "")
    } catch (err) {
      setErro(err instanceof ApiError ? formatarErro(err.detail) : "Falha de conexão.")
    } finally {
      setCarregando(false)
    }
  }

  const minimo = parseBRL(valorMinimo) ?? 0
  const doMes = useMemo(() => (previa?.vendedores ?? []).filter((v) => v.competencia === competencia), [previa, competencia])
  const aGerar = doMes.filter((v) => !v.ja_gerada && v.valor >= minimo && (incluirEstrangeiros || !v.estrangeiro))
  const totalAGerar = aGerar.reduce((s, v) => s + v.valor, 0)
  const jaGeradas = doMes.filter((v) => v.ja_gerada).length
  const estrangeiros = doMes.filter((v) => v.estrangeiro).length
  const abaixoMinimo = doMes.filter((v) => v.valor < minimo && !v.ja_gerada).length
  const semEndereco = aGerar.filter((v) => !v.estrangeiro && !v.cidade).length
  // Conferência com o painel da Shopee: o total do relatório é a comissão
  // dos vendedores; somado à nota da própria Shopee dá a comissão do mês.
  const soma = (lista: typeof doMes) => lista.reduce((s, v) => s + v.valor, 0)
  const totalRelatorio = soma(doMes)
  const deFora = [
    { rotulo: "já geradas antes", lista: doMes.filter((v) => v.ja_gerada) },
    { rotulo: "de fora do Brasil (não incluídos)", lista: doMes.filter((v) => !v.ja_gerada && v.estrangeiro && !incluirEstrangeiros) },
    { rotulo: "abaixo do valor mínimo", lista: doMes.filter((v) => !v.ja_gerada && v.valor < minimo && (incluirEstrangeiros || !v.estrangeiro)) },
  ].filter((g) => g.lista.length > 0)

  async function gerar() {
    if (!arquivo) return
    setErro(null)
    setCarregando(true)
    try {
      const form = new FormData()
      form.append("vinculo_id", vinculo.id)
      form.append("arquivo", arquivo)
      form.append("competencia", competencia)
      form.append("valor_minimo", String(minimo))
      form.append("incluir_estrangeiros", String(incluirEstrangeiros))
      if (aliqSn != null) form.append("aliq_sn", String(aliqSn))
      form.append("data_competencia", /^\d{4}-\d{2}-\d{2}$/.test(dataCompetencia) ? dataCompetencia : hojeLocal())
      if (passos.length > 0) form.append("depois", passos.join(","))
      const resp = await api.postForm<GeracaoShopee>("/shopee/gerar", form)
      setResultado(resp)
      if (resp.geradas > 0 || resp.lote) onGeradas()
      if (resp.lote) onLote?.(resp.lote)
    } catch (err) {
      setErro(err instanceof ApiError ? formatarErro(err.detail) : "Falha de conexão.")
    } finally {
      setCarregando(false)
    }
  }

  return (
    <Modal titulo={`Relatório da Shopee — ${vinculo.apelido}`} onClose={onClose} largura="max-w-3xl">
      {erro && <p className="mb-4 rounded-lg bg-danger-50 px-4 py-3 text-sm text-danger-700">{erro}</p>}

      {!previa && (
        <form onSubmit={lerArquivo} className="flex flex-col gap-4">
          <p className="text-sm text-slate-600 dark:text-slate-300">
            No painel de afiliados da Shopee, baixe o <strong>relatório mensal de comissões</strong> (arquivo
            “MonthlyReport…csv”) e envie aqui. Eu gero uma nota pra cada vendedor que te pagou comissão no mês — os vendedores
            não ficam salvos como tomadores.
          </p>
          {/* Arrastar e soltar (05/10/2026): sem tratar o "drop", o navegador
              abria o arquivo em vez de carregar aqui. */}
          <label
            onDragOver={(e) => {
              e.preventDefault()
              setArrastando(true)
            }}
            onDragLeave={() => setArrastando(false)}
            onDrop={(e) => {
              e.preventDefault()
              setArrastando(false)
              const solto = e.dataTransfer.files?.[0]
              if (!solto) return
              if (!/\.csv$/i.test(solto.name)) {
                setErro("Esse não parece o relatório da Shopee — ele é um arquivo .csv.")
                return
              }
              setErro(null)
              setArquivo(solto)
            }}
            className={`flex cursor-pointer flex-col items-center gap-2 rounded-xl border-2 border-dashed px-4 py-8 text-center text-sm text-slate-500 hover:border-primary-400 ${
              arrastando ? "border-primary-500 bg-primary-50 dark:bg-primary-900/30" : "border-slate-300 dark:border-slate-600"
            }`}
          >
            <FileSpreadsheet size={28} className="text-primary-500" />
            {arquivo ? (
              <span className="font-medium text-slate-800 dark:text-slate-100">{arquivo.name}</span>
            ) : (
              "Arraste o arquivo .csv pra cá ou clique pra escolher"
            )}
            <input type="file" accept=".csv,text/csv" className="hidden" onChange={(e) => setArquivo(e.target.files?.[0] ?? null)} />
          </label>
          <div className="flex justify-end gap-3">
            <Button type="button" variant="outline" onClick={onClose}>
              Cancelar
            </Button>
            <Button type="submit" variant="accent" disabled={!arquivo || carregando}>
              {carregando ? "Lendo..." : "Ler relatório"}
            </Button>
          </div>
        </form>
      )}

      {previa && !resultado && (
        <div className="flex flex-col gap-4">
          <div className="flex flex-wrap gap-2">
            {previa.competencias.map((m) => (
              <button
                key={m.competencia}
                type="button"
                onClick={() => setCompetencia(m.competencia)}
                className={`rounded-lg border px-3 py-2 text-left text-sm transition-colors ${
                  m.competencia === competencia
                    ? "border-primary-500 bg-primary-50 text-primary-800 dark:bg-primary-900/30 dark:text-primary-200"
                    : "border-slate-200 text-slate-600 hover:border-primary-300 dark:border-slate-600 dark:text-slate-300"
                }`}
              >
                <span className="block font-semibold">{formatCompetenciaLonga(m.competencia)}</span>
                <span className="text-xs">
                  {m.vendedores} vendedores · {formatBRL(m.total)}
                  {m.ja_geradas > 0 && ` · ${m.ja_geradas} já geradas`}
                </span>
              </button>
            ))}
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <MoedaField
              label="Não gerar notas abaixo de"
              saida="br"
              valor={valorMinimo}
              onChange={setValorMinimo}
              hint={abaixoMinimo ? `${abaixoMinimo} vendedor(es) ficam de fora` : "0 = gera todas"}
            />
            <CampoPercentual label="Alíquota do Simples (%)" valor={aliqSn} onChange={setAliqSn} />
            <CampoData
              valor={dataCompetencia}
              onChange={setDataCompetencia}
              mostrarCompetencia={false}
              hint={
                competencia
                  ? `É a competência de cada nota (é nesse mês que elas aparecem na lista). A descrição fala da comissão de ${formatCompetenciaLonga(competencia).toLowerCase()}.`
                  : "É a competência de cada nota."
              }
            />
          </div>

          {estrangeiros > 0 && (
            <label className="flex items-start gap-2 rounded-lg bg-warning-50 px-3 py-2 text-sm text-warning-700">
              <input type="checkbox" checked={incluirEstrangeiros} onChange={(e) => setIncluirEstrangeiros(e.target.checked)} className="mt-0.5" />
              <span>
                <Globe2 size={14} className="mr-1 inline" />
                Incluir {estrangeiros} vendedor(es) de fora do Brasil. A nota sai do mesmo jeito das que você já emitia pra eles
                (identificação fiscal estrangeira, país do vendedor e ISS tributado aqui). Se for a primeira vez, confirme com seu
                contador.
              </span>
            </label>
          )}

          <div className="rounded-xl border border-success-100 bg-success-50/60 px-4 py-3 dark:border-success-900/40 dark:bg-success-900/20">
            <p className="text-sm text-success-700 dark:text-success-300">
              <strong>
                {aGerar.length} nota{aGerar.length === 1 ? "" : "s"} · {formatBRL(totalAGerar)}
              </strong>{" "}
              da comissão de {competencia && formatCompetenciaLonga(competencia).toLowerCase()}
              {jaGeradas > 0 && ` (${jaGeradas} já geradas antes ficam como estão)`}
            </p>
            <p className="mt-1 text-xs text-slate-600 dark:text-slate-300">
              O relatório tem {doMes.length} vendedores e soma <strong>{formatBRL(totalRelatorio)}</strong> — confira com o painel da
              Shopee (comissão total do mês menos a nota da própria Shopee).
              {deFora.length > 0 && (
                <>
                  {" "}
                  Ficam de fora agora:{" "}
                  {deFora.map((g, i) => (
                    <span key={g.rotulo}>
                      {i > 0 && "; "}
                      {g.lista.length} {g.rotulo} ({formatBRL(soma(g.lista))})
                    </span>
                  ))}
                  .
                </>
              )}
            </p>
            {semEndereco > 0 && (
              <p className="mt-1 text-xs text-warning-700">{semEndereco} sem endereço reconhecido — a nota sai sem o endereço do tomador.</p>
            )}
          </div>

          <div className="max-h-72 overflow-y-auto rounded-lg border border-slate-100 dark:border-slate-700/60">
            <table className="w-full text-left text-sm">
              <thead className="sticky top-0 bg-white text-xs uppercase tracking-wide text-slate-400 dark:bg-slate-800">
                <tr>
                  <th className="px-3 py-2 font-medium">Vendedor</th>
                  <th className="px-3 py-2 font-medium">Cidade</th>
                  <th className="px-3 py-2 text-right font-medium">Comissão</th>
                </tr>
              </thead>
              <tbody>
                {(verTodos ? doMes : doMes.slice(0, 50)).map((v) => {
                  const fora = v.ja_gerada || v.valor < minimo || (v.estrangeiro && !incluirEstrangeiros)
                  return (
                    <tr key={v.documento} className={`border-t border-slate-50 dark:border-slate-700/40 ${fora ? "opacity-45" : ""}`}>
                      <td className="px-3 py-1.5">
                        <span className="font-medium text-slate-800 dark:text-slate-200">{v.razao_social}</span>
                        <span className="block text-xs text-slate-400">
                          {v.tipo_documento} {formatarDocumento(v.documento, v.tipo_documento)}
                          {v.lojas.length > 1 && ` · ${v.lojas.length} lojas`}
                          {v.ja_gerada && " · já gerada"}
                        </span>
                        {v.avisos.length > 0 && !v.ja_gerada && (
                          <span className="flex items-center gap-1 text-xs text-warning-700">
                            <AlertTriangle size={12} /> {v.avisos[0]}
                          </span>
                        )}
                      </td>
                      <td className="px-3 py-1.5 text-xs text-slate-500">{v.cidade ? `${v.cidade}/${v.uf}` : v.estrangeiro ? "Exterior" : "—"}</td>
                      <td className="px-3 py-1.5 text-right text-slate-700 dark:text-slate-200">{formatBRL(v.valor)}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
            {!verTodos && doMes.length > 50 && (
              <button type="button" onClick={() => setVerTodos(true)} className="w-full py-2 text-xs font-medium text-primary-600 hover:underline">
                Ver todos os {doMes.length}
              </button>
            )}
          </div>

          {previa.linhas_ignoradas.length > 0 && (
            <details className="text-xs text-slate-500">
              <summary>{previa.linhas_ignoradas.length} linha(s) do arquivo não puderam ser lidas</summary>
              <ul className="mt-1 list-disc pl-5">
                {previa.linhas_ignoradas.map((l) => (
                  <li key={l}>{l}</li>
                ))}
              </ul>
            </details>
          )}

          <fieldset className="rounded-xl border border-slate-200 px-4 py-3 dark:border-slate-700">
            <legend className="px-1 text-xs font-semibold uppercase tracking-wide text-slate-400">Depois de gerar, a Ana também</legend>
            <div className="flex flex-col gap-2 text-sm text-slate-700 dark:text-slate-200">
              {(
                [
                  ["assinar", "Assina todas com o certificado"],
                  ["prefeitura", ambienteTeste ? "Envia à prefeitura (ambiente de teste)" : "Envia à prefeitura"],
                  ["email", "Manda cada nota pro e-mail do vendedor (o que veio no relatório)"],
                ] as const
              ).map(([passo, rotulo]) => (
                <label key={passo} className="flex cursor-pointer items-start gap-2">
                  <input type="checkbox" className="mt-0.5" checked={depois[passo]} disabled={carregando} onChange={(e) => mudarDepois(passo, e.target.checked)} />
                  {rotulo}
                </label>
              ))}
            </div>
            <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
              {passos.length > 0
                ? "Isso roda em segundo plano: depois do seu OK você pode fechar a página. Quando acabar, eu deixo um relatório aqui em Notas em lote e mando por e-mail. Se a prefeitura recusar uma nota por causa do CEP, eu procuro o CEP certo pelo endereço e mando de novo."
                : "Sem nada marcado, as notas ficam só geradas, esperando você assinar."}
            </p>
          </fieldset>

          <div className="flex justify-end gap-3">
            <Button type="button" variant="outline" onClick={onClose}>
              Cancelar
            </Button>
            <Button type="button" variant="accent" disabled={carregando || (aGerar.length === 0 && (jaGeradas === 0 || passos.length === 0))} onClick={gerar}>
              {carregando
                ? "Gerando..."
                : aGerar.length === 0
                  ? "Continuar as que já foram geradas"
                  : `Gerar ${aGerar.length} nota${aGerar.length === 1 ? "" : "s"}${passos.length === 3 ? " e fazer tudo" : passos.length > 0 ? " e continuar" : ""}`}
            </Button>
          </div>
        </div>
      )}

      {resultado && (
        <div className="flex flex-col gap-4">
          <p className="flex items-center gap-2 rounded-lg bg-success-50 px-4 py-3 text-sm text-success-700">
            <CheckCircle2 size={18} />
            {resultado.geradas} nota{resultado.geradas === 1 ? "" : "s"} gerada{resultado.geradas === 1 ? "" : "s"} ({formatBRL(resultado.total)}).
            {resultado.ja_existiam > 0 && ` ${resultado.ja_existiam} já existiam.`}
            {resultado.puladas > 0 && ` ${resultado.puladas} ficaram de fora pelos filtros.`}
          </p>
          {resultado.erros.length > 0 && (
            <ul className="flex flex-col gap-1 text-sm text-danger-700">
              {resultado.erros.map((e) => (
                <li key={e} className="rounded-lg bg-danger-50 px-3 py-2">
                  {e}
                </li>
              ))}
            </ul>
          )}
          {resultado.lote ? (
            <div className="rounded-xl border border-primary-100 bg-primary-50/60 px-4 py-3 text-sm text-slate-700 dark:border-primary-900/40 dark:bg-primary-900/20 dark:text-slate-200">
              <p className="font-semibold text-primary-800 dark:text-primary-200">
                Já comecei a sequência em {resultado.lote.total} nota{resultado.lote.total === 1 ? "" : "s"}.
              </p>
              <p className="mt-1">
                Estou {passos.includes("email") ? "assinando, enviando à prefeitura e mandando pros vendedores" : passos.includes("submeter") ? "assinando e enviando à prefeitura" : "assinando"}, uma por vez.{" "}
                <strong>Pode fechar esta página</strong> — eu continuo sozinha. Quando acabar, o relatório fica em Notas em lote e vai pro seu
                e-mail.
              </p>
            </div>
          ) : (
            <p className="text-sm text-slate-500 dark:text-slate-400">
              {resultado.aviso_lote ?? "As notas estão em Notas em lote, prontas pra revisar. Lá, marque todas e use “Fazer tudo o que falta”."}
            </p>
          )}
          <div className="flex flex-wrap justify-end gap-3">
            <Button type="button" variant={onVerNotas ? "outline" : "accent"} onClick={onClose}>
              Fechar
            </Button>
            {onVerNotas && competencia && (
              <Button type="button" variant="accent" onClick={() => onVerNotas(/^\d{4}-\d{2}-\d{2}$/.test(dataCompetencia) ? dataCompetencia.slice(0, 7) : competencia)}>
                Ver as notas na lista
              </Button>
            )}
          </div>
        </div>
      )}
    </Modal>
  )
}
