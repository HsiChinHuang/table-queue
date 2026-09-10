// @vitest-environment jsdom
/**
 * LoadingSkeleton (F-15): each of the five variants renders its own structure and the list
 * variant honours count.
 */
import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, render } from '@testing-library/react';
import { LoadingSkeleton } from './LoadingSkeleton';

const pulseCount = (container: HTMLElement) =>
  container.querySelectorAll('[class*="animate-pulse"]').length;

afterEach(cleanup);

describe('variants', () => {
  it('card renders a bordered placeholder card with action stubs', () => {
    const { container } = render(<LoadingSkeleton variant="card" />);
    const root = container.firstElementChild;
    expect(root?.className).toContain('rounded-xl');
    expect(pulseCount(container)).toBeGreaterThanOrEqual(5);
  });

  it('row renders a single compact line', () => {
    const { container } = render(<LoadingSkeleton variant="row" />);
    expect((container.firstElementChild as HTMLElement).className).toContain('rounded-lg');
    expect(pulseCount(container)).toBe(3);
  });

  it('list repeats `count` blocks', () => {
    const { container } = render(<LoadingSkeleton variant="list" count={4} />);
    expect(pulseCount(container)).toBe(4);
  });

  it('form renders three labelled field stubs plus a submit stub', () => {
    const { container } = render(<LoadingSkeleton variant="form" />);
    expect(pulseCount(container)).toBe(7);
  });

  it('board renders the two-panel board placeholder', () => {
    const { container } = render(<LoadingSkeleton variant="board" />);
    const root = container.firstElementChild;
    expect(root?.className).toContain('grid');
    expect(root?.children.length).toBe(2);
  });

  it('appends className to the rendered root', () => {
    const { container } = render(<LoadingSkeleton variant="list" className="mt-4" />);
    expect(container.firstElementChild?.className).toContain('mt-4');
  });
});
