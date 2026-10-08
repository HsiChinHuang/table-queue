#!/usr/bin/env tsx
// scripts/platform.ts
// Unified CLI for GitHub / GitLab issue operations.
//
// Usage:
//   npx tsx scripts/platform.ts <resource> <action> [options]
//
// Resources / actions:
//   issue create --title <t> --body <b> --labels <l1,l2>
//   issue get <number>
//   issue update <number> [--title <t>] [--body <b> | --body-file <path>] [--labels <l1,l2>]
//     --body-file: read the body from a UTF-8 file. PREFERRED for long bodies:
//     on Windows hosts, command-line args over ~8KB fail (CreateProcessA limit),
//     and bodies starting with `--` (e.g. markdown frontmatter) are rejected
//     by the flag parser. Use --body-file for groomed issue bodies.
//   issue close <number>
//   issue reopen <number>
//   issue comment <number> --body <b>
//   issue latest-comment <number>
//   issue list [--labels <l1,l2>] [--state open|closed|all]
//   label add <number> --labels <l1,l2>
//   label remove <number> --label <l>
//   label set <number> --labels <l1,l2>
//
// Env vars (from .env):
//   PLATFORM   github | gitlab
//   API_TOKEN  PAT
//   REPO_ID    owner/repo OR https://host/owner/repo(.git)? OR git@host:owner/repo(.git)?
//   API_URL    (optional) self-hosted base URL
//
// Output: JSON to stdout on success. Errors on stderr, non-zero exit.
//
// Exit codes:
//   0 - success
//   1 - runtime error (HTTP non-2xx, network, config invalid)
//   2 - usage error (bad arguments)

import * as fs from 'fs';

// ============================================================
// Types
// ============================================================

interface PlatformConfig {
  platform: 'github' | 'gitlab';
  token: string;
  apiUrl: string;
  owner: string;
  repo: string;
}

interface Issue {
  number: number;
  title: string;
  state: 'open' | 'closed';
  labels: string[];
  updated_at: string;
}

interface Comment {
  author: string;
  body: string;
  created_at: string;
}

// ============================================================
// .env loading
// ============================================================

