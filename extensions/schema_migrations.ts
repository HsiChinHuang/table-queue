// extensions/schema_migrations.ts
// Schema version migration functions

export type MigrationFn = (data: unknown) => unknown;

export const migrations: Record<string, MigrationFn> = {
  // Example:
  // '1.0->1.1': migrate_1_0_to_1_1,
  // '1.1->2.0': migrate_1_1_to_2_0,
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