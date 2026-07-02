const API_BASE = "";

export type V2Payload<T> = {
  data?: T;
  meta?: Record<string, unknown>;
};

type AuthExpiredListener = () => void;

const authExpiredListeners = new Set<AuthExpiredListener>();

export function onAuthExpired(listener: AuthExpiredListener) {
  authExpiredListeners.add(listener);
  return () => authExpiredListeners.delete(listener);
}

function notifyAuthExpired() {
  authExpiredListeners.forEach((listener) => listener());
}

export async function requestJson<T>(
  path: string,
  init?: RequestInit,
  options?: { timeoutMs?: number; timeoutMessage?: string },
): Promise<T> {
  const timeoutMs = options?.timeoutMs;
  const controller = timeoutMs ? new AbortController() : undefined;
  const timeoutId = controller
    ? window.setTimeout(() => controller.abort(), timeoutMs)
    : undefined;
  const signal = controller?.signal ?? init?.signal;
  try {
    const response = await fetch(`${API_BASE}${path}`, { credentials: "same-origin", ...init, signal });
    if (!response.ok) {
      const text = await response.text().catch(() => "");
      const message = readError(text) || defaultHttpError(response.status, response.statusText);
      if (response.status === 401) {
        notifyAuthExpired();
      }
      throw new Error(message);
    }
    const contentType = response.headers.get("content-type") || "";
    if (!contentType.includes("application/json")) {
      const text = await response.text().catch(() => "");
      throw new Error(text || "API response was not JSON.");
    }
    return response.json() as Promise<T>;
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error(options?.timeoutMessage || "Request timed out. Process fewer items at once, then try again.");
    }
    throw error;
  } finally {
    if (timeoutId) window.clearTimeout(timeoutId);
  }
}

export function unwrapV2<T>(payload: V2Payload<T>): T {
  if (payload.data === undefined) throw new Error("API response missing data");
  return payload.data;
}

function readError(text: string) {
  if (!text) return "";
  try {
    const payload = JSON.parse(text) as { detail?: unknown; message?: unknown };
    const detail = payload.detail ?? payload.message;
    if (typeof detail === "string") return detail;
    if (detail && typeof detail === "object") {
      const record = detail as Record<string, unknown>;
      const message = record.message;
      if (typeof message === "string") return message;
      return JSON.stringify(detail);
    }
    return String(detail ?? text);
  } catch {
    return text;
  }
}
function defaultHttpError(status: number, statusText: string) {
  if (status === 401) return "\u767b\u5f55\u5df2\u5931\u6548\uff0c\u8bf7\u91cd\u65b0\u767b\u5f55\u3002";
  if (status === 403) return "\u5f53\u524d\u8d26\u53f7\u6ca1\u6709\u6743\u9650\u6267\u884c\u8fd9\u4e2a\u64cd\u4f5c\u3002";
  if (status === 404) return "\u8bf7\u6c42\u7684\u8d44\u6e90\u4e0d\u5b58\u5728\uff0c\u6216\u4f60\u6ca1\u6709\u6743\u9650\u67e5\u770b\u3002";
  if (status >= 500) return "\u670d\u52a1\u5668\u5904\u7406\u5931\u8d25\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5\u3002";
  return `${status} ${statusText}`;
}