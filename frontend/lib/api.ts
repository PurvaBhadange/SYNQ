/**
 * SYNQ API Client
 * Typed client for communicating with the SYNQ FastAPI backend.
 */

/**
 * Resolves the API base URL depending on runtime environment:
 * 1. Server-side runtime (Next.js SSR, Route Handlers, Server Actions):
 *    Uses process.env.BACKEND_URL injected by Vercel Services binding.
 * 2. Client-side browser runtime:
 *    Uses NEXT_PUBLIC_API_URL if configured, otherwise defaults to '/api/v1'
 *    in deployed environments (routed to synq-backend via Vercel rewrites),
 *    or 'http://localhost:8000/api/v1' during local standalone development.
 */
export function getApiBase(): string {
  if (typeof window === 'undefined') {
    if (process.env.BACKEND_URL) {
      return `${process.env.BACKEND_URL.replace(/\/+$/, '')}/api/v1`;
    }
    if (process.env.NEXT_PUBLIC_API_URL) {
      return process.env.NEXT_PUBLIC_API_URL.replace(/\/+$/, '');
    }
    return 'https://synq-6p9m.onrender.com/api/v1';
  }

  if (process.env.NEXT_PUBLIC_API_URL) {
    return process.env.NEXT_PUBLIC_API_URL.replace(/\/+$/, '');
  }

  // If in browser on localhost or 127.0.0.1 without dev proxy:
  if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
    return 'http://localhost:8000/api/v1';
  }

  // Deployed production environment: connect directly to live Render backend
  // with configured AI providers, SQLite DB, and WebSockets
  return 'https://synq-6p9m.onrender.com/api/v1';
}

export const API_BASE = getApiBase();

// ── Types ────────────────────────────────────────────────────────────────────

export type ProjectDomain = 'software' | 'research' | 'education' | 'content' | 'business' | 'general';
export type ProjectStatus = 'active' | 'paused' | 'archived';

export interface Project {
  id: string;
  name: string;
  description: string | null;
  domain: ProjectDomain;
  status: ProjectStatus;
  allowed_providers: string[];
  memory_graph_id: string | null;
  task_count: number;
  created_at: string;
  updated_at: string;
}

export interface CreateProjectPayload {
  name: string;
  description?: string;
  domain?: ProjectDomain;
  allowed_providers?: string[];
}

export interface ProviderInfo {
  provider_id: string;
  model_id: string;
  display_name: string;
  is_local: boolean;
  is_configured: boolean;
  is_enabled: boolean;
  supported_task_types: string[];
  context_window_tokens: number;
  supports_streaming: boolean;
  supports_structured_output: boolean;
  supports_tool_calling: boolean;
  capability_source: string;
}

export interface RegistryStatus {
  total_registered: number;
  configured: number;
  local: number;
  cloud: number;
  providers: ProviderInfo[];
}

// ── Helpers ──────────────────────────────────────────────────────────────────

async function apiFetch<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const base = getApiBase();
  const cleanPath = path.startsWith('/') ? path : `/${path}`;
  const url = `${base}${cleanPath}`;
  const response = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`API error ${response.status}: ${text}`);
  }

  if (response.status === 204) return undefined as T;
  return response.json();
}

// ── Projects ──────────────────────────────────────────────────────────────────

