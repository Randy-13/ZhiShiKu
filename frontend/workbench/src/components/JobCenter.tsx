import { RefreshCw, X } from "lucide-react";
import type { JobItem } from "../api";

type JobCenterProps = {
  jobs: JobItem[];
  isOpen: boolean;
  isLoading: boolean;
  error: string;
  onClose: () => void;
  onRefresh: () => void;
  onCancel: (id: string) => void;
};

const statusLabels: Record<string, string> = {
  queued: "排队中",
  running: "处理中",
  success: "成功",
  failed: "失败",
  cancelled: "已取消",
};

const kindLabels: Record<string, string> = {
  readable_draft: "生成可读原文",
  learn_refine: "提炼重点",
  mine_interpret: "视角解读",
  writer_topics: "生成创作选题",
  writer_article: "生成文章初稿",
  writer_revise: "修订文章",
  media_transcript: "音视频转写",
  media_parse: "媒体解析",
  llm_generate: "LLM 生成",
  image_generate: "生成配图",
  writer_image_item: "生成单张配图",
  publish_preflight: "发布预检",
};

export function JobCenter({ jobs, isOpen, isLoading, error, onClose, onRefresh, onCancel }: JobCenterProps) {
  if (!isOpen) return null;
  return (
    <div className="modal-backdrop job-center-backdrop" role="presentation">
      <section className="modal-panel job-center-panel" role="dialog" aria-modal="true" aria-labelledby="job-center-title">
        <div className="modal-title-row">
          <div>
            <span>任务中心</span>
            <h2 id="job-center-title">后台任务</h2>
          </div>
          <button className="icon-button" type="button" onClick={onClose} aria-label="关闭任务中心">
            <X size={18} />
          </button>
        </div>
        <div className="job-center-toolbar">
          <span>{jobs.length ? `${jobs.length} 个最近任务` : "暂无任务"}</span>
          <button className="secondary-button" type="button" onClick={onRefresh} disabled={isLoading}>
            <RefreshCw size={16} />
            <span>{isLoading ? "刷新中" : "刷新"}</span>
          </button>
        </div>
        {error ? <p className="auth-error">{error}</p> : null}
        <div className="job-list">
          {jobs.length === 0 ? (
            <div className="empty-panel">
              <strong>还没有后台任务</strong>
              <p>后续媒体解析、原文生成、图片生成等长任务会在这里排队和追踪。</p>
            </div>
          ) : (
            jobs.map((job) => (
              <article className="job-row" key={job.id}>
                <div className={`job-status job-status--${job.status}`}>{statusLabels[job.status] ?? job.status}</div>
                <div className="job-main">
                  <strong>{kindLabels[job.kind] ?? job.kind}</strong>
                  <span>{job.errorMessage || job.events?.at(-1)?.message || "任务已记录"}</span>
                  <small>{job.createdAt}</small>
                </div>
                {job.status === "queued" || job.status === "running" ? (
                  <button className="secondary-button" type="button" onClick={() => onCancel(job.id)}>
                    取消
                  </button>
                ) : null}
              </article>
            ))
          )}
        </div>
      </section>
    </div>
  );
}
