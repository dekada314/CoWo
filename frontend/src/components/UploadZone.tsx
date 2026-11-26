import { ChangeEvent, DragEvent, useRef, useState } from "react";
import { FileText, LoaderCircle, Plus, UploadCloud, X } from "lucide-react";

type Props = {
  loading: boolean;
  onUpload: (files: File[]) => Promise<void>;
};

function fileSize(size: number) {
  if (size < 1024 * 1024) return `${Math.max(1, Math.round(size / 1024))} КБ`;
  return `${(size / 1024 / 1024).toFixed(1)} МБ`;
}

export function UploadZone({ loading, onUpload }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState("");

  function select(nextFiles: File[]) {
    setError("");
    const allowed = nextFiles.filter((file) =>
      ["pdf", "docx", "md", "txt"].includes(file.name.split(".").pop()?.toLowerCase() ?? ""),
    );
    if (allowed.length !== nextFiles.length) {
      setError("Некоторые файлы пропущены: поддерживаются PDF, DOCX, MD и TXT");
    }
    if (allowed.length > 10) {
      setError("За один раз можно загрузить не больше 10 документов");
    }
    setFiles(allowed.slice(0, 10));
  }

  function onChange(event: ChangeEvent<HTMLInputElement>) {
    select(Array.from(event.target.files ?? []));
  }

  function onDrop(event: DragEvent) {
    event.preventDefault();
    setDragging(false);
    select(Array.from(event.dataTransfer.files));
  }

  async function submit() {
    if (!files.length) return;
    try {
      await onUpload(files);
      setFiles([]);
      if (inputRef.current) inputRef.current.value = "";
    } catch {
      return;
    }
  }

  return (
    <section className="panel upload-panel">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Новые материалы</p>
          <h2>Добавить документы</h2>
        </div>
        <span className="limit-pill">до 10 файлов</span>
      </div>
      <div
        className={`drop-zone ${dragging ? "is-dragging" : ""}`}
        onDragEnter={(event) => { event.preventDefault(); setDragging(true); }}
        onDragOver={(event) => event.preventDefault()}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
      >
        <input
          ref={inputRef}
          type="file"
          multiple
          accept=".pdf,.docx,.md,.txt"
          onChange={onChange}
        />
        <span className="drop-icon"><UploadCloud size={25} /></span>
        <div>
          <strong>Перетащите файлы сюда</strong>
          <p>PDF, DOCX, Markdown или TXT</p>
        </div>
        <button className="button button--secondary" onClick={() => inputRef.current?.click()}>
          <Plus size={17} /> Выбрать
        </button>
      </div>
      {files.length > 0 && (
        <div className="selected-files">
          {files.map((file, index) => (
            <div className="selected-file" key={`${file.name}-${file.lastModified}`}>
              <span className="file-icon"><FileText size={18} /></span>
              <div><strong>{file.name}</strong><small>{fileSize(file.size)}</small></div>
              <button
                className="icon-button"
                aria-label={`Убрать ${file.name}`}
                onClick={() => setFiles((current) => current.filter((_, item) => item !== index))}
              >
                <X size={17} />
              </button>
            </div>
          ))}
          <button className="button button--primary upload-action" onClick={submit} disabled={loading}>
            {loading ? <LoaderCircle size={18} className="spin" /> : <UploadCloud size={18} />}
            {loading ? "Загружаем" : `Загрузить ${files.length}`}
          </button>
        </div>
      )}
      {error && <div className="inline-alert" role="alert">{error}</div>}
    </section>
  );
}
