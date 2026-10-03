import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import path from 'path';

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    // T12: no forced all-interfaces bind - Vite defaults to loopback (127.0.0.1).
    // Phone demo: run `npm run dev -- --host` (see README "Mobile Testing").
    proxy: {
      '/api': { target: process.env.VITE_API_TARGET ?? 'http://localhost:8000', changeOrigin: true },
    },
  },
  test: {
    environment: 'node',
    // F-15: shared test setup (loads @testing-library/jest-dom matchers). DOM tests still opt
    // in per file with the `// @vitest-environment jsdom` pragma because the default here is node.
    setupFiles: ['./src/test/setup.ts'],
    coverage: {
      provider: 'v8',
      reportsDirectory: './coverage',
      include: ['src/**/*.{ts,tsx}'],
      exclude: ['src/**/*.test.*', 'src/test/**', 'src/main.tsx', 'src/vite-env.d.ts'],
      // AC-6/AC-7 read statement coverage out of coverage/coverage-summary.json (that is what
      // their bash blocks parse). No `thresholds` block here on purpose: a global threshold would
      // fail the whole suite for files F-15 does not own - pages/hooks belonging to F-07..F-14
      // are still untested. The kit also has no `test:coverage` script; AC-6/AC-7 call
      // `npm test -- --run --coverage --coverage.reporter=json-summary` directly.
    },
  },
});
