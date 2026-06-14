import { useCallback, useEffect, useMemo, useState } from "react";
import { jobsApi } from "../apiJobs";
import type { JobItem } from "../api";

export function useJobsFlow() {
  const [jobs, setJobs] = useState<JobItem[]>([]);
  const [isJobCenterOpen, setIsJobCenterOpen] = useState(false);
  const [isJobsLoading, setIsJobsLoading] = useState(false);
  const [jobsError, setJobsError] = useState("");

  const refreshJobs = useCallback(async () => {
    setIsJobsLoading(true);
    setJobsError("");
    try {
      const payload = await jobsApi.list();
      setJobs(payload.items ?? []);
    } catch (error) {
      setJobsError(error instanceof Error ? error.message : "任务中心加载失败");
    } finally {
      setIsJobsLoading(false);
    }
  }, []);

  const cancelJob = useCallback(async (id: string) => {
    setJobsError("");
    try {
      const payload = await jobsApi.cancel(id);
      setJobs((current) => current.map((item) => (item.id === id ? payload.item : item)));
    } catch (error) {
      setJobsError(error instanceof Error ? error.message : "任务取消失败");
    }
  }, []);

  const openJobCenter = useCallback(() => {
    setIsJobCenterOpen(true);
    refreshJobs();
  }, [refreshJobs]);

  const closeJobCenter = useCallback(() => {
    setIsJobCenterOpen(false);
  }, []);

  useEffect(() => {
    refreshJobs();
  }, [refreshJobs]);

  const activeJobCount = useMemo(
    () => jobs.filter((job) => job.status === "queued" || job.status === "running").length,
    [jobs],
  );

  return {
    jobs,
    activeJobCount,
    isJobCenterOpen,
    isJobsLoading,
    jobsError,
    refreshJobs,
    cancelJob,
    openJobCenter,
    closeJobCenter,
  };
}
