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
  });
});
