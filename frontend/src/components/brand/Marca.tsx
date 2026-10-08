import { useId } from "react"

// Identidade da Agente Ana: o símbolo "A" com o gradiente accent→primary da
// paleta (index.css). 08/10/2026 — saiu a ilustração 3D da "bonequinha"
// ("meio cara de coisa amadora"): onde a Ana "fala" (avisos, telas de
// entrada, e-mails) agora aparece o mesmo "A" do logotipo. O símbolo é SVG
// inline com useId pros ids de gradiente não colidirem quando aparece várias
// vezes na mesma página.

/** A Ana "falando": o símbolo da marca, no tamanho pedido. (O nome ficou do
 * tempo em que era um rosto; quem usa não precisa mudar.) */
export function AnaAvatar({ size = 40, className = "" }: { size?: number; className?: string }) {
  return (
    <span role="img" aria-label="Agente Ana" className={`inline-flex shrink-0 ${className}`} style={{ width: size, height: size }}>
      <SimboloAna size={size} />
    </span>
  )
}

export function SimboloAna({ size = 36, className = "" }: { size?: number; className?: string }) {
  const id = useId().replace(/:/g, "")
  return (
    <svg viewBox="0 0 64 64" width={size} height={size} className={className} aria-hidden="true">
      <defs>
        <linearGradient id={`g${id}`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#ec4899" />
          <stop offset="1" stopColor="#2f4fd1" />
        </linearGradient>
      </defs>
      <rect width="64" height="64" rx="16" fill={`url(#g${id})`} />
      <path
        fillRule="evenodd"
        d="M32 14 L48 50 H40.5 L37.2 42 H26.8 L23.5 50 H16 Z M29.2 36 H34.8 L32 29 Z"
        fill="#fff"
      />
      <circle cx="47" cy="17" r="4" fill="#fff" />
    </svg>
  )
}

// Logotipo completo: símbolo + "Agente Ana". `escuro` = sobre fundo navy
// (sidebar), onde o texto precisa ser claro independente do tema.
export function Marca({
  subtitulo,
  escuro = false,
  tamanho = 36,
}: {
  subtitulo?: string
  escuro?: boolean
  tamanho?: number
}) {
  const corNome = escuro ? "text-white" : "text-slate-900 dark:text-slate-100"
  const corSub = escuro ? "text-slate-400" : "text-slate-500 dark:text-slate-400"
  return (
    <div className="flex items-center gap-2.5">
      <SimboloAna size={tamanho} className="shrink-0" />
      <div className="leading-tight">
        <p className={`whitespace-nowrap text-base font-semibold tracking-tight ${corNome}`}>
          <span className="font-normal opacity-80">Agente</span>{" "}
          <span className={escuro ? "text-accent-300" : "text-accent-500"}>Ana</span>
        </p>
        {subtitulo && <p className={`text-[11px] ${corSub}`}>{subtitulo}</p>}
      </div>
    </div>
  )
}
