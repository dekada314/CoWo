import { FormEvent, useEffect, useMemo, useState } from "react";
import { BookOpen, Download, LoaderCircle, MessageSquareText, Network, Plus, Sparkles, Trash2 } from "lucide-react";
import { api, humanizeError } from "../lib/api";
import type { Answer, ChatMessage, ChatSession } from "../types";

const suggestions = ["Какие главные идеи объединяют документы?", "Объясни ключевые концепты простыми словами", "Какие темы требуют дополнительного исследования?"];

export function AskPanel() {
  const [question, setQuestion] = useState("");
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const activeSession = useMemo(() => sessions.find((s) => s.id === activeSessionId) ?? null, [sessions, activeSessionId]);
  useEffect(() => { void loadSessions(); }, []);
  async function loadSessions() { try { const loaded = await api.getChatSessions(); setSessions(loaded); if (!activeSessionId && loaded[0]) setActiveSessionId(loaded[0].id); } catch (e) { setError(humanizeError(e)); } }
  function startNewChat() { setActiveSessionId(null); setAnswer(null); setQuestion(""); setError(""); }
  function selectSession(session: ChatSession) { setActiveSessionId(session.id); setAnswer(null); setError(""); }
  async function deleteSession(event: React.MouseEvent, id: string) { event.stopPropagation(); try { await api.deleteChatSession(id); const next = sessions.filter((s) => s.id !== id); setSessions(next); if (activeSessionId === id) { setActiveSessionId(next[0]?.id ?? null); setAnswer(null); } } catch (e) { setError(humanizeError(e)); } }
  async function ask(event?: FormEvent) { event?.preventDefault(); if (!question.trim() || loading) return; setLoading(true); setError(""); try { const result = await api.ask(question.trim(), activeSessionId ?? undefined); setAnswer(result); setQuestion(""); await loadSessions(); if (result.session_id) setActiveSessionId(result.session_id); } catch (e) { setError(humanizeError(e)); } finally { setLoading(false); } }
  async function downloadSource(url: string, filename: string) { try { await api.download(url, filename); } catch (e) { setError(humanizeError(e)); } }
  const messages: ChatMessage[] = activeSession?.messages ?? [];
  return <div className="ask-layout">
    <section className="ask-intro"><p className="eyebrow">Retrieval agent</p><h1>Спросите свою базу знаний</h1><p>Ответ будет собран только из ваших документов и дополнен проверенными источниками.</p><div className="ask-promise"><div><BookOpen size={19} /><span><strong>Источники</strong> к каждому ответу</span></div><div><Network size={19} /><span><strong>Пути в графе</strong> вместо догадок</span></div></div></section>
    <div className="chat-layout">
      <aside className="panel chat-history"><div className="chat-history-heading"><h2>Диалоги</h2><button className="icon-button" onClick={startNewChat} aria-label="Новый диалог"><Plus size={18} /></button></div><button className="button button--secondary chat-new-button" onClick={startNewChat}><Plus size={16} /> Новый диалог</button><div className="chat-session-list">{sessions.map((session) => <button key={session.id} className={`chat-session ${session.id === activeSessionId ? "chat-session--active" : ""}`} onClick={() => selectSession(session)}><span className="chat-session-title">{session.title || "Новый диалог"}</span><span className="chat-session-meta">{session.messages.length} сообщ.</span><span className="chat-session-delete" role="button" tabIndex={0} onClick={(event) => void deleteSession(event, session.id)} aria-label="Удалить диалог"><Trash2 size={14} /></span></button>)}{!sessions.length && <p className="chat-history-empty">Здесь появятся ваши диалоги</p>}</div></aside>
      <div className="chat-thread">{messages.length > 0 && <section className="panel chat-messages" aria-label="История сообщений">{messages.map((message) => <div key={message.id} className={`chat-bubble chat-bubble--${message.role}`}><span>{message.role === "user" ? "Вы" : "Агент"}</span><p>{message.content}</p></div>)}</section>}
        <section className="panel question-panel"><form onSubmit={ask}><label htmlFor="question">Ваш вопрос</label><textarea id="question" value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="Например: как связаны RAG и семантический поиск?" rows={5} maxLength={4000} /><div className="question-actions"><span>{question.length} / 4000</span><button className="button button--primary" disabled={!question.trim() || loading}>{loading ? <LoaderCircle size={18} className="spin" /> : <Sparkles size={18} />}{loading ? "Ищу связи" : "Получить ответ"}</button></div></form>{!answer && !messages.length && !loading && <div className="suggestions"><span>Можно начать с этого</span>{suggestions.map((s) => <button key={s} onClick={() => setQuestion(s)}>{s}</button>)}</div>}{error && <div className="inline-alert" role="alert">{error}</div>}</section>
        {answer && <section className="answer-panel"><div className="answer-heading"><span><MessageSquareText size={20} /></span><div><p className="eyebrow">Ответ агента</p><h2>По найденным материалам</h2></div></div><div className="answer-text">{answer.answer}</div><div className="answer-details"><div className="sources"><h3>Источники · {answer.citations.length}</h3>{answer.citations.map((c, i) => <article key={c.card_id}><span>{i + 1}</span><p>{c.summary}</p><button className="icon-button" aria-label="Скачать источник" onClick={() => void downloadSource(c.original_url, `source-${i + 1}`)}><Download size={17} /></button></article>)}</div><div className="evidence"><h3>Пути в графе</h3>{answer.evidence_paths.map((path, i) => <div className="evidence-path" key={`${path.job_id}-${i}`}><div>{path.concepts.map((concept) => <span key={concept}>{concept}</span>)}</div><small>{Math.round(path.score * 100)}% релевантности</small></div>)}</div></div></section>}
      </div>
    </div>
  </div>;
}
