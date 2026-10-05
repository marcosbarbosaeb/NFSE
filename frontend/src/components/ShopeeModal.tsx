import { MoedaField } from "./ui/CampoMoeda"
import { AlertTriangle, CheckCircle2, FileSpreadsheet, Globe2 } from "lucide-react"
import { type FormEvent, useEffect, useMemo, useState } from "react"
import { ApiError, api, formatarErro } from "../lib/api"
import { formatBRL, formatCompetenciaLonga, parseBRL } from "../lib/format"
import type { GeracaoShopee, PreviaShopee, VinculoResumo } from "../lib/types"
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

export function ShopeeModal({
  vinculo,
  aliquotaReferencia,
  onClose,
  onGeradas,
  onVerNotas,
}: {
  vinculo: VinculoResumo
  aliquotaReferencia: number | null
  onClose: () => void
  onGeradas: () => void
  /** "Ver as notas na lista": filtra a lista pela Shopee + mês gerado. */
  onVerNotas?: (competencia: string) => void
}) {
  const [arquivo, setArquivo] = useState<File | null>(null)
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
      const resp = await api.postForm<GeracaoShopee>("/shopee/gerar", form)
      setResultado(resp)
      if (resp.geradas > 0) onGeradas()
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
          <label className="flex cursor-pointer flex-col items-center gap-2 rounded-xl border-2 border-dashed border-slate-300 px-4 py-8 text-center text-sm text-slate-500 hover:border-primary-400 dark:border-slate-600">
            <FileSpreadsheet size={28} className="text-primary-500" />
            {arquivo ? <span className="font-medium text-slate-800 dark:text-slate-100">{arquivo.name}</span> : "Clique pra escolher o arquivo .csv"}
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
                  ? `Vai em cada nota. Na lista, elas continuam em ${formatCompetenciaLonga(competencia)} (mês do relatório).`
                  : "Vai em cada nota."
              }
            />
          </div>

          {estrangeiros > 0 && (
            <label className="flex items-start gap-2 rounded-lg bg-warning-50 px-3 py-2 text-sm text-warning-700">
              <input type="checkbox" checked={incluirEstrangeiros} onChange={(e) => setIncluirEstrangeiros(e.target.checked)} className="mt-0.5" />
              <span>
                <Globe2 size={14} className="mr-1 inline" />
                Incluir {estrangeiros} vendedor(es) de fora do Brasil. Nota pra fora do país é exportação de serviço e tem
                regra própria de ISS — confirme com seu contador antes.
              </span>
            </label>
          )}

          <div className="rounded-xl border border-success-100 bg-success-50/60 px-4 py-3 dark:border-success-900/40 dark:bg-success-900/20">
            <p className="text-sm text-success-700 dark:text-success-300">
              <strong>
                {aGerar.length} nota{aGerar.length === 1 ? "" : "s"} · {formatBRL(totalAGerar)}
              </strong>{" "}
              em {competencia && formatCompetenciaLonga(competencia)}
              {jaGeradas > 0 && ` (${jaGeradas} já geradas antes ficam como estão)`}
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

          <div className="flex justify-end gap-3">
            <Button type="button" variant="outline" onClick={onClose}>
              Cancelar
            </Button>
            <Button type="button" variant="accent" disabled={carregando || aGerar.length === 0} onClick={gerar}>
              {carregando ? "Gerando..." : `Gerar ${aGerar.length} nota${aGerar.length === 1 ? "" : "s"}`}
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
          <p className="text-sm text-slate-500 dark:text-slate-400">
            As notas estão na lista da aba NFS-e, prontas pra revisar e assinar. Na lista, marque todas pra assinar e enviar à
            prefeitura de uma vez — depois é só usar “Enviar todas por e-mail”.
          </p>
          <div className="flex flex-wrap justify-end gap-3">
            <Button type="button" variant={onVerNotas ? "outline" : "accent"} onClick={onClose}>
              Fechar
            </Button>
            {onVerNotas && competencia && (
              <Button type="button" variant="accent" onClick={() => onVerNotas(competencia)}>
                Ver as notas na lista
              </Button>
            )}
          </div>
        </div>
      )}
    </Modal>
  )
}
