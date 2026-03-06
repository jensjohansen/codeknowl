/**
 * Q&A page for CodeKnowl Web UI
 * 
 * Why this exists:
 * - Q&A interface for non-engineers and operators
 * - Supports Milestone 9 requirements for Q&A with citations
 * - Provides web-based access to code understanding
 */

import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { MessageSquare, Send, ExternalLink, Loader2 } from 'lucide-react';
import { repositoryApi, qaApi } from '../utils/api';
import { Button } from '../components/Button';
import type { Repository, QAResponse } from '../types/api';

export function QAPage() {
  const [question, setQuestion] = useState('');
  const [selectedRepo, setSelectedRepo] = useState('');
  const [response, setResponse] = useState<QAResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [streamingText, setStreamingText] = useState('');

  const { data: repos } = useQuery({
    queryKey: ['repositories'],
    queryFn: repositoryApi.list,
  });

  const handleAsk = async (useStream = false) => {
    if (!question.trim()) return;

    setIsLoading(true);
    setResponse(null);
    setStreamingText('');

    try {
      if (useStream) {
        // Streaming response
        await qaApi.stream(
          { question, repo_id: selectedRepo || undefined },
          (chunk) => {
            setStreamingText(prev => prev + chunk);
          }
        );
        
        // Get final response for citations
        const finalResponse = await qaApi.ask({ question, repo_id: selectedRepo || undefined });
        setResponse(finalResponse);
      } else {
        // Non-streaming response
        const result = await qaApi.ask({ question, repo_id: selectedRepo || undefined });
        setResponse(result);
      }
    } catch (error) {
      console.error('Error asking question:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    handleAsk(true); // Use streaming by default
  };

  const displayText = streamingText || response?.answer || '';

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-semibold text-gray-900">Code Q&A</h1>
        <p className="mt-1 text-sm text-gray-600">
          Ask questions about your code with AI-powered answers and citations
        </p>
      </div>

      {/* Question Form */}
      <div className="bg-white rounded-lg shadow p-6">
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="repo" className="block text-sm font-medium text-gray-700 mb-2">
              Repository (optional)
            </label>
            <select
              id="repo"
              className="block w-full border border-gray-300 rounded-md px-3 py-2 shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
              value={selectedRepo}
              onChange={(e) => setSelectedRepo(e.target.value)}
            >
              <option value="">All Repositories</option>
              {repos?.map((repo) => (
                <option key={repo.id} value={repo.id}>
                  {repo.name}
                </option>
              ))}
            </select>
          </div>
          
          <div>
            <label htmlFor="question" className="block text-sm font-medium text-gray-700 mb-2">
              Your Question
            </label>
            <textarea
              id="question"
              rows={4}
              className="block w-full border border-gray-300 rounded-md px-3 py-2 shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
              placeholder="e.g., What does the authenticate function do? How is the database connection established?"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              disabled={isLoading}
            />
          </div>
          
          <div className="flex space-x-3">
            <Button
              type="submit"
              disabled={isLoading || !question.trim()}
            >
              {isLoading ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Thinking...
                </>
              ) : (
                <>
                  <Send className="w-4 h-4 mr-2" />
                  Ask
                </>
              )}
            </Button>
            {response && (
              <Button
                type="button"
                variant="secondary"
                onClick={() => {
                  setResponse(null);
                  setStreamingText('');
                }}
              >
                Clear
              </Button>
            )}
          </div>
        </form>
      </div>

      {/* Response */}
      {(displayText || isLoading) && (
        <div className="bg-white rounded-lg shadow">
          <div className="px-6 py-4 border-b border-gray-200">
            <h2 className="text-lg font-medium text-gray-900 flex items-center">
              <MessageSquare className="w-5 h-5 mr-2" />
              Answer
            </h2>
          </div>
          <div className="p-6">
            <div className="prose max-w-none">
              {displayText ? (
                <div className="whitespace-pre-wrap text-gray-800">
                  {displayText}
                  {isLoading && <span className="animate-pulse">▊</span>}
                </div>
              ) : (
                <div className="text-gray-500 italic">
                  {isLoading ? 'Thinking...' : 'No answer yet'}
                </div>
              )}
            </div>
            
            {/* Citations */}
            {response?.citations && response.citations.length > 0 && (
              <div className="mt-6 pt-6 border-t border-gray-200">
                <h3 className="text-sm font-medium text-gray-900 mb-3">Citations</h3>
                <div className="space-y-3">
                  {response.citations.map((citation, index) => (
                    <div key={index} className="bg-gray-50 rounded-lg p-4">
                      <div className="flex items-center justify-between mb-2">
                        <div className="text-sm font-medium text-gray-900">
                          {citation.file_path}:{citation.line_start}
                          {citation.line_end && `-${citation.line_end}`}
                        </div>
                        <div className="text-xs text-gray-500">
                          Score: {citation.score.toFixed(2)}
                        </div>
                      </div>
                      <pre className="text-sm text-gray-700 bg-gray-100 rounded p-2 overflow-x-auto">
                        <code>{citation.snippet}</code>
                      </pre>
                    </div>
                  ))}
                </div>
              </div>
            )}
            
            {/* Response Metadata */}
            {response && (
              <div className="mt-6 pt-6 border-t border-gray-200">
                <div className="flex items-center justify-between text-sm text-gray-500">
                  <div>Model: {response.model_used}</div>
                  <div>Response time: {response.response_time_ms}ms</div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Tips */}
      <div className="bg-blue-50 rounded-lg p-6">
        <h3 className="text-sm font-medium text-blue-900 mb-2">Tips for better answers:</h3>
        <ul className="text-sm text-blue-800 space-y-1">
          <li>• Be specific about what you want to know</li>
          <li>• Mention function names, classes, or files if applicable</li>
          <li>• Select a specific repository if you know where the code is located</li>
          <li>• Ask about implementation details, patterns, or architecture</li>
        </ul>
      </div>
    </div>
  );
}
