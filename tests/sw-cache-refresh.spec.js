const { test, expect } = require('@playwright/test');

test.describe('service worker refresh policy', () => {
  test('registers versioned service worker and serves no-store sw.js', async ({ page }) => {
    await page.goto('/');

    const assetVersion = await page.locator('meta[name="weave-asset-version"]').getAttribute('content');
    expect(assetVersion).toBeTruthy();

    const registrationUrl = await page.evaluate(async () => {
      if (!('serviceWorker' in navigator)) return '';
      const reg = await navigator.serviceWorker.getRegistration();
      if (!reg || !reg.active) return '';
      return String(reg.active.scriptURL || '');
    });
    expect(registrationUrl).toContain('/sw.js');
    expect(registrationUrl).toContain('v=');

    const swResponse = await page.request.get('/sw.js');
    expect(swResponse.ok()).toBeTruthy();
    const cacheControl = String(swResponse.headers()['cache-control'] || '').toLowerCase();
    expect(cacheControl).toContain('no-store');
  });
});
