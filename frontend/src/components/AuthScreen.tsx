import { FormEvent, useEffect, useState } from "react";
import { AlertCircle, BookOpen, Check, LoaderCircle, Network, ShieldCheck, X } from "lucide-react";
import { api, humanizeError } from "../lib/api";

type Props = {
  onAuthenticated: () => Promise<void>;
};

export function AuthScreen({ onAuthenticated }: Props) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!error) return;
    const timer = window.setTimeout(() => setError(""), 6000);
    return () => window.clearTimeout(timer);
  }, [error]);

  function passwordPolicyError(value: string): string | null {
    if (value.length < 8) return "Пароль должен содержать минимум 8 символов";
    if (![...value].some((character) => character.toUpperCase() === character && character.toLowerCase() !== character)) {
      return "Добавьте хотя бы одну заглавную букву";
    }
    if (![...value].some((character) => character.toLowerCase() === character && character.toUpperCase() !== character)) {
      return "Добавьте хотя бы одну строчную букву";
    }
    return null;
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (mode === "register") {
      const policyError = passwordPolicyError(password);
      if (policyError) {
        setError(policyError);
        return;
      }
    }
    setLoading(true);
    setError("");
    try {
      if (mode === "register") {
        await api.register(email, password);
      }
      await api.login(email, password);
      await onAuthenticated();
    } catch (requestError) {
      setError(humanizeError(requestError));
    } finally {
      setLoading(false);
    }
  }

  function changeMode(nextMode: "login" | "register") {
    setMode(nextMode);
    setError("");
  }

  return (
    <main className="auth-layout">
      <section className="auth-story">
        <div className="brand brand--light">
          <span className="brand-mark"><Network size={21} /></span>
          <span>CoWo</span>
        </div>
        <div className="story-copy">
          <p className="eyebrow eyebrow--light">Knowledge workspace</p>
          <h1>Документы, которые становятся связным знанием.</h1>
          <p className="story-description">
            Загружайте материалы, собирайте граф смыслов и получайте ответы со
            ссылками на первоисточники.
          </p>
          <div className="story-features">
            <div><BookOpen size={20} /><span>Единая библиотека документов</span></div>
            <div><Network size={20} /><span>Автоматический граф концептов</span></div>
            <div><ShieldCheck size={20} /><span>Локальные модели и ваши данные</span></div>
          </div>
        </div>
        <div className="story-orbit" aria-hidden="true">
          <span className="orbit-node orbit-node--one" />
          <span className="orbit-node orbit-node--two" />
          <span className="orbit-node orbit-node--three" />
          <span className="orbit-line orbit-line--one" />
          <span className="orbit-line orbit-line--two" />
        </div>
        <p className="story-footnote">Private by design · OpenAI-compatible</p>
      </section>

      <section className="auth-panel">
        <div className="auth-card">
          <div className="auth-heading">
            <p className="eyebrow">Рабочее пространство</p>
            <h2>{mode === "login" ? "С возвращением" : "Создайте аккаунт"}</h2>
            <p>
              {mode === "login"
                ? "Войдите, чтобы продолжить работу с базой знаний."
                : "Пара минут — и можно загружать первые документы."}
            </p>
          </div>

          <div className="auth-switch" role="tablist" aria-label="Режим авторизации">
            <button
              type="button"
              className={mode === "login" ? "is-active" : ""}
              onClick={() => changeMode("login")}
            >
              Вход
            </button>
            <button
              type="button"
              className={mode === "register" ? "is-active" : ""}
              onClick={() => changeMode("register")}
            >
              Регистрация
            </button>
          </div>

          <form onSubmit={submit} className="auth-form">
            <label>
              <span>Email</span>
              <input
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="you@example.com"
                autoComplete="email"
                required
              />
            </label>
            <label>
              <span>Пароль</span>
              <input
                type="password"
                value={password}
                onChange={(event) => {
                  setPassword(event.target.value);
                  if (mode === "register" && !passwordPolicyError(event.target.value)) {
                    setError("");
                  }
                }}
                placeholder="Не менее 8 символов"
                autoComplete={mode === "login" ? "current-password" : "new-password"}
                aria-invalid={mode === "register" && Boolean(error)}
                required
              />
            </label>
            {mode === "register" && (
              <div className="password-note">
                <Check size={15} /> Минимум 8 символов, заглавная и строчная буквы
              </div>
            )}
            <button className="button button--primary button--wide" disabled={loading}>
              {loading && <LoaderCircle size={18} className="spin" />}
              {mode === "login" ? "Войти" : "Создать аккаунт"}
            </button>
          </form>
        </div>
      </section>
      {error && (
        <div className="auth-toast" role="alert" aria-live="assertive">
          <AlertCircle size={20} />
          <span>{error}</span>
          <button type="button" onClick={() => setError("")} aria-label="Закрыть">
            <X size={17} />
          </button>
        </div>
      )}
    </main>
  );
}
