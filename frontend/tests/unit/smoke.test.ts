// @vitest-environment jsdom
import { expect, it } from 'vitest';
import App from '../../src/App';

// Smoke test for vitest setup
// Note: Page-level tests with React Testing Library come in F-03+
it('smoke test - basic vitest setup works', () => {
  expect(1 + 1).toBe(2);
});

it('App component can be imported', () => {
  expect(App).toBeDefined();
  expect(typeof App).toBe('function');
});