export const projectsApi = {
  list: (status?: ProjectStatus): Promise<Project[]> => {
    const qs = status ? `?status_filter=${status}` : '';
    return apiFetch<Project[]>(`/projects/${qs}`);
  },

  get: (id: string): Promise<Project> =>
    apiFetch<Project>(`/projects/${id}`),

  create: (payload: CreateProjectPayload): Promise<Project> =>
    apiFetch<Project>('/projects/', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  update: (id: string, payload: Partial<CreateProjectPayload>): Promise<Project> =>
    apiFetch<Project>(`/projects/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),

  delete: (id: string): Promise<void> =>
    apiFetch<void>(`/projects/${id}`, { method: 'DELETE' }),
};

// ── Providers ─────────────────────────────────────────────────────────────────

export const providersApi = {
  list: (): Promise<RegistryStatus> =>
    apiFetch<RegistryStatus>('/providers/'),

  checkHealth: (providerId: string, modelId: string): Promise<{ healthy: boolean; error?: string }> =>
    apiFetch(`/providers/${providerId}/${encodeURIComponent(modelId)}/health`),
};

export interface Task {
  id: string;
  project_id: string;
  parent_task_id: string | null;
  title: string;
  description: string | null;
  task_type: string;
  status: 'pending' | 'assigned' | 'running' | 'paused' | 'awaiting_approval' | 'completed' | 'failed' | 'cancelled' | 'rejected' | 'blocked';
  priority: number;
  acceptance_criteria: string | null;
  dependencies: string[];
  assigned_provider: string | null;
  assigned_model: string | null;
  requires_approval: boolean;
  approval_reason?: string | null;
  rejection_reason?: string | null;
  approved_at?: string | null;
  approved_by?: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface TaskApprovalContext {
  task_id: string;
  project_id: string;
  title: string;
  description: string | null;
  task_type: string;
  priority: number;
  status: string;
  requires_approval: boolean;
  acceptance_criteria: string | null;
  assigned_provider: string | null;
  assigned_model: string | null;
  upstream_dependencies: {
    task_id: string;
    title: string;
    status: string;
    task_type: string;
    is_completed: boolean;
    latest_output_preview: string | null;
  }[];
  dependencies_all_completed: boolean;
  approval_reason: string | null;
  rejection_reason: string | null;
  approved_by: string | null;
  approved_at: string | null;
  risks: string[];
  available_actions: string[];
}

export interface TaskDetail extends Task {
  executions: {
    id: string;
    attempt: number;
    provider_id: string;
    model_id: string;
    status: string;
    output: string | null;
    validation_passed: boolean | null;
    validation_result: any;
    error_message: string | null;
    is_fallback: boolean;
    fallback_reason: string | null;
    routing_decision: {
      selected_provider: string;
      selected_model: string;
      selection_reason: string | null;
      rejected_providers: any[];
    } | null;
  }[];
}

export interface GraphNode {
  id: string;
  label: string;
  name?: string;
  title?: string;
  task_type?: string;
  domain?: string;
  preview?: string;
  status?: string;
  [key: string]: any;
}

export interface GraphEdge {
  source: string;
  target: string;
  type: string;
  [key: string]: any;
}

export interface MemoryGraphData {
  project_id: string;
  status?: string;
  backend?: string;
  error?: string | null;
  nodes: GraphNode[];
  edges: GraphEdge[];
  summary: {
    total_nodes: number;
    total_edges: number;
  };
}

// ── Tasks ─────────────────────────────────────────────────────────────────────

export const tasksApi = {
  list: (projectId: string): Promise<Task[]> =>
    apiFetch<Task[]>(`/projects/${projectId}/tasks`),

  create: (projectId: string, payload: Partial<Task>): Promise<Task> =>
    apiFetch<Task>(`/projects/${projectId}/tasks`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  plan: (projectId: string, goal: string, domain?: string): Promise<{ status: string; task_count: number; reasoning: string }> =>
    apiFetch(`/projects/${projectId}/plan`, {
      method: 'POST',
      body: JSON.stringify({ goal, domain }),
    }),

  execute: (taskId: string, overrides?: { user_override_provider?: string; user_override_model?: string }): Promise<any> =>
    apiFetch(`/tasks/${taskId}/execute`, {
      method: 'POST',
      body: JSON.stringify(overrides || {}),
    }),

  approve: (
    taskId: string,
    payload?: { reason?: string; approver?: string; user_override_provider?: string; user_override_model?: string }
  ): Promise<any> =>
    apiFetch(`/tasks/${taskId}/approve`, {
      method: 'POST',
      body: JSON.stringify(payload || {}),
    }),

  reject: (taskId: string, reason: string, approver?: string): Promise<any> =>
    apiFetch(`/tasks/${taskId}/reject`, {
      method: 'POST',
      body: JSON.stringify({ reason, approver: approver || 'Human Operator' }),
    }),

  edit: (taskId: string, payload: Partial<Task>): Promise<Task> =>
    apiFetch<Task>(`/tasks/${taskId}/edit`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  getApprovalContext: (taskId: string): Promise<TaskApprovalContext> =>
    apiFetch<TaskApprovalContext>(`/tasks/${taskId}/approval_context`),

  getDetail: (taskId: string): Promise<TaskDetail> =>
    apiFetch<TaskDetail>(`/tasks/${taskId}/detail`),

  addDependency: (projectId: string, taskId: string, dependsOnTaskId: string): Promise<any> =>
    apiFetch(`/projects/${projectId}/dependencies`, {
      method: 'POST',
      body: JSON.stringify({
        task_id: taskId,
        depends_on_task_id: dependsOnTaskId,
      }),
    }),

  removeDependency: (projectId: string, taskId: string, dependsOnTaskId: string): Promise<any> =>
    apiFetch(`/projects/${projectId}/dependencies`, {
      method: 'DELETE',
      body: JSON.stringify({
        task_id: taskId,
        depends_on_task_id: dependsOnTaskId,
      }),
    }),
};

// ── Memory ────────────────────────────────────────────────────────────────────

export const memoryApi = {
  getStatus: (projectId: string): Promise<{
    project_id: string;
    connected: boolean;
    status: string;
    backend: string;
    host: string;
    port: number;
    error: string | null;
    persistence_guaranteed: boolean;
  }> =>
    apiFetch(`/projects/${projectId}/memory/status`),

  getGraph: (projectId: string): Promise<MemoryGraphData> =>
    apiFetch<MemoryGraphData>(`/projects/${projectId}/memory/graph`),

  getContext: (projectId: string, taskId: string): Promise<any> =>
    apiFetch(`/projects/${projectId}/memory/context/${taskId}`),
};

// ── Export ───────────────────────────────────────────────────────────────────

export interface ExportPreview {
  project_id: string;
  project_name: string;
  completed_task_count: number;
  total_task_count: number;
  deliverable_files: string[];
  formats_supported: string[];
}

export const exportApi = {
  getPreview: (projectId: string): Promise<ExportPreview> =>
    apiFetch<ExportPreview>(`/projects/${projectId}/export/preview`),

  getZipUrl: (projectId: string): string =>
    `${getApiBase()}/projects/${projectId}/export/zip`,

  getMarkdownUrl: (projectId: string): string =>
    `${getApiBase()}/projects/${projectId}/export/markdown`,
};

// ── System ────────────────────────────────────────────────────────────────────

export const systemApi = {
  health: async (): Promise<Record<string, unknown>> => {
    const base = getApiBase();
    const rootUrl = base.replace(/\/api\/v1\/?$/, '');
    const rootHealthUrl = rootUrl ? `${rootUrl}/health` : '/health';

    // 1. Probe FastAPI root /health endpoint (always available on Render and local)
    try {
      const res = await fetch(rootHealthUrl, { headers: { 'Content-Type': 'application/json' } });
      if (res.ok) {
        return await res.json();
      }
    } catch {
      // Proceed to fallback
    }

    // 2. Fallback: probe /api/v1/health
    const apiHealthUrl = `${base.replace(/\/+$/, '')}/health`;
    const res = await fetch(apiHealthUrl, { headers: { 'Content-Type': 'application/json' } });
    if (!res.ok) {
      throw new Error(`Health check failed: ${res.status}`);
    }
    return await res.json();
  },
};

