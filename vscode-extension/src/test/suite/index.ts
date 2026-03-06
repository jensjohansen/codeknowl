/*
File: vscode-extension/src/test/suite/index.ts
Purpose: Mocha test suite entrypoint used by @vscode/test-electron.
Product/business importance: Provides automated verification for the extension MVP in CI.

Copyright (c) 2026 John K Johansen
License: MIT (see LICENSE)
*/

import * as path from 'path';

import Mocha from 'mocha';

/**
 * Run the test suite via Mocha.
 *
 * Why this exists:
 * - VS Code test runner expects this entrypoint to execute the tests.
 */
export function run(): Promise<void> {
  return new Promise((resolve, reject) => {
    const mocha = new Mocha({
      ui: 'tdd',
      color: true
    });

    const testsRoot = path.resolve(__dirname, '.');

    mocha.addFile(path.resolve(testsRoot, './extension.test'));

    try {
      mocha.run((failures: number) => {
        if (failures > 0) {
          reject(new Error(`${failures} tests failed.`));
        } else {
          resolve();
        }
      });
    } catch (err) {
      reject(err);
    }
  });
}
