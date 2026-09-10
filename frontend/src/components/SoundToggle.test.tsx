// @vitest-environment jsdom
/**
 * SoundToggle (F-15): mirrors the persisted soundEnabled flag into its label/title/icon and
 * flips the store on click. The store is the real zustand store; it is reset around each test.
 */
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { SoundToggle } from './SoundToggle';
import { staffStore } from '@/stores/staffStore';

const label = () => screen.getByRole('button').getAttribute('aria-label');
const title = () => screen.getByRole('button').getAttribute('title');

beforeEach(() => staffStore.getState().setSoundEnabled(true));
afterEach(() => {
  cleanup();
  staffStore.getState().setSoundEnabled(true);
});

describe('SoundToggle', () => {
  it('shows the enabled state from the store', () => {
    render(<SoundToggle />);
    expect(label()).toBe('Disable sound');
    expect(title()).toBe('Sound enabled');
  });

  it('flips the store and the label on click', () => {
    render(<SoundToggle />);
    fireEvent.click(screen.getByRole('button'));
    expect(staffStore.getState().soundEnabled).toBe(false);
    expect(label()).toBe('Enable sound');
    expect(title()).toBe('Sound disabled');
  });

  it('reflects a store change made elsewhere', () => {
    const { rerender } = render(<SoundToggle />);
    staffStore.getState().setSoundEnabled(false);
    rerender(<SoundToggle />);
    expect(label()).toBe('Enable sound');
  });

  it('appends className', () => {
    render(<SoundToggle className="absolute right-0" />);
    expect(screen.getByRole('button').className).toContain('absolute right-0');
  });
});
