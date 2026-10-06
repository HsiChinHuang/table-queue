// scripts/validate_schemas.ts
// Validate that all schema files are structurally valid and that all
// $ref references can be resolved.
//
// Three passes:
//   1. Validate each schema against the JSON Schema meta-schema.
//   2. Register every schema with Ajv (by $id).
//   3. Force compilation of every registered schema to resolve $ref.

import * as fs from 'fs';
import * as path from 'path';
import Ajv from 'ajv';
import addFormats from 'ajv-formats';

const ajv = new Ajv({ allErrors: true, strict: false });
addFormats(ajv);

const SCHEMAS_DIR = 'schemas';

function findSchemaFiles(dir: string): string[] {
  if (!fs.existsSync(dir)) {
    console.error(`Schemas directory not found: ${dir}`);
    process.exit(1);
  }

  const results: string[] = [];
  const entries = fs.readdirSync(dir, { withFileTypes: true });

  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      results.push(...findSchemaFiles(fullPath));
    } else if (entry.name.endsWith('.json')) {
      results.push(fullPath);
    }
  }

  return results;
}

interface LoadedSchema {
  path: string;
  schema: Record<string, unknown>;
}

function loadAllSchemas(files: string[]): LoadedSchema[] {
  const loaded: LoadedSchema[] = [];
  for (const file of files) {
    const content = fs.readFileSync(file, 'utf-8');
    const schema = JSON.parse(content) as Record<string, unknown>;
    loaded.push({ path: file, schema });
  }
  return loaded;
}

function main(): void {
  const files = findSchemaFiles(SCHEMAS_DIR);
  console.log(`Found ${files.length} schema files\n`);

  const schemas = loadAllSchemas(files);
  let errors = 0;

  // ------------------------------------------------------------
  // Pass 1: Validate schema structure against the meta-schema
  // ------------------------------------------------------------
  console.log('Pass 1: validate schema structure\n');

  for (const { path: filePath, schema } of schemas) {
    try {
      const valid = ajv.validateSchema(schema);
      if (valid) {
        console.log(`[OK]    ${filePath}`);
      } else {
        const errs = ajv.errors || [];
        console.error(`[ERROR] ${filePath}`);
        for (const e of errs) {
          console.error(`        ${e.instancePath || '/'}: ${e.message}`);
        }
        errors++;
      }
    } catch (err) {
      console.error(`[ERROR] ${filePath}: ${(err as Error).message}`);
      errors++;
    }
  }

  if (errors > 0) {
    console.error(`\nPass 1 failed with ${errors} error(s)`);
    process.exit(1);
  }

  // ------------------------------------------------------------
  // Pass 2: Register all schemas with Ajv
  // ------------------------------------------------------------
  console.log('\nPass 2: register schemas\n');

  for (const { path: filePath, schema } of schemas) {
    const id = schema.$id as string | undefined;
    if (!id) {
      console.error(`[ERROR] ${filePath}: missing $id`);
      errors++;
      continue;
    }
    if (ajv.getSchema(id)) {
      console.error(`[ERROR] ${filePath}: duplicate $id "${id}"`);
      errors++;
      continue;
    }
    try {
      ajv.addSchema(schema);
      console.log(`[OK]    ${id}`);
    } catch (err) {
      console.error(`[ERROR] ${filePath}: ${(err as Error).message}`);
      errors++;
    }
  }

  if (errors > 0) {
    console.error(`\nPass 2 failed with ${errors} error(s)`);
    process.exit(1);
  }

  // ------------------------------------------------------------
  // Pass 3: Force compilation to resolve all $ref
  // ------------------------------------------------------------
  console.log('\nPass 3: resolve $ref\n');

  for (const { path: filePath, schema } of schemas) {
    const id = schema.$id as string;
    try {
      const validate = ajv.getSchema(id);
      if (!validate) {
        console.error(`[ERROR] ${filePath}: schema not retrievable after registration`);
        errors++;
      } else {
        console.log(`[OK]    ${id}`);
      }
    } catch (err) {
      console.error(`[ERROR] ${filePath}: ${(err as Error).message}`);
      errors++;
    }
  }

  if (errors > 0) {
    console.error(`\n${errors} schema(s) failed`);
    process.exit(1);
  }

  console.log(`\nAll ${schemas.length} schemas are valid`);
}

main();