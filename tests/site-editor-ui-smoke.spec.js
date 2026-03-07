const { test, expect } = require('@playwright/test');

test.use({ serviceWorkers: 'block' });

test('관리자 편집 UI 스모크: 통계/푸터 편집 + 배경 위치 드래그', async ({ page }) => {
  const mockState = { textEdits: {}, imageEdits: {} };
  let mockUpdatedAt = '2026-03-08T00:00:00';

  await page.route('**/api/auth/me**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        user: {
          id: 1,
          username: 'admin',
          nickname: '관리자',
          role: 'ADMIN',
          status: 'active',
          isAdmin: true,
        },
      }),
    });
  });

  await page.route('**/api/content/site-editor', async (route) => {
    const req = route.request();
    if (req.method() === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, state: mockState, updatedAt: mockUpdatedAt }),
      });
      return;
    }
    if (req.method() === 'PUT') {
      const body = req.postDataJSON() || {};
      const next = body.state || body;
      mockState.textEdits = next.textEdits || {};
      mockState.imageEdits = next.imageEdits || {};
      mockUpdatedAt = `2026-03-08T00:00:${String((Number(mockUpdatedAt.slice(-2)) + 1) % 60).padStart(2, '0')}`;
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, state: mockState, updatedAt: mockUpdatedAt }),
      });
      return;
    }
    await route.continue();
  });

  await page.route('**/api/content/site-editor/history**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, items: [] }),
    });
  });

  await page.route('**/api/content/site-editor/undo**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, state: mockState, updatedAt: mockUpdatedAt }),
    });
  });

  await page.route('**/api/content/site-editor/reset**', async (route) => {
    mockState.textEdits = {};
    mockState.imageEdits = {};
    mockUpdatedAt = '2026-03-08T00:00:00';
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, state: mockState, updatedAt: mockUpdatedAt }),
    });
  });

  await page.addInitScript(() => {
    window.__WEAVE_E2E__ = true;
    const adminUser = {
      id: 1,
      name: '관리자',
      username: 'admin',
      nickname: '관리자',
      email: 'admin@weave.com',
      role: 'ADMIN',
      status: 'active',
      isAdmin: true,
    };
    localStorage.setItem('weave_current_user', JSON.stringify(adminUser));
  });

  await page.goto('/');

  await expect(page.locator('#site-edit-toggle-btn')).toBeVisible();
  await page.click('#site-edit-toggle-btn');
  await expect(page.locator('#site-edit-toggle-btn')).toContainText('편집 종료');

  await expect(page.locator('#stat-generation')).toHaveAttribute('contenteditable', 'true');
  await expect(page.locator('footer h5')).toHaveAttribute('contenteditable', 'true');
  await expect(page.locator('#join-inquiry-panel h5').first()).toHaveAttribute('contenteditable', 'true');

  await page.evaluate(() => {
    const stat = document.getElementById('stat-generation');
    if (stat) stat.innerHTML = '99기';
    const footerTitle = document.querySelector('footer h5');
    if (footerTitle) footerTitle.innerHTML = '푸터 테스트 제목';
    const joinInquiryTitle = document.querySelector('#join-inquiry-panel h5');
    if (joinInquiryTitle) joinInquiryTitle.innerHTML = '문의하기 테스트 제목';
  });

  await page.click('#site-edit-save-btn');
  await expect(page.locator('#stat-generation')).toContainText('99기');
  await expect(page.locator('footer h5')).toContainText('푸터 테스트 제목');
  await expect(page.locator('#join-inquiry-panel h5').first()).toContainText('문의하기 테스트 제목');

  // 배경 위치 드래그 동작 확인
  await page.evaluate(() => {
    document.querySelectorAll('[class*="panel"]').forEach((el) => el.classList.remove('panel-active'));
    document.getElementById('write')?.classList.add('panel-active');
    const statsTab = document.getElementById('stats-tab');
    if (statsTab) statsTab.click();
  });

  await expect(page.locator('#home-hero-bg-preview')).toBeVisible();
  const beforeX = await page.inputValue('#home-hero-bg-position-x-number');
  const beforeY = await page.inputValue('#home-hero-bg-position-y-number');

  await page.evaluate(() => {
    const preview = document.getElementById('home-hero-bg-preview');
    if (!preview) return;
    const rect = preview.getBoundingClientRect();
    const startX = rect.left + Math.max(10, Math.floor(rect.width * 0.2));
    const startY = rect.top + Math.max(10, Math.floor(rect.height * 0.2));
    const endX = rect.left + Math.max(20, Math.floor(rect.width * 0.8));
    const endY = rect.top + Math.max(20, Math.floor(rect.height * 0.7));

    preview.dispatchEvent(new PointerEvent('pointerdown', {
      bubbles: true,
      pointerId: 1,
      clientX: startX,
      clientY: startY,
    }));
    preview.dispatchEvent(new PointerEvent('pointermove', {
      bubbles: true,
      pointerId: 1,
      clientX: endX,
      clientY: endY,
    }));
    preview.dispatchEvent(new PointerEvent('pointerup', { bubbles: true, pointerId: 1 }));
  });

  const afterX = await page.inputValue('#home-hero-bg-position-x-number');
  const afterY = await page.inputValue('#home-hero-bg-position-y-number');

  expect(afterX).not.toBe(beforeX);
  expect(afterY).not.toBe(beforeY);

  await expect(page.locator('#home-hero-bg-image-input')).toBeVisible();
  await expect(page.locator('#home-hero-bg-image-dropzone')).toBeVisible();

  // 로고 파일 교체 컨트롤은 없어야 함
  await expect(page.locator('#home-hero-image-input')).toHaveCount(0);
  await expect(page.locator('#home-hero-image-dropzone')).toHaveCount(0);
});
