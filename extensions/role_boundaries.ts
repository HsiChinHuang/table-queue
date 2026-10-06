// extensions/role_boundaries.ts
// Role boundary enforcement: intercept out-of-scope operations at tool-call level

// (no imports — all operations are pure in-memory checks)

export type Role = 'definer' | 'builder' | 'verifier' | 'orchestrator';

interface RolePermissions {
  allowed_write_paths: string[];
  forbidden_write_paths: string[];
  allowed_tools: string[];
  forbidden_commands: string[];
}

const ROLE_PERMISSIONS: Record<Role, RolePermissions> = {
  definer: {
    allowed_write_paths: [
      'docs/issues/',
      'docs/plan.md',
      'docs/backlog.md',
      'docs/state/issue_map.json',
      'docs/state/dag.json',
      'docs/state/milestones/',
      'docs/state/outputs/',
    ],
    forbidden_write_paths: [
      'src/',
      'tests/',
      'docs/state/snapshot.json',
      'docs/state/seq.txt',
      'docs/state/merge_cp.json',
      'docs/state/idempotency.json',
      'docs/state/retry.json',
      'docs/state/retry_subagent.json',
    ],
    allowed_tools: ['read', 'bash', 'grep', 'find', 'edit', 'write'],
    forbidden_commands: [
      'sudo', 'su',
      'rm -rf /', 'rm -rf ~', 'rm -rf /*',
      'git push --force',
      'git push origin main',
      'git push origin master',
      'env', 'printenv',
      'dd', 'mkfs', 'fdisk',
      'chmod 777 /',
    ],
  },

  builder: {
    allowed_write_paths: [
      'src/',
      'tests/',
      '../worktrees/',
      'docs/state/outputs/',
    ],
    forbidden_write_paths: [
      'docs/issues/',
      'docs/state/snapshot.json',
      'docs/state/seq.txt',
      'docs/state/merge_cp.json',
      'docs/state/idempotency.json',
      'docs/state/retry.json',
      'docs/state/retry_subagent.json',
    ],
    allowed_tools: ['read', 'bash', 'grep', 'find', 'edit', 'write'],
    forbidden_commands: [
      'sudo', 'su',
      'rm -rf /', 'rm -rf ~', 'rm -rf /*',
      'git push --force',
      'git push origin main',
      'git push origin master',
      'env', 'printenv',
      'dd', 'mkfs', 'fdisk',
      'chmod 777 /',
    ],
  },

  verifier: {
    allowed_write_paths: [
      'docs/state/outputs/',
    ],
    forbidden_write_paths: [
      'src/',
      'tests/',
      'docs/issues/',
      'docs/state/snapshot.json',
      'docs/state/seq.txt',
      'docs/state/merge_cp.json',
      'docs/state/idempotency.json',
      'docs/state/retry.json',
      'docs/state/retry_subagent.json',
    ],
    allowed_tools: ['read', 'bash', 'grep', 'find'],
    forbidden_commands: [
      'sudo', 'su',
      'rm -rf /', 'rm -rf ~', 'rm -rf /*',
      'git push --force',
      'git push origin main',
      'env', 'printenv',
    ],
  },

  orchestrator: {
    allowed_write_paths: [
      'docs/state/',
      'docs/log/',
      'docs/backlog.md',
      'docs/state/issue_map.json',
    ],
    forbidden_write_paths: [
      'src/',
      'tests/',
      'docs/issues/',
    ],
    allowed_tools: ['read', 'bash', 'grep', 'find', 'edit', 'write'],
    forbidden_commands: [
      'sudo', 'su',
      'rm -rf /', 'rm -rf ~', 'rm -rf /*',
      'git push --force',
      'env', 'printenv',
      'dd', 'mkfs', 'fdisk',
    ],
  },
};

// ============================================================
// Boundary checks
// ============================================================

export interface BoundaryCheckResult {
  allowed: boolean;
  reason: string;
}

/**
 * Check whether a role may write to a given path.
 */
