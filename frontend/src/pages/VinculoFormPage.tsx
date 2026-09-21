import { type FormEvent, useEffect, useState } from "react"
import { useNavigate, useParams, useSearchParams } from "react-router-dom"
import { Button } from "../components/ui/Button"
import { Card } from "../components/ui/Card"
import { Field, FieldWrap } from "../components/ui/Field"
import { ApiError, api, formatarErro } from "../lib/api"
import type { Tomador, VinculoCriarRequest, VinculoDetalhe } from "../lib/types"

const METODOS_CAPTURA = [
  { value: "manual", label: "Manual (digitar o valor)" },
  { value: "csv", label: "Importação de CSV" },
  { value: "pdf", label: "PDF (extração automática — ainda não disponível)" },
  { value: "chat", label: "Pelo chat (ainda não disponível)" },
]

interface FormState {
  apelido: string
  cod_local_prestacao: string
  cod_trib_nacional: string
  cod_trib_municipal: string
  template_descricao: string
  metodo_captura_valor: string
  serie: string
  requer_revisao: boolean
  ativo: boolean
  dia_limite_emissao: string
  dias_para_recebimento: string
}

const ESTADO_INICIAL: FormState = {
  apelido: "",
  cod_local_prestacao: "",
  cod_trib_nacional: "",
  cod_trib_municipal: "",
  template_descricao: "",
  metodo_captura_valor: "manual",
  serie: "1",
  requer_revisao: true,
  ativo: true,
  dia_limite_emissao: "",
  dias_para_recebimento: "",
}

