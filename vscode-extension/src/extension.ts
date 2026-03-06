/*
File: vscode-extension/src/extension.ts
Purpose: VS Code extension entrypoint registering commands and wiring UI to the CodeKnowl backend.
Product/business importance: Enables the Milestone 2 IDE experience for asking questions from within VS Code.

Copyright (c) 2026 John K Johansen
License: MIT (see LICENSE)
*/

import * as vscode from 'vscode';
import { execFile } from 'child_process';
import { promisify } from 'util';

type RepoRecord = {
  repo_id: string;
  local_path: string;
  accepted_branch: string;
  preferred_remote?: string | null;
  created_at_utc: string;
};

type Citation = {
  file_path: string;
  start_line?: number;
  end_line?: number;
  note?: string;
};

type AskResponse = {
  answer: string;
  citations?: Citation[];
};

type IndexResponse = {
  run_id: string;
  repo_id: string;
  status: string;
  started_at_utc: string;
  finished_at_utc?: string;
  error?: string;
  head_commit?: string;
};

type RepoStatusResponse = {
  repo_id: string;
  local_path: string;
  created_at_utc: string;
  latest_index_run?: {
    run_id: string;
    status: string;
    started_at_utc: string;
    finished_at_utc?: string;
    error?: string;
    head_commit?: string;
  };
};

function getBackendBaseUrl(): string {
  const configuration = vscode.workspace.getConfiguration('codeknowl');
  const rawBaseUrl = configuration.get<string>('backendBaseUrl');
  return (rawBaseUrl ?? 'http://localhost:8000').replace(/\/+$/, '');
}

function getBackendApiKey(): string | undefined {
  const configuration = vscode.workspace.getConfiguration('codeknowl');
  const rawApiKey = configuration.get<string>('apiKey');
  const trimmed = (rawApiKey ?? '').trim();
  return trimmed.length > 0 ? trimmed : undefined;
}

function getPrimaryWorkspaceFolder(): vscode.WorkspaceFolder {
  const folders = vscode.workspace.workspaceFolders;
  if (!folders || folders.length === 0) {
    throw new Error('No workspace folder is open');
  }
  return folders[0];
}

function repoIdStateKey(workspacePath: string): string {
  return `repoId:${workspacePath}`;
}

function selectedRepoIdStateKey(workspacePath: string): string {
  return `selectedRepoId:${workspacePath}`;
}

function acceptedBranchStateKey(workspacePath: string): string {
  return `acceptedBranch:${workspacePath}`;
}

function preferredRemoteStateKey(workspacePath: string): string {
  return `preferredRemote:${workspacePath}`;
}

const execFileAsync = promisify(execFile);

async function runGit(repoPath: string, args: string[]): Promise<string> {
  const result = await execFileAsync('git', ['-C', repoPath, ...args]);
  return (result.stdout ?? '').toString().trim();
}

async function listGitRemotes(repoPath: string): Promise<string[]> {
  const out = await runGit(repoPath, ['remote']);
  return out
    .split('\n')
    .map((s) => s.trim())
    .filter((s) => s.length > 0);
}

async function listLocalBranches(repoPath: string): Promise<string[]> {
  const out = await runGit(repoPath, ['for-each-ref', '--format=%(refname:short)', 'refs/heads']);
  return out
    .split('\n')
    .map((s) => s.trim())
    .filter((s) => s.length > 0);
}

async function tryGetRemoteHeadBranch(repoPath: string, remote: string): Promise<string | undefined> {
  try {
    const symbolicReference = await runGit(repoPath, ['symbolic-ref', '--quiet', `refs/remotes/${remote}/HEAD`]);
    const match = symbolicReference.match(new RegExp(`^refs/remotes/${remote}/(.+)$`));
    return match?.[1];
  } catch {
    return undefined;
  }
}

async function getCurrentBranch(repoPath: string): Promise<string> {
  const out = await runGit(repoPath, ['rev-parse', '--abbrev-ref', 'HEAD']);
  return out.length > 0 ? out : 'main';
}

