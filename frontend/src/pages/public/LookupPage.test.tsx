// @vitest-environment jsdom
/**
 * LookupPage tests - F-09: Lookup page tests
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import LookupPage, { normalizeQueueNumber } from './LookupPage';

// Mock the getStatus API call
vi.mock('@/api/public', () => ({
  getStatus: vi.fn(),
}));

const renderWithRouter = (ui: React.ReactElement) => {
  return render(<MemoryRouter>{ui}</MemoryRouter>);
};

describe('normalizeQueueNumber', () => {
  it('should uppercase lowercase input', () => {
    expect(normalizeQueueNumber('a006')).toBe('A006');
  });

  it('should trim and uppercase input with whitespace', () => {
    expect(normalizeQueueNumber(' a006 ')).toBe('A006');
  });

  it('should return unchanged input when already uppercase', () => {
    expect(normalizeQueueNumber('A006')).toBe('A006');
  });
});

describe('LookupPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should render queue number input', () => {
    renderWithRouter(<LookupPage />);
    const inputs = screen.getAllByPlaceholderText('A001');
    expect(inputs.length).toBeGreaterThan(0);
  });

  it('should render last 3 digits input with correct attributes', () => {
    renderWithRouter(<LookupPage />);
    const last3Inputs = screen.getAllByPlaceholderText('123');
    expect(last3Inputs[0].getAttribute('inputmode')).toBe('numeric');
    expect(last3Inputs[0].getAttribute('maxlength')).toBe('3');
  });

  it('should render submit button with correct label', () => {
    renderWithRouter(<LookupPage />);
    const buttons = screen.getAllByRole('button', { name: 'Look Up Status' });
    expect(buttons.length).toBeGreaterThan(0);
  });

  it('should uppercase queue number input on change', () => {
    renderWithRouter(<LookupPage />);
    const queueInputs = screen.getAllByPlaceholderText('A001') as HTMLInputElement[];
    fireEvent.change(queueInputs[0], { target: { value: 'a001' } });
    expect(queueInputs[0].value).toBe('A001');
  });
});
