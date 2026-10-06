import { Activity, CircleAlert, CreditCard, FileCheck, FileText, Mail, ShieldCheck, Users, Wrench } from "lucide-react"
import { formatCompetenciaLonga } from "../../lib/format"
import { ASSINATURAS, motivosDeAtencao, nomeDaConta, numero, plural } from "../../lib/gestao"
import type { PainelGestao } from "../../lib/types"
import { TituloSecao } from "../PaginaAbas"
import { BarrasHorizontais } from "../graficos/BarrasHorizontais"
import { CartaoGrafico, GraficoVazio } from "../graficos/base"
import { Badge } from "../ui/Badge"
import { Card } from "../ui/Card"
import { StatCard } from "../ui/StatCard"
import { useVerMais } from "../ui/VerMais"

// Gestão › Visão geral (06/10/2026): o retrato da plataforma no mês. Todos os
// números são das contas reais — as de simulação ficam de fora.

export function VisaoGeralGestao({ painel }: { painel: PainelGestao }) {
  const r = painel.resumo
  const mes = formatCompetenciaLonga(painel.competencia).toLowerCase()
  return (
    <>
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-3">
        <StatCard
          icon={<Users size={18} />}
          label="Contas"
          value={numero(r.contas)}
          sublabel={`${r.email_confirmado === 1 ? "1 confirmou" : `${numero(r.email_confirmado)} confirmaram`} o e-mail${
            r.contas_teste > 0 ? ` · ${numero(r.contas_teste)} de teste` : ""
          }`}
        />
        <StatCard
          icon={<Activity size={18} />}
          iconClassName="bg-success-50 text-success-600 dark:bg-success-900/40 dark:text-success-300"
          label="Ativas nos últimos 30 dias"
          value={numero(r.ativas_30_dias)}
          sublabel={`${numero(Math.max(0, r.contas - r.ativas_30_dias))} sem entrar nesse período`}
        />
        <StatCard
          icon={<ShieldCheck size={18} />}
          label="Com certificado digital"
          value={numero(r.com_certificado)}
          sublabel={`de ${plural(r.contas, "conta", "contas")}`}
        />
        <StatCard
          icon={<FileCheck size={18} />}
          label="Emitiram nota no mês"
          value={numero(r.emitiram_no_mes)}
          sublabel={`de ${plural(r.contas, "conta", "contas")}`}
        />
        <StatCard
          icon={<FileText size={18} />}
          label="Notas no mês"
          value={numero(r.notas_mes)}
          sublabel={`${numero(r.notas_total)} desde o começo`}
        />
        <StatCard
          icon={<Mail size={18} />}
          label="E-mails no mês"
          value={numero(r.emails_mes)}
          sublabel={`${numero(r.emails_lote_mes)} de lote · ${plural(r.emails_falha_mes, "falha", "falhas")}`}
          sublabelClassName={r.emails_falha_mes > 0 ? "text-warning-700 dark:text-warning-300" : undefined}
        />
      </div>
      <p className="-mt-3 text-xs text-slate-400 dark:text-slate-500">
        Mês de {mes}. Contam só as contas de verdade
        {r.contas_simulacao > 0 ? ` — ${plural(r.contas_simulacao, "conta de simulação fica", "contas de simulação ficam")} de fora.` : "."}
      </p>

      <Atencao painel={painel} />

      <Card className="p-5">
        <TituloSecao icone={CreditCard}>Assinaturas</TituloSecao>
        <Assinaturas assinaturas={r.assinaturas} />
        {/* Bloqueio de quem não tem assinatura (06/10/2026). */}
        <p className="mt-4 rounded-lg bg-slate-50 px-3 py-2.5 text-sm text-slate-600 dark:bg-slate-900/40 dark:text-slate-300">
          <strong className={r.bloqueio_ativo ? "text-danger-700 dark:text-danger-300" : "text-slate-800 dark:text-slate-100"}>
            Bloqueio de quem não tem assinatura: {r.bloqueio_ativo ? "ligado" : "desligado"}.
          </strong>{" "}
          {r.sem_acesso === 0
            ? "Nenhuma conta com teste vencido ou assinatura encerrada."
            : r.bloqueio_ativo
              ? `${plural(r.sem_acesso, "conta está", "contas estão")} só pra consulta (teste vencido ou assinatura encerrada).`
              : `${plural(r.sem_acesso, "conta ficaria", "contas ficariam")} só pra consulta se você ligasse hoje (teste vencido ou assinatura encerrada).`}{" "}
          {r.liberadas_na_mao > 0 && `${plural(r.liberadas_na_mao, "liberada", "liberadas")} por você. `}
          Pra liberar alguém, abra a conta na aba Contas.
        </p>
      </Card>

      <section className="flex flex-col gap-2">
        <TituloSecao icone={Wrench}>Ferramentas mais usadas</TituloSecao>
        <Ferramentas painel={painel} />
      </section>
    </>
  )
}

