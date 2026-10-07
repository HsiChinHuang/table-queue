// extensions/schema_migrations.ts
// Schema version migration functions

export type MigrationFn = (data: unknown) => unknown;

type JsonObject = Record<string, unknown>;

function isObject(value: unknown): value is JsonObject {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

/**
 * 1.0 -> 2.0 (snapshot.json)
 *
 * - Slot: rename last_heartbeat -> last_activity_at
 * - Slot: add run_id (default null)
 * - schema_version: "1.0" -> "2.0"
 *
 * Unknown fields are preserved (forward-compat) but additionalProperties:false
 * in the 2.0 schema will reject them at validation time. This migration only
 * reshapes what it knows about.
 */
function migrateSnapshot_1_0_to_2_0(data: unknown): unknown {
  if (!isObject(data)) return data;
  const out: JsonObject = { ...data, schema_version: '2.0' };

  if (Array.isArray(data.slots)) {
    out.slots = data.slots.map((slot) => {
      if (!isObject(slot)) return slot;
      const migrated: JsonObject = { ...slot };
      // rename last_heartbeat -> last_activity_at
      if ('last_heartbeat' in migrated) {
        migrated.last_activity_at = migrated.last_heartbeat;
        delete migrated.last_heartbeat;
      }
      if (!('last_activity_at' in migrated)) {
        migrated.last_activity_at = migrated.spawn_at ?? null;
      }
      // add run_id
      if (!('run_id' in migrated)) {
        migrated.run_id = null;
      }
      return migrated;
    });
  }

  return out;
}

/**
 * 1.0 -> 2.0 (handoff.json envelope)
 *
 * Handoff files live under docs/state/outputs/*.json. The migration is applied
 * on read (see recovery / validators). It reshapes the error field:
 *
 * - If error.error_type is one of the removed business-layer values, map to
 *   business_failure and populate error.context.failure_type.
 * - Ensure next_action.phase is legal (enum) or null.
 * - Ensure retry_count exists (default 0).
 */
const LEGACY_ERROR_TYPE_MAP: Record<string, string> = {
  verification_failure: 'business_failure',
  implementation_failure: 'business_failure',
  grooming_failure: 'business_failure',
  test_failure: 'business_failure',
  merge_conflict: 'business_failure',
  regression: 'business_failure',
};

const LEGACY_FAILURE_TYPE_MAP: Record<string, string> = {
  verification_failure: 'implementation',
  implementation_failure: 'implementation',
  grooming_failure: 'ac_ambiguous',
  test_failure: 'test_quality',
  merge_conflict: 'merge_conflict',
  regression: 'regression',
};

function migrateHandoff_1_0_to_2_0(data: unknown): unknown {
  if (!isObject(data)) return data;
  const out: JsonObject = { ...data, schema_version: '2.0' };

  if (!('retry_count' in out)) {
    out.retry_count = 0;
  }
  if (!('next_action' in out)) {
    out.next_action = null;
  }

  if (isObject(data.error)) {
    const err: JsonObject = { ...data.error };
    const legacyType = err.error_type;
    if (typeof legacyType === 'string' && legacyType in LEGACY_ERROR_TYPE_MAP) {
      err.error_type = LEGACY_ERROR_TYPE_MAP[legacyType];
      const ctx: JsonObject = isObject(err.context) ? { ...err.context } : {};
      if (!('failure_type' in ctx)) {
        ctx.failure_type = LEGACY_FAILURE_TYPE_MAP[legacyType];
      }
      err.context = ctx;
    }
    out.error = err;
  } else if (!('error' in out)) {
    out.error = null;
  }

  if (isObject(data.next_action)) {
    // phase may be missing or a string; leave as-is if legal, else null the whole object
    const na: JsonObject = { ...data.next_action };
    out.next_action = na;
  }

  return out;
}

export const migrations: Record<string, MigrationFn> = {
  '1.0->2.0': (data) => {
    // Dispatch by shape. snapshot.json has slots + merge_queue;
    // handoff.json has role + phase + status.
    if (isObject(data) && ('slots' in data || 'merge_queue' in data)) {
      return migrateSnapshot_1_0_to_2_0(data);
    }
    if (isObject(data) && 'role' in data && 'phase' in data && 'status' in data) {
      return migrateHandoff_1_0_to_2_0(data);
    }
    // Unknown shape: only bump version
    if (isObject(data) && 'schema_version' in data) {
      return { ...data, schema_version: '2.0' };
    }
    return data;
  },
};

/**
 * Migrate data from fromVersion to toVersion.
 * If no migration function is found, returns the original data.
 */
export function migrate(
  data: unknown,
  fromVersion: string,
  toVersion: string
): unknown {
  if (fromVersion === toVersion) {
    return data;
  }

  const key = `${fromVersion}->${toVersion}`;
  const fn = migrations[key];

  if (!fn) {
    console.warn(`No migration found for ${key}`);
    return data;
  }

  return fn(data);
}

/**
 * Check whether data's schema_version is the current version.
 */
export function isCurrentVersion(
  data: { schema_version?: string },
  currentVersion: string
): boolean {
  return data.schema_version === currentVersion;
}