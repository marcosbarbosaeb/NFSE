import { OrientacaoCertificado } from "./OrientacaoCertificado"
import { ArrowRight, Check, DownloadCloud, FileBadge, Building2, Users } from "lucide-react"
import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { api } from "../lib/api"
import { mensagemDeErro } from "../lib/excluir"
import type { Prontidao } from "../lib/types"
import { Card } from "./ui/Card"

/** Conta nova (06/10/2026): "ela deve ser orientada a cadastrar o certificado
 * A1 — senão não deve ser possível fazer as atividades de emissão — e guiada
 * pra página da empresa pra colocar os dados que faltam". Três passos, na
 * ordem: certificado, dados da empresa, tomadores (pelos pré-cadastrados).
 * Some sozinho quando está tudo pronto. */

export function useProntidao(versao = 0): Prontidao | null {
  const [dados, setDados] = useState<Prontidao | null>(null)
  useEffect(() => {
    let vivo = true
    api
      .get<Prontidao>("/empresa/prontidao")
      .then((d) => vivo && setDados(d))
      .catch(() => vivo && setDados(null))
    return () => {
      vivo = false
    }
  }, [versao])
  return dados
}

const BOTAO =
  "inline-flex shrink-0 items-center justify-center gap-1.5 rounded-lg px-3.5 py-2 text-sm font-semibold transition-colors"

