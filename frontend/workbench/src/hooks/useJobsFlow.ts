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
      setJobsError(error instanceof Error ? error.message : "\u4efb\u52a1\u4e2d\u5fc3\u52a0\u8f7d\u5931\u8d25");
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
      setJobsError(error instanceof Error ? error.message : "\u4efb\u52a1\u53d6\u6d88\u5931\u8d25");
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

  useEffect(() => {
    const hasActiveJob = jobs.some((job) => job.status === "queued" || job.status === "running");
    if (!hasActiveJob) return;
    const timer = window.setInterval(() => {
      refreshJobs();
    }, 3000);
    return () => window.clearInterval(timer);
  }, [jobs, refreshJobs]);

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