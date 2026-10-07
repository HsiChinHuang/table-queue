// extensions/merge_orchestrator.ts
// Merge flow: transactional merge + verification

import * as fs from 'fs';
import { execSync } from 'child_process';
import { readJsonFile } from './schema_validator.js';

// ============================================================
// Type definitions
// ============================================================

export interface MergeContext {
  issue_id: string;
  branch: string;
  title: string;
  verifier_pass_at: string;
  test_command: string;
}

export interface MergeResult {
  success: boolean;
  step: number;
  state: string;
  merge_sha: string | null;
  error: string | null;
}

export interface MergeCheckpoint {
  schema_version: string;
  issue_id: string;
  step: number;
  state: string;
  timestamp: string;
  pre_merge_sha: string | null;
  merge_sha: string | null;
  test_result: {
    total: number;
    passed: number;
    failed: number;
  } | null;
}

// ============================================================
// Merge flow
// ============================================================

export async function executeMerge(ctx: MergeContext): Promise<MergeResult> {
  const cp: MergeCheckpoint = {
    schema_version: '1.0',
    issue_id: ctx.issue_id,
    step: 1,
    state: 'fetched',
    timestamp: new Date().toISOString(),
    pre_merge_sha: null,
    merge_sha: null,
    test_result: null,
  };

  try {
    // Step 1: fetch origin
    execSync('git fetch origin', { stdio: 'pipe' });
    writeCheckpoint(cp);

    // Step 2: reset main to origin
    execSync('git checkout main', { stdio: 'pipe' });
    execSync('git reset --hard origin/main', { stdio: 'pipe' });
    cp.pre_merge_sha = getCurrentSha();
    cp.step = 2;
    cp.state = 'reset';
    cp.timestamp = new Date().toISOString();
    writeCheckpoint(cp);

    // Step 3: dry-run merge
    try {
      execSync(`git merge --no-commit --no-ff ${ctx.branch}`, {
        stdio: 'pipe',
      });
      execSync('git merge --abort', { stdio: 'pipe' });
    } catch {
      execSync('git merge --abort', { stdio: 'pipe' });
      return {
        success: false,
        step: 3,
        state: 'conflict',
        merge_sha: null,
        error: 'Merge conflict detected',
      };
    }

    // Step 4: actual merge
    execSync(`git merge --no-ff ${ctx.branch}`, { stdio: 'pipe' });
    cp.merge_sha = getCurrentSha();
    cp.step = 4;
    cp.state = 'merged';
    cp.timestamp = new Date().toISOString();
    writeCheckpoint(cp);

    // Step 5: run tests
    const testResult = runTests(ctx.test_command);
    cp.test_result = testResult;
    cp.step = 5;
    cp.state = 'tested';
    cp.timestamp = new Date().toISOString();
    writeCheckpoint(cp);

    if (testResult.failed > 0) {
      execSync(`git reset --hard ${cp.pre_merge_sha}`, { stdio: 'pipe' });
      return {
        success: false,
        step: 5,
        state: 'test_failed',
        merge_sha: cp.merge_sha,
        error: `${testResult.failed} tests failed`,
      };
    }

    // Step 6: push
    execSync('git push origin main', { stdio: 'pipe' });
    cp.step = 6;
    cp.state = 'pushed';
    cp.timestamp = new Date().toISOString();
    writeCheckpoint(cp);

    // Step 7: closure
    closure(ctx, cp);
    cp.step = 7;
    cp.state = 'closed';
    cp.timestamp = new Date().toISOString();
    writeCheckpoint(cp);

    fs.unlinkSync('docs/state/merge_cp.json');

    return {
      success: true,
      step: 7,
      state: 'closed',
      merge_sha: cp.merge_sha,
      error: null,
    };
  } catch (err) {
    return {
      success: false,
      step: cp.step,
      state: cp.state,
      merge_sha: cp.merge_sha,
      error: (err as Error).message,
    };
  }
}

// ============================================================
// Test execution
// ============================================================

function runTests(testCommand: string): {
  total: number;
  passed: number;
  failed: number;
} {
  try {
    execSync(testCommand, { stdio: 'pipe' });
    return { total: 0, passed: 0, failed: 0 };
  } catch (err) {
    const output = (err as { stdout?: Buffer }).stdout?.toString() || '';
    const match = output.match(/(\d+) passed.*?(\d+) failed/);
    if (match && match[1] !== undefined && match[2] !== undefined) {
      const passed = parseInt(match[1], 10);
      const failed = parseInt(match[2], 10);
      return {
        total: passed + failed,
        passed,
        failed,
      };
    }
    return { total: 0, passed: 0, failed: 1 };
  }
}

// ============================================================
// Closure
// ============================================================

