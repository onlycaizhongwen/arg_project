export type ApiErrorPayload = {
  error?: {
    code?: string;
    message?: string;
    trace_id?: string;
  };
};

export type UploadResponse = {
  job_id: string;
  document_id: string;
  document_version_id: string;
  source_id: string;
  knowledge_base_id: string;
  permission_tags: string[];
  filename: string;
  status: string;
};

export type JobResponse = {
  job_id: string;
  document_version_id: string;
  tenant_id: string;
  status: string;
  retry_count: number;
  error_message: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  updated_at: string;
};

export type SearchResult = {
  chunk_id?: string;
  document_id?: string;
  document_version_id?: string;
  text?: string;
  content?: string;
  score?: number;
  semantic_score?: number | null;
  keyword_score?: number | null;
  pre_rank_score?: number | null;
  rerank_score?: number | null;
  recall_sources?: string[];
  metadata?: Record<string, unknown>;
};

export type SearchResponse = {
  query?: string;
  results?: SearchResult[];
  items?: SearchResult[];
  search_plan?: Record<string, unknown>;
  rerank_provider?: string;
  rerank_degraded?: boolean;
};

export type DiagnosticsResponse = {
  status: string;
  generated_at: string;
  tenant_id: string;
  window_minutes: number;
  stale_lock_minutes: number;
  job_metrics: {
    by_status: Record<string, number>;
    pending_count: number;
    running_count: number;
    retrying_count: number;
    failed_count: number;
    total_recent_count: number;
    failed_recent_count: number;
    failure_rate: number;
  };
  queue_metrics: {
    available: boolean;
    queue: string;
    ready_count: number;
    consumer_count: number;
    error: string | null;
  };
  lock_metrics: {
    active_count: number;
    stale_count: number;
  };
  rerank_metrics: {
    provider: string;
    model: string;
    enabled_by_config: boolean;
    degraded_recent_count: number;
  };
  signals: string[];
};

export type RerankRuntimeConfig = {
  provider: "disabled" | "mock" | "external";
  model: string;
  base_url: string;
  timeout_seconds: number;
};

export type SearchRequest = {
  query: string;
  tenant_id: string;
  knowledge_base_ids: string[];
  permission_context: string[];
  search_mode: "semantic" | "keyword" | "hybrid";
  top_k: number;
  recall_size: number;
  pre_rank_size: number;
  dedup_enabled: boolean;
  diversity_enabled: boolean;
  max_chunks_per_document: number;
  rerank_enabled: boolean;
  rerank_size: number;
};

const apiBase = (import.meta.env.VITE_API_BASE || "").replace(/\/$/, "");

export async function getHealth(): Promise<Record<string, string>> {
  return requestJson("/health");
}

export async function getDiagnostics(tenantId: string): Promise<DiagnosticsResponse> {
  const params = new URLSearchParams({
    tenant_id: tenantId,
    window_minutes: "120",
    stale_lock_minutes: "30",
  });
  return requestJson(`/api/v1/diagnostics/overview?${params.toString()}`);
}

export async function getMetricsText(tenantId: string): Promise<string> {
  const params = new URLSearchParams({
    tenant_id: tenantId,
    window_minutes: "120",
    stale_lock_minutes: "30",
  });
  const response = await fetch(`${apiBase}/api/v1/metrics?${params.toString()}`);
  if (!response.ok) {
    throw await toApiError(response);
  }
  return response.text();
}

export async function getRerankRuntimeConfig(): Promise<RerankRuntimeConfig> {
  return requestJson("/api/v1/runtime-config/rerank");
}

export async function updateRerankRuntimeConfig(payload: RerankRuntimeConfig): Promise<RerankRuntimeConfig> {
  return requestJson("/api/v1/runtime-config/rerank", {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
}

export async function uploadFile(payload: {
  file: File;
  tenantId: string;
  sourceId: string;
  knowledgeBaseId: string;
  permissionTags: string;
  actorId: string;
  requestSource: string;
}): Promise<UploadResponse> {
  const params = new URLSearchParams({
    tenant_id: payload.tenantId,
    source_id: payload.sourceId,
    knowledge_base_id: payload.knowledgeBaseId,
    permission_tags: payload.permissionTags,
  });
  const formData = new FormData();
  formData.append("file", payload.file);
  return requestJson(`/api/v1/ingestions/files?${params.toString()}`, {
    method: "POST",
    headers: contextHeaders(payload),
    body: formData,
  });
}

export async function getJob(jobId: string): Promise<JobResponse> {
  return requestJson(`/api/v1/jobs/${encodeURIComponent(jobId)}`);
}

export async function search(payload: SearchRequest, headersPayload: {
  tenantId: string;
  actorId: string;
  requestSource: string;
  permissionTags: string;
}): Promise<SearchResponse> {
  return requestJson("/api/v1/rag/search", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...contextHeaders(headersPayload),
    },
    body: JSON.stringify(payload),
  });
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBase}${path}`, init);
  if (!response.ok) {
    throw await toApiError(response);
  }
  return response.json() as Promise<T>;
}

function contextHeaders(payload: {
  tenantId: string;
  actorId: string;
  requestSource: string;
  permissionTags?: string;
}): Record<string, string> {
  const headers: Record<string, string> = {
    "X-Tenant-Id": payload.tenantId,
    "X-Actor-Id": payload.actorId,
    "X-Request-Source": payload.requestSource,
  };
  if (payload.permissionTags) {
    headers["X-Permission-Tags"] = payload.permissionTags;
  }
  return headers;
}

async function toApiError(response: Response): Promise<Error> {
  let payload: ApiErrorPayload | null = null;
  try {
    payload = await response.json();
  } catch {
    // Ignore non-JSON responses.
  }
  const code = payload?.error?.code || `HTTP_${response.status}`;
  const message = payload?.error?.message || response.statusText || "Request failed";
  return new Error(`${code}: ${message}`);
}
