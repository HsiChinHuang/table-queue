// extensions/schema_validator.ts
// Schema validator hook: validates subagent output before Orchestrator reads it

import * as fs from 'fs';
import * as path from 'path';
import Ajv from 'ajv';
import type { ErrorObject } from 'ajv';
import addFormats from 'ajv-formats';

const SCHEMAS_DIR = 'schemas';

const ajv = new Ajv({ allErrors: true, strict: false });
addFormats(ajv);

// ============================================================
// BOM-tolerant JSON reader
// ============================================================

/**
 * Strip a UTF-8 BOM (U+FEFF) from the beginning of a string.
 *
 * Files written by Windows PowerShell's `Out-File -Encoding utf8`,
 * Notepad, or some git configurations may carry a BOM. JSON.parse
 * rejects a leading BOM; this helper neutralises that.
 */
export function stripBom(text: string): string {
  return text.charCodeAt(0) === 0xfeff ? text.slice(1) : text;
}

/**
 * Read a file and parse it as JSON, tolerating a leading UTF-8 BOM.
 * Throws on I/O error or parse error.
 */
export function readJsonFile(filePath: string): unknown {
  const raw = fs.readFileSync(filePath, 'utf-8');
  return JSON.parse(stripBom(raw));
}

// ============================================================
// Schema registration
// ============================================================

/**
 * Recursively find all .json files under a directory.
 * Excludes .example files.
 */
function findJsonFiles(dir: string): string[] {
  const results: string[] = [];
  if (!fs.existsSync(dir)) return results;

  const entries = fs.readdirSync(dir, { withFileTypes: true });
  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      results.push(...findJsonFiles(fullPath));
    } else if (entry.name.endsWith('.json')) {
      results.push(fullPath);
    }
  }
  return results;
}

/**
 * Register all schemas at module load time so $ref can resolve.
 */
function registerAllSchemas(): void {
  const files = findJsonFiles(SCHEMAS_DIR);
  for (const file of files) {
    try {
      const schema = readJsonFile(file) as { $id?: string };
      if (schema.$id && !ajv.getSchema(schema.$id)) {
        ajv.addSchema(schema);
      }
    } catch (err) {
      console.warn(
        `Failed to register schema ${file}: ${(err as Error).message}`
      );
    }
  }
}

registerAllSchemas();

// ============================================================
// Schema path maps
// ============================================================

// Role output schemas (used by handoff validation)
const HANDOFF_SCHEMA_MAP: Record<string, string> = {
  'definer:survey': 'schemas/definer/survey.json',
  'definer:review_plan': 'schemas/definer/review_plan.json',
  'definer:groom': 'schemas/definer/groom.json',
  'definer:re_groom': 'schemas/definer/re_groom.json',
  'builder:implement': 'schemas/builder/implement.json',
  'builder:fix_qa': 'schemas/builder/fix_qa.json',
  'builder:fix_merge': 'schemas/builder/fix_merge.json',
  'builder:fix_regression': 'schemas/builder/fix_regression.json',
  'verifier:verify_issue': 'schemas/verifier/verify_issue.json',
  'verifier:verify_pre_merge': 'schemas/verifier/verify_pre_merge.json',
  'verifier:verify_post_merge': 'schemas/verifier/verify_post_merge.json',
};

// State file schemas (used by recovery and other runtime checks)
const STATE_SCHEMA_MAP: Record<string, string> = {
  snapshot: 'schemas/state/snapshot.json',
  retry: 'schemas/state/retry.json',
  retry_subagent: 'schemas/state/retry_subagent.json',
  config_snapshot: 'schemas/state/config_snapshot.json',
  issue_map: 'schemas/state/issue_map.json',
  merge_cp: 'schemas/state/merge_cp.json',
  idempotency: 'schemas/state/idempotency.json',
  launcher_checkpoint: 'schemas/state/launcher_checkpoint.json',
  merge_test_index: 'schemas/state/merge_test_index.json',
  merge_history: 'schemas/state/merge_history.json',
  milestone: 'schemas/state/milestone.json',
  token_usage: 'schemas/state/token_usage.json',
  misjudgments: 'schemas/state/misjudgments.json',
  status_metrics: 'schemas/state/status_metrics.json',
  factpack: 'schemas/state/factpack.json',
};

// ============================================================
// Validation result
// ============================================================

export interface SchemaValidationResult {
  valid: boolean;
  schema_path: string;
  errors: SchemaError[];
}

export interface SchemaError {
  path: string;
  message: string;
  keyword: string;
  params: Record<string, unknown>;
}

// ============================================================
// Core validation logic (internal)
// ============================================================

/**
 * Validate a JSON data file against a registered schema.
 */
