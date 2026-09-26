import { useId } from "react"

// Identidade da Agente Ana: o avatar (rosto da marca, usado onde a Ana
// "fala" — landing, avisos) e o símbolo "A" (ícone compacto: favicon,
// sidebar, telas de entrada). Os dois usam o mesmo gradiente accent→primary
// da paleta (index.css), então combinam com o resto do sistema. SVG inline
// com useId pros ids de gradiente não colidirem quando aparecem várias
// vezes na mesma página.

export function AnaAvatar({ size = 40, className = "" }: { size?: number; className?: string }) {
  const id = useId().replace(/:/g, "")
  return (
    <svg
      viewBox="0 0 64 64"
      width={size}
      height={size}
      className={className}
      role="img"
      aria-label="Ana, a agente"
    >
      <defs>
        <linearGradient id={`bg${id}`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#ec4899" />
          <stop offset="1" stopColor="#2f4fd1" />
        </linearGradient>
        <clipPath id={`c${id}`}>
          <circle cx="32" cy="32" r="32" />
        </clipPath>
      </defs>
      <g clipPath={`url(#c${id})`}>
        <rect width="64" height="64" fill={`url(#bg${id})`} />
        <path d="M17 30c0-11 7-18 15-18s15 7 15 18v16c0 3-3 5-6 5H23c-3 0-6-2-6-5z" fill="#2a1a14" />
        <path d="M8 66c1-11 10-17 24-17s23 6 24 17z" fill="#131b3f" />
        <path d="M26 49l6 8 6-8" fill="#fff" />
        <rect x="28" y="38" width="8" height="12" rx="3" fill="#d9a07c" />
        <ellipse cx="32" cy="30" rx="10" ry="12" fill="#eab48f" />
        <path
          d="M21.5 28c1-8 5.5-12.5 11.5-12.5 5 0 9 3.5 10 9-5-.5-10-3-12.5-6.5-1.5 4-5 8-9 10z"
          fill="#2a1a14"
        />
        <circle cx="28" cy="31" r="1.3" fill="#2a1a14" />
        <circle cx="36" cy="31" r="1.3" fill="#2a1a14" />
        <path d="M28.5 35.5c2 2 5 2 7 0" stroke="#a3534a" strokeWidth="1.4" fill="none" strokeLinecap="round" />
      </g>
    </svg>
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
