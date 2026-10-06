// scripts/validate_handoff.ts
// Validate a single handoff JSON file.
// Usage: tsx scripts/validate_handoff.ts <path> <role> <phase>

import * as fs from 'fs';
import { validateHandoffSchema } from '../extensions/schema_validator.js';

function main(): void {
  const args = process.argv.slice(2);

  if (args.length !== 3) {
    console.error(
      'Usage: tsx scripts/validate_handoff.ts <path> <role> <phase>'
    );
    process.exit(1);
  }

  const handoffPath = args[0];
  const role = args[1];
  const phase = args[2];

  if (handoffPath === undefined || role === undefined || phase === undefined) {
    console.error('Missing required arguments');
    process.exit(1);
  }

  if (!fs.existsSync(handoffPath)) {
    console.error(`Handoff not found: ${handoffPath}`);
    process.exit(1);
  }

  const result = validateHandoffSchema(role, phase, handoffPath);

  if (result.valid) {
    console.log(`[OK] ${handoffPath} is valid for ${role}:${phase}`);
    process.exit(0);
  }

  console.error(`[ERROR] ${handoffPath} is invalid for ${role}:${phase}`);
  for (const err of result.errors) {
    console.error(`  ${err.path}: ${err.message}`);
  }
  process.exit(1);
}

main();