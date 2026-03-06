/**
 * Dashboard page for CodeKnowl Web UI
 * 
 * Why this exists:
 * - Overview page for operators and non-engineers
 * - Supports Milestone 9 requirements for admin UI
 * - Shows system status and quick actions
 */

import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { GitBranch, MessageSquare, Activity, AlertCircle, CheckCircle, Clock } from 'lucide-react';
import { repositoryApi, indexingApi, healthApi } from '../utils/api';
import { Button } from '../components/Button';

export function DashboardPage() {
  const { data: repos, isLoading: reposLoading } = useQuery({
    queryKey: ['repositories'],
    queryFn: repositoryApi.list,
  });

  const { data: jobs, isLoading: jobsLoading } = useQuery({
    queryKey: ['indexing-jobs'],
    queryFn: () => indexingApi.listJobs(),
  });

  const { data: health, isLoading: healthLoading } = useQuery({
    queryKey: ['health'],
    queryFn: healthApi.status,
  });

  const stats = {
    totalRepos: repos?.length || 0,
    healthyRepos: repos?.filter(r => r.indexing_status === 'completed').length || 0,
    activeJobs: jobs?.filter(j => j.status === 'running').length || 0,
    systemHealth: health?.status || 'unknown',
  };

  if (reposLoading || jobsLoading || healthLoading) {
    return <div className="text-gray-600">Loading dashboard...</div>;
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-semibold text-gray-900">Dashboard</h1>
        <p className="mt-1 text-sm text-gray-600">
          Overview of your CodeKnowl instance
        </p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <GitBranch className="h-8 w-8 text-blue-600" />
            </div>
            <div className="ml-4">
              <div className="text-2xl font-bold text-gray-900">{stats.totalRepos}</div>
              <div className="text-sm text-gray-500">Total Repositories</div>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <CheckCircle className="h-8 w-8 text-green-600" />
            </div>
            <div className="ml-4">
              <div className="text-2xl font-bold text-gray-900">{stats.healthyRepos}</div>
              <div className="text-sm text-gray-500">Indexed Repositories</div>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <Activity className="h-8 w-8 text-yellow-600" />
            </div>
            <div className="ml-4">
              <div className="text-2xl font-bold text-gray-900">{stats.activeJobs}</div>
              <div className="text-sm text-gray-500">Active Indexing Jobs</div>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center">
            <div className="flex-shrink-0">
              {health?.status === 'healthy' ? (
                <CheckCircle className="h-8 w-8 text-green-600" />
              ) : (
                <AlertCircle className="h-8 w-8 text-red-600" />
              )}
            </div>
            <div className="ml-4">
              <div className="text-2xl font-bold text-gray-900 capitalize">{stats.systemHealth}</div>
              <div className="text-sm text-gray-500">System Health</div>
            </div>
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="bg-white rounded-lg shadow">
        <div className="px-6 py-4 border-b border-gray-200">
          <h2 className="text-lg font-medium text-gray-900">Quick Actions</h2>
        </div>
        <div className="p-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Link to="/repositories">
              <Button className="w-full">
                <GitBranch className="w-4 h-4 mr-2" />
                Manage Repositories
              </Button>
            </Link>
            <Link to="/qa">
              <Button variant="secondary" className="w-full">
                <MessageSquare className="w-4 h-4 mr-2" />
                Ask Questions
              </Button>
            </Link>
            <Link to="/indexing">
              <Button variant="secondary" className="w-full">
                <Activity className="w-4 h-4 mr-2" />
                View Indexing Status
              </Button>
            </Link>
          </div>
        </div>
      </div>

      {/* Recent Activity */}
      <div className="bg-white rounded-lg shadow">
        <div className="px-6 py-4 border-b border-gray-200">
          <h2 className="text-lg font-medium text-gray-900">Recent Indexing Jobs</h2>
        </div>
        <div className="divide-y divide-gray-200">
          {jobs?.slice(0, 5).map((job) => (
            <div key={job.id} className="px-6 py-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  <div className={`w-2 h-2 rounded-full ${
                    job.status === 'completed' ? 'bg-green-400' :
                    job.status === 'running' ? 'bg-yellow-400' :
                    job.status === 'failed' ? 'bg-red-400' :
                    'bg-gray-400'
                  }`} />
                  <div>
                    <div className="text-sm font-medium text-gray-900">
                      {job.repo_id}
                    </div>
                    <div className="text-sm text-gray-500">
                      {new Date(job.created_at).toLocaleString()}
                    </div>
                  </div>
                </div>
                <div className="text-sm text-gray-500 capitalize">
                  {job.status}
                </div>
              </div>
            </div>
          ))}
          {(!jobs || jobs.length === 0) && (
            <div className="px-6 py-4 text-center text-gray-500">
              No recent indexing jobs
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
