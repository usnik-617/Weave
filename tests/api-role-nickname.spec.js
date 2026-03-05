const { test, expect } = require('@playwright/test');

function uniqueId() {
  return `${Date.now()}${Math.floor(Math.random() * 10000)}`;
}

async function getCsrfToken(request) {
  const response = await request.get('/api/auth/csrf');
  expect(response.ok()).toBeTruthy();
  const body = await response.json();
  return body?.data?.csrfToken || body?.csrfToken || body?.data?.token;
}

const TEST_HEADER = { 'X-Playwright-Test': '1' };

async function loginAdmin(request) {
  for (let attempt = 0; attempt < 3; attempt++) {
    const loginCsrf = await getCsrfToken(request);
    const login = await request.post('/api/auth/login?playwright_test=1', {
      data: { username: 'admin', password: 'Weave!2026' },
      headers: { 'X-CSRF-Token': loginCsrf, ...TEST_HEADER },
    });
    if (login.ok()) return;
    const status = login.status();
    const text = await login.text();
    if (status === 429 && attempt < 2) {
      await new Promise((resolve) => setTimeout(resolve, 200));
      continue;
    }
    throw new Error(`admin login failed(${status}): ${text}`);
  }
}

test('역할/닉네임 정책 기본 동작', async ({ request }) => {
  const uid = uniqueId();
  const short = uid.slice(-6);

  await loginAdmin(request);

  const firstNickname = `변경${short}`;
  const patchCsrf1 = await getCsrfToken(request);
  const patch1 = await request.patch('/api/me/nickname', {
    data: { nickname: firstNickname },
    headers: { 'X-CSRF-Token': patchCsrf1, ...TEST_HEADER },
  });
  expect(patch1.status()).toBe(403);

  const secondNickname = `재변${short}`;
  const patchCsrf2 = await getCsrfToken(request);
  const patch2 = await request.patch('/api/me/nickname', {
    data: { nickname: secondNickname },
    headers: { 'X-CSRF-Token': patchCsrf2, ...TEST_HEADER },
  });
  expect(patch2.status()).toBe(403);

  const roleCsrf1 = await getCsrfToken(request);
  const memberRequest = await request.post('/api/role-requests/member', {
    data: {},
    headers: { 'X-CSRF-Token': roleCsrf1, ...TEST_HEADER },
  });
  expect(memberRequest.status()).toBe(400);

  const roleCsrf2 = await getCsrfToken(request);
  const duplicateRequest = await request.post('/api/role-requests/member', {
    data: {},
    headers: { 'X-CSRF-Token': roleCsrf2, ...TEST_HEADER },
  });
  expect(duplicateRequest.status()).toBe(400);
});
