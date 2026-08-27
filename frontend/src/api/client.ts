export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

export async function api<T>(url: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(url, options);
  if (!response.ok) {
    const payload = await response.json().catch(() => ({})) as {
      detail?: string | Array<{ msg?: string }>;
    };
    const message = Array.isArray(payload.detail)
      ? payload.detail.map((item) => item.msg).filter(Boolean).join("；")
      : payload.detail;
    throw new ApiError(message || `请求失败（${response.status}）`, response.status);
  }
  return response.json() as Promise<T>;
}

export function jsonRequest(method: "POST" | "PUT" | "PATCH", body: unknown): RequestInit {
  return {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
}

export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "发生未知错误";
}
