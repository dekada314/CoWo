import {
  Download,
  Eye,
  FileText,
  LoaderCircle,
  MoreHorizontal,
  RefreshCw,
  Trash2,
} from "lucide-react";
import { humanizeErrorCode } from "../lib/api";
import type { StoredJob } from "../types";

type Props = {
  jobs: StoredJob[];
  onOpen: (job: StoredJob) => void;
  onRetry: (job: StoredJob) => void;
  onDownload: (job: StoredJob) => void;
  onDelete: (job: StoredJob) => void;
  deletingJobIds: Set<string>;
};

const statusLabels = {
  queued: "В очереди",
  running: "Обрабатывается",
  completed: "Готов",
  failed: "Ошибка",
  cancelled: "Отменён",
};

const stageLabels: Record<string, string> = {
  UPLOADED: "Загружен",
  EXTRACTION: "Извлечение текста",
  CHUNKING: "Разбиение",
  EMBEDDING: "Векторизация",
  INDEXING: "Индексация",
  GRAPH_EXTRACTION: "Анализ концептов",
  GRAPH_INDEXING: "Запись графа",
};

function dateLabel(value: string) {
  return new Intl.DateTimeFormat("ru", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

export function JobsTable({
  jobs,
  onOpen,
  onRetry,
  onDownload,
  onDelete,
  deletingJobIds,
}: Props) {
  return (
    <section className="panel jobs-panel">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Библиотека</p>
          <h2>Последние документы</h2>
        </div>
        <span className="document-count">{jobs.length}</span>
      </div>
      {jobs.length === 0 ? (
        <div className="empty-state">
          <span><FileText size={25} /></span>
          <h3>Здесь появятся документы</h3>
          <p>Добавьте первый файл — агенты разберут его и соберут карточку знаний.</p>
        </div>
      ) : (
        <div className="jobs-list">
          {jobs.map((job) => (
            <article className="job-row" key={job.id}>
              <span className="job-file-icon"><FileText size={20} /></span>
              <div className="job-main">
                <strong title={job.filename}>{job.filename}</strong>
                <div className="job-meta">
                  <span>{dateLabel(job.created_at)}</span>
                  <span>Попытка {job.attempt}</span>
                  {job.stage && <span>{stageLabels[job.stage] ?? job.stage}</span>}
                </div>
                {job.error_message && <small className="job-error">{humanizeErrorCode(job.error_message)}</small>}
              </div>
              <span className={`status status--${job.status}`}>
                <i /> {statusLabels[job.status]}
              </span>
              <div className="job-actions">
                {job.status === "completed" && (
                  <>
                    <button className="icon-button" onClick={() => onOpen(job)} aria-label="Открыть карточку">
                      <Eye size={18} />
                    </button>
                    <button className="icon-button" onClick={() => onDownload(job)} aria-label="Скачать оригинал">
                      <Download size={18} />
                    </button>
                  </>
                )}
                {job.status === "failed" && (
                  <button className="icon-button" onClick={() => onRetry(job)} aria-label="Повторить обработку">
                    <RefreshCw size={18} />
                  </button>
                )}
                {(job.status === "queued" || job.status === "running") && (
                  <span className="processing-icon"><MoreHorizontal size={20} /></span>
                )}
                {job.status !== "running" && (
                  <button
                    className="icon-button icon-button--danger"
                    onClick={() => onDelete(job)}
                    disabled={deletingJobIds.has(job.id)}
                    aria-label="Удалить документ"
                  >
                    {deletingJobIds.has(job.id)
                      ? <LoaderCircle className="spin" size={18} />
                      : <Trash2 size={18} />}
                  </button>
                )}
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
