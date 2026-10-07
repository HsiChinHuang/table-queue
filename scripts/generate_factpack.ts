// scripts/generate_factpack.ts
// Generate a factpack JSON for the next Definer spawn.
//
// Usage: tsx scripts/generate_factpack.ts <subject_id> <phase>
//
//   subject_id: t<N> for groom/re_groom; phase_<n>_<name> for survey
//   phase:      survey | groom | re_groom
//
// Output: docs/state/factpack/<subject_id>.json
// Exit codes:
//   0 - success
//   1 - missing required input file or invalid arguments
//   2 - usage error

import * as fs from 'fs';
import * as path from 'path';

const FACT_DIR = 'docs/state/factpack';
const PHASES = ['survey', 'groom', 're_groom'] as const;
type Phase = (typeof PHASES)[number];

const SUBJECT_ID_PATTERN = /^(t[0-9]+|phase_[0-9]+_[a-z_]+)$/;

interface Factpack {
  schema_version: '1.0';
  subject_id: string;
  phase: Phase;
  created_at: string;
  facts: {
    tech_stack: string | null;
    commands_md: string;
    coding_standards_md: string;
    config_subset: Record<string, unknown>;
    issue_map: Record<string, unknown> | null;
  };
}

function usage(): never {
  console.error('Usage: generate_factpack.ts <subject_id> <phase>');
  console.error(`  subject_id: t<N> | phase_<n>_<name>`);
  console.error(`  phase:      ${PHASES.join(' | ')}`);
  process.exit(2);
}

function readRequired(filePath: string): string {
  if (!fs.existsSync(filePath)) {
    console.error(`ERROR: required input file not found: ${filePath}`);
    process.exit(1);
  }
  return fs.readFileSync(filePath, 'utf-8');
}

/**
 * Extract the content of a level-2 section from a Markdown file.
 * Returns the section body (without the heading line) or null if absent.
 */
function extractSection(content: string, sectionTitle: string): string | null {
  const escaped = sectionTitle.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const pattern = new RegExp(
    `^##\\s+${escaped}\\s*$\\n([\\s\\S]*?)(?=^##\\s|\\z)`,
    'm'
  );
  const match = content.match(pattern);
  if (!match || match[1] === undefined) return null;
  const body = match[1].trim();
  return body.length > 0 ? body : null;
}

function loadTechStack(): string | null {
  // Try plan.md first
  if (fs.existsSync('docs/plan.md')) {
    const plan = fs.readFileSync('docs/plan.md', 'utf-8');
    const tech = extractSection(plan, 'Tech stack');
    if (tech) return tech;
  }
  // Fallback: requirements.md
  if (fs.existsSync('docs/requirements.md')) {
    const req = fs.readFileSync('docs/requirements.md', 'utf-8');
    const tech = extractSection(req, 'Tech stack');
    if (tech) return tech;
  }
  return null;
}

const CONFIG_KEYS_PREFIXES = ['contract_first.', 'limits.issue_granularity.'];

function loadConfigSubset(): Record<string, unknown> {
  const path = 'docs/state/config_snapshot.json';
  if (!fs.existsSync(path)) {
    return {};
  }
  const snapshot = JSON.parse(fs.readFileSync(path, 'utf-8')) as {
    values?: Record<string, unknown>;
  };
  const values = snapshot.values ?? {};
  const subset: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(values)) {
    if (CONFIG_KEYS_PREFIXES.some((p) => key.startsWith(p))) {
      subset[key] = value;
    }
  }
  return subset;
}

function loadIssueMap(phase: Phase): Record<string, unknown> | null {
  if (phase !== 'survey') return null;
  const path = 'docs/state/issue_map.json';
  if (!fs.existsSync(path)) {
    console.error(`ERROR: ${path} is required for survey factpack`);
    process.exit(1);
  }
  const parsed = JSON.parse(fs.readFileSync(path, 'utf-8')) as {
    mappings?: Record<string, unknown>;
  };
  return { mappings: parsed.mappings ?? {} };
}

function main(): void {
  const args = process.argv.slice(2);
  if (args.length !== 2) {
    usage();
  }
  const subjectId = args[0];
  const phaseArg = args[1];
  if (subjectId === undefined || phaseArg === undefined) {
    usage();
  }
  if (!SUBJECT_ID_PATTERN.test(subjectId)) {
    console.error(`ERROR: invalid subject_id: "${subjectId}"`);
    process.exit(2);
  }
  if (!(PHASES as readonly string[]).includes(phaseArg)) {
    console.error(`ERROR: invalid phase: "${phaseArg}"`);
    process.exit(2);
  }
  const phase = phaseArg as Phase;

  // Consistency: survey uses phase_<n>_<name>; groom/re_groom use t<N>
  const isMilestoneId = subjectId.startsWith('phase_');
  if (phase === 'survey' && !isMilestoneId) {
    console.error(`ERROR: survey requires a milestone subject_id (phase_<n>_<name>)`);
    process.exit(2);
  }
  if ((phase === 'groom' || phase === 're_groom') && isMilestoneId) {
    console.error(`ERROR: ${phase} requires an issue subject_id (t<N>)`);
    process.exit(2);
  }

  const facts: Factpack['facts'] = {
    tech_stack: loadTechStack(),
    commands_md: readRequired('docs/commands.md'),
    coding_standards_md: readRequired('docs/coding_standards.md'),
    config_subset: loadConfigSubset(),
    issue_map: loadIssueMap(phase),
  };

  const factpack: Factpack = {
    schema_version: '1.0',
    subject_id: subjectId,
    phase,
    created_at: new Date().toISOString(),
    facts,
  };

  fs.mkdirSync(FACT_DIR, { recursive: true });
  const outPath = path.join(FACT_DIR, `${subjectId}.json`);
  const tmp = `${outPath}.tmp`;
  fs.writeFileSync(tmp, JSON.stringify(factpack, null, 2));
  fs.renameSync(tmp, outPath);

  console.log(`Wrote ${outPath}`);
}

main();