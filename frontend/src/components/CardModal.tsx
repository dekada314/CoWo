import { useEffect } from "react";
import { Download, Network, X } from "lucide-react";
import type { KnowledgeCard } from "../types";

type Props = {
  card: KnowledgeCard;
  filename: string;
  onClose: () => void;
  onDownload: () => void;
};

export function CardModal({ card, filename, onClose, onDownload }: Props) {
  useEffect(() => {
    function escape(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", escape);
    return () => window.removeEventListener("keydown", escape);
  }, [onClose]);

  return (
    <div className="modal-backdrop" onMouseDown={onClose}>
      <section className="card-modal" onMouseDown={(event) => event.stopPropagation()} role="dialog" aria-modal="true">
        <header className="modal-header">
          <div>
            <p className="eyebrow">Карточка знаний</p>
            <h2>{filename}</h2>
          </div>
          <button className="icon-button" onClick={onClose} aria-label="Закрыть"><X size={20} /></button>
        </header>
        <div className="modal-body">
          <p className="card-summary">{card.analysis.summary}</p>
          <div className="topic-pair">
            <div><span>Домен</span><strong>{card.analysis.domain.name}</strong><p>{card.analysis.domain.description}</p></div>
            <div><span>Сообщество</span><strong>{card.analysis.community.name}</strong><p>{card.analysis.community.description}</p></div>
          </div>
          <div className="card-section">
            <h3>Ключевые мысли</h3>
            <ul className="key-points">
              {card.analysis.key_points.map((point) => <li key={point}>{point}</li>)}
            </ul>
          </div>
          <div className="card-section">
            <h3><Network size={18} /> Концепции</h3>
            <div className="concept-grid">
              {card.analysis.concepts.map((concept) => (
                <div key={concept.name}><strong>{concept.name}</strong><p>{concept.description}</p></div>
              ))}
            </div>
          </div>
        </div>
        <footer className="modal-footer">
          <span>ID · {card.id.slice(0, 8)}</span>
          <button className="button button--secondary" onClick={onDownload}><Download size={17} /> Скачать оригинал</button>
        </footer>
      </section>
    </div>
  );
}
