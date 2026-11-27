import type {
  Answer,
  AuthResponse,
  Job,
  KnowledgeGraph,
  KnowledgeCard,
  ChatSession,
  StoredJob,
  User,
} from "../types";

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
  ) {
    super(detail);
  }
}

let accessToken: string | null = null;
let refreshRequest: Promise<AuthResponse> | null = null;

const errorMessages: Record<string, string> = {
  email_already_registered: "Аккаунт с таким email уже существует",
  invalid_credentials: "Неверный email или пароль",
  invalid_token: "Сессия завершена. Войдите снова",
  refresh_token_reused: "Сессия отозвана из-за повторного использования токена",
  user_inactive: "Аккаунт деактивирован",
  llm_model_not_configured: "Локальная модель пока не настроена",
  document_file_limit_exceeded: "Файл превышает допустимый размер",
  document_batch_limit_exceeded: "За раз можно загрузить не больше 10 документов",
  unsupported_document_type: "Поддерживаются PDF, DOCX, Markdown и TXT",
  empty_document: "Документ пуст",
  invalid_filename: "Некорректное имя файла",
  document_has_no_text: "В документе не удалось найти текст",
  document_parse_failed: "Не удалось прочитать документ. Проверьте, что файл не повреждён",
  document_parse_timeout: "Распознавание документа заняло слишком много времени",
  document_text_limit_exceeded: "Извлечённый текст превышает допустимый объём",
  knowledge_not_found: "В базе знаний пока нет подходящего ответа",
  document_processing_in_progress: "Дождитесь завершения обработки документа",
  document_deletion_failed: "Не удалось полностью удалить документ. Повторите попытку",
  ingestion_submission_unavailable: "Не удалось сохранить задание. Повторите попытку",
  queue_publish_failed: "Не удалось поставить документ в очередь. Проверьте RabbitMQ и повторите обработку",
  job_not_found: "Документ или задание не найдено",
  card_not_ready: "Карточка ещё не готова. Дождитесь завершения обработки",
  only_failed_jobs_can_be_retried: "Повторно запустить можно только задание с ошибкой",
  document_integrity_check_failed: "Исходный файл повреждён или был изменён",
  worker_lost_attempts_exhausted: "Обработчик прервался. Лимит попыток исчерпан",
  job_lease_lost: "Обработка была передана другому воркеру",
  job_timeout: "Обработка документа заняла слишком много времени",
  ingestion_internal_error: "Внутренняя ошибка обработки документа",
  llm_unavailable: "Языковая модель временно недоступна",
  llm_invalid_structured_output: "Модель вернула некорректный результат",
  llm_output_truncated: "Ответ модели оказался неполным",
  document_analysis_budget_exceeded: "Документ слишком большой для доступного лимита анализа",
  analysis_fragment_too_large: "Фрагмент документа слишком большой для анализа",
  embedding_unavailable: "Модель векторизации временно недоступна",
  embedding_invalid_response: "Модель векторизации вернула некорректный результат",
  concept_not_found: "Концепция не найдена",
  graph_unavailable: "Граф знаний временно недоступен",
  retrieval_unavailable: "Поиск по базе знаний временно недоступен",
  responder_invalid_sources: "Не удалось проверить источники ответа",
  responder_invalid_output: "Модель вернула некорректный ответ",
  chat_not_found: "Диалог не найден",
  request_failed: "Не удалось выполнить запрос. Повторите попытку",
  invalid_email_format: "Введите корректный email",
  required_field_missing: "Заполните обязательные поля",
  validation_failed: "Проверьте правильность заполнения полей",
};

export function humanizeErrorCode(detail: string, status = 0): string {
  const exact = errorMessages[detail];
  if (exact) return exact;
  if (/[А-Яа-яЁё]/.test(detail)) return detail;
  if (/^llm_http_/.test(detail)) return "Ошибка при обращении к языковой модели";
  if (/^embedding_http_/.test(detail)) return "Ошибка при обращении к модели векторизации";
  if (/^community_http_/.test(detail)) return "Ошибка при построении тематических групп";
  if (status === 401) return "Сессия завершена. Войдите снова";
  if (status === 403) return "Недостаточно прав для выполнения действия";
  if (status === 404) return "Запрошенные данные не найдены";
  if (status === 409) return "Действие недоступно в текущем состоянии";
  if (status >= 500) return "Сервис временно недоступен. Повторите попытку позже";
  return "Не удалось выполнить запрос. Повторите попытку";
}

export function humanizeError(error: unknown): string {
  if (error instanceof ApiError) {
    return humanizeErrorCode(error.detail, error.status);
  }
  if (error instanceof Error) {
    return "Не удалось связаться с сервером. Проверьте подключение и повторите попытку";
  }
  return "Не удалось выполнить запрос. Повторите попытку";
}

function setToken(token: string | null) {
  accessToken = token;
}

