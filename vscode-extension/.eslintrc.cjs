/*
File: vscode-extension/.eslintrc.cjs
Purpose: ESLint configuration for the VS Code extension TypeScript code.
Product/business importance: Enforces consistent linting rules and prevents quality regressions in the IDE component.

Copyright (c) 2026 John K Johansen
License: MIT (see LICENSE)
*/

/* eslint-disable @typescript-eslint/no-var-requires */

module.exports = {
  root: true,
  parser: '@typescript-eslint/parser',
  parserOptions: {
    project: './tsconfig.json',
    tsconfigRootDir: __dirname
  },
  plugins: ['@typescript-eslint'],
  extends: [
    'eslint:recommended',
    'plugin:@typescript-eslint/recommended'
  ],
  env: {
    node: true,
    es2022: true
  },
  ignorePatterns: ['dist/**'],
  rules: {
    '@typescript-eslint/no-floating-promises': 'error'
  }
};
