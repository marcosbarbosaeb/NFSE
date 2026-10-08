import { Check, Loader2, MapPin, Pencil, RefreshCw, Search } from "lucide-react"
import { useState } from "react"
import { ApiError, api, formatarErro } from "../../lib/api"
import { documentoDoTomador, formatarDocumento } from "../../lib/documento"
import type { ConsultaCnpj, IdentificarTomadorResposta, Tomador, VinculoDetalhe } from "../../lib/types"
import { Button } from "../ui/Button"
import { CampoCidade } from "../ui/CampoCidade"
import { Card } from "../ui/Card"
import { Field } from "../ui/Field"
import { AvisoNotaExterior, CamposEmpresaDeFora, type DadosEmpresaDeFora, corpoEmpresaDeFora, empresaDeForaCompleta, identificadaDeFora, motivoSemNif } from "./EmpresaDeFora"

/** Dados do tomador (nome e endereço) com edição (05/10/2026: "o CEP deu
 * errado e ao entrar em tomador não aparece pra editar"). O CNPJ não muda.
 * A Ana ajuda de três jeitos: puxa tudo da Receita, preenche a rua pelo CEP
 * e acha o CEP pelo endereço. O CEP é conferido com a cidade antes de
 * gravar — é o erro que mais faz a prefeitura recusar nota.
 *
 * Empresa de fora do Brasil (tem país + NIF no lugar do CNPJ): aqui se edita
 * o nome, o país e o NIF — endereço e CEP do Brasil não se aplicam. */

interface Dados {
  razao_social: string
  cod_municipio: string
  cep: string
  logradouro: string
  numero: string
  complemento: string
  bairro: string
}

interface CepAchado {
  cep: string
  logradouro: string
  bairro: string
  cidade: string
  uf: string
  cod_municipio?: string | null
}

const deTomador = (t: Tomador): Dados => ({
  razao_social: t.razao_social,
  cod_municipio: t.cod_municipio,
  cep: t.cep ?? "",
  logradouro: t.logradouro ?? "",
  numero: t.numero ?? "",
  complemento: t.complemento ?? "",
  bairro: t.bairro ?? "",
})

const foraDeTomador = (t: Tomador): DadosEmpresaDeFora => ({
  razao_social: t.razao_social,
  pais: t.pais ?? "",
  nif: t.nif ?? "",
  motivo_sem_nif: motivoSemNif(t.motivo_sem_nif),
  endereco: t.logradouro ?? "",
})

const mascaraCep = (v: string) => {
  const d = v.replace(/\D/g, "").slice(0, 8)
  return d.length > 5 ? `${d.slice(0, 5)}-${d.slice(5)}` : d
}

const msg = (err: unknown) => (err instanceof ApiError ? formatarErro(err.detail) : "Falha de conexão. Tente de novo.")

