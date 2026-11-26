import { useEffect, useMemo, useState } from "react";
import {
  BookOpen,
  CheckCircle2,
  Clock3,
  FileStack,
  LibraryBig,
  LogOut,
  MessageSquareText,
  Network,
  Server,
  X,
} from "lucide-react";
import { AskPanel } from "./components/AskPanel";
import { AuthScreen } from "./components/AuthScreen";
import { CardModal } from "./components/CardModal";
import { GraphExplorer } from "./components/GraphExplorer";
import { JobsTable } from "./components/JobsTable";
import { UploadZone } from "./components/UploadZone";
import { api, humanizeError, refreshAccessToken } from "./lib/api";
import type { KnowledgeCard, StoredJob, User } from "./types";

type View = "library" | "graph" | "ask";

type OpenCard = {
  card: KnowledgeCard;
  job: StoredJob;
};

export default function App() {
  const [user, setUser] = useState<User | null>(null);
  const [initializing, setInitializing] = useState(true);
  const [view, setView] = useState<View>("library");
  const [jobs, setJobs] = useState<StoredJob[]>([]);
  const [uploading, setUploading] = useState(false);
  const [deletingJobIds, setDeletingJobIds] = useState<Set<string>>(new Set());
  const [openCard, setOpenCard] = useState<OpenCard | null>(null);
  const [notice, setNotice] = useState<{ kind: "success" | "error"; text: string } | null>(null);

  async function loadUser() {
    const currentUser = await api.me();
    setUser(currentUser);
  }

  useEffect(() => {
    async function bootstrap() {
      try {
        await refreshAccessToken();
        await loadUser();
      } catch {
        setUser(null);
      } finally {
        setInitializing(false);
      }
    }
    void bootstrap();
  }, []);

  useEffect(() => {
    let cancelled = false;
    if (!user) {
      setJobs([]);
      return () => { cancelled = true; };
    }
    void api.listDocuments()
      .then((documents) => {
        if (!cancelled) setJobs(documents);
      })
      .catch((error) => {
        if (!cancelled) {
          setJobs([]);
          setNotice({ kind: "error", text: humanizeError(error) });
        }
      });
    return () => { cancelled = true; };
  }, [user]);

  const activeJobIds = useMemo(
    () => jobs.filter((job) => job.status === "queued" || job.status === "running").map((job) => job.id).join(","),
    [jobs],
  );

  useEffect(() => {
    if (!activeJobIds) return;
    const ids = activeJobIds.split(",");
    const timer = window.setInterval(async () => {
      const updates = await Promise.allSettled(ids.map((id) => api.getJob(id)));
      setJobs((current) => current.map((job) => {
        const index = ids.indexOf(job.id);
        const update = updates[index];
        return update?.status === "fulfilled" ? { ...job, ...update.value } : job;
      }));
    }, 3500);
    return () => window.clearInterval(timer);
  }, [activeJobIds]);

  useEffect(() => {
    if (!notice) return;
    const timer = window.setTimeout(() => setNotice(null), 4500);
    return () => window.clearTimeout(timer);
  }, [notice]);

  async function upload(files: File[]) {
    setUploading(true);
    try {
      const response = await api.upload(files);
      const created = Array.isArray(response) ? response : [response];
      const now = new Date().toISOString();
      setJobs((current) => [
        ...created.map((job, index) => ({
          ...job,
          filename: files[index]?.name ?? "Документ",
          created_at: now,
        })),
        ...current,
      ]);
      try {
        setJobs(await api.listDocuments());
      } catch {
        // Keep the optimistic entries; polling will still update their status.
      }
      setNotice({ kind: "success", text: created.length === 1 ? "Документ принят в обработку" : `${created.length} документов приняты в обработку` });
    } catch (error) {
      setNotice({ kind: "error", text: humanizeError(error) });
      throw error;
    } finally {
      setUploading(false);
    }
  }

  async function openKnowledgeCard(job: StoredJob) {
    try {
      setOpenCard({ card: await api.getCard(job.id), job });
    } catch (error) {
      setNotice({ kind: "error", text: humanizeError(error) });
    }
  }

  function openGraphCard(card: KnowledgeCard) {
    setOpenCard({
      card,
      job: {
        id: card.job_id,
        document_version_id: card.document_version_id,
        filename: card.filename,
        created_at: "",
        status: "completed",
        stage: null,
        attempt: 1,
        pipeline_version: "graph",
        error_message: null,
        started_at: null,
        finished_at: null,
      },
    });
  }

  async function retry(job: StoredJob) {
    try {
      const updated = await api.retryJob(job.id);
      setJobs((current) => current.map((item) => item.id === job.id ? { ...item, ...updated } : item));
      setNotice({ kind: "success", text: "Повторная обработка запланирована" });
    } catch (error) {
      setNotice({ kind: "error", text: humanizeError(error) });
    }
  }

  async function download(job: StoredJob) {
    try {
      await api.download(`/api/v1/ingestion/jobs/${job.id}/original`, job.filename);
    } catch (error) {
      setNotice({ kind: "error", text: humanizeError(error) });
    }
  }

  async function deleteDocument(job: StoredJob) {
    if (!window.confirm(`Удалить «${job.filename}» из базы знаний?`)) return;
    setDeletingJobIds((current) => new Set(current).add(job.id));
    try {
      await api.deleteDocument(job.id);
      setJobs((current) => current.filter((item) => item.id !== job.id));
      setOpenCard((current) => current?.job.id === job.id ? null : current);
      setNotice({ kind: "success", text: "Документ удалён из базы знаний" });
    } catch (error) {
      setNotice({ kind: "error", text: humanizeError(error) });
    } finally {
      setDeletingJobIds((current) => {
        const next = new Set(current);
        next.delete(job.id);
        return next;
      });
    }
  }

  async function logout() {
    try {
      await api.logout();
    } finally {
      setUser(null);
      setView("library");
    }
  }

  const completed = jobs.filter((job) => job.status === "completed").length;
  const processing = jobs.filter((job) => job.status === "queued" || job.status === "running").length;

  if (initializing) {
    return (
      <div className="app-loading">
        <span className="brand-mark"><Network size={23} /></span>
        <strong>CoWo</strong>
        <i />
      </div>
    );
  }

  if (!user) {
    return <AuthScreen onAuthenticated={loadUser} />;
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark"><Network size={21} /></span>
          <span>CoWo</span>
        </div>
        <nav aria-label="Основная навигация">
          <button className={view === "library" ? "is-active" : ""} onClick={() => setView("library")}>
            <LibraryBig size={19} /> Библиотека
          </button>
          <button className={view === "graph" ? "is-active" : ""} onClick={() => setView("graph")}>
            <Network size={19} /> Граф знаний
          </button>
          <button className={view === "ask" ? "is-active" : ""} onClick={() => setView("ask")}>
            <MessageSquareText size={19} /> Спросить базу
          </button>
        </nav>
        <div className="system-card">
          <span><Server size={17} /></span>
          <div><strong>Локальный контур</strong><small>Данные остаются внутри</small></div>
        </div>
        <div className="sidebar-user">
          <span className="avatar">{user.email[0].toUpperCase()}</span>
          <div><strong>{user.email.split("@")[0]}</strong><small>{user.email}</small></div>
          <button className="icon-button" onClick={logout} aria-label="Выйти"><LogOut size={18} /></button>
        </div>
      </aside>

      <main className="workspace">
        <header className="mobile-header">
          <div className="brand"><span className="brand-mark"><Network size={19} /></span><span>CoWo</span></div>
          <button className="icon-button" onClick={logout} aria-label="Выйти"><LogOut size={18} /></button>
        </header>

        {view === "library" ? (
          <div className="library-view">
            <header className="page-heading">
              <div>
                <p className="eyebrow">Добрый день</p>
                <h1>Ваша база знаний</h1>
                <p>Загружайте материалы — остальное возьмут на себя агенты.</p>
              </div>
              <button className="button button--dark" onClick={() => setView("ask")}>
                <MessageSquareText size={18} /> Задать вопрос
              </button>
            </header>

            <section className="stats" aria-label="Статистика библиотеки">
              <div><span className="stat-icon"><FileStack size={20} /></span><div><strong>{jobs.length}</strong><small>Всего документов</small></div></div>
              <div><span className="stat-icon"><CheckCircle2 size={20} /></span><div><strong>{completed}</strong><small>Готово к поиску</small></div></div>
              <div><span className="stat-icon"><Clock3 size={20} /></span><div><strong>{processing}</strong><small>В обработке</small></div></div>
              <div><span className="stat-icon"><BookOpen size={20} /></span><div><strong>{completed ? "Online" : "—"}</strong><small>Knowledge graph</small></div></div>
            </section>

            <div className="library-grid">
              <UploadZone loading={uploading} onUpload={upload} />
              <JobsTable
                jobs={jobs}
                onOpen={openKnowledgeCard}
                onRetry={retry}
                onDownload={download}
                onDelete={deleteDocument}
                deletingJobIds={deletingJobIds}
              />
            </div>
          </div>
        ) : view === "graph" ? <GraphExplorer onOpenCard={openGraphCard} /> : <AskPanel />}

        <nav className="mobile-nav" aria-label="Мобильная навигация">
          <button className={view === "library" ? "is-active" : ""} onClick={() => setView("library")}><LibraryBig size={19} /><span>Библиотека</span></button>
          <button className={view === "graph" ? "is-active" : ""} onClick={() => setView("graph")}><Network size={19} /><span>Граф</span></button>
          <button className={view === "ask" ? "is-active" : ""} onClick={() => setView("ask")}><MessageSquareText size={19} /><span>Спросить</span></button>
        </nav>
      </main>

      {openCard && (
        <CardModal
          card={openCard.card}
          filename={openCard.job.filename}
          onClose={() => setOpenCard(null)}
          onDownload={() => download(openCard.job)}
        />
      )}

      {notice && (
        <div className={`toast toast--${notice.kind}`} role="status">
          {notice.kind === "success" ? <CheckCircle2 size={19} /> : <X size={19} />}
          <span>{notice.text}</span>
          <button onClick={() => setNotice(null)} aria-label="Закрыть"><X size={16} /></button>
        </div>
      )}
    </div>
  );
}
