/**
 * Repository detail page for CodeKnowl Web UI
 * 
 * Why this exists:
 * - Detailed repository management for operators
 * - Supports Milestone 9 requirements for repo lifecycle management
 * - Shows indexing status and repository-specific information
 */

import React from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, GitBranch, RefreshCw, Calendar, FileText, AlertCircle } from 'lucide-react';
import { repositoryApi, indexingApi } from '../utils/api';
import { Button } from '../components/Button';
import type { Repository, IndexingJob } from '../types/api';

export function RepositoryDetailPage() {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();

  const { data: repo, isLoading: repoLoading } = useQuery({
    queryKey: ['repository', id],
    queryFn: () => repositoryApi.get(id!),
    enabled: !!id,
  });

  const { data: jobs, isLoading: jobsLoading } = useQuery({
    queryKey: ['repository-jobs', id],
    queryFn: () => indexingApi.listJobs(id!),
    enabled: !!id,
  });

  const reindexMutation = useMutation({
    mutationFn: () => repositoryApi.reindex(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['repository', id] });
      queryClient.invalidateQueries({ queryKey: ['repository-jobs', id] });
    },
  });

  const handleReindex = () => {
    reindexMutation.mutate();
  };

  if (repoLoading || jobsLoading) {
    return <div className="text-gray-600">Loading repository details...</div>;
  }

  if (!repo) {
    return <div className="text-gray-600">Repository not found</div>;
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center space-x-4">
        <Link to="/repositories">
          <Button variant="ghost" size="sm">
            <ArrowLeft className="w-4 h-4" />
          </Button>
        </Link>
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">{repo.name}</h1>
          <p className="text-sm text-gray-600">{repo.url}</p>
        </div>
      </div>

      {/* Repository Info */}
      <div className="bg-white rounded-lg shadow">
        <div className="px-6 py-4 border-b border-gray-200">
          <h2 className="text-lg font-medium text-gray-900">Repository Information</h2>
        </div>
        <div className="p-6">
          <dl className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <dt className="text-sm font-medium text-gray-500">Status</dt>
              <dd className="mt-1 text-sm text-gray-900 capitalize">{repo.indexing_status}</dd>
            </div>
            <div>
              <dt className="text-sm font-medium text-gray-500">Created</dt>
              <dd className="mt-1 text-sm text-gray-900">
                {new Date(repo.created_at).toLocaleDateString()}
              </dd>
            </div>
            <div>
              <dt className="text-sm font-medium text-gray-500">Last Updated</dt>
              <dd className="mt-1 text-sm text-gray-900">
                {new Date(repo.updated_at).toLocaleDateString()}
              </dd>
            </div>
            <div>
              <dt className="text-sm font-medium text-gray-500">Last Indexed</dt>
              <dd className="mt-1 text-sm text-gray-900">
                {repo.last_indexed_at 
                  ? new Date(repo.last_indexed_at).toLocaleDateString()
                  : 'Never'
                }
              </dd>
            </div>
          </dl>
          
          {repo.indexing_error && (
            <div className="mt-4 p-3 bg-red-50 rounded-md">
              <div className="flex">
                <AlertCircle className="h-5 w-5 text-red-400" />
                <div className="ml-3">
                  <h3 className="text-sm font-medium text-red-800">Indexing Error</h3>
                  <div className="mt-2 text-sm text-red-700">
                    {repo.indexing_error}
                  </div>
                </div>
              </div>
            </div>
          )}
          
          <div className="mt-6">
            <Button
              onClick={handleReindex}
              disabled={reindexMutation.isPending || repo.indexing_status === 'in_progress'}
            >
              <RefreshCw className="w-4 h-4 mr-2" />
              {reindexMutation.isPending ? 'Starting...' : 'Reindex Repository'}
            </Button>
          </div>
        </div>
      </div>

      {/* Indexing History */}
      <div className="bg-white rounded-lg shadow">
        <div className="px-6 py-4 border-b border-gray-200">
          <h2 className="text-lg font-medium text-gray-900">Indexing History</h2>
        </div>
        <div className="divide-y divide-gray-200">
          {jobs?.map((job) => (
            <div key={job.id} className="px-6 py-4">
              <div className="flex items-center justify-between">
                <div>
                  <div className="flex items-center space-x-2">
                    <div className={`w-2 h-2 rounded-full ${
                      job.status === 'completed' ? 'bg-green-400' :
                      job.status === 'running' ? 'bg-yellow-400' :
                      job.status === 'failed' ? 'bg-red-400' :
                      'bg-gray-400'
                    }`} />
                    <span className="text-sm font-medium text-gray-900 capitalize">
                      {job.status}
                    </span>
                  </div>
                  <div className="mt-1 text-sm text-gray-500">
                    Created: {new Date(job.created_at).toLocaleString()}
                  </div>
                  {job.started_at && (
                    <div className="text-sm text-gray-500">
                      Started: {new Date(job.started_at).toLocaleString()}
                    </div>
                  )}
                  {job.completed_at && (
                    <div className="text-sm text-gray-500">
                      Completed: {new Date(job.completed_at).toLocaleString()}
                    </div>
                  )}
                  {job.progress && (
                    <div className="mt-2">
                      <div className="text-sm text-gray-600">{job.progress.stage}</div>
                      <div className="mt-1 bg-gray-200 rounded-full h-2">
                        <div
                          className="bg-blue-600 h-2 rounded-full"
                          style={{
                            width: `${(job.progress.completed / job.progress.total) * 100}%`
                          }}
                        />
                      </div>
                      <div className="text-xs text-gray-500 mt-1">
                        {job.progress.completed} / {job.progress.total}
                      </div>
                    </div>
                  )}
                  {job.error && (
                    <div className="mt-2 text-sm text-red-600">
                      Error: {job.error}
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}
          {(!jobs || jobs.length === 0) && (
            <div className="px-6 py-4 text-center text-gray-500">
              No indexing jobs yet
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
