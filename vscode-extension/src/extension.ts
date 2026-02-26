import * as vscode from 'vscode';

type AskResponse = {
  answer: string;
  citations?: Array<{
    file_path: string;
    start_line?: number;
    end_line?: number;
    note?: string;
  }>;
};

function getBackendBaseUrl(): string {
  const cfg = vscode.workspace.getConfiguration('codeknowl');
  const raw = cfg.get<string>('backendBaseUrl');
  return (raw ?? 'http://localhost:8000').replace(/\/+$/, '');
}

async function askBackend(question: string, baseUrl: string): Promise<AskResponse> {
  const res = await fetch(`${baseUrl}/qa/ask`, {
    method: 'POST',
    headers: {
      'content-type': 'application/json'
    },
    body: JSON.stringify({ question })
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Backend request failed: ${res.status} ${res.statusText}: ${text}`);
  }

  return (await res.json()) as AskResponse;
}

export function activate(context: vscode.ExtensionContext): void {
  const output = vscode.window.createOutputChannel('CodeKnowl');

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
    output.appendLine(`[ask] baseUrl=${baseUrl}`);
    output.appendLine(`[ask] question=${question}`);
    output.show(true);

    try {
      const resp = await askBackend(question, baseUrl);
      output.appendLine('');
      output.appendLine(resp.answer);

      if (resp.citations && resp.citations.length > 0) {
        output.appendLine('');
        output.appendLine('Citations:');
        for (const c of resp.citations) {
          const range = c.start_line && c.end_line ? `:${c.start_line}-${c.end_line}` : '';
          output.appendLine(`- ${c.file_path}${range}`);
        }
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      vscode.window.showErrorMessage(`CodeKnowl: ${msg}`);
      output.appendLine('');
      output.appendLine(`[error] ${msg}`);
    }
  });

  context.subscriptions.push(output, askCmd);
}

export function deactivate(): void {
  // no-op
}
