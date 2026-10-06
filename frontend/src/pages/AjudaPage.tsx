import { ArrowRight, ChevronDown, LifeBuoy, MessageCircleQuestion, Search, Sparkles, X } from "lucide-react"
import { useEffect, useMemo, useState } from "react"
import { Link } from "react-router-dom"
import { BotaoSuporte } from "../components/SuporteModal"
import { AnaAvatar } from "../components/brand/Marca"
import { Button } from "../components/ui/Button"
import { Card } from "../components/ui/Card"
import { api } from "../lib/api"
import { FAQ, type PerguntaFaq, TEMAS_FAQ, perguntaVisivel } from "../lib/faq"
import { useModulos } from "../lib/modulos"
import type { AjudaInfo } from "../lib/types"

// Ajuda / FAQ (05/10/2026) — pedido do Marcos: "vamos fazer uma sessão de
// FAQ" e, sobre IA, "não quero pagar; queria algo simples, apenas para
// explicar para a pessoa as dúvidas dela — poderíamos criar um arquivo de
// explicação e vincular ele a alguma IA grátis".
//
// Três camadas, da mais rápida pra mais lenta:
//   1. as perguntas daqui (src/lib/faq.ts), com busca;
//   2. se a variável AJUDA_IA_URL estiver configurada, uma IA gratuita de
//      terceiros carregada com o guia (GET /api/ajuda devolve o endereço).
//      O guia em si (backend/app/data/guia-agente-ana.md) não é público:
//      só a administração baixa, na Gestão;
//   3. o suporte de verdade (o mesmo formulário do menu).
// A tela vale pra qualquer módulo: só some a pergunta de um módulo que a
// empresa não tem.

/** "Conciliação" → "conciliacao": a busca ignora acento e maiúscula. */
function semAcento(texto: string): string {
  return texto.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase()
}

// Mesma cara do <Button> (components/ui/Button) em link: o <a> de abrir a IA
// não pode ser <button>.
const LINK_BOTAO = "inline-flex items-center justify-center gap-1.5 rounded-lg px-4 py-2 text-sm font-medium transition-colors"
const LINK_ACCENT = `${LINK_BOTAO} bg-accent-500 text-white hover:bg-accent-600`

function Pergunta({ item, aberta, onAlternar }: { item: PerguntaFaq; aberta: boolean; onAlternar: () => void }) {
  const idResposta = `faq-resposta-${item.id}`
  return (
    <li className="border-t border-slate-100 first:border-t-0 dark:border-slate-700/60">
      <h3>
        <button
          type="button"
          onClick={onAlternar}
          aria-expanded={aberta}
          aria-controls={idResposta}
          className="flex w-full items-start justify-between gap-3 px-4 py-3 text-left text-sm font-medium text-slate-800 hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary-500 dark:text-slate-100 dark:hover:bg-slate-700/40 sm:px-5"
        >
          <span>{item.pergunta}</span>
          <ChevronDown
            size={18}
            aria-hidden="true"
            className={`mt-0.5 shrink-0 text-slate-400 transition-transform dark:text-slate-500 ${aberta ? "rotate-180" : ""}`}
          />
        </button>
      </h3>
      {aberta && (
        <div id={idResposta} className="px-4 pb-4 sm:px-5">
          <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-300">{item.resposta}</p>
          {item.link && (
            <Link
              to={item.link}
              className="mt-2 inline-flex items-center gap-1 text-sm font-semibold text-primary-600 hover:underline dark:text-primary-300"
            >
              Ir pra essa tela <ArrowRight size={14} aria-hidden="true" />
            </Link>
          )}
        </div>
      )}
    </li>
  )
}

