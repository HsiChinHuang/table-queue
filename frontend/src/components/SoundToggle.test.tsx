// @vitest-environment jsdom
/**
 * SoundToggle (F-15): mirrors the persisted soundEnabled flag into its label/title/icon and
 * flips the store on click. The store is the real zustand store; it is reset around each test.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
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

// T17 AC-5: jsdom has no AudioContext, so a recording class stands in for it.
class MockAudioContext {
  static instances: MockAudioContext[] = [];
  state: 'suspended' | 'running' | 'closed' = 'running';
  currentTime = 0;
  destination: unknown = {};
  close = vi.fn(async () => {
    this.state = 'closed';
  });
  createOscillator = vi.fn(() => ({
    connect: vi.fn(),
    start: vi.fn(),
    stop: vi.fn(),
    frequency: { value: 0 },
  }));
  createGain = vi.fn(() => ({
    connect: vi.fn(),
    gain: { setValueAtTime: vi.fn(), exponentialRampToValueAtTime: vi.fn() },
  }));
  constructor() {
    MockAudioContext.instances.push(this);
  }
}

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

describe('T17 AudioContext lifecycle (AC-5)', () => {
  beforeEach(() => {
    MockAudioContext.instances = [];
    vi.stubGlobal('AudioContext', MockAudioContext);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('creates at most one AudioContext: lazy on first interaction, reused across beeps, closed on unmount', () => {
    const { unmount } = render(<SoundToggle />);
    const button = screen.getByRole('button');
    // Rendered enabled - but never at mount: zero instances so far.
    expect(MockAudioContext.instances.length).toBe(0);
    fireEvent.click(button); // off: no beep, no context
    expect(MockAudioContext.instances.length).toBe(0);
    fireEvent.click(button); // on: first beep -> exactly one instance, oscillator started
    expect(MockAudioContext.instances.length).toBe(1);
    const ctx = MockAudioContext.instances[0];
    expect(ctx.createOscillator).toHaveBeenCalledTimes(1);
    expect(ctx.createOscillator.mock.results[0].value.start).toHaveBeenCalledTimes(1);
    // Toggle off->on for a second beep: the SAME instance is reused.
    fireEvent.click(button); // off: no beep
    expect(ctx.createOscillator).toHaveBeenCalledTimes(1);
    fireEvent.click(button); // on: beep #2
    expect(MockAudioContext.instances.length).toBe(1); // no per-beep construction
    expect(ctx.createOscillator).toHaveBeenCalledTimes(2);
    // Teardown closes the one instance - no live context left behind.
    unmount();
    expect(ctx.close).toHaveBeenCalledTimes(1);
    expect(ctx.state).toBe('closed');
  });

  it('registers the first-interaction unlock listeners once, not per toggle', () => {
    const addSpy = vi.spyOn(window, 'addEventListener');
    render(<SoundToggle />);
    const button = screen.getByRole('button');
    fireEvent.click(button); // off
    fireEvent.click(button); // on
    fireEvent.click(button); // off
    expect(addSpy.mock.calls.filter((c) => c[0] === 'click').length).toBeLessThanOrEqual(1);
    expect(addSpy.mock.calls.filter((c) => c[0] === 'keydown').length).toBeLessThanOrEqual(1);
    addSpy.mockRestore();
  });

  it('after many toggles a single interaction still arms a beep on the same context', () => {
    render(<SoundToggle />);
    const button = screen.getByRole('button');
    for (let i = 0; i < 3; i++) {
      fireEvent.click(button); // off
      fireEvent.click(button); // on: toggle-on click beeps
    }
    expect(MockAudioContext.instances.length).toBe(1); // one context for the whole dance
    const ctx = MockAudioContext.instances[0];
    expect(ctx.createOscillator).toHaveBeenCalledTimes(3);
    // One more single user interaction: still armed, still the same instance.
    fireEvent.keyDown(window, { key: 'a' });
    expect(MockAudioContext.instances.length).toBe(1);
    expect(ctx.createOscillator).toHaveBeenCalledTimes(4);
  });
});
