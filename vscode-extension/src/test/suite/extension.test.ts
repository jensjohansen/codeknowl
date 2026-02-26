import * as assert from 'assert';
import * as vscode from 'vscode';

suite('CodeKnowl Extension Test Suite', () => {
  test('Command is registered', async () => {
    const ext = vscode.extensions.getExtension('codeknowl.codeknowl');
    assert.ok(ext, 'Expected CodeKnowl extension to be present');
    await ext?.activate();

    const cmds = await vscode.commands.getCommands(true);
    assert.ok(cmds.includes('codeknowl.ask'), 'Expected codeknowl.ask to be registered');
  });
});
