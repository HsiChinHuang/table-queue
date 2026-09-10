/**
 * Shared Vitest setup (F-15). Wired through vite.config.ts test.setupFiles.
 * Adds the jest-dom matchers (toBeInTheDocument / toHaveTextContent / toBeDisabled) to every
 * test file so component tests do not have to import them individually.
 */
import '@testing-library/jest-dom/vitest';
