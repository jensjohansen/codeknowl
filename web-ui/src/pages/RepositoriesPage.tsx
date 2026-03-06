/**
 * Repositories management page for CodeKnowl Web UI
 * 
 * Why this exists:
 * - Repository lifecycle management for operators
 * - Supports Milestone 9 requirements for admin UI
 * - Enables repo onboarding and management
 */

import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Plus, GitBranch, RefreshCw, Trash2, ExternalLink, Clock, CheckCircle, AlertCircle, XCircle } from 'lucide-react';
import { repositoryApi } from '../utils/api';
import { Button } from '../components/Button';
import type { Repository } from '../types/api';

export function RepositoriesPage() {
  const [showAddForm, setShowAddForm] = useState(false);
  const [newRepo, setNewRepo] = useState({ name: '', url: '' });
  
  const queryClient = useQueryClient();
  
  const { data: repos, isLoading } = useQuery({
    queryKey: ['repositories'],
    queryFn: repositoryApi.list,
  });

  const createRepoMutation = useMutation({
    mutationFn: repositoryApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['repositories'] });
      setShowAddForm(false);
      setNewRepo({ name: '', url: '' });
    },
  });

  const deleteRepoMutation = useMutation({
    mutationFn: repositoryApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['repositories'] });
    },
  });

  const reindexMutation = useMutation({
    mutationFn: repositoryApi.reindex,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['repositories'] });
      queryClient.invalidateQueries({ queryKey: ['indexing-jobs'] });
    },
  });

  const handleCreateRepo = (e: React.FormEvent) => {
    e.preventDefault();
    createRepoMutation.mutate(newRepo);
  };

  const handleDeleteRepo = (id: string) => {
    if (confirm('Are you sure you want to delete this repository?')) {
      deleteRepoMutation.mutate(id);
    }
  };

  const handleReindex = (id: string) => {
    reindexMutation.mutate(id);
  };

  const getStatusIcon = (status: Repository['indexing_status']) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="w-4 h-4 text-green-500" />;
      case 'in_progress':
        return <RefreshCw className="w-4 h-4 text-yellow-500 animate-spin" />;
      case 'failed':
        return <AlertCircle className="w-4 h-4 text-red-500" />;
      default:
        return <XCircle className="w-4 h-4 text-gray-400" />;
    }
  };

  const getStatusText = (status: Repository['indexing_status']) => {
    switch (status) {
      case 'completed':
        return 'Indexed';
      case 'in_progress':
        return 'Indexing';
      case 'failed':
        return 'Failed';
      default:
        return 'Not Started';
    }
  };

  if (isLoading) {
    return <div className="text-gray-600">Loading repositories...</div>;
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Repositories</h1>
          <p className="mt-1 text-sm text-gray-600">
            Manage your code repositories and indexing
          </p>
        </div>
        <Button onClick={() => setShowAddForm(true)}>
          <Plus className="w-4 h-4 mr-2" />
          Add Repository
        </Button>
      </div>

      {/* Add Repository Form */}
      {showAddForm && (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-medium text-gray-900 mb-4">Add New Repository</h2>
          <form onSubmit={handleCreateRepo} className="space-y-4">
            <div>
              <label htmlFor="name" className="block text-sm font-medium text-gray-700">
                Repository Name
              </label>
              <input
                type="text"
                id="name"
                required
                className="mt-1 block w-full border border-gray-300 rounded-md px-3 py-2 shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                value={newRepo.name}
                onChange={(e) => setNewRepo({ ...newRepo, name: e.target.value })}
                placeholder="my-repo"
              />
            </div>
            <div>
              <label htmlFor="url" className="block text-sm font-medium text-gray-700">
                Git URL
              </label>
              <input
                type="url"
                id="url"
                required
                className="mt-1 block w-full border border-gray-300 rounded-md px-3 py-2 shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                value={newRepo.url}
                onChange={(e) => setNewRepo({ ...newRepo, url: e.target.value })}
                placeholder="https://github.com/user/repo.git"
              />
            </div>
            <div className="flex space-x-3">
              <Button
                type="submit"
                disabled={createRepoMutation.isPending}
              >
                {createRepoMutation.isPending ? 'Adding...' : 'Add Repository'}
              </Button>
              <Button
                type="button"
                variant="secondary"
                onClick={() => setShowAddForm(false)}
              >
                Cancel
              </Button>
            </div>
          </form>
        </div>
      )}

      {/* Repositories List */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        <div className="divide-y divide-gray-200">
          {repos?.map((repo) => (
            <div key={repo.id} className="p-6">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-4">
                  <div className="flex-shrink-0">
                    <GitBranch className="w-6 h-6 text-gray-400" />
                  </div>
                  <div>
                    <div className="flex items-center space-x-2">
                      <h3 className="text-lg font-medium text-gray-900">{repo.name}</h3>
                      <a
                        href={repo.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-gray-400 hover:text-gray-600"
                      >
                        <ExternalLink className="w-4 h-4" />
                      </a>
                    </div>
                    <div className="mt-1 flex items-center space-x-4 text-sm text-gray-500">
                      <span>{repo.url}</span>
                      {repo.last_indexed_at && (
                        <span className="flex items-center">
                          <Clock className="w-4 h-4 mr-1" />
                          Last indexed: {new Date(repo.last_indexed_at).toLocaleDateString()}
                        </span>
                      )}
                    </div>
                    {repo.indexing_error && (
                      <div className="mt-1 text-sm text-red-600">
                        Error: {repo.indexing_error}
                      </div>
                    )}
                  </div>
                </div>
                <div className="flex items-center space-x-4">
                  <div className="flex items-center space-x-2">
                    {getStatusIcon(repo.indexing_status)}
                    <span className="text-sm text-gray-600">{getStatusText(repo.indexing_status)}</span>
                  </div>
                  <div className="flex items-center space-x-2">
                    <Link to={`/repositories/${repo.id}`}>
                      <Button variant="secondary" size="sm">
                        View Details
                      </Button>
                    </Link>
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => handleReindex(repo.id)}
                      disabled={reindexMutation.isPending || repo.indexing_status === 'in_progress'}
                    >
                      <RefreshCw className="w-4 h-4" />
                    </Button>
                    <Button
                      variant="danger"
                      size="sm"
                      onClick={() => handleDeleteRepo(repo.id)}
                      disabled={deleteRepoMutation.isPending}
                    >
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  </div>
                </div>
              </div>
            </div>
          ))}
          {(!repos || repos.length === 0) && (
            <div className="p-6 text-center text-gray-500">
              No repositories yet. Add your first repository to get started.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
