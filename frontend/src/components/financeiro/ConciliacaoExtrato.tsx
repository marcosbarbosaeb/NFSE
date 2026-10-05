import { ArrowLeftRight, CheckCircle2, EyeOff, FileUp, Sparkles, Undo2 } from "lucide-react"
import { useEffect, useMemo, useState } from "react"
import { Link } from "react-router-dom"
import { linkGerarNota } from "./RecebimentosSemNota"
import { Badge } from "../ui/Badge"
import { Button } from "../ui/Button"
import { CaixaBusca, type OpcaoBusca } from "../ui/CaixaBusca"
import { Card } from "../ui/Card"
import { ApiError, api, formatarErro } from "../../lib/api"
import { competenciaAtual, formatBRL, formatCompetenciaAbrev, formatCompetenciaLonga } from "../../lib/format"
import { useModulos } from "../../lib/modulos"
import type { ContaAPagar, LancamentoPendente, PainelConciliacao, ResumoExtratoConciliacao, VinculoResumo } from "../../lib/types"

/** Parte 2 da Conciliação — "O extrato do banco está todo classificado?"
 * (05/10/2026): o que veio do banco e ainda não foi classificado de um lado;
 * o que está em aberto no sistema (notas a receber, contas a pagar) do
 * outro. A pessoa escolhe um de cada lado e concilia — ou classifica na hora
 * quando não há par. Em cima, os números da importação (linhas, período,
 * último extrato). Saiu de pages/ConciliacaoPage.tsx quando a tela passou a
 * mostrar as duas conciliações. */

type Aba = "receitas" | "despesas"

function dataBR(iso: string | null): string {
  return iso ? iso.split("-").reverse().join("/") : "sem data"
}

const igual = (a: number, b: number) => Math.abs(a - b) < 0.005

