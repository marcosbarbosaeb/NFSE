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
  /** Sem número fiscal: "1" = dispensada, "2" = o país dela não exige; "" = tem número. */
  motivo_sem_nif: "" | "1" | "2"
  /** Cidade e endereço lá fora — opcional, só pra consulta. */
  endereco: string
}

export const AVISO_NOTA_EXTERIOR =
  "Nota pra empresa de fora do Brasil sai com a identificação fiscal estrangeira e o país; o ISS é tratado como nas notas que a Receita já autorizou pra vendedores de fora. Na primeira vez, confirme com seu contador."

const OPCOES_PAIS = PAISES.map((p) => ({ id: p.codigo, rotulo: p.nome }))

export function empresaDeForaCompleta(d: DadosEmpresaDeFora): boolean {
  return d.razao_social.trim().length >= 2 && d.pais.length === 2 && (d.nif.trim().length > 0 || d.motivo_sem_nif !== "")
}

/** Identificada pra nota: país + NIF, ou país + o motivo de não ter NIF. */
export function identificadaDeFora(t: { pais?: string | null; nif?: string | null; motivo_sem_nif?: string | null }): boolean {
  return Boolean(t.pais && (t.nif || t.motivo_sem_nif))
}

export const motivoSemNif = (valor: string | null | undefined): "" | "1" | "2" => (valor === "1" || valor === "2" ? valor : "")

/** O corpo que `POST /vinculos/{id}/identificar` espera. */
export function corpoEmpresaDeFora(d: DadosEmpresaDeFora) {
  return {
    tipo: "exterior" as const,
    razao_social: d.razao_social.trim(),
    pais: d.pais,
    nif: d.motivo_sem_nif ? "" : d.nif.trim(),
    motivo_sem_nif: d.motivo_sem_nif || null,
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
  const semNif = valor.motivo_sem_nif !== ""
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
        value={semNif ? "" : valor.nif}
        onChange={(e) => mudar("nif", e.target.value)}
        maxLength={40}
        placeholder={semNif ? "Não tem" : "Ex.: IE1234567X"}
        disabled={semNif}
      />
      <p className="text-xs text-slate-500 sm:col-span-2 dark:text-slate-400">
        <strong>O que é o NIF?</strong> É o número que identifica a empresa no imposto do país dela — como o CNPJ é aqui. Ele vem no
        contrato ou no extrato de pagamento, às vezes escrito como “Tax ID”, “VAT number” ou “Registration number”. Copie igual está lá.
      </p>
      <div className="sm:col-span-2">
        <label className="flex cursor-pointer items-start gap-2 text-sm text-slate-700 dark:text-slate-200">
          <input
            type="checkbox"
            className="mt-0.5 h-4 w-4 rounded border-slate-300 text-primary-600 focus:ring-primary-500"
            checked={semNif}
            onChange={(e) => onChange({ ...valor, motivo_sem_nif: e.target.checked ? "2" : "", nif: e.target.checked ? "" : valor.nif })}
          />
          <span>Esta empresa não tem número fiscal</span>
        </label>
        {semNif && (
          <div className="mt-2 rounded-lg border border-slate-200 p-3 dark:border-slate-700">
            <p className="text-xs text-slate-500 dark:text-slate-400">
              A nota aceita sair sem o número, mas pede o motivo. Qual é o caso desta empresa?
            </p>
            <div className="mt-2 space-y-1.5">
              {(
                [
                  ["2", "O país dela não exige esse número"],
                  ["1", "Ela é dispensada de ter o número"],
                ] as const
              ).map(([codigo, rotulo]) => (
                <label key={codigo} className="flex cursor-pointer items-center gap-2 text-sm text-slate-700 dark:text-slate-200">
                  <input
                    type="radio"
                    name="motivo-sem-nif"
                    className="h-4 w-4 border-slate-300 text-primary-600 focus:ring-primary-500"
                    checked={valor.motivo_sem_nif === codigo}
                    onChange={() => onChange({ ...valor, motivo_sem_nif: codigo, nif: "" })}
                  />
                  {rotulo}
                </label>
              ))}
            </div>
            <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
              Na dúvida entre as duas, pergunte ao seu contador — e só marque se a empresa realmente não tem o número: quando ela
              tem, o certo é informar.
            </p>
          </div>
        )}
      </div>
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