async function discoverAcceptedBranch(repoPath: string, preferredRemote: string | undefined): Promise<string> {
  const remoteDefault = preferredRemote ? await tryGetRemoteHeadBranch(repoPath, preferredRemote) : undefined;
  if (remoteDefault && remoteDefault.trim().length > 0) {
    return remoteDefault.trim();
  }

  let localBranches: string[] = [];
  try {
    localBranches = await listLocalBranches(repoPath);
  } catch {
    localBranches = [];
  }

  if (localBranches.includes('main')) {
    return 'main';
  }
  if (localBranches.includes('master')) {
    return 'master';
  }
  if (localBranches.length > 0) {
    return localBranches[0];
  }
  return await getCurrentBranch(repoPath);
}

type DiscoveredRepoMetadata = {
  acceptedBranch: string;
  preferredRemote?: string;
};

async function discoverAndConfirmRepoMetadata(
  context: vscode.ExtensionContext,
  workspacePath: string
): Promise<DiscoveredRepoMetadata> {
  const acceptedKey = acceptedBranchStateKey(workspacePath);
  const preferredRemoteKey = preferredRemoteStateKey(workspacePath);

  const cachedAccepted = context.workspaceState.get<string>(acceptedKey);
  const cachedPreferredRemote = context.workspaceState.get<string>(preferredRemoteKey);
  if (cachedAccepted && cachedAccepted.length > 0) {
    return {
      acceptedBranch: cachedAccepted,
      preferredRemote: cachedPreferredRemote
    };
  }

  let remotes: string[] = [];
  try {
    remotes = await listGitRemotes(workspacePath);
  } catch {
    remotes = [];
  }

  const preferredRemote =
    cachedPreferredRemote ?? (remotes.includes('origin') ? 'origin' : remotes.length > 0 ? remotes[0] : undefined);

  const discoveredAccepted = await discoverAcceptedBranch(workspacePath, preferredRemote);

  const choice = await vscode.window.showQuickPick(
    [
      {
        label: 'Confirm',
        description: `${discoveredAccepted}${preferredRemote ? ` (remote: ${preferredRemote})` : ''}`,
        value: 'confirm' as const
      },
      {
        label: 'Edit',
        description: 'Adjust accepted branch / preferred remote before onboarding',
        value: 'edit' as const
      }
    ],
    {
      title: 'Confirm repository metadata for CodeKnowl',
      placeHolder: 'CodeKnowl discovered these values from your local git checkout'
    }
  );

  if (!choice) {
    throw new Error('Repo onboarding cancelled');
  }

  let acceptedBranch = discoveredAccepted;
  let finalPreferredRemote = preferredRemote;

  if (choice.value === 'edit') {
    const editedBranch = await vscode.window.showInputBox({
      title: 'Accepted branch',
      prompt: 'Single branch that CodeKnowl should treat as accepted (e.g., main/master/trunk)',
      value: discoveredAccepted
    });
    if (!editedBranch || editedBranch.trim().length === 0) {
      throw new Error('Accepted branch is required');
    }
    acceptedBranch = editedBranch.trim();

    if (remotes.length > 0) {
      const remotePick = await vscode.window.showQuickPick([
        { label: '(none)', description: 'Track local branch head only', value: undefined },
        ...remotes.map((r) => ({ label: r, value: r }))
      ]);

      if (!remotePick) {
        throw new Error('Repo onboarding cancelled');
      }
      finalPreferredRemote = (remotePick as { value: string | undefined }).value;
    } else {
      finalPreferredRemote = undefined;
    }
  }

  await context.workspaceState.update(acceptedKey, acceptedBranch);
  await context.workspaceState.update(preferredRemoteKey, finalPreferredRemote);
  return { acceptedBranch, preferredRemote: finalPreferredRemote };
}

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const apiKey = getBackendApiKey();

  const mergedHeaders = new Headers(init?.headers ?? {});
  if (apiKey) {
    mergedHeaders.set('X-CodeKnowl-Api-Key', apiKey);
  }

  const res = await fetch(url, { ...init, headers: mergedHeaders });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Backend request failed: ${res.status} ${res.statusText}: ${text}`);
  }
  return (await res.json()) as T;
}

async function listRepos(baseUrl: string): Promise<RepoRecord[]> {
  return await fetchJson<RepoRecord[]>(`${baseUrl}/repos`);
}

function normalizePathForComparison(p: string): string {
  return p.replace(/\\/g, '/').replace(/\/+$/, '');
}

async function resolveRepoIdForWorkspace(
  context: vscode.ExtensionContext,
  baseUrl: string,
  workspacePath: string
): Promise<string> {
  const selectedKey = selectedRepoIdStateKey(workspacePath);
  const selected = context.workspaceState.get<string>(selectedKey);
  if (selected && selected.length > 0) {
    return selected;
  }

  const key = repoIdStateKey(workspacePath);
  const cached = context.workspaceState.get<string>(key);
  if (cached && cached.length > 0) {
    return cached;
  }

  const discovered = await discoverAndConfirmRepoMetadata(context, workspacePath);
  const acceptedBranch = discovered.acceptedBranch;
  const preferredRemote = discovered.preferredRemote;

  const repos = await listRepos(baseUrl);
  const normalizedWorkspace = normalizePathForComparison(workspacePath);
  const match = repos.find(
    (r: RepoRecord) =>
      normalizePathForComparison(r.local_path) === normalizedWorkspace && r.accepted_branch === acceptedBranch
  );

  const repo =
    match ??
    (await fetchJson<RepoRecord>(`${baseUrl}/repos`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        local_path: workspacePath,
        accepted_branch: acceptedBranch,
        preferred_remote: preferredRemote
      })
    }));
  await context.workspaceState.update(key, repo.repo_id);
  return repo.repo_id;
}

async function selectRepoForWorkspace(
  context: vscode.ExtensionContext,
  baseUrl: string,
  workspacePath: string
): Promise<string> {
  const repos = await listRepos(baseUrl);
  const normalizedWorkspace = normalizePathForComparison(workspacePath);

  const items = repos
    .map((r: RepoRecord) => {
      const matchesWorkspace = normalizePathForComparison(r.local_path) === normalizedWorkspace;
      const label = `${r.accepted_branch} — ${r.repo_id.slice(0, 8)}`;
      const description = r.local_path;
      const detail = matchesWorkspace ? 'Matches current workspace path' : 'Different local path';
      return { label, description, detail, repo: r };
    })
    .sort((a, b) => {
      const aMatch = a.detail.startsWith('Matches');
      const bMatch = b.detail.startsWith('Matches');
      if (aMatch !== bMatch) {
        return aMatch ? -1 : 1;
      }
      return a.description.localeCompare(b.description);
    });

  const picked = await vscode.window.showQuickPick(items, {
    title: 'Select active CodeKnowl repo for this workspace',
    placeHolder: 'Pick a repo_id to scope CodeKnowl commands'
  });

  if (!picked) {
    throw new Error('Repo selection cancelled');
  }

  const selectedKey = selectedRepoIdStateKey(workspacePath);
  await context.workspaceState.update(selectedKey, picked.repo.repo_id);
  return picked.repo.repo_id;
}

async function getRepoRecordById(baseUrl: string, repoId: string): Promise<RepoRecord | undefined> {
  const repos = await listRepos(baseUrl);
  return repos.find((r: RepoRecord) => r.repo_id === repoId);
}

async function updateStatusBar(
  statusBar: vscode.StatusBarItem,
  context: vscode.ExtensionContext,
  baseUrl: string,
  workspacePath: string
): Promise<void> {
  try {
    const repoId = await resolveRepoIdForWorkspace(context, baseUrl, workspacePath);
    const rec = await getRepoRecordById(baseUrl, repoId);
    const repoShort = repoId.slice(0, 8);
    const branch = rec?.accepted_branch ?? 'unknown';
    statusBar.text = `CodeKnowl: ${repoShort} (${branch})`;
    statusBar.tooltip = `Active CodeKnowl repo_id: ${repoId}`;
    statusBar.show();
  } catch {
    statusBar.text = 'CodeKnowl: (no repo)';
    statusBar.tooltip = 'No active CodeKnowl repository is configured for this workspace';
    statusBar.show();
  }
}

async function indexRepo(baseUrl: string, repoId: string): Promise<IndexResponse> {
  return await fetchJson<IndexResponse>(`${baseUrl}/repos/${encodeURIComponent(repoId)}/index`, {
    method: 'POST'
  });
}

async function repoStatus(baseUrl: string, repoId: string): Promise<RepoStatusResponse> {
  return await fetchJson<RepoStatusResponse>(`${baseUrl}/repos/${encodeURIComponent(repoId)}/status`);
}

async function qaAsk(baseUrl: string, repoId: string, question: string): Promise<AskResponse> {
  return await fetchJson<AskResponse>(`${baseUrl}/repos/${encodeURIComponent(repoId)}/qa/ask`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ question })
  });
}

type ExplainFileResponse = {
  citations?: Citation[];
};

async function qaExplainFile(baseUrl: string, repoId: string, path: string): Promise<ExplainFileResponse> {
  const url = new URL(`${baseUrl}/repos/${encodeURIComponent(repoId)}/qa/explain-file`);
  url.searchParams.set('path', path);
  return await fetchJson<ExplainFileResponse>(url.toString());
}

type QueryWithCitationsResponse = {
  results?: Array<{ citation?: Citation }>;
};

async function qaWhereDefined(baseUrl: string, repoId: string, name: string): Promise<QueryWithCitationsResponse> {
  const url = new URL(`${baseUrl}/repos/${encodeURIComponent(repoId)}/qa/where-defined`);
  url.searchParams.set('name', name);
  return await fetchJson<QueryWithCitationsResponse>(url.toString());
}

async function qaWhatCalls(baseUrl: string, repoId: string, callee: string): Promise<QueryWithCitationsResponse> {
  const url = new URL(`${baseUrl}/repos/${encodeURIComponent(repoId)}/qa/what-calls`);
  url.searchParams.set('callee', callee);
  return await fetchJson<QueryWithCitationsResponse>(url.toString());
}

function formatCitation(c: Citation): string {
  const start = c.start_line;
  const end = c.end_line;
  const range = start && end ? `:${start}-${end}` : start ? `:${start}` : '';
  return `${c.file_path}${range}`;
}

async function pickAndOpenCitation(citations: Citation[], workspaceFolder: vscode.WorkspaceFolder): Promise<void> {
  if (citations.length === 0) {
    return;
  }

  const items = citations.map((c: Citation) => ({
    label: formatCitation(c),
    description: c.note,
    citation: c
  }));

  const picked = await vscode.window.showQuickPick(items, {
    title: 'CodeKnowl: Citations',
    placeHolder: 'Select a citation to open'
  });

  if (!picked) {
    return;
  }

  const c = picked.citation;
  const uri = vscode.Uri.joinPath(workspaceFolder.uri, c.file_path);
  const doc = await vscode.workspace.openTextDocument(uri);
  const editor = await vscode.window.showTextDocument(doc, { preview: true });

  const line = Math.max((c.start_line ?? 1) - 1, 0);
  const pos = new vscode.Position(line, 0);
  editor.selection = new vscode.Selection(pos, pos);
  editor.revealRange(new vscode.Range(pos, pos), vscode.TextEditorRevealType.InCenter);
}

export function activate(context: vscode.ExtensionContext): void {
  const output = vscode.window.createOutputChannel('CodeKnowl');
  const statusBar = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
  statusBar.command = 'codeknowl.selectRepo';
  statusBar.text = 'CodeKnowl: ...';
  statusBar.tooltip = 'Select active CodeKnowl repo';
  statusBar.show();

  try {
    const baseUrl = getBackendBaseUrl();
    const workspaceFolder = getPrimaryWorkspaceFolder();
    void updateStatusBar(statusBar, context, baseUrl, workspaceFolder.uri.fsPath);
  } catch {
    // ignore
  }

  const selectRepoCmd = vscode.commands.registerCommand('codeknowl.selectRepo', async () => {
    const baseUrl = getBackendBaseUrl();
    const workspaceFolder = getPrimaryWorkspaceFolder();
    const workspacePath = workspaceFolder.uri.fsPath;
    output.appendLine(`[select-repo] baseUrl=${baseUrl}`);
    output.appendLine(`[select-repo] workspace=${workspacePath}`);
    output.show(true);

    try {
      const repoId = await selectRepoForWorkspace(context, baseUrl, workspacePath);
      output.appendLine(`[select-repo] selected_repo_id=${repoId}`);
      void vscode.window.showInformationMessage(`CodeKnowl: active repo set to ${repoId}`);
      await updateStatusBar(statusBar, context, baseUrl, workspacePath);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      void vscode.window.showErrorMessage(`CodeKnowl: ${msg}`);
      output.appendLine('');
      output.appendLine(`[error] ${msg}`);
    }
  });

  const indexWorkspaceCmd = vscode.commands.registerCommand('codeknowl.indexWorkspace', async () => {
    const baseUrl = getBackendBaseUrl();
    const workspaceFolder = getPrimaryWorkspaceFolder();
    const workspacePath = workspaceFolder.uri.fsPath;
    output.appendLine(`[index] baseUrl=${baseUrl}`);
    output.appendLine(`[index] workspace=${workspacePath}`);
    output.show(true);

    try {
      const repoId = await resolveRepoIdForWorkspace(context, baseUrl, workspacePath);
      output.appendLine(`[index] repo_id=${repoId}`);
      await updateStatusBar(statusBar, context, baseUrl, workspacePath);
      const indexResponse = await indexRepo(baseUrl, repoId);
      output.appendLine(`[index] status=${indexResponse.status}`);
      if (indexResponse.error) {
        output.appendLine(`[index] error=${indexResponse.error}`);
      }
      const status = await repoStatus(baseUrl, repoId);
      const headCommit = status.latest_index_run?.head_commit;
      if (headCommit) {
        output.appendLine(`[index] head_commit=${headCommit}`);
      }
      void vscode.window.showInformationMessage(`CodeKnowl: index ${indexResponse.status}`);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      void vscode.window.showErrorMessage(`CodeKnowl: ${msg}`);
      output.appendLine('');
      output.appendLine(`[error] ${msg}`);
    }
  });

  const askCmd = vscode.commands.registerCommand('codeknowl.ask', async () => {
    const question = await vscode.window.showInputBox({
      title: 'CodeKnowl: Ask',
      prompt: 'Ask a question about the currently indexed repository',
      ignoreFocusOut: true
    });

    if (!question || question.trim().length === 0) {
      return;
    }

    const baseUrl = getBackendBaseUrl();
    const workspaceFolder = getPrimaryWorkspaceFolder();
    const workspacePath = workspaceFolder.uri.fsPath;
    output.appendLine(`[ask] baseUrl=${baseUrl}`);
    output.appendLine(`[ask] workspace=${workspacePath}`);
    output.appendLine(`[ask] question=${question}`);
    output.show(true);

    try {
      const repoId = await resolveRepoIdForWorkspace(context, baseUrl, workspacePath);
      output.appendLine(`[ask] repo_id=${repoId}`);
      await updateStatusBar(statusBar, context, baseUrl, workspacePath);
      const askResponse = await qaAsk(baseUrl, repoId, question);
      output.appendLine('');
      output.appendLine(askResponse.answer);

      if (askResponse.citations && askResponse.citations.length > 0) {
        output.appendLine('');
        output.appendLine('Citations:');
        for (const c of askResponse.citations) {
          output.appendLine(`- ${formatCitation(c)}`);
        }

        await pickAndOpenCitation(askResponse.citations, workspaceFolder);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      void vscode.window.showErrorMessage(`CodeKnowl: ${msg}`);
      output.appendLine('');
      output.appendLine(`[error] ${msg}`);
    }
  });

  const explainCurrentFileCmd = vscode.commands.registerCommand('codeknowl.explainCurrentFile', async () => {
    const editor = vscode.window.activeTextEditor;
    if (!editor) {
      void vscode.window.showErrorMessage('CodeKnowl: No active editor');
      return;
    }
    const baseUrl = getBackendBaseUrl();
    const workspaceFolder = getPrimaryWorkspaceFolder();
    const workspacePath = workspaceFolder.uri.fsPath;
    const relPath = vscode.workspace.asRelativePath(editor.document.uri, false);

    output.appendLine(`[explain] baseUrl=${baseUrl}`);
    output.appendLine(`[explain] file=${relPath}`);
    output.show(true);

    try {
      const repoId = await resolveRepoIdForWorkspace(context, baseUrl, workspacePath);
      await updateStatusBar(statusBar, context, baseUrl, workspacePath);
      const explainFileResponse = await qaExplainFile(baseUrl, repoId, relPath);
      const citations = explainFileResponse.citations ?? [];
      if (citations.length === 0) {
        void vscode.window.showInformationMessage('CodeKnowl: no citations returned');
        return;
      }
      await pickAndOpenCitation(citations, workspaceFolder);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      void vscode.window.showErrorMessage(`CodeKnowl: ${msg}`);
      output.appendLine('');
      output.appendLine(`[error] ${msg}`);
    }
  });

  const whereDefinedCmd = vscode.commands.registerCommand('codeknowl.whereDefined', async () => {
    const name = await vscode.window.showInputBox({
      title: 'CodeKnowl: Where Defined',
      prompt: 'Symbol name',
      ignoreFocusOut: true
    });
    if (!name || name.trim().length === 0) {
      return;
    }
    const baseUrl = getBackendBaseUrl();
    const workspaceFolder = getPrimaryWorkspaceFolder();
    const workspacePath = workspaceFolder.uri.fsPath;

    output.appendLine(`[where-defined] baseUrl=${baseUrl}`);
    output.appendLine(`[where-defined] symbol=${name}`);
    output.show(true);

    try {
      const repoId = await resolveRepoIdForWorkspace(context, baseUrl, workspacePath);
      await updateStatusBar(statusBar, context, baseUrl, workspacePath);
      const whereDefinedResponse = await qaWhereDefined(baseUrl, repoId, name);
      const citations = (whereDefinedResponse.results ?? [])
        .map((r: { citation?: Citation }) => r.citation)
        .filter((c: Citation | undefined): c is Citation => Boolean(c));
      if (citations.length === 0) {
        void vscode.window.showInformationMessage('CodeKnowl: no matches');
        return;
      }
      await pickAndOpenCitation(citations, workspaceFolder);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      void vscode.window.showErrorMessage(`CodeKnowl: ${msg}`);
      output.appendLine('');
      output.appendLine(`[error] ${msg}`);
    }
  });

  const whatCallsCmd = vscode.commands.registerCommand('codeknowl.whatCalls', async () => {
    const name = await vscode.window.showInputBox({
      title: 'CodeKnowl: What Calls',
      prompt: 'Callee name',
      ignoreFocusOut: true
    });
    if (!name || name.trim().length === 0) {
      return;
    }
    const baseUrl = getBackendBaseUrl();
    const workspaceFolder = getPrimaryWorkspaceFolder();
    const workspacePath = workspaceFolder.uri.fsPath;

    output.appendLine(`[what-calls] baseUrl=${baseUrl}`);
    output.appendLine(`[what-calls] callee=${name}`);
    output.show(true);

    try {
      const repoId = await resolveRepoIdForWorkspace(context, baseUrl, workspacePath);
      await updateStatusBar(statusBar, context, baseUrl, workspacePath);
      const whatCallsResponse = await qaWhatCalls(baseUrl, repoId, name);
      const citations = (whatCallsResponse.results ?? [])
        .map((r: { citation?: Citation }) => r.citation)
        .filter((c: Citation | undefined): c is Citation => Boolean(c));
      if (citations.length === 0) {
        void vscode.window.showInformationMessage('CodeKnowl: no matches');
        return;
      }
      await pickAndOpenCitation(citations, workspaceFolder);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      void vscode.window.showErrorMessage(`CodeKnowl: ${msg}`);
      output.appendLine('');
      output.appendLine(`[error] ${msg}`);
    }
  });

  context.subscriptions.push(
    output,
    statusBar,
    askCmd,
    selectRepoCmd,
    indexWorkspaceCmd,
    explainCurrentFileCmd,
    whereDefinedCmd,
    whatCallsCmd
  );
}

export function deactivate(): void {
  // no-op
}
