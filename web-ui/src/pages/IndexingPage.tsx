/**
 * Indexing status page for CodeKnowl Web UI
 * 
 * Why this exists:
 * - Indexing status monitoring for operators
 * - Supports Milestone 9 requirements for viewing indexing status
 * - Provides detailed job tracking and progress monitoring
 */

import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { Activity, Clock, CheckCircle, AlertCircle, XCircle, Loader2 } from 'lucide-react';
import { indexingApi } from '../utils/api';
import type { IndexingJob } from '../types/api';

export function IndexingPage() {
  const { data: jobs, isLoading } = useQuery({
    queryKey: ['indexing-jobs'],
    queryFn: () => indexingApi.listJobs(),
  });

  const getStatusIcon = (status: IndexingJob['status']) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="w-5 h-5 text-green-500" />;
      case 'running':
        return <Loader2 className="w-5 h-5 text-yellow-500 animate-spin" />;
      case 'failed':
        return <AlertCircle className="w-5 h-5 text-red-500" />;
      default:
        return <XCircle className="w-5 h-5 text-gray-400" />;
    }
  };

  const getStatusText = (status: IndexingJob['status']) => {
    switch (status) {
      case 'completed':
        return 'Completed';
      case 'running':
        return 'Running';
      case 'failed':
        return 'Failed';
      default:
        return 'Pending';
    }
  };

  const getDuration = (job: IndexingJob) => {
    if (!job.started_at) return '-';
    
    const start = new Date(job.started_at);
    const end = job.completed_at ? new Date(job.completed_at) : new Date();
    const duration = end.getTime() - start.getTime();
    
    if (duration < 60000) {
      return `${Math.floor(duration / 1000)}s`;
    } else if (duration < 3600000) {
      return `${Math.floor(duration / 60000)}m ${Math.floor((duration % 60000) / 1000)}s`;
    } else {
      return `${Math.floor(duration / 3600000)}h ${Math.floor((duration % 3600000) / 60000)}m`;
    }
  };

  const stats = {
    total: jobs?.length || 0,
    running: jobs?.filter(j => j.status === 'running').length || 0,
    completed: jobs?.filter(j => j.status === 'completed').length || 0,
    failed: jobs?.filter(j => j.status === 'failed').length || 0,
  };

  if (isLoading) {
    return <div className="text-gray-600">Loading indexing status...</div>;
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-semibold text-gray-900">Indexing Status</h1>
        <p className="mt-1 text-sm text-gray-600">
          Monitor repository indexing jobs and progress
        </p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <Activity className="h-8 w-8 text-blue-600" />
            </div>
            <div className="ml-4">
              <div className="text-2xl font-bold text-gray-900">{stats.total}</div>
              <div className="text-sm text-gray-500">Total Jobs</div>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <Loader2 className="h-8 w-8 text-yellow-600 animate-spin" />
            </div>
            <div className="ml-4">
              <div className="text-2xl font-bold text-gray-900">{stats.running}</div>
              <div className="text-sm text-gray-500">Running</div>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <CheckCircle className="h-8 w-8 text-green-600" />
            </div>
            <div className="ml-4">
              <div className="text-2xl font-bold text-gray-900">{stats.completed}</div>
              <div className="text-sm text-gray-500">Completed</div>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <AlertCircle className="h-8 w-8 text-red-600" />
            </div>
            <div className="ml-4">
              <div className="text-2xl font-bold text-gray-900">{stats.failed}</div>
              <div className="text-sm text-gray-500">Failed</div>
            </div>
          </div>
        </div>
      </div>

      {/* Jobs List */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200">
          <h2 className="text-lg font-medium text-gray-900">Recent Jobs</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Repository
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Progress
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Created
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Duration
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {jobs?.map((job) => (
                <tr key={job.id}>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                    {job.repo_id}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex items-center">
                      {getStatusIcon(job.status)}
                      <span className="ml-2 text-sm text-gray-900">
                        {getStatusText(job.status)}
                      </span>
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {job.progress ? (
                      <div>
                        <div className="text-xs text-gray-900">{job.progress.stage}</div>
                        <div className="mt-1 bg-gray-200 rounded-full h-2 w-24">
                          <div
                            className="bg-blue-600 h-2 rounded-full"
                            style={{
                              width: `${(job.progress.completed / job.progress.total) * 100}%`
                            }}
                          />
                        </div>
                        <div className="text-xs text-gray-500">
                          {job.progress.completed} / {job.progress.total}
                        </div>
                      </div>
                    ) : (
                      '-'
                    )}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    <div className="flex items-center">
                      <Clock className="w-4 h-4 mr-1" />
                      {new Date(job.created_at).toLocaleString()}
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {getDuration(job)}
                  </td>
                </tr>
              ))}
              {(!jobs || jobs.length === 0) && (
                <tr>
                  <td colSpan={5} className="px-6 py-4 text-center text-gray-500">
                    No indexing jobs found
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
