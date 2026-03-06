/**
 * Tests for App component
 * 
 * Why this exists:
 * - Tests required by Definition of Done for Milestone 9
 * - Verifies React app renders correctly
 * - Ensures basic functionality works
 */

import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import App from './App';

// Mock the auth hook
vi.mock('./hooks/useAuth', () => ({
  useAuth: vi.fn(() => ({
    user: { id: '1', username: 'test', email: 'test@example.com', groups: [], permissions: [] },
    loading: false,
    login: vi.fn(),
    logout: vi.fn(),
  })),
}));

// Mock the API
vi.mock('./utils/api', () => ({
  authApi: {
    me: vi.fn(() => Promise.resolve({ id: '1', username: 'test', email: 'test@example.com', groups: [], permissions: [] })),
  },
}));

describe('App', () => {
  it('renders without crashing', () => {
    render(<App />);
    expect(screen.getByText('Dashboard')).toBeInTheDocument();
  });

  it('shows navigation items', () => {
    render(<App />);
    expect(screen.getByText('Repositories')).toBeInTheDocument();
    expect(screen.getByText('Q&A')).toBeInTheDocument();
    expect(screen.getByText('Indexing')).toBeInTheDocument();
  });
});
