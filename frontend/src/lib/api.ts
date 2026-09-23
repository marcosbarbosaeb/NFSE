// Cliente HTTP fino pra API do FastAPI. Em dev, o Vite faz proxy de /api
// pro backend (ver vite.config.ts) — então isto sempre fala com a MESMA
// origem que serve o frontend, e o cookie de sessão (SessionMiddleware,
// same_site="lax") viaja normalmente sem precisar de CORS.

export class ApiError extends Error {
  status: number
  detail: unknown

  constructor(status: number, detail: unknown) {
    super(typeof detail === "string" ? detail : "Erro na requisição")
    this.status = status
    this.detail = detail
  }
}

// FastAPI devolve `detail` como string nos erros explícitos (HTTPException)
// mas como uma LISTA de objetos {loc, msg} quando é validação automática do
// Pydantic (422) — mesma distinção que o painel antigo já tratava em
// `formatarErro` (app/main.py), só que aqui centralizada.
export function formatarErro(detail: unknown): string {
  if (typeof detail === "string") return detail
  if (Array.isArray(detail)) {
    return detail
      .map((e) => {
        const campo = Array.isArray(e?.loc) ? e.loc[e.loc.length - 1] : "campo"
        return `${campo}: ${e?.msg ?? "inválido"}`
      })
      .join("; ")
  }
  return "Erro inesperado."
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`/api${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  })
  const isJson = resp.headers.get("content-type")?.includes("application/json")
  const body = isJson ? await resp.json() : await resp.text()
  if (!resp.ok) {
    throw new ApiError(resp.status, isJson ? body.detail : body)
  }
  return body as T
}

// Upload multipart (certificado, importação de CSV) — sem Content-Type
// manual: o browser define o boundary sozinho a partir do FormData.
async function postForm<T>(path: string, form: FormData): Promise<T> {
  const resp = await fetch(`/api${path}`, { method: "POST", body: form })
  const isJson = resp.headers.get("content-type")?.includes("application/json")
  const body = isJson ? await resp.json() : await resp.text()
  if (!resp.ok) {
    throw new ApiError(resp.status, isJson ? body.detail : body)
  }
  return body as T
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, data?: unknown) =>
    request<T>(path, { method: "POST", body: data !== undefined ? JSON.stringify(data) : undefined }),
  put: <T>(path: string, data?: unknown) =>
    request<T>(path, { method: "PUT", body: data !== undefined ? JSON.stringify(data) : undefined }),
  patch: <T>(path: string, data?: unknown) =>
    request<T>(path, { method: "PATCH", body: data !== undefined ? JSON.stringify(data) : undefined }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
  postForm,
}
