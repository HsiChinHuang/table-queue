/**
 * T15: source-level regression tests pinning the mock layer out of the production bundle.
 *
 * These mirror the grep arms of AC-1 and AC-3 in _docs/issues/T15.md:
 *  - AC-1: frontend/src/api/mock is reachable ONLY via an import.meta.env.DEV-guarded
 *    dynamic import - no static import anywhere in the production path.
 *  - AC-3: no hardcoded 1234 PIN literal in the mock/seed source; the PIN is read from
 *    import.meta.env (VITE_MOCK_STAFF_PIN).
 *
 * The emitted-bundle invariant (AC-2) is enforced by the grep assertion wired into the
 * `build` script in package.json.
 *
 * Sources are read with import.meta.glob (?raw) so the test needs no node: builtins
 * (the frozen dependency set has no @types/node).
 */
import { describe, expect, it } from 'vitest';

// Raw source of every file under frontend/src.
const sources = import.meta.glob('../**/*.{ts,tsx}', {
  query: '?raw',
  import: 'default',
  eager: true,
}) as Record<string, string>;

// Glob keys are relative to this file's directory (frontend/src/api): the mock
// module is './mock/*' and the client is './client.ts'.
const isMockFile = (key: string) => key.startsWith('./mock/');
// The test file itself references the mock path in its own regexes - exclude it.
const isThisFile = (key: string) => key.includes('mockBundle.test');

// Quoted module specifiers that name the mock module ('./mock', '@/api/mock', ...).
const MOCK_SPECIFIER = /['"][^'"]*\/mock(\/[^'"]*)?['"]/;
// A STATIC import of the mock module (an import-from statement with a mock specifier).
const STATIC_MOCK_IMPORT = /\bfrom\s*['"][^'"]*\/mock(\/[^'"]*)?['"]/;

const importingFiles = Object.entries(sources).filter(
  ([key, src]) => !isMockFile(key) && !isThisFile(key) && MOCK_SPECIFIER.test(src)
);
const mockSources = Object.entries(sources).filter(([key]) => isMockFile(key));

describe('T15 AC-1: mock module reachable only via a DEV-guarded dynamic import', () => {
  it('the dev mock layer is still referenced (a DEV-guarded dynamic import, not a deletion)', () => {
    expect(importingFiles.length).toBeGreaterThan(0);
  });

  it('no STATIC import of the mock module outside frontend/src/api/mock', () => {
    for (const [key, src] of importingFiles) {
      expect(src, `${key} must not statically import the mock module`).not.toMatch(STATIC_MOCK_IMPORT);
    }
  });

  it('every file that imports the mock module carries an import.meta.env.DEV guard', () => {
    for (const [key, src] of importingFiles) {
      expect(src, `${key} must guard the mock import with import.meta.env.DEV`).toContain(
        'import.meta.env.DEV'
      );
    }
  });

  it('the mockRequest call site in client.ts is behind the DEV + VITE_USE_MOCK guard', () => {
    const src = sources['./client.ts'];
    expect(src).toBeDefined();
    const lines = src.split('\n');
    const guardLine = lines.findIndex(
      (line: string) => line.includes('import.meta.env.DEV') && line.includes("VITE_USE_MOCK === 'true'")
    );
    const callLine = lines.findIndex((line: string) => line.includes('mockRequest(method, path, body)'));
    expect(guardLine).toBeGreaterThan(-1);
    expect(callLine).toBeGreaterThan(-1);
    // The call must sit directly inside the guarded branch.
    expect(callLine - guardLine).toBeGreaterThanOrEqual(0);
    expect(callLine - guardLine).toBeLessThanOrEqual(2);
  });
});

describe('T15 AC-3: seed PIN parameterised from env, no 1234 literal in the mock source', () => {
  it('no hardcoded 1234 literal anywhere in frontend/src/api/mock', () => {
    expect(mockSources.length).toBeGreaterThan(0);
    for (const [key, src] of mockSources) {
      expect(src, `${key} must not contain a 1234 literal`).not.toContain('1234');
    }
  });

  it('the mock/seed source reads the PIN from import.meta.env', () => {
    const found = mockSources.filter(
      ([, src]) => /pin/i.test(src) && src.includes('import.meta.env')
    );
    expect(found.length).toBeGreaterThan(0);
  });
});
