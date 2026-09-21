import { CheckCircle2, ShieldAlert, UploadCloud } from "lucide-react"
import { type FormEvent, useEffect, useState } from "react"
import { Badge } from "../components/ui/Badge"
import { Button } from "../components/ui/Button"
import { Card } from "../components/ui/Card"
import { Field } from "../components/ui/Field"
import { ApiError, api, formatarErro } from "../lib/api"
import type { CertificadoStatus, Prestador } from "../lib/types"

export function ConfiguracoesPage() {
  const [prestador, setPrestador] = useState<Prestador | null>(null)
  const [certificado, setCertificado] = useState<CertificadoStatus | null>(null)
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState<string | null>(null)

  const [pfx, setPfx] = useState<File | null>(null)
  const [senha, setSenha] = useState("")
  const [enviandoCert, setEnviandoCert] = useState(false)
  const [erroCert, setErroCert] = useState<string | null>(null)

  function carregar() {
    setCarregando(true)
    setErro(null)
    Promise.all([api.get<Prestador>("/prestador"), api.get<CertificadoStatus>("/certificado/status")])
      .then(([p, c]) => {
        setPrestador(p)
        setCertificado(c)
      })
      .catch((err) => setErro(err instanceof ApiError ? formatarErro(err.detail) : "Falha de conexão."))
      .finally(() => setCarregando(false))
  }

  useEffect(carregar, [])

  async function enviarCertificado(e: FormEvent) {
    e.preventDefault()
    if (!pfx) return
    setErroCert(null)
    setEnviandoCert(true)
    try {
      const form = new FormData()
      form.append("pfx", pfx)
      form.append("senha", senha)
      const status = await api.postForm<CertificadoStatus>("/certificado", form)
      setCertificado(status)
      setPfx(null)
      setSenha("")
    } catch (err) {
      setErroCert(err instanceof ApiError ? formatarErro(err.detail) : "Falha de conexão. Tente de novo.")
    } finally {
      setEnviandoCert(false)
    }
  }

  if (carregando) return <p className="text-sm text-slate-400">Carregando...</p>
  if (erro) return <p className="rounded-lg bg-danger-50 px-4 py-3 text-sm text-danger-700">{erro}</p>

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Configurações</h1>
        <p className="text-sm text-slate-500">Certificado digital e dados do prestador.</p>
      </div>

      <Card className="p-5">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">Certificado digital (A1)</h2>
          {certificado?.carregado ? (
            certificado.vencido ? (
              <Badge variant="danger">Vencido</Badge>
            ) : (
              <Badge variant="success">Carregado</Badge>
            )
          ) : (
            <Badge variant="neutral">Nenhum carregado</Badge>
          )}
        </div>

        {certificado?.carregado && (
          <div className="mb-4 flex items-center gap-2 rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-600">
            {certificado.vencido ? <ShieldAlert size={16} className="text-danger-600" /> : <CheckCircle2 size={16} className="text-success-600" />}
            {certificado.validade
              ? `Validade: ${new Date(`${certificado.validade}T00:00:00`).toLocaleDateString("pt-BR")}`
              : "Sem data de validade informada."}
          </div>
        )}

        <form onSubmit={enviarCertificado} className="flex flex-col gap-3">
          {erroCert && <p className="rounded-lg bg-danger-50 px-4 py-3 text-sm text-danger-700">{erroCert}</p>}
          <label className="block">
            <span className="mb-1 block text-sm font-medium text-slate-700">Arquivo .pfx</span>
            <input
              type="file"
              accept=".pfx,application/x-pkcs12"
              required
              onChange={(e) => setPfx(e.target.files?.[0] ?? null)}
              className="text-sm"
            />
          </label>
          <Field label="Senha do certificado" type="password" required value={senha} onChange={(e) => setSenha(e.target.value)} />
          <div>
            <Button type="submit" variant="accent" disabled={enviandoCert || !pfx}>
              <UploadCloud size={15} /> {enviandoCert ? "Enviando..." : certificado?.carregado ? "Substituir certificado" : "Enviar certificado"}
            </Button>
          </div>
        </form>
      </Card>

      {prestador && (
        <Card className="p-5">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">Dados do prestador</h2>
          <dl className="grid grid-cols-1 gap-3 text-sm sm:grid-cols-2">
            <div>
              <dt className="text-xs text-slate-400">Razão social</dt>
              <dd className="text-slate-800">{prestador.razao_social}</dd>
            </div>
            <div>
              <dt className="text-xs text-slate-400">CNPJ/CPF</dt>
              <dd className="text-slate-800">{prestador.cpf_cnpj}</dd>
            </div>
            {prestador.inscricao_municipal && (
              <div>
                <dt className="text-xs text-slate-400">Inscrição municipal</dt>
                <dd className="text-slate-800">{prestador.inscricao_municipal}</dd>
              </div>
            )}
            <div>
              <dt className="text-xs text-slate-400">Município (IBGE)</dt>
              <dd className="text-slate-800">{prestador.cod_municipio}</dd>
            </div>
            {(prestador.logradouro || prestador.cep) && (
              <div className="sm:col-span-2">
                <dt className="text-xs text-slate-400">Endereço</dt>
                <dd className="text-slate-800">
                  {[prestador.logradouro, prestador.numero, prestador.bairro, prestador.cep].filter(Boolean).join(", ") || "—"}
                </dd>
              </div>
            )}
          </dl>
          <p className="mt-4 text-xs text-slate-400">
            Edição desses dados ainda é administrativa (fora do painel) — fala com quem cuida do backend se precisar mudar algo aqui.
          </p>
        </Card>
      )}
    </div>
  )
}
