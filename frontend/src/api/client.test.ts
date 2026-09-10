// @vitest-environment jsdom
/**
 * Tests for the API client (F-15): URL construction, auth header, 204/401/429/5xx handling,
 * body serialisation, header merging, the abort/timeout mapping and the VITE_USE_MOCK branch.
 * fetch is always stubbed - no test here touches the network.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { API_BASE_URL, del, get, patch, post, put } from './client';
import { ApiError } from './errors';
import { staffStore } from './staffStore';

interface Stub {
  ok?: boolean;
  status?: number;
  body?: unknown;
  rejectWith?: Error;
}

const calls: { url: string; init: RequestInit }[] = [];

function stubFetch({ ok = true, status = 200, body = null, rejectWith }: Stub = {}) {
  calls.length = 0;
  const fetchMock = vi.fn(async (url: unknown, init: RequestInit) => {
    calls.push({ url: String(url), init });
    if (rejectWith) throw rejectWith;
    return {
      ok,
      status,
      json: async () => body,
    };
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

const sentBody = () => (calls.length ? calls[0].init.body : undefined);

beforeEach(() => {
  staffStore.clearToken();
  vi.unstubAllEnvs();
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  staffStore.clearToken();
});

describe('URL and method', () => {
  it('prefixes API_BASE_URL and defaults the Content-Type header', async () => {
    stubFetch({ body: { id: 'branch-001' } });
    const data = await get<{ id: string }>('/public/branches/branch-001');
    expect(data).toEqual({ id: 'branch-001' });
    expect(calls[0].url).toBe(`${API_BASE_URL}/public/branches/branch-001`);
    expect(calls[0].init.method).toBe('GET');
    expect(calls[0].init.headers).toMatchObject({ 'Content-Type': 'application/json' });
    expect(calls[0].init.signal).toBeInstanceOf(AbortSignal);
  });

  it('exposes the default base URL', () => {
    expect(API_BASE_URL).toBe('/api/v1');
  });
});

describe('auth header', () => {
  it('sends the bearer token once one is stored', async () => {
    staffStore.setToken('abc1239999');
    stubFetch({ body: { ok: true } });
    await get('/staff/dashboard');
    expect(calls[0].init.headers).toMatchObject({ Authorization: 'Bearer abc1239999' });
  });

  it('omits the Authorization header when logged out', async () => {
    stubFetch({ body: {} });
    await get('/staff/dashboard');
    expect(calls[0].init.headers).not.toHaveProperty('Authorization');
  });

  it('merges caller-supplied headers over the defaults', async () => {
    stubFetch({ body: {} });
    await get('/staff/dashboard', { 'X-Trace': 'trace-1' });
    expect(calls[0].init.headers).toMatchObject({ 'X-Trace': 'trace-1' });
  });
});

describe('response handling', () => {
  it('returns null for 204 No Content without parsing the body', async () => {
    stubFetch({ ok: true, status: 204 });
    expect(await del('/staff/waitlist/1')).toBeNull();
  });

  it('posts the body as JSON and returns the parsed payload', async () => {
    stubFetch({ body: { queue_number: 'A001' } });
    const data = await post<{ queue_number: string }>('/public/waitlist', { party_size: 4 });
    expect(sentBody()).toBe(JSON.stringify({ party_size: 4 }));
    expect(data).toEqual({ queue_number: 'A001' });
  });

  it('sends PUT, PATCH and DELETE verbs', async () => {
    stubFetch({ body: {} });
    await put('/staff/settings', { hold_minutes: 10 });
    expect(calls[0].init.method).toBe('PUT');
    await patch('/staff/settings', { hold_minutes: 12 });
    expect(calls[1].init.method).toBe('PATCH');
    await del('/staff/tables/t1');
    expect(calls[2].init.method).toBe('DELETE');
  });

  it('omits the body when none is given', async () => {
    stubFetch({ body: {} });
    await post('/staff/pin/change');
    expect(sentBody()).toBeUndefined();
  });

  it('maps a domain error body to an ApiError with its code and details', async () => {
    stubFetch({
      ok: false,
      status: 422,
      body: { error: { code: 'VALIDATION_ERROR', message: 'party size too big', details: { max: 20 } } },
    });
    await expect(get('/public/waitlist')).rejects.toBeInstanceOf(ApiError);
    await expect(get('/public/waitlist')).rejects.toMatchObject({
      code: 'VALIDATION_ERROR',
      statusCode: 422,
      message: 'party size too big',
      details: { max: 20 },
    });
  });

  it('falls back to the mapped message when the error body has no message', async () => {
    stubFetch({ ok: false, status: 404, body: { error: { code: 'WAITLIST_NOT_FOUND' } } });
    await expect(get('/public/waitlist')).rejects.toMatchObject({
      code: 'WAITLIST_NOT_FOUND',
      statusCode: 404,
    });
  });

  it('uses INTERNAL_ERROR when the error body carries no code', async () => {
    stubFetch({ ok: false, status: 400, body: { detail: 'bad' } });
    await expect(get('/public/waitlist')).rejects.toMatchObject({ code: 'INTERNAL_ERROR' });
  });

  it('maps 5xx to the generic retry message', async () => {
    stubFetch({ ok: false, status: 503, body: {} });
    await expect(get('/staff/tables')).rejects.toMatchObject({
      code: 'INTERNAL_ERROR',
      statusCode: 503,
      message: 'Something went wrong. Please try again.',
    });
  });

  it('maps 429 to RATE_LIMITED', async () => {
    stubFetch({ ok: false, status: 429, body: {} });
    await expect(get('/public/waitlist')).rejects.toMatchObject({
      code: 'RATE_LIMITED',
      statusCode: 429,
    });
  });

  it('clears the token and redirects on 401', async () => {
    // jsdom refuses real navigation, so replace window.location with a plain probe object.
    const locationProbe: { href: string } = { href: '' };
    vi.stubGlobal('location', locationProbe);
    Object.defineProperty(window, 'location', { value: locationProbe, writable: true, configurable: true });
    staffStore.setToken('stale-token');
    stubFetch({ ok: false, status: 401, body: {} });
    await expect(get('/staff/dashboard')).rejects.toMatchObject({
      code: 'AUTH_TOKEN_EXPIRED',
      statusCode: 401,
    });
    expect(staffStore.token).toBeNull();
    expect(locationProbe.href).toBe('/staff/login');
  });

  it('maps a network failure to NETWORK_ERROR with status 0', async () => {
    stubFetch({ rejectWith: new TypeError('Failed to fetch') });
    await expect(get('/staff/dashboard')).rejects.toMatchObject({
      code: 'NETWORK_ERROR',
      statusCode: 0,
      message: 'Network error. Please check your connection.',
    });
  });

  it('maps an aborted request to the timeout message', async () => {
    const abort = new Error('The operation was aborted');
    abort.name = 'AbortError';
    stubFetch({ rejectWith: abort });
    await expect(get('/staff/dashboard')).rejects.toMatchObject({
      code: 'NETWORK_ERROR',
      message: 'Request timed out. Please check your connection.',
    });
  });

  it('re-throws ApiError unchanged', async () => {
    stubFetch({ rejectWith: new ApiError('CONFLICT', 409, 'someone moved first') });
    await expect(post('/staff/waitlist/1/seat', {})).rejects.toBeInstanceOf(ApiError);
    await expect(post('/staff/waitlist/1/seat', {})).rejects.toMatchObject({
      code: 'CONFLICT',
      statusCode: 409,
    });
  });
});

describe('mock mode', () => {
  it('answers from the mock layer without calling fetch', async () => {
    const fetchMock = stubFetch({ body: { never: true } });
    vi.stubEnv('VITE_USE_MOCK', 'true');
    const data = await get<{ success: boolean }>('/unhandled/path');
    expect(fetchMock).not.toHaveBeenCalled();
    expect(data).toEqual({ success: true, data: null });
    vi.stubEnv('VITE_USE_MOCK', 'false');
  });

  it('reaches a registered mock handler for a staff login', async () => {
    const fetchMock = stubFetch({});
    vi.stubEnv('VITE_USE_MOCK', 'true');
    const data = await post<{ success?: boolean; token?: string }>('/api/v1/staff/login', {
      pin: '1234',
    });
    expect(fetchMock).not.toHaveBeenCalled();
    expect(data).toBeTruthy();
    vi.stubEnv('VITE_USE_MOCK', 'false');
  });
});
