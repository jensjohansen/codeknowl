import * as path from 'path';

import Mocha from 'mocha';

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
