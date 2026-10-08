import { PastaDoMes } from "../pasta/PastaDoMes"
import { ArrowLeft, Loader2, LogIn, MessageCircle } from "lucide-react"
import type { ReactNode } from "react"
import { resumoPermissoes } from "../../lib/contador"
import { formatarDocumento } from "../../lib/documento"
import { formatBRL, formatCompetenciaAbrev, formatCompetenciaLonga } from "../../lib/format"
import type { ClienteAtendido } from "../../lib/types"
import { ColunasMensais } from "../graficos/ColunasMensais"
import { nomeEmpresa } from "../TrocaEmpresa"
import { Badge } from "../ui/Badge"
import { Button } from "../ui/Button"
import { Card } from "../ui/Card"
import { BaixarNotasDoMes, BarraDoLimite, FilaDeTarefas, tarefasDe } from "./PainelContador"

// A ficha de uma empresa dentro do painel do contador (08/10/2026): os dados
// que interessam a ele — faturamento, limite do regime, fechamento,
// certificado, o que tem pra fazer — sem entrar na empresa. "Entrar" continua
// existindo pra quando ele vai trabalhar nela.

const FECHAMENTO: Record<string, { texto: string; variante: "success" | "warning" | "info" | "neutral" }> = {
  fechado: { texto: "fechado", variante: "success" },
  pendente: { texto: "falta conferir", variante: "warning" },
  aguardando: { texto: "aguardando pagamento", variante: "info" },
  vazio: { texto: "nada lançado", variante: "neutral" },
}

function Dado({ rotulo, children, dica }: { rotulo: string; children: ReactNode; dica?: string }) {
  return (
    <div className="min-w-0" title={dica}>
      <dt className="text-[11px] font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">{rotulo}</dt>
      <dd className="text-sm font-medium text-slate-800 dark:text-slate-100">{children}</dd>
    </div>
  )
}