function Passo({
  n,
  feito,
  atual,
  icone: Icone,
  titulo,
  texto,
  to,
  rotulo,
  acao,
  nota,
}: {
  n: number
  feito: boolean
  atual: boolean
  icone: typeof FileBadge
  titulo: string
  texto: React.ReactNode
  to: string
  rotulo: string
  /** Em vez de levar pra outra tela, resolve aqui mesmo (ex.: buscar na Receita). */
  acao?: { rotulo: string; fazendo: boolean; onClick: () => void }
  nota?: React.ReactNode
}) {
  return (
    <li
      className={`flex flex-wrap items-center gap-x-4 gap-y-2 rounded-xl border px-4 py-3 ${
        feito
          ? "border-success-100 bg-success-50/50 dark:border-success-900/40 dark:bg-success-900/15"
          : atual
            ? "border-primary-300 bg-white dark:border-primary-600 dark:bg-slate-800"
            : "border-slate-200 bg-white/60 dark:border-slate-700 dark:bg-slate-800/60"
      }`}
      aria-current={atual ? "step" : undefined}
    >
      <span
        className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm font-bold ${
          feito ? "bg-success-600 text-white" : atual ? "bg-primary-600 text-white" : "bg-slate-200 text-slate-500 dark:bg-slate-700 dark:text-slate-300"
        }`}
      >
        {feito ? <Check size={16} aria-label="feito" /> : n}
      </span>
      <div className="min-w-0 flex-1 basis-56">
        <p className="flex items-center gap-1.5 text-sm font-semibold text-slate-900 dark:text-slate-100">
          <Icone size={15} className="shrink-0 text-slate-400" aria-hidden /> {titulo}
        </p>
        <p className="mt-0.5 text-sm text-slate-600 dark:text-slate-300">{texto}</p>
      </div>
      {!feito && acao && (
        <button
          type="button"
          onClick={acao.onClick}
          disabled={acao.fazendo}
          className={`${BOTAO} bg-accent-500 text-white hover:bg-accent-600 disabled:opacity-60`}
        >
          <DownloadCloud size={15} aria-hidden /> {acao.rotulo}
        </button>
      )}
      {!feito && (
        <Link
          to={to}
          className={`${BOTAO} ${atual && !acao ? "bg-accent-500 text-white hover:bg-accent-600" : "border border-slate-300 text-slate-700 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-700"}`}
        >
          {rotulo} <ArrowRight size={15} aria-hidden />
        </Link>
      )}
      {nota && <p className="basis-full pl-12 text-sm">{nota}</p>}
    </li>
  )
}

export function PrimeirosPassos() {
  // "Sobre o completar os dados da empresa, falei para puxarmos pelo CNPJ"
  // (07/10/2026): o passo 2 busca na Receita em vez de mandar digitar.
  const [versao, setVersao] = useState(0)
  const [buscando, setBuscando] = useState(false)
  const [receita, setReceita] = useState<{ ok: boolean; texto: string } | null>(null)
  const [tentou, setTentou] = useState(false)
  const p = useProntidao(versao)
  async function buscarNaReceita() {
    setBuscando(true)
    setReceita(null)
    try {
      const r = await api.post<{ preenchidos: string[]; faltam: { rotulo: string }[] }>("/prestador/completar-pelo-cnpj", {})
      setReceita({
        ok: true,
        texto: r.preenchidos.length
          ? `Busquei na Receita e preenchi: ${r.preenchidos.join(", ")}.${r.faltam.length ? " O que sobrou, a Receita não informa." : ""}`
          : "A Receita não tinha o que falta. Complete à mão, é rapidinho.",
      })
      setVersao((n) => n + 1)
    } catch (err) {
      setReceita({ ok: false, texto: mensagemDeErro(err) })
    } finally {
      setBuscando(false)
      setTentou(true)
    }
  }
  if (!p || !p.aplica || p.pronta) return null
  // A Receita sabe o endereço e o regime; a alíquota do Simples, não.
  const daReceita = !tentou && p.dados_faltando.some((f) => f.campo === "regime")
  const certOk = p.certificado === "ok"
  // Só o obrigatório segura o passo (hoje: o regime tributário). O que é
  // opcional aparece como sugestão, sem travar nada (08/10/2026).
  const obrigatorios = p.dados_faltando.filter((f) => f.obrigatorio)
  const opcionais = p.dados_faltando.filter((f) => !f.obrigatorio)
  const dadosOk = obrigatorios.length === 0
  const tomadoresOk = p.tomadores > 0
  const atual = !certOk ? 1 : !dadosOk ? 2 : 3
  return (
    <Card className="border-primary-200 bg-primary-50/60 p-5 dark:border-primary-800 dark:bg-primary-900/20" data-tour="primeiros-passos">
      <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">Primeiros passos pra emitir sua nota</h2>
      <p className="mt-0.5 text-sm text-slate-600 dark:text-slate-300">
        {certOk
          ? "Falta pouco: depois disso, todo mês eu preparo as notas e você só confere."
          : "Comece pelo certificado digital: sem ele eu não consigo assinar a nota nem falar com a prefeitura, então a emissão fica travada."}
      </p>
      <ol className="mt-4 flex flex-col gap-2">
        <Passo
          n={1}
          feito={certOk}
          atual={atual === 1}
          icone={FileBadge}
          titulo="Certificado digital A1"
          texto={
            certOk
              ? "Certificado guardado, com segurança."
              : p.certificado === "vencido"
                ? "O certificado guardado venceu. Envie o novo arquivo (.pfx) pra voltar a emitir."
                : "Envie o arquivo do certificado A1 da empresa (.pfx) e a senha dele. Fica cifrado; eu uso só pra assinar as suas notas."
          }
          to="/app/empresa?aba=certificado"
          rotulo={p.certificado === "vencido" ? "Enviar o novo" : "Enviar o certificado"}
        />
        {!certOk && (
          <li className="list-none">
            <OrientacaoCertificado />
          </li>
        )}
        <Passo
          n={2}
          feito={dadosOk}
          atual={atual === 2}
          icone={Building2}
          titulo="Dados da empresa"
          texto={
            dadosOk ? (
              opcionais.length > 0 ? (
                <>
                  O que a nota exige já está preenchido. Opcional, se quiser completar:{" "}
                  <Link to={opcionais[0].link} className="font-medium text-primary-700 underline dark:text-primary-300">
                    {opcionais.map((f) => f.rotulo.toLowerCase()).join("; ")}
                  </Link>
                  .
                </>
              ) : (
                "Regime tributário e endereço conferidos."
              )
            ) : (
              <>
                Só preciso de uma coisa: <strong>{obrigatorios.map((f) => f.rotulo).join("; ")}</strong> — {obrigatorios[0].por_que}.
                {opcionais.length > 0 && <> O resto ({opcionais.map((f) => f.rotulo.toLowerCase()).join("; ")}) é opcional: pode ficar em branco.</>}
              </>
            )
          }
          to={obrigatorios[0]?.link ?? "/app/empresa?aba=emitente"}
          rotulo={daReceita ? "Preencher à mão" : "Completar os dados"}
          acao={daReceita ? { rotulo: buscando ? "Buscando..." : "Puxar pelo CNPJ", fazendo: buscando, onClick: () => void buscarNaReceita() } : undefined}
          nota={
            receita && (
              <span role="status" className={receita.ok ? "text-success-700 dark:text-success-300" : "text-danger-600"}>
                {receita.texto}
              </span>
            )
          }
        />
        <Passo
          n={3}
          feito={tomadoresOk}
          atual={atual === 3}
          icone={Users}
          titulo="Seus tomadores"
          texto={
            tomadoresOk
              ? "Você já tem tomador cadastrado."
              : "Escolha pra quem você emite nota. Os mais comuns (Shopee, Amazon, Mercado Livre, AWIN...) já vêm pré-cadastrados, com o serviço e a descrição prontos."
          }
          to="/app/tomadores/novo"
          rotulo="Escolher tomadores"
        />
      </ol>
      {certOk && !tomadoresOk && (
        <p className="mt-3 text-xs text-slate-500 dark:text-slate-400">
          Já emitia pelo Emissor Nacional? Depois de cadastrar os seus tomadores, dá pra trazer as notas antigas em{" "}
          <Link to="/app/empresa?aba=notas" className="font-semibold text-primary-600 hover:underline dark:text-primary-300">
            Empresa › Notas e e-mails
          </Link>{" "}
          — você escolhe de quais tomadores.
        </p>
      )}
    </Card>
  )
}

/** Faixa das telas de nota: sem certificado válido a emissão fica travada. */
export function TravaDeEmissao({ prontidao }: { prontidao: Prontidao | null }) {
  if (!prontidao || !prontidao.aplica || prontidao.pode_emitir) return null
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-3 rounded-2xl border border-warning-100 bg-warning-50 p-5 dark:border-warning-900/50 dark:bg-warning-900/20" role="alert">
      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-warning-100 text-warning-700 dark:bg-warning-900/40 dark:text-warning-300">
        <FileBadge size={20} aria-hidden />
      </span>
      <div className="min-w-0 flex-1 basis-64">
        <p className="text-base font-semibold text-slate-900 dark:text-slate-100">
          {prontidao.certificado === "vencido" ? "O certificado digital venceu" : "Falta o certificado digital A1 pra emitir"}
        </p>
        <p className="mt-0.5 text-sm text-slate-700 dark:text-slate-300">{prontidao.motivo}</p>
      </div>
      <Link to="/app/empresa?aba=certificado" className={`${BOTAO} bg-accent-500 text-white hover:bg-accent-600`}>
        Enviar o certificado <ArrowRight size={15} aria-hidden />
      </Link>
      <OrientacaoCertificado className="basis-full" />
    </div>
  )
}
