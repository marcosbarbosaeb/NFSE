import { Info } from "lucide-react"
import { PAISES } from "../../lib/paises"
import { CaixaBusca } from "../ui/CaixaBusca"
import { Field, FieldWrap } from "../ui/Field"

/** Tomador de fora do Brasil (05/10/2026 — o caso do Google AdSense: quem
 * paga é uma empresa estrangeira, sem CNPJ). Os campos são os mesmos no
 * passo "Quem é" e na edição dos "Dados do tomador". */

export interface DadosEmpresaDeFora {
  razao_social: string
  /** Código ISO de 2 letras. */
  pais: string
  nif: string
  /** Cidade e endereço lá fora — opcional, só pra consulta. */
  endereco: string
}

export const AVISO_NOTA_EXTERIOR =
  "Nota pra empresa de fora do Brasil sai com a identificação fiscal estrangeira e o país; o ISS é tratado como nas notas que a Receita já autorizou pra vendedores de fora. Na primeira vez, confirme com seu contador."

const OPCOES_PAIS = PAISES.map((p) => ({ id: p.codigo, rotulo: p.nome }))

export function empresaDeForaCompleta(d: DadosEmpresaDeFora): boolean {
  return d.razao_social.trim().length >= 2 && d.pais.length === 2 && d.nif.trim().length > 0
}

/** O corpo que `POST /vinculos/{id}/identificar` espera. */
export function corpoEmpresaDeFora(d: DadosEmpresaDeFora) {
  return {
    tipo: "exterior" as const,
    razao_social: d.razao_social.trim(),
    pais: d.pais,
    nif: d.nif.trim(),
    endereco_exterior: d.endereco.trim() || null,
  }
}

export function AvisoNotaExterior({ className = "" }: { className?: string }) {
  return (
    <p
      className={`flex items-start gap-2 rounded-lg bg-primary-50 px-3 py-2 text-xs text-slate-600 dark:bg-primary-900/20 dark:text-slate-300 ${className}`}
    >
      <Info size={14} className="mt-0.5 shrink-0 text-primary-600 dark:text-primary-300" aria-hidden />
      <span>{AVISO_NOTA_EXTERIOR}</span>
    </p>
  )
}

export function CamposEmpresaDeFora({ valor, onChange }: { valor: DadosEmpresaDeFora; onChange: (v: DadosEmpresaDeFora) => void }) {
  const mudar = (campo: keyof DadosEmpresaDeFora, texto: string) => onChange({ ...valor, [campo]: texto })
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
      <div className="sm:col-span-2">
        <Field
          label="Nome da empresa"
          value={valor.razao_social}
          onChange={(e) => mudar("razao_social", e.target.value)}
          maxLength={200}
          placeholder="Ex.: Google Ireland Limited"
          hint="Do jeito que aparece no contrato ou no extrato de pagamento."
        />
      </div>
      <FieldWrap label="País da empresa" hint="Digite pra buscar.">
        <CaixaBusca
          valor={valor.pais}
          opcoes={OPCOES_PAIS}
          onEscolher={(codigo) => mudar("pais", codigo)}
          placeholder="Escolha o país"
          ariaLabel="País da empresa"
          alerta={!valor.pais}
          className="[&_input]:py-2 [&_input]:pl-3"
        />
      </FieldWrap>
      <Field
        label="NIF / número fiscal no país"
        value={valor.nif}
        onChange={(e) => mudar("nif", e.target.value)}
        maxLength={40}
        placeholder="Ex.: IE1234567X"
      />
      <p className="text-xs text-slate-500 sm:col-span-2 dark:text-slate-400">
        <strong>O que é o NIF?</strong> É o número que identifica a empresa no imposto do país dela — como o CNPJ é aqui. Ele vem no
        contrato ou no extrato de pagamento, às vezes escrito como “Tax ID”, “VAT number” ou “Registration number”. Copie igual está lá.
      </p>
      <div className="sm:col-span-2">
        <Field
          label="Cidade e endereço lá fora (opcional)"
          value={valor.endereco}
          onChange={(e) => mudar("endereco", e.target.value)}
          maxLength={200}
          placeholder="Ex.: Dublin, Gordon House, Barrow Street"
          hint="Fica guardado só pra você consultar. Na nota vai só o país."
        />
      </div>
    </div>
  )
}
