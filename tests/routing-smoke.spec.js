const { test, expect } = require('@playwright/test');

async function parseJsonSafe(response) {
  const text = await response.text();
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

test('SPA and ops routes smoke check', async ({ request }) => {
  const rootRes = await request.get('/');
  expect(rootRes.ok()).toBeTruthy();
  expect((await rootRes.text()).toLowerCase()).toContain('<!doctype html');

  const spaFallbackRes = await request.get('/route-that-should-fallback-to-spa');
  expect(spaFallbackRes.ok()).toBeTruthy();
  expect((await spaFallbackRes.text()).toLowerCase()).toContain('<!doctype html');

  const healthRes = await request.get('/healthz');
  expect(healthRes.ok()).toBeTruthy();
  const healthBody = await parseJsonSafe(healthRes);
  expect(healthBody?.success).toBeTruthy();
  expect(healthBody?.data?.status).toBe('healthy');

  const metricsRes = await request.get('/metrics');
  expect(metricsRes.ok()).toBeTruthy();
  const metricsBody = await parseJsonSafe(metricsRes);
  expect(typeof metricsBody?.uptime_seconds).toBe('number');
  expect(typeof metricsBody?.total_requests).toBe('number');
});