function loadEnvFile(filePath: string): Record<string, string> {
  if (!fs.existsSync(filePath)) {
    console.error(`ERROR: .env not found at ${filePath}`);
    process.exit(1);
  }
  const content = fs.readFileSync(filePath, 'utf-8');
  const env: Record<string, string> = {};
  for (const line of content.split('\n')) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;
    const eq = trimmed.indexOf('=');
    if (eq === -1) continue;
    const key = trimmed.slice(0, eq).trim();
    let value = trimmed.slice(eq + 1).trim();
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

// ============================================================
// REPO_ID normalization
// ============================================================

function normalizeRepoId(input: string): { owner: string; repo: string } {
  const simpleMatch = input.match(/^([^/\s:]+)\/([^/\s]+?)(?:\.git)?$/);
  if (simpleMatch && simpleMatch[1] !== undefined && simpleMatch[2] !== undefined) {
    return { owner: simpleMatch[1], repo: simpleMatch[2] };
  }

  try {
    const url = new URL(input);
    const parts = url.pathname
      .replace(/^\//, '')
      .replace(/\.git$/, '')
      .split('/');
    if (parts.length >= 2 && parts[0] !== undefined && parts[1] !== undefined) {
      return { owner: parts[0], repo: parts[1] };
    }
  } catch {
    // Not a URL
  }

  const sshMatch = input.match(/^git@[^:]+:([^/]+)\/([^/]+?)(?:\.git)?$/);
  if (sshMatch && sshMatch[1] !== undefined && sshMatch[2] !== undefined) {
    return { owner: sshMatch[1], repo: sshMatch[2] };
  }

  console.error(`ERROR: cannot parse REPO_ID: "${input}"`);
  console.error('Expected one of:');
  console.error('  owner/repo');
  console.error('  https://host/owner/repo(.git)?');
  console.error('  git@host:owner/repo(.git)?');
  process.exit(1);
}

// ============================================================
// Config loading
// ============================================================

function loadConfig(): PlatformConfig {
  const env = loadEnvFile('.env');
  const platform = env['PLATFORM'];
  const token = env['API_TOKEN'];
  const repoId = env['REPO_ID'];
  const apiUrlEnv = env['API_URL'];

  if (platform !== 'github' && platform !== 'gitlab') {
    console.error(`ERROR: PLATFORM must be "github" or "gitlab" (got "${platform ?? ''}")`);
    process.exit(1);
  }
  if (!token) {
    console.error('ERROR: API_TOKEN is required in .env');
    process.exit(1);
  }
  if (!repoId) {
    console.error('ERROR: REPO_ID is required in .env');
    process.exit(1);
  }

  const { owner, repo } = normalizeRepoId(repoId);
  const apiUrl =
    apiUrlEnv ??
    (platform === 'github'
      ? 'https://api.github.com'
      : 'https://gitlab.com/api/v4');

  return { platform, token, apiUrl, owner, repo };
}

// ============================================================
// HTTP helper
// ============================================================

interface HttpResponse {
  status: number;
  data: unknown;
}

async function request(
  method: string,
  url: string,
  headers: Record<string, string>,
  body?: unknown
): Promise<HttpResponse> {
  const init: RequestInit = {
    method,
    headers: {
      ...headers,
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
  };
  if (body !== undefined) {
    init.body = JSON.stringify(body);
  }

  const response = await fetch(url, init);
  const text = await response.text();

  let data: unknown = null;
  if (text.length > 0) {
    try {
      data = JSON.parse(text);
    } catch {
      data = text;
    }
  }

  return { status: response.status, data };
}

function authHeaders(config: PlatformConfig): Record<string, string> {
  if (config.platform === 'github') {
    return {
      Authorization: `Bearer ${config.token}`,
      'X-GitHub-Api-Version': '2022-11-28',
      'User-Agent': 'pi-agent-orchestrator',
    };
  }
  return {
    'PRIVATE-TOKEN': config.token,
  };
}

// ============================================================
// Endpoint bases
// ============================================================

function githubBase(config: PlatformConfig): string {
  return `${config.apiUrl}/repos/${config.owner}/${config.repo}`;
}

function gitlabBase(config: PlatformConfig): string {
  const projectPath = encodeURIComponent(`${config.owner}/${config.repo}`);
  return `${config.apiUrl}/projects/${projectPath}`;
}

// ============================================================
// Issue normalization
// ============================================================

function normalizeGitHubIssue(raw: Record<string, unknown>): Issue {
  const labelsRaw = raw['labels'];
  let labels: string[] = [];
  if (Array.isArray(labelsRaw)) {
    labels = labelsRaw
      .map((l) => {
        if (typeof l === 'string') return l;
        if (typeof l === 'object' && l !== null && 'name' in l) {
          return String((l as { name?: unknown }).name ?? '');
        }
        return '';
      })
      .filter((l) => l.length > 0);
  }
  return {
    number: Number(raw['number']),
    title: String(raw['title'] ?? ''),
    state: (raw['state'] === 'closed' ? 'closed' : 'open'),
    labels,
    updated_at: String(raw['updated_at'] ?? ''),
  };
}

function normalizeGitLabIssue(raw: Record<string, unknown>): Issue {
  const stateRaw = String(raw['state'] ?? '');
  return {
    number: Number(raw['iid']),
    title: String(raw['title'] ?? ''),
    state: stateRaw === 'closed' ? 'closed' : 'open',
    labels: Array.isArray(raw['labels']) ? (raw['labels'] as string[]) : [],
    updated_at: String(raw['updated_at'] ?? ''),
  };
}

function normalizeIssue(
  config: PlatformConfig,
  raw: Record<string, unknown>
): Issue {
  return config.platform === 'github'
    ? normalizeGitHubIssue(raw)
    : normalizeGitLabIssue(raw);
}

function normalizeComment(
  config: PlatformConfig,
  raw: Record<string, unknown>
): Comment {
  if (config.platform === 'github') {
    const user = raw['user'] as { login?: string } | undefined;
    return {
      author: String(user?.login ?? ''),
      body: String(raw['body'] ?? ''),
      created_at: String(raw['created_at'] ?? ''),
    };
  }
  const author = raw['author'] as { username?: string } | undefined;
  return {
    author: String(author?.username ?? ''),
    body: String(raw['body'] ?? ''),
    created_at: String(raw['created_at'] ?? ''),
  };
}

// ============================================================
// Actions
// ============================================================

async function createIssue(
  config: PlatformConfig,
  title: string,
  body: string,
  labels: string[]
): Promise<Issue> {
  const url =
    config.platform === 'github'
      ? `${githubBase(config)}/issues`
      : `${gitlabBase(config)}/issues`;
  const payload =
    config.platform === 'github'
      ? { title, body, labels }
      : { title, description: body, labels: labels.join(',') };

  const { status, data } = await request('POST', url, authHeaders(config), payload);
  if (status < 200 || status >= 300) {
    throw new Error(`createIssue failed: HTTP ${status}: ${JSON.stringify(data)}`);
  }
  return normalizeIssue(config, data as Record<string, unknown>);
}

async function getIssue(config: PlatformConfig, number: number): Promise<Issue> {
  const url =
    config.platform === 'github'
      ? `${githubBase(config)}/issues/${number}`
      : `${gitlabBase(config)}/issues/${number}`;
  const { status, data } = await request('GET', url, authHeaders(config));
  if (status < 200 || status >= 300) {
    throw new Error(`getIssue failed: HTTP ${status}: ${JSON.stringify(data)}`);
  }
  return normalizeIssue(config, data as Record<string, unknown>);
}

async function updateIssue(
  config: PlatformConfig,
  number: number,
  title: string | null,
  body: string | null,
  labels: string[] | null
): Promise<Issue> {
  // Only send fields that were explicitly provided. Missing fields are
  // left untouched by the API.
  const url =
    config.platform === 'github'
      ? `${githubBase(config)}/issues/${number}`
      : `${gitlabBase(config)}/issues/${number}`;

  const payload: Record<string, unknown> = {};
  if (config.platform === 'github') {
    if (title !== null) payload['title'] = title;
    if (body !== null) payload['body'] = body;
    if (labels !== null) payload['labels'] = labels;
  } else {
    if (title !== null) payload['title'] = title;
    if (body !== null) payload['description'] = body;
    if (labels !== null) payload['labels'] = labels.join(',');
  }

  if (Object.keys(payload).length === 0) {
    // Nothing to update; return the current state without an API call.
    return getIssue(config, number);
  }

  const { status, data } = await request('PATCH', url, authHeaders(config), payload);
  if (status < 200 || status >= 300) {
    throw new Error(`updateIssue failed: HTTP ${status}: ${JSON.stringify(data)}`);
  }
  return normalizeIssue(config, data as Record<string, unknown>);
}

async function setIssueState(
  config: PlatformConfig,
  number: number,
  state: 'open' | 'closed'
): Promise<Issue> {
  const url =
    config.platform === 'github'
      ? `${githubBase(config)}/issues/${number}`
      : `${gitlabBase(config)}/issues/${number}`;
  const payload =
    config.platform === 'github'
      ? { state }
      : { state_event: state === 'closed' ? 'close' : 'reopen' };

  const { status, data } = await request('PATCH', url, authHeaders(config), payload);
  if (status < 200 || status >= 300) {
    throw new Error(`setIssueState failed: HTTP ${status}: ${JSON.stringify(data)}`);
  }
  return normalizeIssue(config, data as Record<string, unknown>);
}

async function postComment(
  config: PlatformConfig,
  number: number,
  body: string
): Promise<Comment> {
  const url =
    config.platform === 'github'
      ? `${githubBase(config)}/issues/${number}/comments`
      : `${gitlabBase(config)}/issues/${number}/notes`;
  const payload = { body };

  const { status, data } = await request('POST', url, authHeaders(config), payload);
  if (status < 200 || status >= 300) {
    throw new Error(`postComment failed: HTTP ${status}: ${JSON.stringify(data)}`);
  }
  return normalizeComment(config, data as Record<string, unknown>);
}

async function getLatestComment(
  config: PlatformConfig,
  number: number
): Promise<Comment | null> {
  const url =
    config.platform === 'github'
      ? `${githubBase(config)}/issues/${number}/comments?per_page=100`
      : `${gitlabBase(config)}/issues/${number}/notes?per_page=100&sort=asc`;
  const { status, data } = await request('GET', url, authHeaders(config));
  if (status < 200 || status >= 300) {
    throw new Error(`getLatestComment failed: HTTP ${status}: ${JSON.stringify(data)}`);
  }
  if (!Array.isArray(data) || data.length === 0) {
    return null;
  }
  const last = data[data.length - 1] as Record<string, unknown>;
  return normalizeComment(config, last);
}

async function listIssues(
  config: PlatformConfig,
  labels: string[] | null,
  state: 'open' | 'closed' | 'all'
): Promise<Issue[]> {
  const params = new URLSearchParams();
  params.set('per_page', '100');

  if (config.platform === 'github') {
    if (state !== 'all') params.set('state', state);
    if (labels && labels.length > 0) params.set('labels', labels.join(','));
  } else {
    const glState = state === 'open' ? 'opened' : state;
    if (state !== 'all') params.set('state', glState);
    if (labels && labels.length > 0) params.set('labels', labels.join(','));
  }

  const base =
    config.platform === 'github'
      ? `${githubBase(config)}/issues`
      : `${gitlabBase(config)}/issues`;
  const url = `${base}?${params.toString()}`;

  const { status, data } = await request('GET', url, authHeaders(config));
  if (status < 200 || status >= 300) {
    throw new Error(`listIssues failed: HTTP ${status}: ${JSON.stringify(data)}`);
  }
  if (!Array.isArray(data)) {
    return [];
  }

  const filtered = (data as Record<string, unknown>[]).filter((raw) => {
    if (config.platform !== 'github') return true;
    return !('pull_request' in raw);
  });

  return filtered.map((raw) => normalizeIssue(config, raw));
}

async function addLabels(
  config: PlatformConfig,
  number: number,
  labels: string[]
): Promise<Issue> {
  if (config.platform === 'github') {
    const url = `${githubBase(config)}/issues/${number}/labels`;
    const { status, data } = await request('POST', url, authHeaders(config), {
      labels,
    });
    if (status < 200 || status >= 300) {
      throw new Error(`addLabels failed: HTTP ${status}: ${JSON.stringify(data)}`);
    }
  } else {
    const url = `${gitlabBase(config)}/issues/${number}`;
    const { status, data } = await request('PUT', url, authHeaders(config), {
      add_labels: labels.join(','),
    });
    if (status < 200 || status >= 300) {
      throw new Error(`addLabels failed: HTTP ${status}: ${JSON.stringify(data)}`);
    }
  }
  return getIssue(config, number);
}

async function removeLabel(
  config: PlatformConfig,
  number: number,
  label: string
): Promise<Issue> {
  if (config.platform === 'github') {
    const url = `${githubBase(config)}/issues/${number}/labels/${encodeURIComponent(label)}`;
    const { status, data } = await request('DELETE', url, authHeaders(config));
    if (status < 200 || status >= 300) {
      throw new Error(`removeLabel failed: HTTP ${status}: ${JSON.stringify(data)}`);
    }
  } else {
    const url = `${gitlabBase(config)}/issues/${number}`;
    const { status, data } = await request('PUT', url, authHeaders(config), {
      remove_labels: label,
    });
    if (status < 200 || status >= 300) {
      throw new Error(`removeLabel failed: HTTP ${status}: ${JSON.stringify(data)}`);
    }
  }
  return getIssue(config, number);
}

async function setLabels(
  config: PlatformConfig,
  number: number,
  labels: string[]
): Promise<Issue> {
  const url =
    config.platform === 'github'
      ? `${githubBase(config)}/issues/${number}/labels`
      : `${gitlabBase(config)}/issues/${number}`;
  const payload =
    config.platform === 'github' ? { labels } : { labels: labels.join(',') };

  const { status, data } = await request('PUT', url, authHeaders(config), payload);
  if (status < 200 || status >= 300) {
    throw new Error(`setLabels failed: HTTP ${status}: ${JSON.stringify(data)}`);
  }
  return getIssue(config, number);
}

// ============================================================
// CLI parsing
// ============================================================

function parseFlags(args: string[]): {
  positional: string[];
  flags: Record<string, string>;
} {
  const positional: string[] = [];
  const flags: Record<string, string> = {};
  let i = 0;
  while (i < args.length) {
    const a = args[i];
    if (a === undefined) break;
    if (a.startsWith('--')) {
      const key = a.slice(2);
      const next = args[i + 1];
      if (next === undefined || next.startsWith('--')) {
        console.error(`ERROR: flag --${key} requires a value`);
        process.exit(2);
      }
      flags[key] = next;
      i += 2;
    } else {
      positional.push(a);
      i += 1;
    }
  }
  return { positional, flags };
}

function usage(): never {
  console.error('Usage: npx tsx scripts/platform.ts <resource> <action> [options]');
  console.error('');
  console.error('Resources / actions:');
  console.error('  issue create --title <t> --body <b> --labels <l1,l2>');
  console.error('  issue get <number>');
  console.error('  issue update <number> [--title <t>] [--body <b> | --body-file <path>] [--labels <l1,l2>]');
  console.error('  issue close <number>');
  console.error('  issue reopen <number>');
  console.error('  issue comment <number> --body <b>');
  console.error('  issue latest-comment <number>');
  console.error('  issue list [--labels <l1,l2>] [--state open|closed|all]');
  console.error('  label add <number> --labels <l1,l2>');
  console.error('  label remove <number> --label <l>');
  console.error('  label set <number> --labels <l1,l2>');
  process.exit(2);
}

function printJson(data: unknown): void {
  console.log(JSON.stringify(data, null, 2));
}

// ============================================================
// Main
// ============================================================

async function main(): Promise<void> {
  const args = process.argv.slice(2);
  if (args.length < 2) {
    usage();
  }

  const resource = args[0];
  const action = args[1];
  if (resource === undefined || action === undefined) {
    usage();
  }

  const rest = args.slice(2);
  const { positional, flags } = parseFlags(rest);
  const config = loadConfig();

  try {
    if (resource === 'issue' && action === 'create') {
      const title = flags['title'];
      const body = flags['body'] ?? '';
      const labels = (flags['labels'] ?? '').split(',').map((s) => s.trim()).filter(Boolean);
      if (!title) {
        console.error('ERROR: --title is required for issue create');
        process.exit(2);
      }
      const issue = await createIssue(config, title, body, labels);
      printJson(issue);
      return;
    }

    if (resource === 'issue' && action === 'get') {
      const num = positional[0];
      if (!num || !/^[0-9]+$/.test(num)) {
        console.error('ERROR: issue get requires a numeric issue number');
        process.exit(2);
      }
      const issue = await getIssue(config, parseInt(num, 10));
      printJson(issue);
      return;
    }

    if (resource === 'issue' && action === 'update') {
      const num = positional[0];
      if (!num || !/^[0-9]+$/.test(num)) {
        console.error('ERROR: issue update requires a numeric issue number');
        process.exit(2);
      }
      const title = flags['title'] ?? null;
      let body: string | null = flags['body'] ?? null;
      if (flags['body-file'] !== undefined) {
        if (body !== null) {
          console.error('ERROR: use either --body or --body-file, not both');
          process.exit(2);
        }
        const bodyPath = flags['body-file'];
        if (!fs.existsSync(bodyPath)) {
          console.error(`ERROR: --body-file path does not exist: ${bodyPath}`);
          process.exit(2);
        }
        body = fs.readFileSync(bodyPath, 'utf8');
      }
      const labelsRaw = flags['labels'];
      const labels = labelsRaw !== undefined
        ? labelsRaw.split(',').map((s) => s.trim()).filter(Boolean)
        : null;
      if (title === null && body === null && labels === null) {
        console.error('ERROR: issue update requires at least one of --title, --body, --body-file, --labels');
        process.exit(2);
      }
      const issue = await updateIssue(config, parseInt(num, 10), title, body, labels);
      printJson(issue);
      return;
    }

    if (resource === 'issue' && action === 'close') {
      const num = positional[0];
      if (!num || !/^[0-9]+$/.test(num)) {
        console.error('ERROR: issue close requires a numeric issue number');
        process.exit(2);
      }
      const issue = await setIssueState(config, parseInt(num, 10), 'closed');
      printJson(issue);
      return;
    }

    if (resource === 'issue' && action === 'reopen') {
      const num = positional[0];
      if (!num || !/^[0-9]+$/.test(num)) {
        console.error('ERROR: issue reopen requires a numeric issue number');
        process.exit(2);
      }
      const issue = await setIssueState(config, parseInt(num, 10), 'open');
      printJson(issue);
      return;
    }

    if (resource === 'issue' && action === 'comment') {
      const num = positional[0];
      const body = flags['body'];
      if (!num || !/^[0-9]+$/.test(num)) {
        console.error('ERROR: issue comment requires a numeric issue number');
        process.exit(2);
      }
      if (!body) {
        console.error('ERROR: --body is required for issue comment');
        process.exit(2);
      }
      const comment = await postComment(config, parseInt(num, 10), body);
      printJson(comment);
      return;
    }

    if (resource === 'issue' && action === 'latest-comment') {
      const num = positional[0];
      if (!num || !/^[0-9]+$/.test(num)) {
        console.error('ERROR: issue latest-comment requires a numeric issue number');
        process.exit(2);
      }
      const comment = await getLatestComment(config, parseInt(num, 10));
      printJson(comment);
      return;
    }

    if (resource === 'issue' && action === 'list') {
      const labelsRaw = flags['labels'];
      const labels = labelsRaw
        ? labelsRaw.split(',').map((s) => s.trim()).filter(Boolean)
        : null;
      const stateRaw = flags['state'] ?? 'open';
      if (stateRaw !== 'open' && stateRaw !== 'closed' && stateRaw !== 'all') {
        console.error(`ERROR: --state must be open, closed, or all (got "${stateRaw}")`);
        process.exit(2);
      }
      const issues = await listIssues(config, labels, stateRaw);
      printJson(issues);
      return;
    }

    if (resource === 'label' && action === 'add') {
      const num = positional[0];
      const labelsRaw = flags['labels'];
      if (!num || !/^[0-9]+$/.test(num)) {
        console.error('ERROR: label add requires a numeric issue number');
        process.exit(2);
      }
      if (!labelsRaw) {
        console.error('ERROR: --labels is required for label add');
        process.exit(2);
      }
      const labels = labelsRaw.split(',').map((s) => s.trim()).filter(Boolean);
      const issue = await addLabels(config, parseInt(num, 10), labels);
      printJson(issue);
      return;
    }

    if (resource === 'label' && action === 'remove') {
      const num = positional[0];
      const label = flags['label'];
      if (!num || !/^[0-9]+$/.test(num)) {
        console.error('ERROR: label remove requires a numeric issue number');
        process.exit(2);
      }
      if (!label) {
        console.error('ERROR: --label is required for label remove');
        process.exit(2);
      }
      const issue = await removeLabel(config, parseInt(num, 10), label);
      printJson(issue);
      return;
    }

    if (resource === 'label' && action === 'set') {
      const num = positional[0];
      const labelsRaw = flags['labels'] ?? '';
      if (!num || !/^[0-9]+$/.test(num)) {
        console.error('ERROR: label set requires a numeric issue number');
        process.exit(2);
      }
      const labels = labelsRaw.split(',').map((s) => s.trim()).filter(Boolean);
      const issue = await setLabels(config, parseInt(num, 10), labels);
      printJson(issue);
      return;
    }

    usage();
  } catch (err) {
    console.error(`ERROR: ${(err as Error).message}`);
    process.exit(1);
  }
}

main();