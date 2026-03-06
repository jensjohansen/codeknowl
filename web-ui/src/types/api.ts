/**
 * API types for CodeKnowl backend integration
 * 
 * Why this exists:
 * - TypeScript interfaces for API contracts
 * - Ensures type safety across the React UI
 * - Supports Milestone 9 requirements for admin UI and Q&A interface
 */

export interface Repository {
  id: string;
  name: string;
  url: string;
  local_path: string;
  created_at: string;
  updated_at: string;
  indexing_status: 'not_started' | 'in_progress' | 'completed' | 'failed';
  last_indexed_at?: string;
  indexing_error?: string;
}

export interface IndexingJob {
  id: string;
  repo_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  created_at: string;
  started_at?: string;
  completed_at?: string;
  error?: string;
  progress?: {
    stage: string;
    completed: number;
    total: number;
  };
}

export interface QARequest {
  question: string;
  repo_id?: string;
  context?: string[];
}

export interface QAResponse {
  answer: string;
  citations: Citation[];
  model_used: string;
  response_time_ms: number;
}

export interface Citation {
  file_path: string;
  line_start: number;
  line_end?: number;
  snippet: string;
  score: number;
}

export interface HealthStatus {
  status: 'healthy' | 'degraded' | 'unhealthy';
  version: string;
  uptime_seconds: number;
  components: ComponentHealth[];
}

export interface ComponentHealth {
  name: string;
  status: 'healthy' | 'unhealthy';
  details?: string;
}

export interface AuthUser {
  id: string;
  username: string;
  email: string;
  groups: string[];
  permissions: string[];
}