function closure(ctx: MergeContext, cp: MergeCheckpoint): void {
  // 1. Move issue file
  const src = `docs/issues/${ctx.issue_id}.md`;
  const dst = `docs/issues/closed/${ctx.issue_id}.md`;
  if (fs.existsSync(src)) {
    const content = fs.readFileSync(src, 'utf-8');
    const closedContent = addClosedAt(content, new Date().toISOString());
    fs.writeFileSync(dst, closedContent, { encoding: 'utf-8' });
    fs.unlinkSync(src);
  }

  // 2. Update closed/index.md
  updateClosedIndex(ctx.issue_id, ctx.title, cp.merge_sha);

  // 3. Clean up worktree
  try {
    execSync(`git worktree remove ../worktrees/${ctx.issue_id}`, {
      stdio: 'pipe',
    });
  } catch {
    // worktree may already be gone
  }

  // 4. Update merge_history
  updateMergeHistory(ctx, cp.merge_sha, 'clean');

  // 5. Update merge_test_index
  updateMergeTestIndex(ctx.issue_id);

  // 6. Remove from snapshot
  removeFromSnapshot(ctx.issue_id);
}

// ============================================================
// Update merge_test_index
// ============================================================

interface MergeTestIndex {
  schema_version: string;
  updated_at: string;
  tests: Array<{ issue_id: string; command: string }>;
}

function updateMergeTestIndex(issueId: string): void {
  const indexPath = 'docs/state/merge_test_index.json';
  let index: MergeTestIndex = {
    schema_version: '1.0',
    updated_at: new Date().toISOString(),
    tests: [],
  };

  if (fs.existsSync(indexPath)) {
    index = readJsonFile(indexPath) as MergeTestIndex;
  }

  const issuePath = `docs/issues/closed/${issueId}.md`;
  if (fs.existsSync(issuePath)) {
    const content = fs.readFileSync(issuePath, 'utf-8');
    const commands = extractVerificationCommands(content);
    for (const cmd of commands) {
      const exists = index.tests.some(
        (t) => t.issue_id === issueId && t.command === cmd
      );
      if (!exists) {
        index.tests.push({ issue_id: issueId, command: cmd });
      }
    }
  }

  index.updated_at = new Date().toISOString();
  writeJsonAtomic(indexPath, index);
}

/**
 * Extract verification commands from an issue file's
 * `## Verification commands` section.
 */
function extractVerificationCommands(content: string): string[] {
  const sectionMatch = content.match(
    /## Verification commands\s*\n([\s\S]*?)(?=\n## |\n---|$)/
  );
  if (!sectionMatch || sectionMatch[1] === undefined) return [];

  const section = sectionMatch[1];
  const commands: string[] = [];

  for (const line of section.split('\n')) {
    const trimmed = line.trim();
    if (!trimmed || !trimmed.startsWith('-')) continue;

    const match = trimmed.match(/^-\s+ac[0-9]+:\s+(.+)$/);
    if (match && match[1] !== undefined) {
      let cmd = match[1].trim();
      if (cmd.startsWith('`') && cmd.endsWith('`')) {
        cmd = cmd.slice(1, -1);
      }
      if (cmd !== 'manual') {
        commands.push(cmd);
      }
    }
  }

  return commands;
}

// ============================================================
// Update closed/index.md
// ============================================================

function updateClosedIndex(
  issueId: string,
  title: string,
  mergeSha: string | null
): void {
  const indexPath = 'docs/issues/closed/index.md';
  const timestamp = new Date().toISOString();

  if (!fs.existsSync(indexPath)) {
    const header =
      '# Closed Issues Index\n\n' +
      'Runtime-maintained by Orchestrator.\n\n' +
      '| ID | Title | Closed At | Retries | Merge Commit |\n' +
      '|---|---|---|---|---|\n';
    fs.writeFileSync(indexPath, header, { encoding: 'utf-8' });
  }

  const content = fs.readFileSync(indexPath, 'utf-8');
  const shortSha = mergeSha ? mergeSha.slice(0, 7) : '—';
  const newRow = `| ${issueId} | ${title} | ${timestamp} | 0 | ${shortSha} |\n`;

  fs.writeFileSync(indexPath, content + newRow, { encoding: 'utf-8' });
}

// ============================================================
// Update merge_history
// ============================================================

function updateMergeHistory(
  ctx: MergeContext,
  mergeSha: string | null,
  mergeType: 'clean' | 'merge-fix'
): void {
  const historyPath = 'docs/state/merge_history.json';
  let history: {
    schema_version: string;
    updated_at: string;
    entries: unknown[];
  } = {
    schema_version: '1.0',
    updated_at: new Date().toISOString(),
    entries: [],
  };
  if (fs.existsSync(historyPath)) {
    history = readJsonFile(historyPath) as typeof history;
  }
  history.entries.push({
    issue_id: ctx.issue_id,
    merge_sha: mergeSha,
    timestamp: new Date().toISOString(),
    merge_type: mergeType,
  });
  history.updated_at = new Date().toISOString();
  writeJsonAtomic(historyPath, history);
}

