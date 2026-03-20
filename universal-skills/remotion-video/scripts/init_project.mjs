#!/usr/bin/env node
/*
Copy the starter template into a target directory.
File uses .mjs extension so ESM import/export works regardless of the
parent project's "type" setting in package.json.

Usage:
  node scripts/init_project.mjs <target-dir>
*/

import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const templateDir = path.resolve(__dirname, '..', 'assets', 'starter-template');

async function copyDir(source, destination) {
  await fs.mkdir(destination, {recursive: true});
  const entries = await fs.readdir(source, {withFileTypes: true});
  for (const entry of entries) {
    const sourcePath = path.join(source, entry.name);
    const destPath = path.join(destination, entry.name);
    if (entry.isDirectory()) {
      await copyDir(sourcePath, destPath);
    } else {
      await fs.copyFile(sourcePath, destPath);
    }
  }
}

async function main() {
  const targetDir = process.argv[2];
  if (!targetDir) {
    throw new Error('Missing target directory. Usage: node scripts/init_project.mjs <target-dir>');
  }

  const resolvedTarget = path.resolve(process.cwd(), targetDir);
  await copyDir(templateDir, resolvedTarget);
  console.log(`Starter template copied to: ${resolvedTarget}`);
}

main().catch((error) => {
  console.error(`ERROR: ${error instanceof Error ? error.message : String(error)}`);
  process.exit(1);
});