async function parseError(response: Response): Promise<ApiError> {
  try {
    const payload = (await response.json()) as { detail?: unknown };
    if (typeof payload.detail === "string") {
      return new ApiError(response.status, payload.detail);
    }
    if (Array.isArray(payload.detail)) {
      const validation = payload.detail.find(
        (item): item is { msg: string; type?: string; loc?: Array<string | number> } =>
          typeof item === "object" && item !== null && "msg" in item
          && typeof item.msg === "string",
      );
      if (validation) {
        const location = validation.loc?.map(String) ?? [];
        if (location.includes("email") || /email address/i.test(validation.msg)) {
          return new ApiError(response.status, "invalid_email_format");
        }
        if (validation.type === "missing") {
          return new ApiError(response.status, "required_field_missing");
        }
        const message = validation.msg.replace(/^Value error,\s*/, "");
        if (/[А-Яа-яЁё]/.test(message)) {
          return new ApiError(response.status, message);
        }
        return new ApiError(response.status, "validation_failed");
      }
    }
    return new ApiError(response.status, "request_failed");
  } catch {
    return new ApiError(response.status, "request_failed");
  }
}

async function rawRequest<T>(
  path: string,
  options: RequestInit = {},
  canRefresh = true,
): Promise<T> {
  const headers = new Headers(options.headers);
  if (accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }
  if (options.body && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(path, {
    ...options,
    headers,
    credentials: "include",
  });
  if (response.status === 401 && canRefresh && !path.startsWith("/api/v1/auth/")) {
    try {
      await refreshAccessToken();
      return rawRequest<T>(path, options, false);
    } catch {
      setToken(null);
      throw await parseError(response);
    }
  }
  if (!response.ok) {
    throw await parseError(response);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export async function refreshAccessToken(): Promise<AuthResponse> {
  if (!refreshRequest) {
    refreshRequest = rawRequest<AuthResponse>(
      "/api/v1/auth/refresh",
      { method: "POST" },
      false,
    ).finally(() => {
      refreshRequest = null;
    });
  }
  const response = await refreshRequest;
  setToken(response.access_token);
  return response;
}

export const api = {
  async register(email: string, password: string) {
    return rawRequest<User>(
      "/api/v1/auth/register",
      { method: "POST", body: JSON.stringify({ email, password }) },
      false,
    );
  },
  async login(email: string, password: string) {
    const response = await rawRequest<AuthResponse>(
      "/api/v1/auth/login",
      { method: "POST", body: JSON.stringify({ email, password }) },
      false,
    );
    setToken(response.access_token);
    return response;
  },
  async logout() {
    try {
      await rawRequest<void>("/api/v1/auth/logout", { method: "POST" }, false);
    } finally {
      setToken(null);
    }
  },
  me: () => rawRequest<User>("/api/v1/auth/me"),
  async upload(files: File[]) {
    const body = new FormData();
    const isBatch = files.length > 1;
    for (const file of files) {
      body.append(isBatch ? "files" : "file", file);
    }
    return rawRequest<Job | Job[]>(
      `/api/v1/ingestion/documents${isBatch ? "/batch" : ""}`,
      { method: "POST", body },
    );
  },
  getJob: (id: string) => rawRequest<Job>(`/api/v1/ingestion/jobs/${id}`),
  listDocuments: () =>
    rawRequest<StoredJob[]>("/api/v1/ingestion/documents"),
  getCard: (id: string) =>
    rawRequest<KnowledgeCard>(`/api/v1/ingestion/jobs/${id}/card`),
  getGraph: () => rawRequest<KnowledgeGraph>("/api/v1/graph"),
  getConceptCards: (id: string) =>
    rawRequest<KnowledgeCard[]>(
      `/api/v1/graph/concepts/${encodeURIComponent(id)}/cards`,
    ),
  retryJob: (id: string) =>
    rawRequest<Job>(`/api/v1/ingestion/jobs/${id}/retry`, { method: "POST" }),
  deleteDocument: (id: string) =>
    rawRequest<void>(`/api/v1/ingestion/jobs/${id}`, { method: "DELETE" }),
  ask: (question: string, sessionId?: string) =>
    rawRequest<Answer>("/api/v1/retrieval/answer", {
      method: "POST",
      body: JSON.stringify({ question, ...(sessionId ? { session_id: sessionId } : {}) }),
    }),
  getChatSessions: () => rawRequest<ChatSession[]>("/api/v1/retrieval/sessions"),
  deleteChatSession: (id: string) =>
    rawRequest<void>(`/api/v1/retrieval/sessions/${id}`, { method: "DELETE" }),
  async download(url: string, filename: string) {
    const headers = new Headers();
    if (accessToken) {
      headers.set("Authorization", `Bearer ${accessToken}`);
    }
    let response = await fetch(url, { headers, credentials: "include" });
    if (response.status === 401) {
      await refreshAccessToken();
      if (accessToken) {
        headers.set("Authorization", `Bearer ${accessToken}`);
      }
      response = await fetch(url, { headers, credentials: "include" });
    }
    if (!response.ok) {
      throw await parseError(response);
    }
    const contentDisposition = response.headers.get("content-disposition") ?? "";
    const encodedName = contentDisposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
    const downloadName = encodedName ? decodeURIComponent(encodedName) : filename;
    const blob = await response.blob();
    const objectUrl = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = objectUrl;
    anchor.download = downloadName;
    document.body.append(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(objectUrl);
  },
};
