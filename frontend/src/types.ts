export type User = {
  id: string;
  email: string;
  is_active: boolean;
};

export type AuthResponse = {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
};

export type JobStatus = "queued" | "running" | "completed" | "failed" | "cancelled";

export type Job = {
  id: string;
  document_version_id: string;
  status: JobStatus;
  stage: string | null;
  attempt: number;
  pipeline_version: string;
  error_message: string | null;
  started_at: string | null;
  finished_at: string | null;
};

export type StoredJob = Job & {
  document_id?: string;
  filename: string;
  created_at: string;
};

export type Topic = {
  name: string;
  description: string;
};

export type KnowledgeCard = {
  id: string;
  job_id: string;
  document_id: string;
  document_version_id: string;
  filename: string;
  original_url: string;
  analysis: {
    summary: string;
    key_points: string[];
    community: Topic;
    domain: Topic;
    concepts: Topic[];
  };
};

export type GraphCommunity = {
  id: string;
  name: string;
  summary: string;
};

export type GraphDomain = {
  id: string;
  name: string;
  summary: string;
  community_id: string;
};

export type GraphConcept = {
  id: string;
  name: string;
  summary: string;
  domain_id: string;
  card_count: number;
};

export type GraphEdge = {
  source_id: string;
  target_id: string;
  weight: number;
};

export type KnowledgeGraph = {
  communities: GraphCommunity[];
  domains: GraphDomain[];
  concepts: GraphConcept[];
  edges: GraphEdge[];
};

export type Citation = {
  card_id: string;
  job_id: string;
  document_id: string;
  document_version_id: string;
  summary: string;
  original_url: string;
};

export type EvidencePath = {
  job_id: string;
  concepts: string[];
  score: number;
};

export type Answer = {
  session_id?: string;
  answer: string;
  citations: Citation[];
  evidence_paths: EvidencePath[];
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
};

export type ChatSession = {
  id: string;
  title: string | null;
  updated_at: string;
  messages: ChatMessage[];
};
