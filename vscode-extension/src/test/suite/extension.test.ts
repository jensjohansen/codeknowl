/*
File: vscode-extension/src/test/suite/extension.test.ts
Purpose: Minimal integration tests validating command registration and extension activation.
Product/business importance: Prevents shipping an extension that loads but does not expose expected commands.

Copyright (c) 2026 John K Johansen
License: MIT (see LICENSE)
*/

import * as assert from 'assert';
import * as vscode from 'vscode';

suite('CodeKnowl Extension Test Suite', () => {
  test('Command is registered', async () => {
    const ext = vscode.extensions.getExtension('codeknowl.codeknowl');
    assert.ok(ext, 'Expected CodeKnowl extension to be present');
    await ext?.activate();

    const cmds = await vscode.commands.getCommands(true);
    assert.ok(cmds.includes('codeknowl.ask'), 'Expected codeknowl.ask to be registered');
    assert.ok(cmds.includes('codeknowl.selectRepo'), 'Expected codeknowl.selectRepo to be registered');
    assert.ok(cmds.includes('codeknowl.indexWorkspace'), 'Expected codeknowl.indexWorkspace to be registered');
    assert.ok(cmds.includes('codeknowl.explainCurrentFile'), 'Expected codeknowl.explainCurrentFile to be registered');
    assert.ok(cmds.includes('codeknowl.whereDefined'), 'Expected codeknowl.whereDefined to be registered');
    assert.ok(cmds.includes('codeknowl.whatCalls'), 'Expected codeknowl.whatCalls to be registered');
  });
});
