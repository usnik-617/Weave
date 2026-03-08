const { test, expect } = require('@playwright/test');

const TEST_HEADER = { 'X-Playwright-Test': '1' };

async function jsonBody(response) {
  const text = await response.text();
  try {
    return JSON.parse(text);
  } catch {
    return { raw: text };
  }
}

async function getCsrfToken(request) {
  const response = await request.get('/api/auth/csrf');
  expect(response.ok()).toBeTruthy();
  const body = await jsonBody(response);
  return body?.data?.csrfToken || body?.csrfToken || body?.data?.token;
}

async function loginAdmin(request) {
  for (let attempt = 0; attempt < 3; attempt += 1) {
    const csrfToken = await getCsrfToken(request);
    const response = await request.post('/api/auth/login?playwright_test=1', {
      data: { username: 'admin', password: 'Weave!2026' },
      headers: { 'X-CSRF-Token': csrfToken, ...TEST_HEADER },
    });
    if (response.ok()) return;
    if (response.status() === 429 && attempt < 2) {
      await new Promise((resolve) => setTimeout(resolve, 200));
      continue;
    }
    throw new Error(`admin login failed(${response.status()}): ${await response.text()}`);
  }
}

test('site-editor history endpoint blocks unauthenticated access', async ({ request }) => {
  const response = await request.get('/api/content/site-editor/history?limit=20');
  expect(response.status()).toBe(401);
});

test('site-editor conflict returns 409 when ifMatchUpdatedAt is stale', async ({ request }) => {
  await loginAdmin(request);

  const stateResponse = await request.get('/api/content/site-editor');
  expect(stateResponse.ok()).toBeTruthy();
  const stateBody = await jsonBody(stateResponse);
  const updatedAt = String(stateBody?.data?.updatedAt || stateBody?.updatedAt || '');

  const csrfToken = await getCsrfToken(request);
  const firstSave = await request.put('/api/content/site-editor', {
    data: {
      state: {
        textEdits: { 'id:home-hero-subtext': `충돌검증-${Date.now()}` },
        imageEdits: {},
      },
      ifMatchUpdatedAt: updatedAt || undefined,
    },
    headers: { 'X-CSRF-Token': csrfToken, ...TEST_HEADER },
  });
  expect(firstSave.status(), await firstSave.text()).toBe(200);

  const staleCsrfToken = await getCsrfToken(request);
  const staleSave = await request.put('/api/content/site-editor', {
    data: {
      state: {
        textEdits: { 'id:home-hero-subtext': `충돌검증-STALE-${Date.now()}` },
        imageEdits: {},
      },
      ifMatchUpdatedAt: updatedAt || undefined,
    },
    headers: { 'X-CSRF-Token': staleCsrfToken, ...TEST_HEADER },
  });
  expect(staleSave.status()).toBe(409);
  const staleBody = await jsonBody(staleSave);
  const staleText = String(staleBody?.error || staleBody?.message || '');
  expect(staleText).toContain('먼저 저장');
});

test('hero_background range validation rejects out-of-range values', async ({ request }) => {
  await loginAdmin(request);
  const csrfToken = await getCsrfToken(request);
  const response = await request.put('/api/content/blocks', {
    data: {
      key: 'hero_background',
      contentHtml: JSON.stringify({
        imageOffsetX: 999,
        imageOffsetY: 0,
        backgroundPosX: 50,
        backgroundPosY: 50,
      }),
    },
    headers: { 'X-CSRF-Token': csrfToken, ...TEST_HEADER },
  });

  expect(response.status()).toBe(400);
  const body = await jsonBody(response);
  const message = String(body?.error || body?.message || '');
  expect(message).toContain('범위');
});
