import { MoedaField } from "../ui/CampoMoeda"
import { Pencil, Plus, RotateCcw, Trash2 } from "lucide-react"
import { type FormEvent, useEffect, useId, useState } from "react"
import { api } from "../../lib/api"
import { classeCampo, mensagemErro, valorParaCampo } from "../../lib/financeiro"
import { formatBRL, formatCompetenciaLonga, parseBRL } from "../../lib/format"
import type { ContaFixa, ContaFixaRequest, TipoLancamento } from "../../lib/types"
import { Badge } from "../ui/Badge"
import { Button } from "../ui/Button"
import { Field } from "../ui/Field"
import { Modal } from "../ui/Modal"

// Contas fixas (28/09/2026): cada uma vira, todo mês, um lançamento "a pagar"
// nas contas do mês (pró-labore, Simples, cartão, ferramentas...).

interface Formulario {
  id: string | null
  nome: string
  categoria: string
  tipo: TipoLancamento
  valor: string
  dia: string
  conta: string
  /** Pagamento agendado até este mês (AAAA-MM, inclusive); "" = não. */
  agendadoAte: string
}

const VAZIO: Formulario = { id: null, nome: "", categoria: "", tipo: "despesa", valor: "", dia: "", conta: "", agendadoAte: "" }

export function ContasFixasModal({ onClose, onMudou }: { onClose: () => void; onMudou: () => void }) {
  const [lista, setLista] = useState<ContaFixa[] | null>(null)
  const [form, setForm] = useState<Formulario | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  const [enviando, setEnviando] = useState(false)
  const [verInativas, setVerInativas] = useState(false)
  const idTipo = useId()

  function carregar() {
    api
      .get<ContaFixa[]>("/financeiro/contas-fixas")
      .then(setLista)
      .catch((err) => {
        setErro(mensagemErro(err))
        setLista([])
      })
  }

  useEffect(carregar, [])

  function editar(c: ContaFixa) {
    setErro(null)
    setForm({
      id: c.id,
      nome: c.nome,
      categoria: c.categoria === c.nome ? "" : c.categoria,
      tipo: c.tipo,
      valor: valorParaCampo(c.valor_padrao),
      dia: c.dia_vencimento ? String(c.dia_vencimento) : "",
      conta: c.conta ?? "",
      agendadoAte: c.agendado_ate ?? "",
    })
  }

  async function salvar(e: FormEvent) {
    e.preventDefault()
    if (!form) return
    setErro(null)
    const valor = form.valor.trim() ? parseBRL(form.valor) : null
    if (form.valor.trim() && (valor === null || valor < 0)) {
      setErro("Valor padrão inválido — deixe vazio se varia todo mês.")
      return
    }
    const dia = form.dia ? Number(form.dia) : null
    if (dia !== null && (!Number.isInteger(dia) || dia < 1 || dia > 31)) {
      setErro("Dia do vencimento entre 1 e 31.")
      return
    }
    const corpo: ContaFixaRequest = {
      nome: form.nome.trim(),
      categoria: form.categoria.trim() || form.nome.trim(),
      tipo: form.tipo,
      valor_padrao: valor || null,
      dia_vencimento: dia,
      conta: form.conta.trim() || null,
      agendado_ate: form.agendadoAte || "",
    }
    if (form.agendadoAte && !valor) {
      setErro("Pra deixar o pagamento agendado, informe o valor da conta.")
      return
    }
    setEnviando(true)
    try {
      if (form.id) await api.patch(`/financeiro/contas-fixas/${form.id}`, corpo)
      else await api.post("/financeiro/contas-fixas", corpo)
      setForm(null)
      carregar()
      onMudou()
    } catch (err) {
      setErro(mensagemErro(err))
    } finally {
      setEnviando(false)
    }
  }

  async function desativar(c: ContaFixa) {
    if (!window.confirm(`Parar de lançar "${c.nome}" todo mês?\n\nO histórico fica; o lançamento em aberto e sem pagamento deste mês em diante sai da lista.`)) return
    setErro(null)
    try {
      await api.delete(`/financeiro/contas-fixas/${c.id}`)
      carregar()
      onMudou()
    } catch (err) {
      setErro(mensagemErro(err))
    }
  }

  async function reativar(c: ContaFixa) {
    setErro(null)
    try {
      await api.patch(`/financeiro/contas-fixas/${c.id}`, { ativa: true })
      carregar()
      onMudou()
    } catch (err) {
      setErro(mensagemErro(err))
    }
  }

  const ativas = (lista ?? []).filter((c) => c.ativa)
  const inativas = (lista ?? []).filter((c) => !c.ativa)

  const linha = (c: ContaFixa) => (
    <li key={c.id} className="flex items-center gap-3 py-2.5">
      <div className="min-w-0 flex-1">
        <p className={`truncate text-sm font-medium ${c.ativa ? "text-slate-800 dark:text-slate-200" : "text-slate-400 line-through dark:text-slate-500"}`}>
          {c.nome} {c.tipo === "retirada" && <Badge variant="info">retirada</Badge>}
        </p>
        <p className="truncate text-xs text-slate-400 dark:text-slate-500">
          {[
            c.categoria !== c.nome ? c.categoria : null,
            c.dia_vencimento ? `vence dia ${c.dia_vencimento}` : null,
            c.conta,
            c.agendado_ate ? `agendado até ${formatCompetenciaLonga(c.agendado_ate).toLowerCase()}` : null,
          ]
            .filter(Boolean)
            .join(" · ") || "sem vencimento"}
        </p>
      </div>
      <span className="shrink-0 text-sm tabular-nums text-slate-700 dark:text-slate-200">
        {c.valor_padrao ? formatBRL(c.valor_padrao) : <span className="text-xs text-slate-400 dark:text-slate-500">varia</span>}
      </span>
      {c.ativa ? (
        <div className="flex shrink-0 gap-1">
          <button
            type="button"
            onClick={() => editar(c)}
            aria-label={`Editar ${c.nome}`}
            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700 dark:hover:bg-slate-700 dark:hover:text-slate-200"
          >
            <Pencil size={15} />
          </button>
          <button
            type="button"
            onClick={() => desativar(c)}
            aria-label={`Desativar ${c.nome}`}
            className="rounded-lg p-1.5 text-slate-400 hover:bg-danger-50 hover:text-danger-600 dark:hover:bg-danger-900/30"
          >
            <Trash2 size={15} />
          </button>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => reativar(c)}
          aria-label={`Reativar ${c.nome}`}
          className="shrink-0 rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700 dark:hover:bg-slate-700 dark:hover:text-slate-200"
        >
          <RotateCcw size={15} />
        </button>
      )}
    </li>
  )

  return (
    <Modal titulo="Contas recorrentes" onClose={onClose} largura="max-w-xl">
      <div className="flex flex-col gap-4">
        <p className="text-sm text-slate-500 dark:text-slate-400">
          Cada conta recorrente aparece todo mês em <strong className="font-medium text-slate-700 dark:text-slate-200">Contas do mês</strong>, pra você ticar quando pagar.
          Sem valor, você informa na hora de ticar (Simples, cartão...). Se o pagamento já está agendado no banco, diga até que
          mês: ela já aparece ticada até lá.
        </p>
        {erro && <p className="rounded-lg bg-danger-50 px-4 py-3 text-sm text-danger-700 dark:bg-danger-900/40 dark:text-danger-300">{erro}</p>}

        {form ? (
          <form onSubmit={salvar} className="flex flex-col gap-3 rounded-xl border border-slate-200 p-4 dark:border-slate-700">
            <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-200">{form.id ? "Editar conta recorrente" : "Nova conta recorrente"}</h3>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <Field label="Nome" required maxLength={120} value={form.nome} onChange={(e) => setForm({ ...form, nome: e.target.value })} placeholder="Ex.: Pró-labore" />
              <Field
                label="Categoria (opcional)"
                maxLength={100}
                value={form.categoria}
                onChange={(e) => setForm({ ...form, categoria: e.target.value })}
                placeholder="igual ao nome"
              />
            </div>
            <label className="block" htmlFor={idTipo}>
              <span className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Tipo</span>
              <select id={idTipo} value={form.tipo} onChange={(e) => setForm({ ...form, tipo: e.target.value as TipoLancamento })} className={classeCampo}>
                <option value="despesa">Despesa</option>
                <option value="retirada">Retirada / distribuição de lucros</option>
              </select>
            </label>
            <div className="grid grid-cols-2 gap-3">
              <MoedaField
                label="Valor"
                saida="br"
                valor={form.valor}
                onChange={(valor) => setForm({ ...form, valor })}
                placeholder="vazio = varia"
                hint="Vazio = varia todo mês."
              />
              <Field
                label="Dia do vencimento"
                type="number"
                min={1}
                max={31}
                value={form.dia}
                onChange={(e) => setForm({ ...form, dia: e.target.value })}
                placeholder="Ex.: 20"
              />
            </div>
            <Field label="Conta (opcional)" maxLength={60} value={form.conta} onChange={(e) => setForm({ ...form, conta: e.target.value })} placeholder="Ex.: Inter" />
            <label className="block">
              <span className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Pagamento já agendado até (opcional)</span>
              <span className="flex items-center gap-2">
                <input
                  type="month"
                  value={form.agendadoAte}
                  onChange={(e) => setForm({ ...form, agendadoAte: e.target.value })}
                  className={classeCampo}
                  aria-label="Pagamento agendado até o mês"
                />
                {form.agendadoAte && (
                  <button type="button" onClick={() => setForm({ ...form, agendadoAte: "" })} className="shrink-0 text-xs font-medium text-slate-500 hover:text-danger-600">
                    tirar
                  </button>
                )}
              </span>
              <span className="mt-1 block text-xs text-slate-400 dark:text-slate-500">
                Até este mês (inclusive) a conta já aparece ticada. No mês seguinte ela volta a aparecer pra pagar.
              </span>
            </label>
            {form.id && <p className="text-xs text-slate-400 dark:text-slate-500">A mudança vale pros próximos meses; o lançamento deste mês você ajusta direto na lista.</p>}
            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={() => setForm(null)}>
                Cancelar
              </Button>
              <Button type="submit" variant="accent" disabled={enviando}>
                {enviando ? "Salvando..." : "Salvar"}
              </Button>
            </div>
          </form>
        ) : (
          <Button variant="outline" onClick={() => setForm({ ...VAZIO })} className="self-start">
            <Plus size={16} /> Nova conta recorrente
          </Button>
        )}

        {lista === null ? (
          <p className="py-4 text-center text-sm text-slate-400">Carregando...</p>
        ) : ativas.length === 0 ? (
          <p className="py-4 text-center text-sm text-slate-400 dark:text-slate-500">Nenhuma conta recorrente ainda.</p>
        ) : (
          <ul className="divide-y divide-slate-100 dark:divide-slate-700/60">{ativas.map(linha)}</ul>
        )}

        {inativas.length > 0 && (
          <div>
            <button type="button" onClick={() => setVerInativas((v) => !v)} className="text-xs font-medium text-primary-600 hover:text-primary-700 dark:text-primary-300" aria-expanded={verInativas}>
              {verInativas ? "Esconder" : "Ver"} desativadas ({inativas.length})
            </button>
            {verInativas && <ul className="mt-1 divide-y divide-slate-100 dark:divide-slate-700/60">{inativas.map(linha)}</ul>}
          </div>
        )}
      </div>
    </Modal>
  )
}