export function VinculoFormPage() {
  const { id } = useParams<{ id: string }>()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const editando = Boolean(id)

  const [form, setForm] = useState<FormState>(ESTADO_INICIAL)
  const [tomadorExistenteId, setTomadorExistenteId] = useState<string | null>(searchParams.get("tomador_id"))
  const [modoTomador, setModoTomador] = useState<"existente" | "novo">(searchParams.get("tomador_id") ? "existente" : "existente")
  const [tomadorSelecionado, setTomadorSelecionado] = useState<Tomador | null>(null)
  const [tomadores, setTomadores] = useState<Tomador[]>([])
  const [novoTomador, setNovoTomador] = useState({
    cnpj: "", razao_social: "", cod_municipio: "", cep: "", logradouro: "", numero: "", complemento: "", bairro: "",
  })

  const [carregando, setCarregando] = useState(editando)
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  // Modo edição: carrega o vínculo existente.
  useEffect(() => {
    if (!editando || !id) return
    api
      .get<VinculoDetalhe>(`/vinculos/${id}`)
      .then((v) => {
        setForm({
          apelido: v.apelido,
          cod_local_prestacao: v.cod_local_prestacao,
          cod_trib_nacional: v.cod_trib_nacional,
          cod_trib_municipal: v.cod_trib_municipal ?? "",
          template_descricao: v.template_descricao,
          metodo_captura_valor: v.metodo_captura_valor,
          serie: v.serie,
          requer_revisao: v.requer_revisao,
          ativo: v.ativo,
          dia_limite_emissao: v.dia_limite_emissao?.toString() ?? "",
          dias_para_recebimento: v.dias_para_recebimento?.toString() ?? "",
        })
        setTomadorSelecionado(v.tomador)
      })
      .catch((err) => setErro(err instanceof ApiError ? formatarErro(err.detail) : "Falha ao carregar."))
      .finally(() => setCarregando(false))
  }, [editando, id])

  // Modo criação: catálogo pra escolher um tomador existente.
  useEffect(() => {
    if (editando) return
    api.get<Tomador[]>("/tomadores?apenas_meus=false").then(setTomadores)
  }, [editando])

  useEffect(() => {
    if (tomadorExistenteId) {
      const achado = tomadores.find((t) => t.id === tomadorExistenteId)
      if (achado) setTomadorSelecionado(achado)
    }
  }, [tomadorExistenteId, tomadores])

  function atualizarCampo<K extends keyof FormState>(campo: K, valor: FormState[K]) {
    setForm((f) => ({ ...f, [campo]: valor }))
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setErro(null)
    setEnviando(true)
    try {
      const base = {
        apelido: form.apelido,
        cod_local_prestacao: form.cod_local_prestacao,
        cod_trib_nacional: form.cod_trib_nacional,
        cod_trib_municipal: form.cod_trib_municipal || null,
        template_descricao: form.template_descricao,
        metodo_captura_valor: form.metodo_captura_valor,
        serie: form.serie,
        requer_revisao: form.requer_revisao,
        dia_limite_emissao: form.dia_limite_emissao ? Number(form.dia_limite_emissao) : null,
        dias_para_recebimento: form.dias_para_recebimento ? Number(form.dias_para_recebimento) : null,
      }

      if (editando && id) {
        await api.patch(`/vinculos/${id}`, { ...base, ativo: form.ativo })
        navigate("/tomadores")
        return
      }

      const payload: VinculoCriarRequest =
        modoTomador === "existente"
          ? { ...base, tomador_id: tomadorExistenteId }
          : { ...base, novo_tomador: { ...novoTomador, cep: novoTomador.cep || null } }

      const criado = await api.post<VinculoDetalhe>("/vinculos", payload)
      navigate(`/tomadores/${criado.id}`)
    } catch (err) {
      setErro(err instanceof ApiError ? formatarErro(err.detail) : "Falha de conexão. Tente de novo.")
    } finally {
      setEnviando(false)
    }
  }

  if (carregando) return <p className="text-sm text-slate-400 dark:text-slate-500">Carregando...</p>

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">{editando ? "Regras de emissão" : "Adicionar tomador"}</h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          {editando
            ? "Estas regras valem como padrão para as próximas notas deste vínculo — não alteram notas já emitidas."
            : "Use um tomador já cadastrado ou cadastre um novo, do jeito que o Emissor Nacional permite."}
        </p>
      </div>

      <form onSubmit={onSubmit} className="flex flex-col gap-6">
        {erro && <p className="rounded-lg bg-danger-50 px-4 py-3 text-sm text-danger-700">{erro}</p>}

        {editando ? (
          tomadorSelecionado && (
            <Card className="p-5">
              <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">Tomador</h2>
              <p className="font-medium text-slate-800 dark:text-slate-200">{tomadorSelecionado.razao_social}</p>
              <p className="text-sm text-slate-500 dark:text-slate-400">{tomadorSelecionado.cnpj}</p>
            </Card>
          )
        ) : (
          <Card className="p-5">
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">Tomador</h2>
            <div className="mb-4 flex rounded-lg bg-slate-100 dark:bg-slate-700 p-1 text-sm">
              <button
                type="button"
                onClick={() => setModoTomador("existente")}
                className={`flex-1 rounded-md px-3 py-1.5 font-medium transition-colors ${
                  modoTomador === "existente" ? "bg-white dark:bg-slate-800 text-primary-700 shadow-sm" : "text-slate-500 dark:text-slate-400"
                }`}
              >
                Usar tomador existente
              </button>
              <button
                type="button"
                onClick={() => setModoTomador("novo")}
                className={`flex-1 rounded-md px-3 py-1.5 font-medium transition-colors ${
                  modoTomador === "novo" ? "bg-white dark:bg-slate-800 text-primary-700 shadow-sm" : "text-slate-500 dark:text-slate-400"
                }`}
              >
                Cadastrar novo tomador
              </button>
            </div>

            {modoTomador === "existente" ? (
              <FieldWrap label="Tomador do catálogo">
                <select
                  required
                  value={tomadorExistenteId ?? ""}
                  onChange={(e) => setTomadorExistenteId(e.target.value || null)}
                  className="w-full rounded-lg border border-slate-300 bg-white dark:bg-slate-800 px-3 py-2 text-sm text-slate-900 dark:text-slate-100 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
                >
                  <option value="" disabled>
                    Selecione...
                  </option>
                  {tomadores.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.razao_social} — {t.cnpj}
                    </option>
                  ))}
                </select>
              </FieldWrap>
            ) : (
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <Field
                  label="CNPJ"
                  required
                  value={novoTomador.cnpj}
                  onChange={(e) => setNovoTomador((t) => ({ ...t, cnpj: e.target.value }))}
                  placeholder="Só números"
                />
                <Field
                  label="Razão social"
                  required
                  value={novoTomador.razao_social}
                  onChange={(e) => setNovoTomador((t) => ({ ...t, razao_social: e.target.value }))}
                />
                <Field
                  label="Município (código IBGE)"
                  required
                  value={novoTomador.cod_municipio}
                  onChange={(e) => setNovoTomador((t) => ({ ...t, cod_municipio: e.target.value }))}
                  placeholder="7 dígitos"
                />
                <Field
                  label="CEP"
                  value={novoTomador.cep}
                  onChange={(e) => setNovoTomador((t) => ({ ...t, cep: e.target.value }))}
                />
                <Field
                  label="Logradouro"
                  value={novoTomador.logradouro}
                  onChange={(e) => setNovoTomador((t) => ({ ...t, logradouro: e.target.value }))}
                />
                <Field
                  label="Número"
                  value={novoTomador.numero}
                  onChange={(e) => setNovoTomador((t) => ({ ...t, numero: e.target.value }))}
                />
                <Field
                  label="Complemento"
                  value={novoTomador.complemento}
                  onChange={(e) => setNovoTomador((t) => ({ ...t, complemento: e.target.value }))}
                />
                <Field
                  label="Bairro"
                  value={novoTomador.bairro}
                  onChange={(e) => setNovoTomador((t) => ({ ...t, bairro: e.target.value }))}
                />
              </div>
            )}
          </Card>
        )}

        <Card className="p-5">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">Regras de emissão</h2>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <Field
              label="Apelido"
              required
              value={form.apelido}
              onChange={(e) => atualizarCampo("apelido", e.target.value)}
              placeholder='Ex.: "AWIN", "Squad Época"'
            />
            <Field
              label="Série"
              required
              value={form.serie}
              onChange={(e) => atualizarCampo("serie", e.target.value)}
            />
            <Field
              label="Código do local de prestação (IBGE)"
              required
              value={form.cod_local_prestacao}
              onChange={(e) => atualizarCampo("cod_local_prestacao", e.target.value)}
            />
            <Field
              label="Código de tributação nacional"
              required
              value={form.cod_trib_nacional}
              onChange={(e) => atualizarCampo("cod_trib_nacional", e.target.value)}
            />
            <Field
              label="Código de tributação municipal"
              value={form.cod_trib_municipal}
              onChange={(e) => atualizarCampo("cod_trib_municipal", e.target.value)}
            />
            <FieldWrap label="Método de captura do valor">
              <select
                value={form.metodo_captura_valor}
                onChange={(e) => atualizarCampo("metodo_captura_valor", e.target.value)}
                className="w-full rounded-lg border border-slate-300 bg-white dark:bg-slate-800 px-3 py-2 text-sm text-slate-900 dark:text-slate-100 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
              >
                {METODOS_CAPTURA.map((m) => (
                  <option key={m.value} value={m.value}>
                    {m.label}
                  </option>
                ))}
              </select>
            </FieldWrap>
          </div>

          <FieldWrap label="Modelo da descrição do serviço">
            <textarea
              required
              value={form.template_descricao}
              onChange={(e) => atualizarCampo("template_descricao", e.target.value)}
              rows={3}
              placeholder="Ex.: Comissão de vendas - {mes_nome_upper}/{ano}"
              className="mt-1 w-full rounded-lg border border-slate-300 bg-white dark:bg-slate-800 px-3 py-2 text-sm text-slate-900 dark:text-slate-100 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
            />
          </FieldWrap>

          <label className="mt-3 flex items-center gap-2 text-sm text-slate-700 dark:text-slate-300">
            <input
              type="checkbox"
              checked={form.requer_revisao}
              onChange={(e) => atualizarCampo("requer_revisao", e.target.checked)}
              className="rounded border-slate-300 dark:border-slate-600 dark:bg-slate-900"
            />
            Exigir revisão antes de assinar cada nota deste vínculo
          </label>

          {editando && (
            <label className="mt-2 flex items-center gap-2 text-sm text-slate-700 dark:text-slate-300">
              <input
                type="checkbox"
                checked={form.ativo}
                onChange={(e) => atualizarCampo("ativo", e.target.checked)}
                className="rounded border-slate-300 dark:border-slate-600 dark:bg-slate-900"
              />
              Vínculo ativo
            </label>
          )}
        </Card>

        <Card className="p-5">
          <h2 className="mb-1 text-sm font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">Calendário</h2>
          <p className="mb-3 text-xs text-slate-400 dark:text-slate-500">
            Opcional — preenche automaticamente os prazos e previsões deste tomador no Calendário.
          </p>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <Field
              label="Dia limite pra emitir a nota"
              type="number"
              min={1}
              max={31}
              value={form.dia_limite_emissao}
              onChange={(e) => atualizarCampo("dia_limite_emissao", e.target.value)}
              hint="Dia do mês — depois disso, o pagamento pode cair pro mês seguinte."
            />
            <Field
              label="Dias até o pagamento cair"
              type="number"
              min={0}
              value={form.dias_para_recebimento}
              onChange={(e) => atualizarCampo("dias_para_recebimento", e.target.value)}
              hint="Contados a partir da data de emissão da nota."
            />
          </div>
        </Card>

        <div className="flex justify-end gap-3">
          <Button type="button" variant="outline" onClick={() => navigate("/tomadores")}>
            Cancelar
          </Button>
          <Button type="submit" variant="accent" disabled={enviando}>
            {enviando ? "Salvando..." : editando ? "Salvar alterações" : "Cadastrar tomador"}
          </Button>
        </div>
      </form>
    </div>
  )
}