// ============================================================
// Remove from snapshot
// ============================================================

function removeFromSnapshot(issueId: string): void {
  const snapshotPath = 'docs/state/snapshot.json';
  if (!fs.existsSync(snapshotPath)) return;

  const snapshot = readJsonFile(snapshotPath) as {
    active_issues?: string[];
    slots?: Array<{ issue_id: string }>;
    merge_queue?: Array<{ issue_id: string }>;
    updated_at?: string;
  };
  snapshot.active_issues = (snapshot.active_issues || []).filter(
    (id: string) => id !== issueId
  );
  snapshot.slots = (snapshot.slots || []).filter(
    (s: { issue_id: string }) => s.issue_id !== issueId
  );
  snapshot.merge_queue = (snapshot.merge_queue || []).filter(
    (q: { issue_id: string }) => q.issue_id !== issueId
  );
  snapshot.updated_at = new Date().toISOString();
  writeJsonAtomic(snapshotPath, snapshot);
}

// ============================================================
// Helper functions
// ============================================================

function addClosedAt(content: string, timestamp: string): string {
  const frontmatterMatch = content.match(/^---\n([\s\S]*?)\n---/);
  if (!frontmatterMatch) return content;

  const frontmatter = frontmatterMatch[1];
  const newFrontmatter = `${frontmatter}\nclosed_at: ${timestamp}`;
  return content.replace(frontmatterMatch[0], `---\n${newFrontmatter}\n---`);
}

function getCurrentSha(): string {
  return execSync('git rev-parse HEAD', { encoding: 'utf-8' }).trim();
}

function writeCheckpoint(cp: MergeCheckpoint): void {
  writeJsonAtomic('docs/state/merge_cp.json', cp);
}

/**
 * Write a JSON file atomically. UTF-8 without BOM.
 */
function writeJsonAtomic(path: string, data: unknown): void {
  const tmp = `${path}.tmp`;
  fs.writeFileSync(tmp, JSON.stringify(data, null, 2), { encoding: 'utf-8' });
  fs.renameSync(tmp, path);
}

// ============================================================
// Merge queue
// ============================================================

export function sortMergeQueue(
  queue: Array<{
    issue_id: string;
    verifier_pass_at: string;
    priority: number;
    depends_merged: boolean;
  }>
): typeof queue {
  return [...queue].sort((a, b) => {
    if (a.depends_merged !== b.depends_merged) {
      return a.depends_merged ? -1 : 1;
    }

    const ta = new Date(a.verifier_pass_at).getTime();
    const tb = new Date(b.verifier_pass_at).getTime();
    if (ta !== tb) return ta - tb;

    return a.issue_id.localeCompare(b.issue_id);
  });
}

// ============================================================
// Fix branch creation (called by Orchestrator)
// ============================================================

export interface FixBranchContext {
  issue_id: string;
  base_branch: string;
  fix_type: 'merge' | 'regression';
  slug: string;
}

export interface FixBranchResult {
  branch_name: string;
  worktree_path: string;
}

/**
 * Create a fix branch and worktree.
 */
export function createFixBranch(ctx: FixBranchContext): FixBranchResult {
  const prefix = ctx.fix_type === 'merge' ? 'MERGE-FIX' : 'REG-FIX';
  const branchName = `issue/${prefix}-${ctx.issue_id}-${ctx.slug}`;
  const worktreePath = `../worktrees/${prefix}-${ctx.issue_id}`;

  try {
    execSync(
      `git worktree add ${worktreePath} -b ${branchName} ${ctx.base_branch}`,
      { stdio: 'pipe' }
    );
  } catch {
    try {
      execSync(`git worktree remove ${worktreePath} --force`, {
        stdio: 'pipe',
      });
      execSync(
        `git worktree add ${worktreePath} -b ${branchName} ${ctx.base_branch}`,
        { stdio: 'pipe' }
      );
    } catch (retryErr) {
      throw new Error(
        `Failed to create fix branch: ${(retryErr as Error).message}`
      );
    }
  }

  return {
    branch_name: branchName,
    worktree_path: worktreePath,
  };
}

/**
 * Clean up a fix branch and worktree.
 */
export function cleanupFixBranch(ctx: FixBranchContext): void {
  const prefix = ctx.fix_type === 'merge' ? 'MERGE-FIX' : 'REG-FIX';
  const worktreePath = `../worktrees/${prefix}-${ctx.issue_id}`;

  try {
    execSync(`git worktree remove ${worktreePath} --force`, {
      stdio: 'pipe',
    });
  } catch {
    // Ignore
  }

  try {
    execSync(
      `git branch -D issue/${prefix}-${ctx.issue_id}-${ctx.slug}`,
      { stdio: 'pipe' }
    );
  } catch {
    // Ignore
  }
}