export function DadosTomador({
  vinculoId,
  tomador,
  abrirEditando = false,
  onSalvo,
  onTrocarParaCnpj,
}: {
  vinculoId: string
  tomador: Tomador
  abrirEditando?: boolean
  onSalvo: (tomador: Tomador) => void
  /** Empresa de fora cadastrada por engano: abre o passo "Quem é" pra informar o CNPJ. */
  onTrocarParaCnpj?: () => void
}) {
  const [editando, setEditando] = useState(abrirEditando)
  const [d, setD] = useState<Dados>(() => deTomador(tomador))
  const [ocupado, setOcupado] = useState<"" | "receita" | "cep" | "busca" | "salvar">("")
  const [erro, setErro] = useState<string | null>(null)
  const [nota, setNota] = useState<string | null>(null)
  const [candidatos, setCandidatos] = useState<CepAchado[] | null>(null)
  const temCnpj = /^\d{14}$/.test(tomador.cnpj)
  // De fora do Brasil: país e/ou NIF no lugar do CNPJ.
  const deFora = !temCnpj && Boolean(tomador.pais || tomador.nif)
  const [fora, setFora] = useState<DadosEmpresaDeFora>(() => foraDeTomador(tomador))
  const mudar = (campo: keyof Dados, valor: string) => setD((a) => ({ ...a, [campo]: valor }))

  async function puxarDaReceita() {
    setOcupado("receita")
    setErro(null)
    setNota(null)
    try {
      const r = await api.get<ConsultaCnpj>(`/cnpj/${tomador.cnpj}`)
      setD((a) => ({
        razao_social: r.razao_social || a.razao_social,
        cod_municipio: r.cod_municipio_sugerido || a.cod_municipio,
        cep: mascaraCep(r.cep ?? a.cep),
        logradouro: r.logradouro ?? a.logradouro,
        numero: r.numero ?? a.numero,
        complemento: r.complemento ?? a.complemento,
        bairro: r.bairro ?? a.bairro,
      }))
      setNota(`Preenchi com o que está na Receita (${r.municipio}/${r.uf}). Confira e salve.`)
    } catch (err) {
      setErro(err instanceof ApiError && err.status === 404 ? "Não achei esse CNPJ na Receita." : "Não deu pra consultar a Receita agora. Preencha à mão.")
    } finally {
      setOcupado("")
    }
  }

  /** CEP completo digitado: preenche rua, bairro e cidade. */
  async function preencherPeloCep(cep: string) {
    const digitos = cep.replace(/\D/g, "")
    if (digitos.length !== 8) return
    setOcupado("cep")
    setErro(null)
    setNota(null)
    try {
      const r = await api.get<CepAchado>(`/cep/${digitos}`)
      setD((a) => ({
        ...a,
        logradouro: r.logradouro || a.logradouro,
        bairro: r.bairro || a.bairro,
        cod_municipio: r.cod_municipio || a.cod_municipio,
      }))
      setNota(`CEP de ${r.cidade}/${r.uf}${r.logradouro ? ` — ${r.logradouro}` : ""}.`)
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) setErro("Esse CEP não existe. Confira os números ou use “Achar o CEP pelo endereço”.")
    } finally {
      setOcupado("")
    }
  }

  async function acharCep() {
    setOcupado("busca")
    setErro(null)
    setNota(null)
    setCandidatos(null)
    try {
      const r = await api.post<{ candidatos: CepAchado[] }>("/cep/buscar", { ...d, cep: d.cep.replace(/\D/g, "") || null })
      if (r.candidatos.length === 0) setErro("Não achei essa rua nessa cidade. Confira o nome da rua (sem o número) e a cidade.")
      else setCandidatos(r.candidatos)
    } catch (err) {
      setErro(msg(err))
    } finally {
      setOcupado("")
    }
  }

  async function salvar() {
    setOcupado("salvar")
    setErro(null)
    setNota(null)
    try {
      const v = await api.patch<VinculoDetalhe>(`/vinculos/${vinculoId}/tomador`, {
        razao_social: d.razao_social,
        cod_municipio: d.cod_municipio,
        cep: d.cep.replace(/\D/g, "") || null,
        logradouro: d.logradouro || null,
        numero: d.numero || null,
        complemento: d.complemento || null,
        bairro: d.bairro || null,
      })
      onSalvo(v.tomador)
      setD(deTomador(v.tomador))
      setEditando(false)
      setCandidatos(null)
    } catch (err) {
      setErro(msg(err))
    } finally {
      setOcupado("")
    }
  }

  async function salvarDeFora() {
    setOcupado("salvar")
    setErro(null)
    try {
      const r = await api.post<IdentificarTomadorResposta>(`/vinculos/${vinculoId}/identificar`, corpoEmpresaDeFora(fora))
      onSalvo(r.vinculo.tomador)
      setFora(foraDeTomador(r.vinculo.tomador))
      setEditando(false)
    } catch (err) {
      setErro(msg(err))
    } finally {
      setOcupado("")
    }
  }

  const endereco = [tomador.logradouro && `${tomador.logradouro}${tomador.numero ? `, ${tomador.numero}` : ""}`, tomador.bairro, tomador.cep && `CEP ${mascaraCep(tomador.cep)}`]
    .filter(Boolean)
    .join(" · ")

  return (
    <Card className="p-5" id="dados-do-tomador">
      <div className="mb-2 flex items-start justify-between gap-3">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">Dados do tomador</h2>
        {!editando && (
          <button
            type="button"
            onClick={() => {
              setD(deTomador(tomador))
              setFora(foraDeTomador(tomador))
              setEditando(true)
            }}
            className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-semibold text-primary-600 hover:bg-primary-50 dark:text-primary-300 dark:hover:bg-primary-900/30"
          >
            <Pencil size={13} /> {deFora ? "Editar nome, país e NIF" : "Editar nome e endereço"}
          </button>
        )}
      </div>

      {!editando ? (
        <>
          <p className="font-medium text-slate-800 dark:text-slate-200">{tomador.razao_social}</p>
          {deFora ? (
            <>
              <p className="text-sm text-slate-500 dark:text-slate-400">
                Empresa de fora do Brasil{documentoDoTomador(tomador) && ` · ${documentoDoTomador(tomador)}`}
              </p>
              {!identificadaDeFora(tomador) && (
                <p className="mt-1 text-sm font-medium text-warning-700 dark:text-warning-300">
                  Falta {!tomador.pais ? "o país" : "o NIF (número fiscal no país dela)"} — sem isso eu não consigo gerar a nota. Clique em “Editar”.
                </p>
              )}
              <p className="mt-1 flex items-start gap-1 text-sm text-slate-500 dark:text-slate-400">
                <MapPin size={14} className="mt-0.5 shrink-0" />
                {tomador.logradouro ? `${tomador.logradouro} (na nota vai só o país)` : "Na nota vai só o país — empresa de fora não tem endereço do Brasil."}
              </p>
            </>
          ) : (
            <>
              <p className="text-sm text-slate-500 dark:text-slate-400">{temCnpj ? formatarDocumento(tomador.cnpj) : "Sem CNPJ (só controle)"}</p>
              <p className="mt-1 flex items-start gap-1 text-sm text-slate-500 dark:text-slate-400">
                <MapPin size={14} className="mt-0.5 shrink-0" />
                {endereco || "Sem endereço cadastrado — a nota sai sem o endereço do tomador."}
              </p>
            </>
          )}
        </>
      ) : deFora ? (
        <div
          className="flex flex-col gap-3"
          // Dentro do formulário do tomador: Enter aqui não pode salvar o de fora.
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.target as HTMLElement).tagName === "INPUT" && !e.defaultPrevented) e.preventDefault()
          }}
        >
          <p className="text-xs text-slate-500 dark:text-slate-400">
            O que você salvar aqui vale pras próximas notas — as que já foram geradas não mudam.
          </p>
          <CamposEmpresaDeFora valor={fora} onChange={setFora} />
          <AvisoNotaExterior />
          {erro && <p className="rounded-lg bg-danger-50 px-3 py-2 text-sm text-danger-700 dark:bg-danger-900/30 dark:text-danger-300">{erro}</p>}
          <div className="flex flex-wrap items-center justify-between gap-2">
            {onTrocarParaCnpj ? (
              <button type="button" onClick={onTrocarParaCnpj} className="text-xs font-medium text-primary-600 hover:underline dark:text-primary-300">
                Na verdade é uma empresa do Brasil? Informar o CNPJ
              </button>
            ) : (
              <span />
            )}
            <div className="flex gap-2">
              <Button
                type="button"
                variant="ghost"
                disabled={ocupado === "salvar"}
                onClick={() => {
                  setEditando(false)
                  setErro(null)
                }}
              >
                Cancelar
              </Button>
              <Button type="button" variant="accent" disabled={ocupado !== "" || !empresaDeForaCompleta(fora)} onClick={salvarDeFora}>
                {ocupado === "salvar" ? "Salvando..." : "Salvar dados do tomador"}
              </Button>
            </div>
          </div>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          <p className="text-xs text-slate-500 dark:text-slate-400">
            {temCnpj ? `CNPJ ${formatarDocumento(tomador.cnpj)} (não muda). ` : ""}
            O que você salvar aqui vale pras próximas notas — e pra nota recusada, se você clicar em “Corrigir e reenviar” nela.
          </p>
          <div className="flex flex-wrap gap-2">
            {temCnpj && (
              <Button type="button" variant="outline" className="px-3 py-1.5" disabled={ocupado !== ""} onClick={puxarDaReceita}>
                {ocupado === "receita" ? <Loader2 size={15} className="animate-spin" /> : <RefreshCw size={15} />} Puxar os dados da Receita
              </Button>
            )}
            <Button type="button" variant="outline" className="px-3 py-1.5" disabled={ocupado !== "" || !d.logradouro.trim() || !d.cod_municipio} onClick={acharCep}>
              {ocupado === "busca" ? <Loader2 size={15} className="animate-spin" /> : <Search size={15} />} Achar o CEP pelo endereço
            </Button>
          </div>

          {erro && <p className="rounded-lg bg-danger-50 px-3 py-2 text-sm text-danger-700 dark:bg-danger-900/30 dark:text-danger-300">{erro}</p>}
          {nota && (
            <p className="flex items-center gap-1.5 rounded-lg bg-success-50 px-3 py-2 text-sm text-success-700 dark:bg-success-900/30 dark:text-success-300">
              <Check size={14} /> {nota}
            </p>
          )}
          {candidatos && (
            <div className="rounded-lg border border-primary-100 bg-primary-50/60 p-3 dark:border-primary-900/40 dark:bg-primary-900/20">
              <p className="mb-2 text-xs font-semibold text-slate-600 dark:text-slate-300">Achei estes CEPs — clique no certo:</p>
              <ul className="flex max-h-48 flex-col gap-1 overflow-y-auto">
                {candidatos.map((c) => (
                  <li key={`${c.cep}-${c.logradouro}-${c.bairro}`}>
                    <button
                      type="button"
                      onClick={() => {
                        setD((a) => ({ ...a, cep: mascaraCep(c.cep), bairro: a.bairro || c.bairro }))
                        setCandidatos(null)
                        setNota(`CEP ${mascaraCep(c.cep)} escolhido. Confira e salve.`)
                      }}
                      className="w-full rounded-md bg-white px-3 py-1.5 text-left text-sm text-slate-700 hover:bg-primary-100 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700"
                    >
                      <strong>{mascaraCep(c.cep)}</strong> — {c.logradouro}
                      {c.bairro && `, ${c.bairro}`}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="sm:col-span-2">
              <Field label="Nome (razão social)" required value={d.razao_social} onChange={(e) => mudar("razao_social", e.target.value)} maxLength={200} />
            </div>
            <Field
              label="CEP"
              inputMode="numeric"
              value={d.cep}
              onChange={(e) => {
                const v = mascaraCep(e.target.value)
                mudar("cep", v)
                if (v.replace(/\D/g, "").length === 8) preencherPeloCep(v)
              }}
              placeholder="00000-000"
              hint={ocupado === "cep" ? "Buscando o endereço..." : "Digite o CEP que eu preencho a rua, o bairro e a cidade."}
            />
            <CampoCidade label="Cidade" required codigo={d.cod_municipio} onChange={(codigo) => mudar("cod_municipio", codigo)} />
            <Field label="Rua / avenida" value={d.logradouro} onChange={(e) => mudar("logradouro", e.target.value)} maxLength={200} />
            <Field label="Número" value={d.numero} onChange={(e) => mudar("numero", e.target.value)} maxLength={20} hint="Sem número? Escreva S/N." />
            <Field label="Complemento" value={d.complemento} onChange={(e) => mudar("complemento", e.target.value)} maxLength={100} />
            <Field label="Bairro" value={d.bairro} onChange={(e) => mudar("bairro", e.target.value)} maxLength={100} />
          </div>
          <div className="flex justify-end gap-2">
            <Button
              type="button"
              variant="ghost"
              disabled={ocupado === "salvar"}
              onClick={() => {
                setEditando(false)
                setErro(null)
                setNota(null)
                setCandidatos(null)
              }}
            >
              Cancelar
            </Button>
            <Button type="button" variant="accent" disabled={ocupado !== "" || d.razao_social.trim().length < 2 || !d.cod_municipio} onClick={salvar}>
              {ocupado === "salvar" ? "Salvando..." : "Salvar dados do tomador"}
            </Button>
          </div>
        </div>
      )}
    </Card>
  )
}
