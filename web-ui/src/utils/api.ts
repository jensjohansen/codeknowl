/**
 * API client for CodeKnowl backend
 * 
 * Why this exists:
 * - HTTP client for backend API integration
 * - Supports Milestone 9 requirements for admin UI and Q&A interface
 * - Handles authentication and error management
 */

import axios from 'axios';
import type { Repository, IndexingJob, QARequest, QAResponse, HealthStatus, AuthUser } from '../types/api';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

// Create axios instance with auth
const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add auth interceptor
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Add error handling interceptor
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('auth_token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// Repository API
export const repositoryApi = {
  list: async (): Promise<Repository[]> => {
    const response = await api.get('/repos');
    return response.data.repos || [];
  },

  get: async (id: string): Promise<Repository> => {
    const response = await api.get(`/repos/${id}`);
    return response.data;
  },

  create: async (data: { name: string; url: string }): Promise<Repository> => {
    const response = await api.post('/repos', data);
    return response.data;
  },

  delete: async (id: string): Promise<void> => {
    await api.delete(`/repos/${id}`);
  },

  reindex: async (id: string): Promise<IndexingJob> => {
    const response = await api.post(`/repos/${id}/index`);
    return response.data;
  },
};

// Indexing API
export const indexingApi = {
  listJobs: async (repoId?: string): Promise<IndexingJob[]> => {
    const url = repoId ? `/repos/${repoId}/jobs` : '/jobs';
    const response = await api.get(url);
    return response.data.jobs || [];
  },

  getJob: async (id: string): Promise<IndexingJob> => {
    const response = await api.get(`/jobs/${id}`);
    return response.data;
  },
};

// Q&A API
export const qaApi = {
  ask: async (request: QARequest): Promise<QAResponse> => {
    const response = await api.post('/qa', request);
    return response.data;
  },

  stream: async (request: QARequest, onChunk: (chunk: string) => void): Promise<QAResponse> => {
    const response = await fetch(`${API_BASE_URL}/qa/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${localStorage.getItem('auth_token')}`,
      },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const reader = response.body?.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    if (reader) {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6);
            if (data === '[DONE]') {
              continue;
            }
            try {
              const parsed = JSON.parse(data);
              if (parsed.content) {
                onChunk(parsed.content);
              }
            } catch (e) {
              // Ignore parsing errors
            }
          }
        }
      }
    }

    // Get final response
    const finalResponse = await api.post('/qa', request);
    return finalResponse.data;
  },
};

// Health API
export const healthApi = {
  status: async (): Promise<HealthStatus> => {
    const response = await api.get('/health');
    return response.data;
  },
};

// Auth API
export const authApi = {
  login: async (username: string, password: string): Promise<{ token: string; user: AuthUser }> => {
    const response = await api.post('/auth/login', { username, password });
    return response.data;
  },

  logout: async (): Promise<void> => {
    await api.post('/auth/logout');
  },

  me: async (): Promise<AuthUser> => {
    const response = await api.get('/auth/me');
    return response.data;
  },
};

export default api;
