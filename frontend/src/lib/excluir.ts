import { ApiError, formatarErro } from "./api"

// DELETE com corpo (confirmação digitada) — o `api.delete` não manda body,
// então aqui vai um fetch direto, com o mesmo tratamento de erro do cliente.
export async function excluirComConfirmacao<T = { ok: boolean }>(caminho: string, confirmacao: string): Promise<T> {
  let resp: Response
  try {
    resp = await fetch(`/api${caminho}`, {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ confirmacao }),
    })
  } catch {
    throw new Error("Falha de conexão. Tente de novo.")
  }
  const ehJson = resp.headers.get("content-type")?.includes("application/json")
  const corpo = ehJson ? await resp.json() : await resp.text()
  if (!resp.ok) throw new ApiError(resp.status, ehJson ? corpo.detail : corpo)
  return corpo as T
}

export function mensagemDeErro(err: unknown): string {
  if (err instanceof ApiError) return formatarErro(err.detail)
  if (err instanceof Error) return err.message
  return "Falha de conexão. Tente de novo."
}