export function AjudaPage() {
  const modulos = useModulos()
  const [busca, setBusca] = useState("")
  const [abertas, setAbertas] = useState<Set<string>>(() => new Set())
  // Endereço da IA gratuita (undefined = ainda perguntando; null = não tem).
  const [iaUrl, setIaUrl] = useState<string | null | undefined>(undefined)

  useEffect(() => {
    let vivo = true
    api
      .get<AjudaInfo>("/ajuda")
      // Confere de novo aqui: o link abre em outra aba, só serve https.
      .then((r) => vivo && setIaUrl(typeof r.ia_url === "string" && r.ia_url.startsWith("https://") ? r.ia_url : null))
      // Sem resposta, a tela segue sem o botão — o guia e o suporte continuam.
      .catch(() => vivo && setIaUrl(null))
    return () => {
      vivo = false
    }
  }, [])

  // Só as perguntas dos módulos que a empresa tem.
  const visiveis = useMemo(
    () => FAQ.filter((p) => perguntaVisivel(p, { emissor: modulos.emissor, financeiro: modulos.financeiro })),
    [modulos.emissor, modulos.financeiro],
  )

  // Todas as palavras digitadas precisam aparecer (na pergunta, na resposta
  // ou no nome do tema), em qualquer ordem.
  const palavras = useMemo(() => semAcento(busca).split(/\s+/).filter(Boolean), [busca])
  const grupos = useMemo(
    () =>
      TEMAS_FAQ.map((tema) => {
        const titulo = semAcento(tema.titulo)
        const itens = visiveis.filter((p) => {
          if (p.tema !== tema.id) return false
          if (palavras.length === 0) return true
          const texto = `${semAcento(p.pergunta)} ${semAcento(p.resposta)} ${titulo}`
          return palavras.every((palavra) => texto.includes(palavra))
        })
        return { ...tema, itens }
      }).filter((g) => g.itens.length > 0),
    [visiveis, palavras],
  )
  const encontradas = grupos.reduce((n, g) => n + g.itens.length, 0)
  const buscando = palavras.length > 0
  // Sobrou uma só: já vem com a resposta aberta (é a que a pessoa procurava).
  // Pra ela, estar na lista `abertas` quer dizer o contrário: a pessoa fechou.
  const unica = buscando && encontradas === 1 ? grupos[0].itens[0].id : null

  function alternar(id: string) {
    setAbertas((atuais) => {
      const novas = new Set(atuais)
      if (novas.has(id)) novas.delete(id)
      else novas.add(id)
      return novas
    })
  }

  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col gap-5">
      <div className="flex items-start gap-3">
        <span className="hidden shrink-0 sm:block">
          <AnaAvatar size={44} />
        </span>
        <div>
          <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">Ajuda</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            As dúvidas mais comuns, respondidas por mim. Digite o que você procura — ou abra um tema.
          </p>
        </div>
      </div>

      <Card className="p-3 sm:p-4">
        <label htmlFor="ajuda-busca" className="sr-only">
          Buscar nas perguntas
        </label>
        <div className="relative">
          <Search size={18} aria-hidden="true" className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 dark:text-slate-500" />
          <input
            id="ajuda-busca"
            type="search"
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
            placeholder="Ex.: certificado, CEP, cancelar nota, extrato..."
            autoComplete="off"
            enterKeyHint="search"
            className="w-full rounded-lg border border-slate-300 bg-white py-2.5 pl-10 pr-10 text-base text-slate-900 placeholder:text-slate-400 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100 dark:placeholder:text-slate-500 sm:text-sm [&::-webkit-search-cancel-button]:hidden"
          />
          {busca && (
            <button
              type="button"
              onClick={() => setBusca("")}
              aria-label="Limpar a busca"
              title="Limpar a busca"
              className="absolute right-2 top-1/2 -translate-y-1/2 rounded-md p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600 dark:text-slate-500 dark:hover:bg-slate-700 dark:hover:text-slate-300"
            >
              <X size={16} aria-hidden="true" />
            </button>
          )}
        </div>
        <p className="mt-2 px-1 text-xs text-slate-500 dark:text-slate-400" role="status" aria-live="polite">
          {buscando
            ? encontradas === 0
              ? "Nenhuma pergunta encontrada."
              : `${encontradas} ${encontradas === 1 ? "pergunta encontrada" : "perguntas encontradas"}.`
            : `${visiveis.length} perguntas, em ${grupos.length} temas.`}
        </p>
      </Card>

      {buscando && encontradas === 0 && (
        <Card className="px-4 py-6 text-center sm:px-6">
          <p className="text-sm font-medium text-slate-800 dark:text-slate-100">Não achei nenhuma pergunta com “{busca.trim()}”.</p>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            Tente outra palavra (por exemplo, “CEP” em vez de “endereço errado”). Se não aparecer, o guia completo e o suporte estão logo
            abaixo.
          </p>
          <Button type="button" variant="outline" className="mt-4" onClick={() => setBusca("")}>
            Ver todas as perguntas
          </Button>
        </Card>
      )}

      {grupos.map((grupo) => (
        <section key={grupo.id} aria-labelledby={`ajuda-tema-${grupo.id}`}>
          <Card className="overflow-hidden">
            <div className="flex items-baseline justify-between gap-3 border-b border-slate-100 bg-slate-50/70 px-4 py-3 dark:border-slate-700/60 dark:bg-slate-900/30 sm:px-5">
              <h2 id={`ajuda-tema-${grupo.id}`} className="text-base font-semibold text-slate-800 dark:text-slate-100">
                {grupo.titulo}
              </h2>
              <span className="shrink-0 text-xs text-slate-400 dark:text-slate-500">
                {grupo.itens.length} {grupo.itens.length === 1 ? "pergunta" : "perguntas"}
              </span>
            </div>
            <ul>
              {grupo.itens.map((item) => (
                <Pergunta key={item.id} item={item} aberta={abertas.has(item.id) !== (item.id === unica)} onAlternar={() => alternar(item.id)} />
              ))}
            </ul>
          </Card>
        </section>
      ))}

      {/* IA gratuita: só quando há um endereço configurado (AJUDA_IA_URL). O guia
          completo NÃO fica à disposição do usuário (06/10/2026: "o usuário comum
          não deve ter acesso a isso") — quem baixa é a administração, na Gestão. */}
      {iaUrl && (
        <section aria-labelledby="ajuda-ia">
          <Card className="p-4 sm:p-6">
            <h2 id="ajuda-ia" className="flex items-center gap-2 text-base font-semibold text-slate-800 dark:text-slate-100">
              <Sparkles size={18} aria-hidden="true" className="text-accent-500" /> Não achou? Pergunte pra uma IA (grátis)
            </h2>
            <p className="mt-2 text-sm leading-relaxed text-slate-600 dark:text-slate-300">
              Deixei as minhas explicações carregadas numa ferramenta de IA gratuita, de terceiros (ela não é da Agente Ana). Você escreve a
              dúvida do seu jeito e ela responde com base nelas.
            </p>
            <p className="mt-2 rounded-lg bg-warning-50 px-3 py-2 text-sm text-warning-700 dark:bg-warning-900/30 dark:text-warning-300">
              Ela pode errar — na dúvida, vale o que está aqui na Ajuda ou a resposta do suporte.{" "}
              <strong>Não cole lá a sua senha, o seu certificado digital nem dados dos seus clientes.</strong>
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              <a href={iaUrl} target="_blank" rel="noreferrer" className={LINK_ACCENT}>
                <MessageCircleQuestion size={16} aria-hidden="true" /> Perguntar pra IA
                <span className="sr-only"> (abre em outra aba)</span>
              </a>
            </div>
          </Card>
        </section>
      )}

      <section aria-labelledby="ajuda-suporte">
        <Card className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between sm:p-6">
          <div>
            <h2 id="ajuda-suporte" className="flex items-center gap-2 text-base font-semibold text-slate-800 dark:text-slate-100">
              <LifeBuoy size={18} aria-hidden="true" className="text-primary-600 dark:text-primary-300" /> Falar com o suporte
            </h2>
            <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">
              Prefere falar com uma pessoa? Mande a sua dúvida: a resposta chega no seu e-mail, normalmente no mesmo dia útil.
            </p>
          </div>
          <BotaoSuporte logado className={`${LINK_BOTAO} shrink-0 bg-primary-600 text-white hover:bg-primary-700`}>
            Falar com o suporte
          </BotaoSuporte>
        </Card>
      </section>
    </div>
  )
}
