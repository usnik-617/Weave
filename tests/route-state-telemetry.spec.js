const { test, expect } = require('@playwright/test');

test('route-state helper updates URL query', async ({ page }) => {
  await page.goto('/');

  await page.evaluate(() => {
    if (typeof updateAppUrlState !== 'function') {
      throw new Error('updateAppUrlState is not available');
    }
    updateAppUrlState({
      panel: 'news',
      newsTab: 'faq',
      q: '정책',
      page: '2',
    });
  });

  await expect(page).toHaveURL(/panel=news/);
  await expect(page).toHaveURL(/newsTab=faq/);
  await expect(page).toHaveURL(/q=%EC%A0%95%EC%B1%85/);
  await expect(page).toHaveURL(/page=2/);
});

test('client telemetry reset returns zero snapshot', async ({ page }) => {
  await page.goto('/');

  const snapshot = await page.evaluate(() => {
    if (typeof getClientTelemetrySnapshot !== 'function') {
      throw new Error('getClientTelemetrySnapshot is not available');
    }
    if (typeof resetClientTelemetry !== 'function') {
      throw new Error('resetClientTelemetry is not available');
    }
    resetClientTelemetry();
    return getClientTelemetrySnapshot();
  });

  expect(snapshot.errors403).toBe(0);
  expect(snapshot.errors429).toBe(0);
  expect(snapshot.uploadFailures).toBe(0);
});