export function FichaDaEmpresa({
  cliente: c,
  ativa,
  fazendo,
  aoVoltar,
  aoAbrir,
  aoSair,
}: {
  cliente: ClienteAtendido
  ativa: string
  fazendo: boolean
  aoVoltar: () => void
  aoAbrir: (c: ClienteAtendido, link?: string) => void
  aoSair: (c: ClienteAtendido) => void
}) {
  const r = c.raio_x
  const dentro = c.prestador_id === ativa
  const serie = r?.serie ?? []
  const semNota = serie.every((p) => p.valor === 0)
  const tarefas = tarefasDe([c])
  const cert = r?.certificado
  const whats = (c.dono?.telefone ?? "").replace(/\D/g, "")

  return (
    <div className="flex flex-col gap-5" data-painel="ficha">
      <button type="button" onClick={aoVoltar} className="inline-flex w-fit items-center gap-1 text-sm font-medium text-slate-500 hover:text-primary-700 dark:text-slate-400 dark:hover:text-primary-300">
        <ArrowLeft size={15} aria-hidden /> Voltar pro painel
      </button>

      <Card className="p-5">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <h2 className="flex flex-wrap items-center gap-2 text-xl font-semibold text-slate-900 dark:text-slate-100">
              <span className="truncate">{nomeEmpresa({ nome_fantasia: c.nome_fantasia, razao_social: c.empresa })}</span>
              {dentro && <Badge variant="info">você está nela</Badge>}
              {c.situacao.bloqueado && <Badge variant="danger">só consulta</Badge>}
            </h2>
            <p className="mt-0.5 text-sm text-slate-500 dark:text-slate-400">
              {c.nome_fantasia && c.nome_fantasia !== c.empresa ? `${c.empresa} · ` : ""}CNPJ {formatarDocumento(c.cnpj)}
              {r?.municipio ? ` · ${r.municipio}` : ""}
            </p>
          </div>
          <Button type="button" variant={dentro ? "outline" : "primary"} disabled={fazendo || dentro} onClick={() => aoAbrir(c)} className="shrink-0">
            {fazendo ? <Loader2 size={15} className="animate-spin" /> : <LogIn size={15} />} {dentro ? "Você está nela" : "Entrar na empresa"}
          </Button>
        </div>

        {r && (
          <dl className="mt-5 grid grid-cols-2 gap-x-4 gap-y-4 border-t border-slate-100 pt-4 sm:grid-cols-4 dark:border-slate-700">
            <Dado rotulo="Regime">{r.regime_nome}</Dado>
            <Dado rotulo={`Notas em ${formatCompetenciaAbrev(r.competencia).toLowerCase()}`}>
              {r.notas_mes} <span className="font-normal text-slate-500 dark:text-slate-400">· {formatBRL(r.faturado_mes)}</span>
            </Dado>
            <Dado rotulo="12 meses anteriores" dica="Soma das notas autorizadas nos 12 meses antes deste (a base do RBT12)">
              {formatBRL(r.faturado_12m)}
            </Dado>
            <Dado rotulo="Alíquota de referência">
              {r.regime === "3" ? (r.aliquota != null ? `${r.aliquota.toLocaleString("pt-BR", { maximumFractionDigits: 2 })}%` : <span className="text-warning-700 dark:text-warning-300">não informada</span>) : "—"}
            </Dado>
            <div className="col-span-2">
              <dt className="mb-0.5 text-[11px] font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">Faturado em notas no ano × limite do regime</dt>
              <dd>
                <BarraDoLimite raio={r} />
              </dd>
            </div>
            {cert && (
              <Dado rotulo="Certificado digital">
                <span className={cert.situacao === "ok" ? "" : cert.situacao === "vencendo" && (cert.dias ?? 0) > 15 ? "text-warning-700 dark:text-warning-300" : "text-danger-600 dark:text-danger-300"}>
                  {cert.situacao === "falta"
                    ? "Não enviado"
                    : cert.situacao === "vencido"
                      ? "Vencido"
                      : cert.validade
                        ? `Até ${cert.validade.split("-").reverse().join("/")}${cert.situacao === "vencendo" ? ` (${cert.dias === 0 ? "vence hoje" : `${cert.dias} dia${cert.dias === 1 ? "" : "s"}`})` : ""}`
                        : "Em dia"}
                </span>
              </Dado>
            )}
            {r.inscricao_municipal && <Dado rotulo="Inscrição municipal">{r.inscricao_municipal}</Dado>}
          </dl>
        )}
      </Card>

      <Card className="p-5">
        <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">O que tem pra fazer nesta empresa</h3>
        <FilaDeTarefas tarefas={tarefas} desligado={fazendo} aoResolver={(cli, link) => aoAbrir(cli, link)} semEmpresa limite={8} />
      </Card>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-5">
        <Card className="p-5 lg:col-span-3">
          <h3 className="mb-1 text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">Notas por mês</h3>
          <p className="mb-3 text-xs text-slate-500 dark:text-slate-400">Valor das notas autorizadas que passaram pela Ana, pela competência.</p>
          {semNota ? (
            <p className="py-8 text-center text-sm text-slate-400 dark:text-slate-500">Nenhuma nota nos últimos 12 meses.</p>
          ) : (
            <>
              <ColunasMensais
                titulo="Valor das notas por mês, últimos 12 meses"
                rotulos={serie.map((p) => formatCompetenciaAbrev(p.competencia).toLowerCase())}
                nomes={serie.map((p) => formatCompetenciaLonga(p.competencia))}
                anos={serie.map((p, i) => (i === 0 || p.competencia.endsWith("-01") ? p.competencia.slice(0, 4) : null))}
                series={[{ nome: "Notas", valores: serie.map((p) => p.valor), classe: "fill-primary-500 dark:fill-primary-400", classeChave: "bg-primary-500 dark:bg-primary-400", classeApagada: "fill-primary-200 dark:fill-primary-700" }]}
                destaque={serie.length - 1}
                altura={190}
              />
              <details className="mt-2 text-sm">
                <summary className="cursor-pointer text-xs font-medium text-primary-700 dark:text-primary-300">Ver os números em tabela</summary>
                <table className="mt-2 w-full text-sm tabular-nums">
                  <thead>
                    <tr className="text-left text-xs uppercase tracking-wide text-slate-400">
                      <th scope="col" className="py-1 font-medium">Mês</th>
                      <th scope="col" className="py-1 text-right font-medium">Notas</th>
                      <th scope="col" className="py-1 text-right font-medium">Valor</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-700/60">
                    {[...serie].reverse().map((p) => (
                      <tr key={p.competencia}>
                        <td className="py-1 text-slate-700 dark:text-slate-200">{formatCompetenciaLonga(p.competencia)}</td>
                        <td className="py-1 text-right text-slate-600 dark:text-slate-300">{p.notas}</td>
                        <td className="py-1 text-right text-slate-800 dark:text-slate-100">{formatBRL(p.valor)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </details>
            </>
          )}
        </Card>

        <div className="flex flex-col gap-5 lg:col-span-2">
          <Card className="p-5">
            <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">Fechamento</h3>
            {r?.fechamentos && r.fechamentos.length > 0 ? (
              <ul className="flex flex-col gap-1.5">
                {[...r.fechamentos].reverse().map((f) => {
                  const e = FECHAMENTO[f.estado] ?? FECHAMENTO.vazio
                  return (
                    <li key={f.competencia} className="flex items-center justify-between gap-3 text-sm">
                      <span className="text-slate-700 dark:text-slate-200">{formatCompetenciaLonga(f.competencia)}</span>
                      <Badge variant={e.variante}>{e.texto}</Badge>
                    </li>
                  )
                })}
              </ul>
            ) : (
              <p className="text-sm text-slate-500 dark:text-slate-400">Esta empresa não usa o módulo Financeiro: não há conciliação pra acompanhar.</p>
            )}
            {c.modulos.includes("emissor") && (
              <div className="mt-4 border-t border-slate-100 pt-3 dark:border-slate-700">
                <p className="text-sm font-medium text-slate-800 dark:text-slate-100">Notas do mês pro seu sistema</p>
                <BaixarNotasDoMes cliente={c} />
              </div>
            )}
          </Card>

          <Card className="p-5">
            <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">Contato e acesso</h3>
            {c.dono && (
              <p className="text-sm text-slate-700 dark:text-slate-200">
                {c.dono.nome ?? "Responsável"} <span className="break-all text-slate-500 dark:text-slate-400">· {c.dono.email}</span>
                {whats && (
                  <a
                    href={`https://wa.me/${whats.length <= 11 ? "55" : ""}${whats}`}
                    target="_blank"
                    rel="noreferrer"
                    className="mt-1 flex w-fit items-center gap-1 text-sm font-medium text-primary-700 hover:underline dark:text-primary-300"
                  >
                    <MessageCircle size={14} aria-hidden /> Chamar no WhatsApp
                  </a>
                )}
              </p>
            )}
            <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">Você pode: {resumoPermissoes(c.permissoes)}.</p>
            <button type="button" onClick={() => aoSair(c)} className="mt-3 text-xs font-medium text-slate-400 underline-offset-2 hover:text-danger-600 hover:underline dark:text-slate-500">
              Deixar de atender esta empresa
            </button>
          </Card>
        </div>
      </div>

      {/* Pasta do mês (08/10/2026): arquivos e conversa com a empresa, sem entrar nela. */}
      <section id="pasta" className="flex scroll-mt-24 flex-col gap-3">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">Pasta do mês</h3>
        <PastaDoMes base={`/contador/atendimentos/${c.id}/pasta`} />
      </section>
    </div>
  )
}