export function canWrite(role: Role, filePath: string): BoundaryCheckResult {
  const perms = ROLE_PERMISSIONS[role];

  // Check forbidden first
  for (const forbidden of perms.forbidden_write_paths) {
    if (filePath.startsWith(forbidden)) {
      return {
        allowed: false,
        reason: `Path "${filePath}" is forbidden for role "${role}"`,
      };
    }
  }

  // Check allowed
  for (const allowed of perms.allowed_write_paths) {
    if (filePath.startsWith(allowed)) {
      return { allowed: true, reason: '' };
    }
  }

  return {
    allowed: false,
    reason: `Path "${filePath}" is not in the allowed list for role "${role}"`,
  };
}

/**
 * Check whether a role may use a given tool.
 */
export function canUseTool(role: Role, tool: string): BoundaryCheckResult {
  const perms = ROLE_PERMISSIONS[role];
  if (perms.allowed_tools.includes(tool)) {
    return { allowed: true, reason: '' };
  }
  return {
    allowed: false,
    reason: `Tool "${tool}" is not allowed for role "${role}"`,
  };
}

/**
 * Check whether a role may run a given command.
 */
export function canRunCommand(
  role: Role,
  command: string
): BoundaryCheckResult {
  const perms = ROLE_PERMISSIONS[role];

  for (const forbidden of perms.forbidden_commands) {
    if (command.includes(forbidden)) {
      return {
        allowed: false,
        reason: `Command contains forbidden pattern "${forbidden}" for role "${role}"`,
      };
    }
  }

  return { allowed: true, reason: '' };
}

// ============================================================
// Hook integration: pre_tool_call
// ============================================================

export interface ToolCallContext {
  role: Role;
  tool: string;
  args: Record<string, unknown>;
}

export interface ToolCallDecision {
  allow: boolean;
  reason: string;
}

/**
 * Hook entry point: intercept before tool call.
 */
export function preToolCall(context: ToolCallContext): ToolCallDecision {
  const { role, tool, args } = context;

  // 1. Check tool permission
  const toolCheck = canUseTool(role, tool);
  if (!toolCheck.allowed) {
    return { allow: false, reason: toolCheck.reason };
  }

  // 2. If write/edit, check target path
  if (tool === 'write' || tool === 'edit') {
    const filePath = (args.path || args.file_path) as string;
    if (!filePath) {
      return { allow: false, reason: 'No path specified for write/edit' };
    }
    const pathCheck = canWrite(role, filePath);
    if (!pathCheck.allowed) {
      return { allow: false, reason: pathCheck.reason };
    }
  }

  // 3. If bash, check command
  if (tool === 'bash') {
    const command = (args.command || args.cmd) as string;
    if (!command) {
      return { allow: false, reason: 'No command specified for bash' };
    }
    const cmdCheck = canRunCommand(role, command);
    if (!cmdCheck.allowed) {
      return { allow: false, reason: cmdCheck.reason };
    }
  }

  return { allow: true, reason: '' };
}

// ============================================================
// Secret pattern scan (output)
// ============================================================

const SECRET_PATTERNS = [
  /ghp_[a-zA-Z0-9]{36}/,
  /gho_[a-zA-Z0-9]{36}/,
  /ghu_[a-zA-Z0-9]{36}/,
  /ghs_[a-zA-Z0-9]{36}/,
  /glpat-[a-zA-Z0-9]{20}/,
  /sk-[a-zA-Z0-9]{48}/,
  /Bearer\s+[a-zA-Z0-9]{20,}/,
  /-----BEGIN/,
];

export interface SecretScanResult {
  has_secret: boolean;
  matched_pattern: string | null;
  redacted_content: string;
}

/**
 * Scan output for secrets.
 */
export function scanForSecrets(
  content: string,
  apiToken?: string
): SecretScanResult {
  let redacted = content;
  let matched: string | null = null;

  // Check the actual API_TOKEN
  if (apiToken && content.includes(apiToken)) {
    matched = 'literal_api_token';
    redacted = redacted.split(apiToken).join('[REDACTED]');
  }

  // Check pattern-based secrets
  for (const pattern of SECRET_PATTERNS) {
    const m = content.match(pattern);
    if (m) {
      matched = matched || pattern.source;
      redacted = redacted.replace(pattern, '[REDACTED]');
    }
  }

  return {
    has_secret: matched !== null,
    matched_pattern: matched,
    redacted_content: redacted,
  };
}