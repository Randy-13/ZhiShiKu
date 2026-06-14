import { requestJson, unwrapV2 } from "./apiCore";
import type { JobItem } from "./api";
import type { V2Payload } from "./apiCore";

export const jobsApi = {
  async list(limit = 30) {
    return unwrapV2(await requestJson<V2Payload<{ items: JobItem[] }>>(`/api/jobs?limit=${encodeURIComponent(String(limit))}`));
  },

  async create(kind: string, payload: Record<string, unknown> = {}) {
    return unwrapV2(
      await requestJson<V2Payload<{ item: JobItem }>>("/api/jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ kind, payload }),
      }),
    );
  },

  async detail(id: string) {
    return unwrapV2(await requestJson<V2Payload<{ item: JobItem }>>(`/api/jobs/${encodeURIComponent(id)}`));
  },

  async cancel(id: string) {
    return unwrapV2(
      await requestJson<V2Payload<{ item: JobItem }>>(`/api/jobs/${encodeURIComponent(id)}/cancel`, {
        method: "POST",
      }),
    );
  },
};
