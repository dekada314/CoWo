import { FormEvent, useState } from "react";
import { BookOpen, Download, LoaderCircle, MessageSquareText, Network, Sparkles } from "lucide-react";
import { api, humanizeError } from "../lib/api";
import type { Answer } from "../types";

const suggestions = [
  "Какие главные идеи объединяют документы?",
  "Объясни ключевые концепты простыми словами",
  "Какие темы требуют дополнительного исследования?",
];

export function AskPanel() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function ask(event?: FormEvent) {
    event?.preventDefault();
    if (!question.trim() || loading) return;
    setLoading(true);
    setError("");
    try {
      setAnswer(await api.ask(question.trim()));
    } catch (requestError) {
      setError(humanizeError(requestError));
    } finally {
      setLoading(false);
    }
  }

  async function downloadSource(url: string, filename: string) {
    try {
      await api.download(url, filename);
    } catch (requestError) {
      setError(humanizeError(requestError));
    }
  }

  return (
    <div className="ask-layout">
      <section className="ask-intro">
        <p className="eyebrow">Retrieval agent</p>
        <h1>Спросите свою базу знаний</h1>
        <p>Ответ будет собран только из ваших документов и дополнен проверенными источниками.</p>
        <div className="ask-promise">
          <div><BookOpen size={19} /><span><strong>Источники</strong> к каждому ответу</span></div>
          <div><Network size={19} /><span><strong>Пути в графе</strong> вместо догадок</span></div>
        </div>
      </section>

      <section className="panel question-panel">
        <form onSubmit={ask}>
          <label htmlFor="question">Ваш вопрос</label>
          <textarea
            id="question"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="Например: как связаны RAG и семантический поиск?"
            rows={5}
            maxLength={4000}
          />
          <div className="question-actions">
            <span>{question.length} / 4000</span>
            <button className="button button--primary" disabled={!question.trim() || loading}>
              {loading ? <LoaderCircle size={18} className="spin" /> : <Sparkles size={18} />}
              {loading ? "Ищу связи" : "Получить ответ"}
            </button>
          </div>
        </form>
        {!answer && !loading && (
          <div className="suggestions">
            <span>Можно начать с этого</span>
            {suggestions.map((suggestion) => (
              <button key={suggestion} onClick={() => setQuestion(suggestion)}>{suggestion}</button>
            ))}
          </div>
        )}
        {error && <div className="inline-alert" role="alert">{error}</div>}
      </section>

      {answer && (
        <section className="answer-panel">
          <div className="answer-heading"><span><MessageSquareText size={20} /></span><div><p className="eyebrow">Ответ агента</p><h2>По найденным материалам</h2></div></div>
          <div className="answer-text">{answer.answer}</div>
          <div className="answer-details">
            <div className="sources">
              <h3>Источники · {answer.citations.length}</h3>
              {answer.citations.map((citation, index) => (
                <article key={citation.card_id}>
                  <span>{index + 1}</span>
                  <p>{citation.summary}</p>
                  <button className="icon-button" aria-label="Скачать источник" onClick={() => downloadSource(citation.original_url, `source-${index + 1}`)}><Download size={17} /></button>
                </article>
              ))}
            </div>
            <div className="evidence">
              <h3>Пути в графе</h3>
              {answer.evidence_paths.map((path, index) => (
                <div className="evidence-path" key={`${path.job_id}-${index}`}>
                  <div>{path.concepts.map((concept) => <span key={concept}>{concept}</span>)}</div>
                  <small>{Math.round(path.score * 100)}% релевантности</small>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}
    </div>
  );
}
