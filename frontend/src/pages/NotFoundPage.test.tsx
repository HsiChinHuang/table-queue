// @vitest-environment jsdom
/**
 * NotFoundPage (F-15). The page ships a single static call to action; the design brief also
 * asked for a path-dependent one, recorded below as a defect instead of silently asserting it.
 */
import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import NotFoundPage from './NotFoundPage';

afterEach(cleanup);

const renderAt = (path: string) =>
  render(
    <MemoryRouter initialEntries={[path]}>
      <NotFoundPage />
    </MemoryRouter>,
  );

describe('NotFoundPage', () => {
  it('shows the 404 copy', () => {
    renderAt('/staff/board');
    expect(screen.getByRole('heading', { level: 1, name: 'Page not found.' })).toBeTruthy();
    expect(screen.getByText('The page you are looking for does not exist.')).toBeTruthy();
  });

  it('links back to the public join page', () => {
    renderAt('/join/branch-001');
    const link = screen.getByRole('link', { name: 'Go home' });
    expect(link.getAttribute('href')).toBe('/join?branch=1');
  });

  it('DEFECT DEF-F15-1: the CTA ignores the current path (design brief wants a staff route for /staff/*)', () => {
    // design-briefs.md wants 'Back to Board' pointing at /staff/board for staff paths; the F-05
    // page always links to /join?branch=1. F-15 may not edit pages/NotFoundPage.tsx (F-05 owns it).
    renderAt('/staff/board');
    expect(screen.getByRole('link', { name: 'Go home' }).getAttribute('href')).toBe('/join?branch=1');
    expect(screen.queryByRole('link', { name: 'Back to Board' })).toBeNull();
  });
});
