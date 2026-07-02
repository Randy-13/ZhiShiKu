const API_BASE = "";

export type V2Payload<T> = {
  data?: T;
  meta?: Record<string, unknown>;
};

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
    const response = await fetch(`${API_BASE}${path}`, { ...init, signal });
    if (!response.ok) {
      const text = await response.text().catch(() => "");
      throw new Error(readError(text) || `${response.status} ${response.statusText}`);
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
