import { useCallback, useEffect, useMemo, useState } from "react"
import { useLocation, useNavigate } from "react-router-dom"
import { useAuth } from "../../lib/auth"
import { type ItemNovidade, useNovidades } from "../../lib/novidades"
import { definirPasseio, jaViu, tutorialAtivo } from "../../lib/tutorial"
import { BOTAO_FORTE, BOTAO_SUAVE, BalaoDaAna } from "./Tour"
import { tourDoCaminho } from "./passos"

/** "O que mudou desde a sua última visita" (08/10/2026). Pedido do Marcos:
 * "além de falar as mudanças [...] seria legal a opção dela ver o que mudou
 * também, com nosso assistente do tutorial. Ela poderia sair ou ver, isso
 * considerando a última vez que ela entrou; se for a primeira, ela tem o
 * tutorial normal."
 *
 * Quando saiu versão desde a última visita, a Ana pergunta: "Ver o que mudou"
 * ou "Agora não". Aceitando, ela passa por cada novidade do perfil da pessoa,
 * abrindo a tela e apontando o lugar. Conta nova não recebe convite (nasce em
 * dia no servidor) — vale o tutorial de primeira visita. */

const MAXIMO = 8

export function PasseioNovidades() {
  const { usuario } = useAuth()
  const { dados, marcarVistas } = useNovidades()
  const { pathname } = useLocation()
  const navigate = useNavigate()
  // null = fechado; -1 = o convite; 0.. = cada novidade
  const [passo, setPasso] = useState<number | null>(null)
  const [dispensado, setDispensado] = useState(false)

  const itens = useMemo<ItemNovidade[]>(() => (dados?.versoes ?? []).filter((v) => v.nova).flatMap((v) => v.itens).slice(0, MAXIMO), [dados])
  const versoesNovas = (dados?.versoes ?? []).filter((v) => v.nova)

  // Convida quando há novidade e a tela atual não está no meio das dicas de primeira visita.
  useEffect(() => {
    if (passo !== null || dispensado || !usuario || usuario.demo || itens.length === 0 || !tutorialAtivo()) return
    if (pathname.startsWith("/app/novidades")) return // já está lendo
    const tour = tourDoCaminho(pathname)
    if (tour && !jaViu(tour.tela)) return
    const t = setTimeout(() => {
      definirPasseio(true)
      setPasso(-1)
    }, 900)
    return () => clearTimeout(t)
  }, [passo, dispensado, usuario, itens.length, pathname])

  const fechar = useCallback(() => {
    definirPasseio(false)
    setPasso(null)
    setDispensado(true)
    marcarVistas() // viu ou dispensou: o sino continua guardando tudo
  }, [marcarVistas])

  const irPara = useCallback(
    (indice: number) => {
      const item = itens[indice]
      if (!item) return fechar()
      if (item.link && item.link.split("?")[0] !== pathname) navigate(item.link)
      setPasso(indice)
    },
    [itens, pathname, navigate, fechar],
  )

  if (passo === null || !dados) return null

  if (passo === -1) {
    return (
      <BalaoDaAna
        titulo="Tem novidade desde a sua última visita"
        texto={
          <>
            {versoesNovas.length === 1 ? versoesNovas[0].resumo : `Saíram ${versoesNovas.length} atualizações. A mais recente: ${versoesNovas[0]?.resumo ?? ""}`}
            <span className="mt-1 block text-xs text-slate-400 dark:text-slate-500">
              Quer que eu te mostre? São {itens.length} {itens.length === 1 ? "ponto" : "pontos"}, menos de um minuto.
            </span>
          </>
        }
        onFechar={fechar}
        rotuloFechar="Agora não"
      >
        <span className="text-xs text-slate-400 dark:text-slate-500">versão {dados.versao}</span>
        <div className="flex gap-2">
          <button type="button" onClick={fechar} className={BOTAO_SUAVE}>
            Agora não
          </button>
          <button type="button" onClick={() => irPara(0)} className={BOTAO_FORTE}>
            Ver o que mudou
          </button>
        </div>
      </BalaoDaAna>
    )
  }

  const item = itens[passo]
  if (!item) return null
  const ultimo = passo === itens.length - 1
  return (
    <BalaoDaAna alvo={item.alvo} titulo={item.titulo} texto={item.texto} onFechar={fechar} rotuloFechar="Fechar o passeio">
      <span className="text-xs tabular-nums text-slate-400 dark:text-slate-500">
        {passo + 1} de {itens.length}
      </span>
      <div className="flex gap-2">
        {passo > 0 ? (
          <button type="button" onClick={() => irPara(passo - 1)} className={BOTAO_SUAVE}>
            Voltar
          </button>
        ) : (
          <button type="button" onClick={fechar} className={BOTAO_SUAVE}>
            Sair
          </button>
        )}
        <button type="button" onClick={() => (ultimo ? fechar() : irPara(passo + 1))} className={BOTAO_FORTE}>
          {ultimo ? "Entendi" : "Próximo"}
        </button>
      </div>
    </BalaoDaAna>
  )
}