export function ConciliacaoExtrato({
  resumo,
  recarga,
  vinculos,
  onVinculosMudaram,
  onMudou,
  onImportar,
}: {
  /** Números da importação (GET /conciliacao/resumo → extrato). */
  resumo: ResumoExtratoConciliacao | null
  /** Muda quando um extrato novo foi importado: recarrega a lista. */
  recarga: number
  vinculos: VinculoResumo[]
  onVinculosMudaram: () => Promise<unknown>
  /** Algo foi classificado: a tela atualiza o estado das duas conciliações. */
  onMudou: () => void
  onImportar: () => void
}) {
  // Notas a receber (e "gerar nota") só existem com o módulo de notas —
  // é o ponto de integração. Sem ele, a entrada só é classificada por cliente.
  const { emissor } = useModulos()
  const [dados, setDados] = useState<PainelConciliacao | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  const [aba, setAba] = useState<Aba>("receitas")
  const [selecionado, setSelecionado] = useState<string | null>(null)
  const [par, setPar] = useState("")
  const [tomador, setTomador] = useState("")
  const [categoria, setCategoria] = useState("")
  const [mes, setMes] = useState(competenciaAtual())
  const [busca, setBusca] = useState("")
  const [ocupado, setOcupado] = useState(false)
  const [feito, setFeito] = useState<{ texto: string; link?: string; rotuloLink?: string } | null>(null)
  const [verIgnorados, setVerIgnorados] = useState(false)
  const [ignorados, setIgnorados] = useState<LancamentoPendente[]>([])
  const [categoriasNovas, setCategoriasNovas] = useState<string[]>([])

  function carregar() {
    return api
      .get<PainelConciliacao>("/conciliacao")
      .then((d) => {
        setDados(d)
        setErro(null)
        return d
      })
      .catch((err) => {
        setErro(err instanceof ApiError ? formatarErro(err.detail) : "Falha de conexão.")
        return null
      })
  }
  const carregarVinculos = onVinculosMudaram

  useEffect(() => {
    void carregar().then((d) => {
      // Abre na aba que tem o que fazer.
      if (d && !d.lancamentos.some((l) => l.credito) && d.lancamentos.some((l) => !l.credito)) setAba("despesas")
    })
  }, [recarga]) // eslint-disable-line react-hooks/exhaustive-deps

  const lancamentos = dados?.lancamentos ?? []
  const receitas = lancamentos.filter((l) => l.credito)
  const despesas = lancamentos.filter((l) => !l.credito)
  const daAba = aba === "receitas" ? receitas : despesas
  const atual = daAba.find((l) => l.id === selecionado) ?? null
  const automaticos = receitas.filter((l) => l.nota_exata && l.emissao_id).length

  // Sem nada selecionado (ou o selecionado saiu da lista): pega o primeiro.
  useEffect(() => {
    if (!atual && daAba.length > 0) setSelecionado(daAba[0].id)
  }, [atual, daAba])

  // Trocou de lançamento: o lado direito começa na sugestão.
  useEffect(() => {
    if (!atual) return
    setPar(atual.credito ? (atual.emissao_id ?? "") : (atual.despesa_id ?? ""))
    setTomador(atual.vinculo_id ?? "")
    setCategoria(`${atual.tipo_despesa}|${atual.categoria}`)
    setMes(atual.data ? atual.data.slice(0, 7) : competenciaAtual())
    setBusca("")
  }, [atual?.id]) // eslint-disable-line react-hooks/exhaustive-deps

  const opcoesTomador: OpcaoBusca[] = useMemo(
    () => [
      ...vinculos.filter((v) => !v.sem_nota).map((v) => ({ id: v.id, rotulo: v.apelido })),
      ...vinculos.filter((v) => v.sem_nota).map((v) => ({ id: v.id, rotulo: v.apelido, grupo: "Só controle (sem nota)" })),
    ],
    [vinculos],
  )
  const opcoesCategoria: OpcaoBusca[] = useMemo(() => {
    const base = [
      ...[...(dados?.categorias ?? []), ...categoriasNovas].map((c) => ({ id: `despesa|${c}`, rotulo: c })),
      ...(dados?.categorias_retirada ?? []).map((c) => ({ id: `retirada|${c}`, rotulo: c, grupo: "Retiradas (não entram como despesa)" })),
    ]
    if (categoria && !base.some((o) => o.id === categoria)) base.unshift({ id: categoria, rotulo: categoria.split("|").slice(1).join("|") })
    return base
  }, [dados, categoria, categoriasNovas])

  // Lado direito, ordenado pelo que mais parece com o lançamento escolhido.
  const filtro = busca.trim().toLowerCase()
  const notas = useMemo(() => {
    const lista = (dados?.notas_abertas ?? []).filter((n) => !filtro || n.apelido.toLowerCase().includes(filtro))
    if (!atual) return lista
    const peso = (n: (typeof lista)[number]) =>
      (n.emissao_id === atual.emissao_id ? -4 : 0) + (igual(n.valor, atual.valor) ? -2 : 0) + (n.vinculo_id === atual.vinculo_id ? -1 : 0)
    return [...lista].sort((a, b) => peso(a) - peso(b) || Math.abs(a.valor - atual.valor) - Math.abs(b.valor - atual.valor))
  }, [dados, atual, filtro])
  const contas = useMemo(() => {
    const lista = (dados?.contas_a_pagar ?? []).filter(
      (c) => !filtro || c.nome.toLowerCase().includes(filtro) || c.categoria.toLowerCase().includes(filtro),
    )
    if (!atual) return lista
    const peso = (c: ContaAPagar) => (c.id === atual.despesa_id ? -4 : 0) + (igual(c.valor, atual.valor) ? -2 : 0)
    return [...lista].sort((a, b) => peso(a) - peso(b) || Math.abs(a.valor - atual.valor) - Math.abs(b.valor - atual.valor))
  }, [dados, atual, filtro])

  async function agir(acao: () => Promise<{ texto: string; link?: string; rotuloLink?: string }>) {
    setOcupado(true)
    setErro(null)
    try {
      const resultado = await acao()
      setFeito(resultado)
      setSelecionado(null)
      await carregar()
      onMudou()
    } catch (err) {
      setErro(err instanceof ApiError ? formatarErro(err.detail) : "Falha de conexão. Tente de novo.")
    } finally {
      setOcupado(false)
    }
  }

  function conciliarReceita(comNota: boolean) {
    if (!atual) return
    const nota = comNota ? dados?.notas_abertas.find((n) => n.emissao_id === par) : undefined
    const vinculoId = nota?.vinculo_id ?? tomador
    if (!vinculoId) return
    void agir(async () => {
      const r = await api.post<{ pagamento_id: string; vinculo_id: string; apelido: string; pode_gerar_nota: boolean }>(
        `/conciliacao/${atual.id}/receita`,
        { vinculo_id: vinculoId, emissao_id: nota?.emissao_id ?? null, competencia: nota ? null : mes },
      )
      if (nota) return { texto: `Baixa dada na nota de ${formatCompetenciaLonga(nota.competencia).toLowerCase()} de ${r.apelido}.` }
      return r.pode_gerar_nota && emissor
        ? {
            texto: `Recebimento de ${r.apelido} lançado, sem nota.`,
            link: linkGerarNota({ vinculo_id: r.vinculo_id, pagamento_id: r.pagamento_id, valor: atual.valor }),
            rotuloLink: "Gerar a nota dele",
          }
        : { texto: `Recebimento de ${r.apelido} lançado.` }
    })
  }

  function conciliarDespesa(comConta: boolean) {
    if (!atual) return
    const conta = comConta ? dados?.contas_a_pagar.find((c) => c.id === par) : undefined
    const [tipo, ...resto] = categoria.split("|")
    const nomeCategoria = resto.join("|")
    if (!conta && !nomeCategoria) return
    void agir(async () => {
      await api.post(`/conciliacao/${atual.id}/despesa`, conta ? { despesa_id: conta.id } : { categoria: nomeCategoria, tipo, competencia: mes })
      return { texto: conta ? `${conta.nome} marcada como paga.` : `Despesa lançada em ${nomeCategoria}.` }
    })
  }

  function ignorar() {
    if (!atual) return
    void agir(async () => {
      await api.post(`/conciliacao/${atual.id}/ignorar?ignorar=true`, {})
      return { texto: "Lançamento ignorado — não entra como receita nem despesa." }
    })
  }

  function trocarTipo() {
    if (!atual) return
    const paraCredito = !atual.credito
    void agir(async () => {
      await api.post(`/conciliacao/${atual.id}/tipo?credito=${paraCredito}`, {})
      setAba(paraCredito ? "receitas" : "despesas")
      return { texto: paraCredito ? "Movido pra receitas." : "Movido pra despesas." }
    })
  }

  function conciliarIguais() {
    void agir(async () => {
      const r = await api.post<{ conciliados: number }>("/conciliacao/automatico", {})
      return { texto: `${r.conciliados} recebimento(s) conciliado(s) com a nota do mesmo valor.` }
    })
  }

  async function criarTomador(nome: string) {
    try {
      const novo = await api.post<{ id: string }>("/vinculos/controle", { nome })
      await carregarVinculos()
      setTomador(novo.id)
      setPar("")
    } catch (err) {
      setErro(err instanceof ApiError ? formatarErro(err.detail) : "Falha de conexão.")
    }
  }

  async function abrirIgnorados() {
    setVerIgnorados(true)
    setIgnorados(await api.get<LancamentoPendente[]>("/conciliacao/ignorados").catch(() => []))
  }

  async function reabrir(id: string) {
    await api.post(`/conciliacao/${id}/ignorar?ignorar=false`, {}).catch(() => undefined)
    setIgnorados((atuais) => atuais.filter((l) => l.id !== id))
    void carregar()
    onMudou()
  }

  const abaBotao = (qual: Aba, rotulo: string, n: number) => (
    <button
      type="button"
      role="tab"
      aria-selected={aba === qual}
      onClick={() => {
        setAba(qual)
        setSelecionado(null)
        setFeito(null)
      }}
      className={`rounded-lg px-3 py-1.5 text-sm font-medium ${aba === qual ? "bg-primary-600 text-white" : "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-700"}`}
    >
      {rotulo} <span className="tabular-nums opacity-80">({n})</span>
    </button>
  )

  const itemDireita = (id: string, titulo: string, detalhe: string, valor: number) => {
    const mesmoValor = !!atual && igual(valor, atual.valor)
    return (
      <li key={id}>
        <label
          className={`flex cursor-pointer items-center gap-3 rounded-lg border px-3 py-2 ${par === id ? "border-primary-500 bg-primary-50 dark:bg-primary-900/30" : "border-transparent hover:bg-slate-50 dark:hover:bg-slate-700/40"}`}
        >
          <input type="radio" name="par" checked={par === id} onChange={() => setPar(id)} disabled={!atual} />
          <span className="min-w-0 flex-1">
            <span className="block truncate text-sm font-medium text-slate-800 dark:text-slate-200">{titulo}</span>
            <span className="block text-xs text-slate-400 dark:text-slate-500">{detalhe}</span>
          </span>
          {mesmoValor && <Badge variant="success">mesmo valor</Badge>}
          <span className="shrink-0 text-sm tabular-nums text-slate-700 dark:text-slate-200">{formatBRL(valor)}</span>
        </label>
      </li>
    )
  }

  const semExtrato = resumo !== null && resumo.linhas === 0
  const numero = (rotulo: string, valor: number, cor = "text-slate-900 dark:text-slate-100", detalhe?: string) => (
    <div className="rounded-xl border border-slate-200/70 bg-white px-4 py-3 dark:border-slate-700/70 dark:bg-slate-800">
      <p className="text-xs font-medium text-slate-500 dark:text-slate-400">{rotulo}</p>
      <p className={`text-2xl font-semibold tabular-nums ${cor}`}>{valor}</p>
      {detalhe && <p className="text-xs text-slate-400 dark:text-slate-500">{detalhe}</p>}
    </div>
  )

  return (
    <div className="flex flex-col gap-5">
      {/* Os números desta conciliação */}
      {resumo && !semExtrato && (
        <div>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            {numero("Linhas importadas", resumo.linhas)}
            {numero("Classificadas", resumo.classificadas, "text-success-700 dark:text-success-300", "viraram recebimento ou despesa")}
            {numero(
              "Pendentes",
              resumo.pendentes,
              resumo.pendentes > 0 ? "text-warning-700 dark:text-warning-300" : "text-slate-900 dark:text-slate-100",
              resumo.pendentes > 0 ? `${resumo.pendentes_entradas} entrada(s) · ${resumo.pendentes_saidas} saída(s)` : "nada por classificar",
            )}
            {numero("Ignoradas", resumo.ignoradas, "text-slate-500 dark:text-slate-400", "não são receita nem despesa")}
          </div>
          <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
            {resumo.de && resumo.ate ? (
              <>
                Período coberto pelos extratos: <strong>{dataBR(resumo.de)}</strong> a <strong>{dataBR(resumo.ate)}</strong>.{" "}
              </>
            ) : null}
            {resumo.ultimo_importado_em && (
              <>
                Último extrato importado em {dataBR(resumo.ultimo_importado_em)}
                {resumo.ultimo_arquivo ? ` (${resumo.ultimo_arquivo})` : ""}.
              </>
            )}
          </p>
        </div>
      )}

      {automaticos > 0 && emissor && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-primary-100 bg-primary-50/70 px-4 py-3 text-sm text-slate-700 dark:border-primary-900/40 dark:bg-primary-900/20 dark:text-slate-200">
          <span>
            Achei <strong>{automaticos}</strong> {automaticos === 1 ? "entrada que tem" : "entradas que têm"} nota em aberto do mesmo valor.
          </span>
          <Button variant="outline" disabled={ocupado} onClick={conciliarIguais}>
            <Sparkles size={16} /> Conciliar {automaticos} de mesmo valor
          </Button>
        </div>
      )}

      {erro && <p className="rounded-lg bg-danger-50 px-4 py-3 text-sm text-danger-700">{erro}</p>}
      {feito && (
        <p className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-lg bg-success-50 px-4 py-3 text-sm text-success-700" role="status">
          <CheckCircle2 size={16} className="shrink-0" /> {feito.texto}
          {feito.link && (
            <Link to={feito.link} className="font-semibold underline">
              {feito.rotuloLink} →
            </Link>
          )}
        </p>
      )}

      <div className="flex flex-wrap items-center justify-between gap-2">
        <div role="tablist" className="flex gap-1 rounded-xl border border-slate-200 bg-white p-1 dark:border-slate-700 dark:bg-slate-800">
          {abaBotao("receitas", "Receitas", receitas.length)}
          {abaBotao("despesas", "Despesas", despesas.length)}
        </div>
        {(dados?.ignorados ?? 0) > 0 && (
          <button type="button" onClick={abrirIgnorados} className="text-xs font-medium text-slate-500 underline hover:text-slate-700">
            {dados?.ignorados} ignorado(s)
          </button>
        )}
      </div>

      {verIgnorados && (
        <Card className="p-4">
          <div className="mb-2 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-slate-700 dark:text-slate-200">Ignorados</h2>
            <button type="button" onClick={() => setVerIgnorados(false)} className="text-xs text-slate-500 underline">
              fechar
            </button>
          </div>
          {ignorados.length === 0 ? (
            <p className="py-2 text-sm text-slate-400">Nenhum.</p>
          ) : (
            <ul className="divide-y divide-slate-100 dark:divide-slate-700/60">
              {ignorados.map((l) => (
                <li key={l.id} className="flex items-center gap-3 py-2 text-sm">
                  <span className="w-20 shrink-0 text-xs text-slate-400">{dataBR(l.data)}</span>
                  <span className="min-w-0 flex-1 break-words text-slate-700 dark:text-slate-300">{l.descricao}</span>
                  <span className="shrink-0 tabular-nums text-slate-700 dark:text-slate-200">
                    {l.credito ? "+" : "−"} {formatBRL(l.valor)}
                  </span>
                  <button type="button" onClick={() => reabrir(l.id)} className="inline-flex shrink-0 items-center gap-1 text-xs font-medium text-primary-600 hover:underline">
                    <Undo2 size={13} /> voltar pra lista
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Card>
      )}

      {dados === null ? (
        <p className="py-10 text-center text-sm text-slate-400">Carregando...</p>
      ) : lancamentos.length === 0 ? (
        <Card className="p-8 text-center">
          <CheckCircle2 className="mx-auto mb-2 h-8 w-8 text-success-600" aria-hidden />
          <p className="font-medium text-slate-800 dark:text-slate-100">
            {semExtrato ? "Nenhum extrato importado ainda." : "Tudo classificado."}
          </p>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            {semExtrato
              ? "Importe o extrato do banco (PDF, OFX ou CSV): eu separo o que entrou do que saiu e você confere."
              : "Quando você importar um extrato, o que não for classificado na hora aparece aqui."}
          </p>
          <Button variant={semExtrato ? "accent" : "outline"} className="mt-4" onClick={onImportar}>
            <FileUp size={16} /> Importar extrato
          </Button>
        </Card>
      ) : (
        <div className="grid grid-cols-1 items-start gap-5 lg:grid-cols-2">
          {/* Esquerda: o que veio do banco */}
          <Card className="p-4">
            <h2 className="mb-1 text-sm font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">
              Do extrato · {aba === "receitas" ? "entradas" : "saídas"} sem classificar
            </h2>
            {daAba.length === 0 ? (
              <p className="py-6 text-center text-sm text-slate-400">
                Nenhuma {aba === "receitas" ? "entrada" : "saída"} pendente.
              </p>
            ) : (
              <ul className="-mx-1 flex max-h-[68vh] flex-col gap-1 overflow-y-auto px-1 py-1">
                {daAba.map((l) => (
                  <li key={l.id}>
                    <button
                      type="button"
                      onClick={() => {
                        setSelecionado(l.id)
                        setFeito(null)
                      }}
                      aria-pressed={l.id === atual?.id}
                      className={`w-full rounded-lg border px-3 py-2 text-left ${l.id === atual?.id ? "border-primary-500 bg-primary-50 dark:bg-primary-900/30" : "border-slate-100 hover:bg-slate-50 dark:border-slate-700/60 dark:hover:bg-slate-700/40"}`}
                    >
                      <span className="flex items-baseline justify-between gap-3">
                        <span className="text-xs text-slate-400 dark:text-slate-500">{dataBR(l.data)}</span>
                        <span className="text-sm font-semibold tabular-nums text-slate-800 dark:text-slate-100">{formatBRL(l.valor)}</span>
                      </span>
                      <span className="mt-0.5 block break-words text-sm text-slate-700 dark:text-slate-300">{l.descricao}</span>
                      <span className="mt-1 flex flex-wrap gap-1">
                        {l.credito && l.nota_exata && emissor && <Badge variant="success">tem nota do mesmo valor</Badge>}
                        {!l.credito && l.despesa_id && <Badge variant="success">tem conta a pagar que bate</Badge>}
                        {l.origem_sugestao === "lembrado" && <Badge variant="info">como da última vez</Badge>}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          {/* Direita: o que está em aberto no sistema */}
          <Card className="p-4 lg:sticky lg:top-20">
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">
                {aba === "receitas" ? (emissor ? "Em aberto · notas a receber" : "Classificar a entrada") : "Em aberto · contas a pagar"}
              </h2>
              <input
                value={busca}
                onChange={(e) => setBusca(e.target.value)}
                placeholder="Filtrar..."
                aria-label="Filtrar a lista"
                className="w-36 rounded-lg border border-slate-300 bg-white px-2 py-1 text-xs dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
              />
            </div>

            {!atual ? (
              <p className="py-6 text-center text-sm text-slate-400">Escolha um lançamento à esquerda.</p>
            ) : (
              <>
                {(aba === "despesas" || emissor) && (<>
                <ul className="-mx-1 flex max-h-[34vh] flex-col gap-0.5 overflow-y-auto px-1">
                  {aba === "receitas"
                    ? notas.map((n) =>
                        itemDireita(n.emissao_id, n.apelido, `nota de ${formatCompetenciaAbrev(n.competencia)}${n.n_dps ? ` · nº ${n.n_dps}` : ""}`, n.valor),
                      )
                    : contas.map((c) =>
                        itemDireita(
                          c.id,
                          c.nome,
                          `${c.categoria !== c.nome ? `${c.categoria} · ` : ""}${formatCompetenciaAbrev(c.competencia)}${c.vencimento ? ` · vence ${dataBR(c.vencimento).slice(0, 5)}` : ""}`,
                          c.valor,
                        ),
                      )}
                  {(aba === "receitas" ? notas : contas).length === 0 && (
                    <li className="py-4 text-center text-sm text-slate-400">
                      {aba === "receitas" ? "Nenhuma nota em aberto." : "Nenhuma conta a pagar em aberto."}
                    </li>
                  )}
                </ul>
                <Button
                  className="mt-3 w-full"
                  disabled={ocupado || !par}
                  onClick={() => (aba === "receitas" ? conciliarReceita(true) : conciliarDespesa(true))}
                >
                  {aba === "receitas" ? "Dar baixa na nota escolhida" : "Marcar a conta escolhida como paga"}
                </Button>
                </>)}

                <div className={aba === "despesas" || emissor ? "mt-4 border-t border-slate-100 pt-3 dark:border-slate-700/60" : ""}>
                  <p className="mb-2 text-xs font-medium text-slate-500 dark:text-slate-400">
                    {aba === "receitas"
                      ? emissor
                        ? "Não é de nenhuma nota? Lance como recebimento:"
                        : "De qual cliente é esse dinheiro?"
                      : "Não estava prevista? Lance como despesa:"}
                  </p>
                  <div className="flex flex-wrap items-center gap-2">
                    {aba === "receitas" ? (
                      <CaixaBusca
                        valor={tomador}
                        opcoes={opcoesTomador}
                        onEscolher={setTomador}
                        onCriar={criarTomador}
                        rotuloCriar="Novo cliente"
                        placeholder="Cliente (digite pra buscar)"
                        ariaLabel="Cliente"
                        className="min-w-[180px] flex-1"
                      />
                    ) : (
                      <CaixaBusca
                        valor={categoria}
                        opcoes={opcoesCategoria}
                        onEscolher={setCategoria}
                        onCriar={(nome) => {
                          setCategoriasNovas((atuais) => [...atuais, nome])
                          setCategoria(`despesa|${nome}`)
                        }}
                        rotuloCriar="Nova categoria"
                        placeholder="Categoria (digite pra buscar)"
                        ariaLabel="Categoria"
                        className="min-w-[180px] flex-1"
                      />
                    )}
                    <input
                      type="month"
                      value={mes}
                      onChange={(e) => setMes(e.target.value)}
                      aria-label="Mês"
                      className="w-40 rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
                    />
                    <Button
                      variant="outline"
                      disabled={ocupado || (aba === "receitas" ? !tomador : !categoria.split("|")[1])}
                      onClick={() => (aba === "receitas" ? conciliarReceita(false) : conciliarDespesa(false))}
                    >
                      Lançar
                    </Button>
                  </div>
                  {aba === "receitas" && emissor && (
                    <p className="mt-1.5 text-xs text-slate-400 dark:text-slate-500">
                      Depois de lançar, dá pra gerar a nota desse recebimento (caso de quem paga antes da nota).
                    </p>
                  )}
                </div>

                <div className="mt-3 flex flex-wrap gap-1 border-t border-slate-100 pt-3 dark:border-slate-700/60">
                  <Button variant="ghost" className="px-2 py-1 text-xs" disabled={ocupado} onClick={trocarTipo}>
                    <ArrowLeftRight size={14} /> {atual.credito ? "Na verdade é despesa" : "Na verdade é receita"}
                  </Button>
                  <Button variant="ghost" className="px-2 py-1 text-xs" disabled={ocupado} onClick={ignorar}>
                    <EyeOff size={14} /> Ignorar (não é receita nem despesa)
                  </Button>
                </div>
              </>
            )}
          </Card>
        </div>
      )}
    </div>
  )
}
