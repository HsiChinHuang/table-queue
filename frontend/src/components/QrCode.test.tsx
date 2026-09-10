// @vitest-environment jsdom
/**
 * QrCode (F-15): wraps qrcode.react's QRCodeSVG with the design-system colours, so the payload
 * must land in a real <svg> and the wrapper must stay centred.
 */
import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, render } from '@testing-library/react';
import { QrCode } from './QrCode';

afterEach(cleanup);

describe('QrCode', () => {
  it('renders an svg QR for the given value', () => {
    const { container } = render(<QrCode value="https://example.test/join?branch=1" />);
    const svg = container.querySelector('svg');
    expect(svg).toBeTruthy();
    expect(svg?.getAttribute('viewBox')).toBeTruthy();
  });

  it('uses the requested pixel size', () => {
    const { container } = render(<QrCode value="x" size={120} />);
    const svg = container.querySelector('svg');
    expect(svg?.getAttribute('width')).toBe('120');
    expect(svg?.getAttribute('height')).toBe('120');
  });

  it('centres the code and appends className', () => {
    const { container } = render(<QrCode value="x" className="mt-6" />);
    const wrapper = container.firstElementChild;
    expect(wrapper?.className).toContain('flex');
    expect(wrapper?.className).toContain('justify-center');
    expect(wrapper?.className).toContain('mt-6');
  });

  it('encodes a different payload into a different svg', () => {
    const { container: a, unmount: unmountA } = render(<QrCode value="AAA" />);
    const first = a.innerHTML;
    unmountA();
    const { container: b } = render(<QrCode value="BBB" />);
    expect(first).not.toBe(b.innerHTML);
  });
});
