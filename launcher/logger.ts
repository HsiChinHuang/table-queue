// launcher/logger.ts
// Launcher's own logger (separate from Orchestrator logs)

import * as fs from 'fs';
import * as path from 'path';

const LOG_PATH = 'docs/log/launcher.log';

function format(level: string, message: string): string {
  const ts = new Date().toISOString();
  return `[${ts}] [${level}] ${message}\n`;
}

function write(level: string, message: string): void {
  const line = format(level, message);

  if (level === 'ERROR') {
    process.stderr.write(line);
  } else {
    process.stdout.write(line);
  }

  const dir = path.dirname(LOG_PATH);
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
  fs.appendFileSync(LOG_PATH, line);
}

export const logger = {
  info: (msg: string) => write('INFO', msg),
  warn: (msg: string) => write('WARN', msg),
  error: (msg: string, err?: unknown) => {
    write('ERROR', msg);
    if (err) {
      write(
        'ERROR',
        err instanceof Error ? err.stack || err.message : String(err)
      );
    }
  },
};