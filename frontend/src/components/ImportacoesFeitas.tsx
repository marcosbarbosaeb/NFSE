import { History, Undo2 } from "lucide-react"
import { useCallback, useEffect, useState } from "react"
import { api } from "../lib/api"
import { mensagemDeErro } from "../lib/excluir"
import { Button } from "./ui/Button"
import { Card } from "./ui/Card"
import { Modal } from "./ui/Modal"

/** "Precisamos poder desfazer uma importação" (07/10/2026): a lista do que já
 * foi importado, com um botão pra desfazer cada uma. `origem`: extratos e
 * planilhas do Financeiro, ou as notas trazidas do Emissor Nacional. Sem
 * nenhuma importação, não aparece. */

type Origem = "financeiro" | "nacional"

interface Item {
  chave: string
  titulo: string
  quando: string | null
  resumo: string
  corpo: Record<string, string>
  aviso: string
}

interface DoFinanceiro {
  importacoes: { tipo: "extrato" | "planilha"; quando: string; titulo: string; resumo: string }[]
}
interface DoNacional {
  importacoes: { id: string; quando: string | null; titulo: string; notas: number; periodo: string }[]
}

const AVISO = {
  extrato:
    "As linhas desse extrato saem da conciliação. Os recebimentos e despesas que ele criou são apagados (as notas voltam a ficar a receber) e as contas que ele deu como pagas voltam a ficar em aberto. O que você lançou à mão continua.",
  planilha:
    "Os recebimentos, despesas, retiradas, contas fixas e rotinas que vieram dessa planilha são apagados. O que você lançou à mão continua.",
  nacional:
    "As notas que essa importação trouxe saem da Ana, junto com os tomadores que ela criou e ficaram sem nenhuma nota. Nada muda no Emissor Nacional: as notas continuam válidas lá, e dá pra importar de novo. As notas geradas aqui pela Ana não são tocadas.",
}

function quandoFoi(iso: string | null): string {
  if (!iso) return "antes de 07/10/2026"
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ""
  return d.toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" })
}

function mes(competencia: string): string {
  const [ano, m] = competencia.split("-")
  return `${m}/${ano}`
}

async function carregar(origem: Origem): Promise<Item[]> {
  if (origem === "financeiro") {
    const d = await api.get<DoFinanceiro>("/financeiro/importacoes")
    return d.importacoes.map((i) => ({
      chave: `${i.tipo}:${i.quando}`,
      titulo: i.titulo,
      quando: i.quando,
      resumo: i.resumo,
      corpo: { tipo: i.tipo, quando: i.quando },
      aviso: AVISO[i.tipo],
    }))
  }
  const d = await api.get<DoNacional>("/importar/nacional/importacoes")
  return d.importacoes.map((i) => ({
    chave: i.id,
    titulo: i.titulo,
    quando: i.quando,
    resumo: `${i.notas} nota${i.notas === 1 ? "" : "s"} · ${i.periodo.split(" a ").map(mes).join(" a ")}`,
    corpo: { importacao: i.id },
    aviso: AVISO.nacional,
  }))
}

export function ImportacoesFeitas({ origem, recarga = 0, onDesfeito }: { origem: Origem; recarga?: number; onDesfeito?: () => void }) {
  const [itens, setItens] = useState<Item[]>([])
  const [alvo, setAlvo] = useState<Item | null>(null)
  const [desfazendo, setDesfazendo] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const [feito, setFeito] = useState<string | null>(null)

  const recarregar = useCallback(() => {
    carregar(origem)
      .then(setItens)
      .catch(() => setItens([]))
  }, [origem])
  useEffect(recarregar, [recarregar, recarga])

  async function desfazer() {
    if (!alvo) return
    setDesfazendo(true)
    setErro(null)
    try {
      await api.post(origem === "financeiro" ? "/financeiro/importacoes/desfazer" : "/importar/nacional/desfazer", alvo.corpo)
      setFeito(`Importação desfeita: ${alvo.titulo}.`)
      setAlvo(null)
      recarregar()
      onDesfeito?.()
    } catch (err) {
      setErro(mensagemDeErro(err))
    } finally {
      setDesfazendo(false)
    }
  }

  if (itens.length === 0 && !feito) return null
  return (
    <Card className="p-5" data-importacoes={origem}>
      <h2 className="mb-1 flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">
        <History size={16} aria-hidden /> Importações feitas
      </h2>
      <p className="mb-3 text-sm text-slate-500 dark:text-slate-400">
        Importou a coisa errada ou ficou bagunçado? Desfaça a importação inteira de uma vez.
      </p>
      {feito && (
        <p role="status" className="mb-3 rounded-lg bg-success-50 px-3 py-2 text-sm text-success-700 dark:bg-success-900/30 dark:text-success-300">
          {feito}
        </p>
      )}
      <ul className="divide-y divide-slate-100 dark:divide-slate-700">
        {itens.map((i) => (
          <li key={i.chave} className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 py-2.5">
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-slate-800 dark:text-slate-200">{i.titulo}</p>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                {quandoFoi(i.quando)} · {i.resumo}
              </p>
            </div>
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                setErro(null)
                setFeito(null)
                setAlvo(i)
              }}
            >
              <Undo2 size={15} aria-hidden /> Desfazer
            </Button>
          </li>
        ))}
      </ul>

      {alvo && (
        <Modal titulo="Desfazer esta importação?" onClose={() => !desfazendo && setAlvo(null)}>
          <p className="text-sm font-medium text-slate-800 dark:text-slate-200">{alvo.titulo}</p>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            {quandoFoi(alvo.quando)} · {alvo.resumo}
          </p>
          <p className="mt-3 text-sm text-slate-600 dark:text-slate-300">{alvo.aviso}</p>
          {erro && <p className="mt-3 rounded-lg bg-danger-50 px-3 py-2 text-sm text-danger-700 dark:bg-danger-900/30 dark:text-danger-300">{erro}</p>}
          <div className="mt-5 flex flex-wrap justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => setAlvo(null)} disabled={desfazendo}>
              Deixar como está
            </Button>
            <Button type="button" variant="danger" onClick={() => void desfazer()} disabled={desfazendo}>
              <Undo2 size={15} aria-hidden /> {desfazendo ? "Desfazendo..." : "Desfazer importação"}
            </Button>
          </div>
        </Modal>
      )}
    </Card>
  )
}
