/**
 * Authentication hook for CodeKnowl Web UI
 * 
 * Why this exists:
 * - Manages authentication state and user sessions
 * - Supports Milestone 9 requirements for authorized access
 * - Integrates with backend auth system
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { authApi } from '../utils/api';
import type { AuthUser } from '../types/api';

export function useAuth() {
  const queryClient = useQueryClient();

  // Get current user
  const { data: user, isLoading, error } = useQuery<AuthUser>({
    queryKey: ['auth', 'user'],
    queryFn: authApi.me,
    retry: false,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });

  // Login mutation
  const loginMutation = useMutation({
    mutationFn: ({ username, password }: { username: string; password: string }) =>
      authApi.login(username, password),
    onSuccess: (data) => {
      localStorage.setItem('auth_token', data.token);
      queryClient.setQueryData(['auth', 'user'], data.user);
    },
  });

  // Logout mutation
  const logoutMutation = useMutation({
    mutationFn: authApi.logout,
    onSuccess: () => {
      localStorage.removeItem('auth_token');
      queryClient.setQueryData(['auth', 'user'], null);
      queryClient.clear();
    },
  });

  const login = (username: string, password: string) => {
    return loginMutation.mutateAsync({ username, password });
  };

  const logout = () => {
    logoutMutation.mutate();
  };

  return {
    user,
    loading: isLoading,
    error,
    login,
    logout,
    loginLoading: loginMutation.isPending,
    loginError: loginMutation.error,
  };
}
