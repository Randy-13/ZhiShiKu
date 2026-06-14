import { requestJson, unwrapV2 } from "./apiCore";
import type { QuotaStatus } from "./api";
import type { V2Payload } from "./apiCore";

export const quotaApi = {
  async me(): Promise<QuotaStatus> {
    return unwrapV2(await requestJson<V2Payload<QuotaStatus>>("/api/v2/quotas/me"));
  },
};
