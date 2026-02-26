/*
File: vscode-extension/src/test/runTest.ts
Purpose: Test runner bootstrap for VS Code extension integration tests.
Product/business importance: Ensures the extension loads and key command wiring does not regress.

Copyright (c) 2026 John K Johansen
License: MIT (see LICENSE)
*/

import * as path from 'path';

import { runTests } from '@vscode/test-electron';

async function main(): Promise<void> {
  try {
    const extensionDevelopmentPath = path.resolve(__dirname, '../../');
    const extensionTestsPath = path.resolve(__dirname, './suite/index.js');

    await runTests({ extensionDevelopmentPath, extensionTestsPath });
  } catch (err) {
    console.error('Failed to run tests');
    process.exit(1);
  }
}

void main();
