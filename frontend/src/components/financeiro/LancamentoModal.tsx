import { type FormEvent, useId, useState } from "react"
import { api } from "../../lib/api"
import { CATEGORIA_RETIRADA, classeCampo, classeCheckbox, mensagemErro, valorParaCampo } from "../../lib/financeiro"
import { competenciaAtual, parseBRL } from "../../lib/format"
import type { AtualizarDespesaRequest, Despesa, RegistrarDespesaRequest, TipoLancamento } from "../../lib/types"
import { Button } from "../ui/Button"
import { Field } from "../ui/Field"
import { Modal } from "../ui/Modal"

// Lançar / editar despesa ou retirada (28/09/2026) — substitui, na tela
// Financeiro, o modal simples de "Registrar despesa": agora com tipo
// (despesa x distribuição de lucros), descrição, conta e "já pago?".

export function LancamentoModal({
  despesa,
  competenciaInicial,
  tipoInicial = "despesa",
  categorias = [],
  contas = [],
  onClose,
  onSalvo,
}: {
  /** Presente = editar. */
  despesa?: Despesa | null
  competenciaInicial?: string
  tipoInicial?: TipoLancamento
  /** Sugestões (datalist) de categorias e contas já usadas. */
  categorias?: string[]
  contas?: string[]
  onClose: () => void
  onSalvo: (d: Despesa) => void
}) {
  const editando = !!despesa
  const idCategorias = useId()
  const idContas = useId()
  const [tipo, setTipo] = useState<TipoLancamento>(despesa?.tipo ?? tipoInicial)
  const [categoria, setCategoria] = useState(despesa?.categoria ?? (tipoInicial === "retirada" ? CATEGORIA_RETIRADA : ""))
  const [descricao, setDescricao] = useState(despesa?.descricao ?? "")
  const [competencia, setCompetencia] = useState(despesa?.competencia ?? competenciaInicial ?? competenciaAtual())
  const [valor, setValor] = useState(valorParaCampo(despesa?.valor))
  const [conta, setConta] = useState(despesa?.conta ?? "")
  const [pago, setPago] = useState(despesa?.pago ?? true)
  const [vencimento, setVencimento] = useState(despesa?.vencimento?.slice(0, 10) ?? "")
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  function trocarTipo(novo: TipoLancamento) {
    setTipo(novo)
    // Retirada sempre cai em "Distribuição de lucros" (a menos que a pessoa
    // já tenha escrito outra coisa).
    if (novo === "retirada" && !categoria.trim()) setCategoria(CATEGORIA_RETIRADA)
    if (novo === "despesa" && categoria === CATEGORIA_RETIRADA) setCategoria("")
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setErro(null)
    const numero = parseBRL(valor)
    if (numero === null || numero < 0 || (!editando && numero === 0)) {
      setErro("Informe um valor maior que zero.")
      return
    }
    const base: RegistrarDespesaRequest = {
      categoria: categoria.trim() || (tipo === "retirada" ? CATEGORIA_RETIRADA : ""),
      competencia,
      valor: numero,
      descricao: descricao.trim() || null,
      tipo,
      conta: conta.trim() || null,
      vencimento: vencimento || null,
      pago,
    }
    if (!base.categoria) {
      setErro("Informe a categoria.")
      return
    }
    setEnviando(true)
    try {
      const salvo = despesa
        ? await api.patch<Despesa>(`/despesas/${despesa.id}`, base satisfies AtualizarDespesaRequest)
        : await api.post<Despesa>("/despesas", base)
      onSalvo(salvo)
    } catch (err) {
      setErro(mensagemErro(err))
    } finally {
      setEnviando(false)
    }
  }

  const botaoTipo = (valorTipo: TipoLancamento, rotulo: string) => (
    <button
      type="button"
      role="radio"
      aria-checked={tipo === valorTipo}
      onClick={() => trocarTipo(valorTipo)}
      className={`flex-1 rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
        tipo === valorTipo
          ? "bg-white text-slate-900 shadow-sm dark:bg-slate-700 dark:text-slate-100"
          : "text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200"
      }`}
    >
      {rotulo}
    </button>
  )

  return (
    <Modal titulo={editando ? "Editar lançamento" : tipo === "retirada" ? "Lançar retirada" : "Lançar despesa"} onClose={onClose}>
      <form onSubmit={onSubmit} className="flex flex-col gap-4">
        {erro && <p className="rounded-lg bg-danger-50 px-4 py-3 text-sm text-danger-700 dark:bg-danger-900/40 dark:text-danger-300">{erro}</p>}

        <div>
          <span className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Tipo</span>
          <div role="radiogroup" aria-label="Tipo de lançamento" className="flex gap-1 rounded-lg bg-slate-100 p-1 dark:bg-slate-900">
            {botaoTipo("despesa", "Despesa")}
            {botaoTipo("retirada", "Retirada / distribuição de lucros")}
          </div>
          {tipo === "retirada" && (
            <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">Retirada não entra nas despesas: sai do lucro que sobrou (saldo a distribuir).</p>
          )}
        </div>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <Field
            label="Categoria"
            required
            value={categoria}
            onChange={(e) => setCategoria(e.target.value)}
            list={idCategorias}
            placeholder={tipo === "retirada" ? CATEGORIA_RETIRADA : "Ex.: Pró-labore, Simples Nacional"}
          />
          <Field
            label="Descrição (opcional)"
            value={descricao}
            onChange={(e) => setDescricao(e.target.value)}
            maxLength={200}
            placeholder={tipo === "retirada" ? "Ex.: Retirada Inter" : "Ex.: Manychat — plano Pro"}
          />
        </div>
        <datalist id={idCategorias}>
          {categorias.map((c) => (
            <option key={c} value={c} />
          ))}
        </datalist>

        <div className="grid grid-cols-2 gap-3">
          <label className="block">
            <span className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Competência</span>
            <input required type="month" value={competencia} onChange={(e) => setCompetencia(e.target.value)} className={classeCampo} />
          </label>
          <Field label="Valor (R$)" required inputMode="decimal" value={valor} onChange={(e) => setValor(e.target.value)} placeholder="0,00" />
        </div>

        <Field
          label="Conta (opcional)"
          value={conta}
          onChange={(e) => setConta(e.target.value)}
          list={idContas}
          maxLength={60}
          placeholder="Ex.: Inter, Mercado Pago"
          hint="De qual conta saiu o dinheiro."
        />
        <datalist id={idContas}>
          {contas.map((c) => (
            <option key={c} value={c} />
          ))}
        </datalist>

        <div className="flex flex-col gap-3 rounded-lg border border-slate-200 p-3 dark:border-slate-700">
          <label className="flex items-center gap-2 text-sm text-slate-700 dark:text-slate-200">
            <input type="checkbox" checked={pago} onChange={(e) => setPago(e.target.checked)} className={classeCheckbox} />
            Já {tipo === "retirada" ? "retirei" : "paguei"}
          </label>
          {!pago && (
            <label className="block">
              <span className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Vencimento (opcional)</span>
              <input type="date" value={vencimento} onChange={(e) => setVencimento(e.target.value)} className={classeCampo} />
              <span className="mt-1 block text-xs text-slate-400 dark:text-slate-500">Fica "a pagar" nas contas do mês até você ticar.</span>
            </label>
          )}
        </div>

        <div className="flex justify-end gap-3 pt-2">
          <Button type="button" variant="outline" onClick={onClose}>
            Cancelar
          </Button>
          <Button type="submit" variant="accent" disabled={enviando}>
            {enviando ? "Salvando..." : editando ? "Salvar" : "Lançar"}
          </Button>
        </div>
      </form>
    </Modal>
  )
}