function Assinaturas({ assinaturas }: { assinaturas: Record<string, number> }) {
  // As situações conhecidas, na ordem da casa, e depois qualquer outra que o servidor mandar.
  const conhecidas = new Set(ASSINATURAS.map((a) => a.id))
  const linhas = [
    ...ASSINATURAS.map((a) => ({ ...a, quantas: assinaturas[a.id] ?? 0 })),
    ...Object.entries(assinaturas)
      .filter(([id]) => !conhecidas.has(id))
      .map(([id, quantas]) => ({ id, rotulo: id, variante: "neutral" as const, quantas })),
  ]
  return (
    <dl className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-6">
      {linhas.map((a) => (
        <div key={a.id} className="flex flex-col-reverse items-start gap-1.5 rounded-xl border border-slate-200 p-3 dark:border-slate-700">
          <dt>
            <Badge variant={a.variante}>{a.rotulo}</Badge>
          </dt>
          <dd className={`text-2xl font-semibold tabular-nums ${a.quantas > 0 ? "text-slate-900 dark:text-slate-100" : "text-slate-300 dark:text-slate-600"}`}>
            {numero(a.quantas)}
          </dd>
        </div>
      ))}
    </dl>
  )
}

function Ferramentas({ painel }: { painel: PainelGestao }) {
  const total = painel.resumo.contas
  const usadas = painel.ferramentas.filter((f) => f.contas > 0)
  const paradas = painel.ferramentas.filter((f) => f.contas === 0)
  const periodo = (doMes: boolean) => (doMes ? "no mês" : "no total")
  const primeira = usadas[0]
  return (
    <CartaoGrafico
      periodo="Quantas contas usam cada ferramenta — e, ao lado do nome, o volume (notas, e-mails, lançamentos...)"
      resumo={
        primeira ? (
          <>
            <strong className="font-semibold">{primeira.nome}</strong> é a mais usada: {numero(primeira.contas)} de{" "}
            {plural(total, "conta", "contas")}.
          </>
        ) : undefined
      }
      tabela={{
        titulo: "Uso de cada ferramenta",
        colunas: ["Ferramenta", "Contas que usam", "Volume", "Período"],
        linhas: painel.ferramentas.map((f) => [f.nome, numero(f.contas), numero(f.volume), periodo(f.do_mes)]),
      }}
    >
      {usadas.length === 0 ? (
        <GraficoVazio>Ninguém usou as ferramentas ainda.</GraficoVazio>
      ) : (
        <BarrasHorizontais
          titulo="Ferramentas, da mais usada pra menos usada, por número de contas"
          itens={usadas.map((f) => ({ nome: f.nome, valor: f.contas, detalhe: `${numero(f.volume)} ${periodo(f.do_mes)}` }))}
          maximo={painel.ferramentas.length}
          total={total}
          formatar={(n) => plural(n, "conta", "contas")}
        />
      )}
      {usadas.length > 0 && (
        // No celular o volume não cabe ao lado do nome: vai escrito aqui.
        <ul className="flex flex-col gap-0.5 text-xs text-slate-500 sm:hidden dark:text-slate-400">
          {usadas.map((f) => (
            <li key={f.id}>
              {f.nome}: {numero(f.volume)} {periodo(f.do_mes)}
            </li>
          ))}
        </ul>
      )}
      {paradas.length > 0 && usadas.length > 0 && (
        <p className="text-xs text-slate-500 dark:text-slate-400">Ainda sem uso: {paradas.map((f) => f.nome).join(", ")}.</p>
      )}
    </CartaoGrafico>
  )
}

function Atencao({ painel }: { painel: PainelGestao }) {
  // "Agora" é a hora em que o servidor montou o painel (a mesma régua dos outros números).
  const agora = Date.parse(painel.gerado_em)
  const itens = painel.contas
    .map((c) => ({ conta: c, motivos: motivosDeAtencao(c, agora) }))
    .filter((i) => i.motivos.length > 0)
    // Primeiro quem tem prazo correndo (teste), depois quem acumula mais motivos.
    .sort((a, b) => peso(b.motivos) - peso(a.motivos))
  const { visiveis, botao } = useVerMais(itens, 8)
  return (
    <Card className="p-5">
      <TituloSecao icone={CircleAlert}>Precisam de atenção</TituloSecao>
      {itens.length === 0 ? (
        <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">Nenhuma conta pedindo atenção agora.</p>
      ) : (
        <>
          <p className="mb-2 text-sm text-slate-500 dark:text-slate-400">
            {plural(itens.length, "conta", "contas")} com e-mail sem confirmar, sem certificado, sem entrar há mais de 30 dias ou com o
            teste acabando.
          </p>
          <ul className="divide-y divide-slate-100 dark:divide-slate-700/60">
            {visiveis.map(({ conta, motivos }) => (
              <li key={conta.id} className="flex flex-col gap-1.5 py-2.5 sm:flex-row sm:items-center sm:justify-between sm:gap-3">
                <span className="min-w-0 truncate text-sm font-medium text-slate-800 dark:text-slate-100" title={nomeDaConta(conta)}>
                  {nomeDaConta(conta)}
                </span>
                <span className="flex shrink-0 flex-wrap gap-1.5">
                  {motivos.map((m) => (
                    <Badge key={m.texto} variant={m.variante}>
                      {m.texto}
                    </Badge>
                  ))}
                </span>
              </li>
            ))}
          </ul>
          {botao}
        </>
      )}
    </Card>
  )
}

function peso(motivos: { variante: string }[]): number {
  const prazo = motivos.some((m) => m.variante === "danger") ? 200 : 0
  return prazo + motivos.filter((m) => m.variante === "warning").length * 10 + motivos.length
}