function validateAgainstSchemaPath(
  schemaPath: string,
  dataPath: string
): SchemaValidationResult {
  if (!fs.existsSync(schemaPath)) {
    return {
      valid: false,
      schema_path: schemaPath,
      errors: [
        {
          path: '/',
          message: `Schema file not found: ${schemaPath}`,
          keyword: 'schema_file',
          params: {},
        },
      ],
    };
  }

  // Load schema content to get its $id
  let schema: { $id?: string };
  try {
    schema = readJsonFile(schemaPath) as { $id?: string };
  } catch (err) {
    return {
      valid: false,
      schema_path: schemaPath,
      errors: [
        {
          path: '/',
          message: `Schema is not valid JSON: ${(err as Error).message}`,
          keyword: 'schema_parse',
          params: {},
        },
      ],
    };
  }

  if (!schema.$id) {
    return {
      valid: false,
      schema_path: schemaPath,
      errors: [
        {
          path: '/',
          message: `Schema has no $id: ${schemaPath}`,
          keyword: 'schema_id',
          params: {},
        },
      ],
    };
  }

  // Load data file
  if (!fs.existsSync(dataPath)) {
    return {
      valid: false,
      schema_path: schemaPath,
      errors: [
        {
          path: '/',
          message: `Data file not found: ${dataPath}`,
          keyword: 'data_file',
          params: {},
        },
      ],
    };
  }

  let data: unknown;
  try {
    data = readJsonFile(dataPath);
  } catch (err) {
    return {
      valid: false,
      schema_path: schemaPath,
      errors: [
        {
          path: '/',
          message: `Data file is not valid JSON: ${(err as Error).message}`,
          keyword: 'json_parse',
          params: {},
        },
      ],
    };
  }

  // Get the compiled validator (resolves $ref via registered schemas)
  const validate = ajv.getSchema(schema.$id);
  if (!validate) {
    return {
      valid: false,
      schema_path: schemaPath,
      errors: [
        {
          path: '/',
          message: `Schema not registered: ${schema.$id}`,
          keyword: 'schema_not_registered',
          params: {},
        },
      ],
    };
  }

  const valid = validate(data);

  if (valid) {
    return { valid: true, schema_path: schemaPath, errors: [] };
  }

  const errors: SchemaError[] = (validate.errors || []).map(
    (e: ErrorObject) => ({
      path: e.instancePath || '/',
      message: e.message || 'unknown error',
      keyword: e.keyword,
      params: e.params as Record<string, unknown>,
    })
  );

  return { valid: false, schema_path: schemaPath, errors };
}

// ============================================================
// Public: handoff validation
// ============================================================

/**
 * Validate handoff JSON against its schema.
 *
 * @param role - Role
 * @param phase - Phase
 * @param handoffPath - Path to the handoff JSON
 * @returns Validation result
 */
export function validateHandoffSchema(
  role: string,
  phase: string,
  handoffPath: string
): SchemaValidationResult {
  const key = `${role}:${phase}`;
  const schemaPath = HANDOFF_SCHEMA_MAP[key];

  if (!schemaPath) {
    return {
      valid: false,
      schema_path: '',
      errors: [
        {
          path: '/',
          message: `No schema found for ${key}`,
          keyword: 'schema_lookup',
          params: {},
        },
      ],
    };
  }

  return validateAgainstSchemaPath(schemaPath, handoffPath);
}

// ============================================================
// Public: state file validation
// ============================================================

/**
 * Validate a state file against its schema.
 *
 * @param schemaName - Logical name (e.g. 'snapshot', 'merge_cp', 'factpack')
 * @param filePath - Path to the state JSON file
 * @returns Validation result
 */
export function validateStateFile(
  schemaName: string,
  filePath: string
): SchemaValidationResult {
  const schemaPath = STATE_SCHEMA_MAP[schemaName];

  if (!schemaPath) {
    return {
      valid: false,
      schema_path: '',
      errors: [
        {
          path: '/',
          message: `No schema found for state file "${schemaName}"`,
          keyword: 'schema_lookup',
          params: {},
        },
      ],
    };
  }

  return validateAgainstSchemaPath(schemaPath, filePath);
}

// ============================================================
// Write validation error report
// ============================================================

export function writeValidationError(
  handoffPath: string,
  result: SchemaValidationResult
): void {
  const errorPath = handoffPath.replace(/\.json$/, '.invalid.json');

  const report = {
    schema_version: '1.0',
    timestamp: new Date().toISOString(),
    handoff_path: handoffPath,
    schema_path: result.schema_path,
    errors: result.errors,
  };

  fs.writeFileSync(errorPath, JSON.stringify(report, null, 2));
}

// ============================================================
// Convenience: validate and report
// ============================================================

export interface ValidateAndReportResult {
  valid: boolean;
  should_retry: boolean;
  retry_reason: string;
}

export function validateAndReport(
  role: string,
  phase: string,
  handoffPath: string,
  maxRetries: number,
  currentRetryCount: number
): ValidateAndReportResult {
  const result = validateHandoffSchema(role, phase, handoffPath);

  if (result.valid) {
    return { valid: true, should_retry: false, retry_reason: '' };
  }

  // Write error report
  writeValidationError(handoffPath, result);

  if (currentRetryCount >= maxRetries) {
    return {
      valid: false,
      should_retry: false,
      retry_reason: `Max retries (${maxRetries}) reached. Escalate to BLOCKER.`,
    };
  }

  const errorSummary = result.errors
    .slice(0, 3)
    .map((e) => `${e.path}: ${e.message}`)
    .join('; ');

  return {
    valid: false,
    should_retry: true,
    retry_reason: `Schema validation failed: ${errorSummary}`,
  };
}