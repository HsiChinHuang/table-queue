// launcher/config_loader.ts
// Load .env + docs/config.yaml, merge and validate

import * as fs from 'fs';
import * as yaml from 'js-yaml';

export interface Config {
  env: Record<string, string>;
  yaml: Record<string, unknown>;
  effective: Record<string, unknown>;
}

const REQUIRED_ENV_VARS = ['PLATFORM', 'API_TOKEN', 'REPO_ID'];

const ENV_OVERRIDABLE: Record<string, string> = {
  MAX_SLOTS: 'slots.max',
  LAUNCHER_AUTO_RESTART: 'launcher.auto_restart',
  LAUNCHER_MAX_RESTART_ATTEMPTS: 'launcher.max_restart_attempts',
  ORCH_SCHEDULED_RESTART: 'orchestrator.scheduled_restart_enabled',
  ORCH_RESTART_HOURS: 'orchestrator.scheduled_restart_hours',
  ORCH_RESTART_TRANSITIONS: 'orchestrator.scheduled_restart_transitions',
};

export async function loadConfig(): Promise<Config> {
  const env = loadEnv('.env');
  const yamlConfig = loadYaml('docs/config.yaml');
  const effective = mergeConfig(env, yamlConfig);

  validateRequired(env);
  validateEnvPermissions('.env');

  return { env, yaml: yamlConfig, effective };
}

function loadEnv(filePath: string): Record<string, string> {
  if (!fs.existsSync(filePath)) {
    throw new Error(`.env not found at ${filePath}`);
  }

  const content = fs.readFileSync(filePath, 'utf-8');
  const env: Record<string, string> = {};

  for (const line of content.split('\n')) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;

    const eqIndex = trimmed.indexOf('=');
    if (eqIndex === -1) {
      console.warn(`Malformed line in .env: ${line}`);
      continue;
    }

    const key = trimmed.slice(0, eqIndex).trim();
    let value = trimmed.slice(eqIndex + 1).trim();

    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }

    env[key] = value;
  }

  return env;
}

function loadYaml(filePath: string): Record<string, unknown> {
  if (!fs.existsSync(filePath)) {
    console.warn(`${filePath} not found, using defaults`);
    return {};
  }
  const content = fs.readFileSync(filePath, 'utf-8');
  return (yaml.load(content) as Record<string, unknown>) || {};
}

function mergeConfig(
  env: Record<string, string>,
  yamlConfig: Record<string, unknown>
): Record<string, unknown> {
  const effective: Record<string, unknown> = { ...yamlConfig };

  for (const [envKey, yamlKey] of Object.entries(ENV_OVERRIDABLE)) {
    const envValue = env[envKey];
    if (envValue !== undefined) {
      setNestedValue(effective, yamlKey, parseEnvValue(envValue));
    }
  }

  return effective;
}

function setNestedValue(
  obj: Record<string, unknown>,
  path: string,
  value: unknown
): void {
  const parts = path.split('.');
  let current: Record<string, unknown> = obj;
  for (let i = 0; i < parts.length - 1; i++) {
    const part = parts[i];
    if (part === undefined) {
      throw new Error(`Invalid config path segment at index ${i}: ${path}`);
    }
    if (typeof current[part] !== 'object' || current[part] === null) {
      current[part] = {};
    }
    current = current[part] as Record<string, unknown>;
  }
  const lastPart = parts[parts.length - 1];
  if (lastPart === undefined) {
    throw new Error(`Empty config path: ${path}`);
  }
  current[lastPart] = value;
}

function parseEnvValue(value: string): unknown {
  if (value === 'true') return true;
  if (value === 'false') return false;
  if (/^-?\d+$/.test(value)) return parseInt(value, 10);
  if (/^-?\d+\.\d+$/.test(value)) return parseFloat(value);
  return value;
}

function validateRequired(env: Record<string, string>): void {
  const missing = REQUIRED_ENV_VARS.filter((key) => !env[key]);
  if (missing.length > 0) {
    throw new Error(`Missing required env vars: ${missing.join(', ')}`);
  }
}

function validateEnvPermissions(filePath: string): void {
  // Windows uses a different permission model; skip the check.
  if (process.platform === 'win32') {
    return;
  }
  const stats = fs.statSync(filePath);
  const mode = stats.mode & 0o777;
  if (mode !== 0o600) {
    console.warn(`.env permissions are ${mode.toString(8)}, expected 600`);
  }
}