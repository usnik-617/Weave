const { test, expect } = require('@playwright/test');

test('관리자 저장 내용이 일반 사용자에도 반영되고 특정 이력 복원이 동작한다', async ({ browser }) => {
  const state = {
    current: { textEdits: {}, imageEdits: {} },
    history: [],
    nextId: 1,
  };

  const routeApi = async (route) => {
    const request = route.request();
    const method = request.method();
    const url = new URL(request.url());
    const path = url.pathname;

    if (path === '/api/auth/me') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, data: { user: null } }),
      });
      return;
    }

    if (path === '/api/auth/csrf') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, data: { csrfToken: 'test-token' } }),
      });
      return;
    }

    if (path === '/api/content/site-editor' && method === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, data: { state: state.current } }),
      });
      return;
    }

    if (path === '/api/content/site-editor' && method === 'PUT') {
      const payload = request.postDataJSON() || {};
      state.history.push({
        id: state.nextId++,
        action: 'save',
        createdAt: new Date().toISOString(),
        createdBy: 1,
        createdByUsername: 'admin',
        state: state.current,
      });
      state.current = {
        textEdits: payload.textEdits || {},
        imageEdits: payload.imageEdits || {},
      };
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, data: { state: state.current } }),
      });
      return;
    }

    if (path === '/api/content/site-editor' && method === 'DELETE') {
      state.history.push({
        id: state.nextId++,
        action: 'reset',
        createdAt: new Date().toISOString(),
        createdBy: 1,
        createdByUsername: 'admin',
        state: state.current,
      });
      state.current = { textEdits: {}, imageEdits: {} };
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, data: { state: state.current } }),
      });
      return;
    }

    if (path.startsWith('/api/content/site-editor/history') && method === 'GET') {
      const items = [...state.history].sort((a, b) => b.id - a.id);
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, data: { items } }),
      });
      return;
    }

    if (path === '/api/content/site-editor/undo' && method === 'POST') {
      const last = state.history.pop();
      if (!last) {
        await route.fulfill({
          status: 404,
          contentType: 'application/json',
          body: JSON.stringify({ success: false, error: '되돌릴 수정 이력이 없습니다.' }),
        });
        return;
      }
      state.current = last.state;
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, data: { state: state.current } }),
      });
      return;
    }

    if (path === '/api/content/site-editor/restore' && method === 'POST') {
      const payload = request.postDataJSON() || {};
      const historyId = Number(payload.historyId || 0);
      const target = state.history.find((item) => item.id === historyId);
      if (!target) {
        await route.fulfill({
          status: 404,
          contentType: 'application/json',
          body: JSON.stringify({ success: false, error: '선택한 수정 이력을 찾을 수 없습니다.' }),
        });
        return;
      }
      state.history.push({
        id: state.nextId++,
        action: 'restore',
        createdAt: new Date().toISOString(),
        createdBy: 1,
        createdByUsername: 'admin',
        state: state.current,
      });
      state.current = target.state;
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, data: { state: state.current } }),
      });
      return;
    }

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, data: { items: [], user: null } }),
    });
  };

  const adminContext = await browser.newContext({ serviceWorkers: 'block' });
  await adminContext.route('**/api/**', routeApi);
  const adminPage = await adminContext.newPage();

  await adminPage.goto('/');
  await adminPage.evaluate(() => {
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
    if (typeof updateAuthUI === 'function') updateAuthUI();
  });

  await adminPage.click('#site-edit-toggle-btn');

  await expect(adminPage.locator('#activities .section-header h2')).toHaveAttribute('contenteditable', 'true');

  await adminPage.evaluate(() => {
    const text = document.getElementById('home-hero-subtext');
    if (text) text.innerHTML = '홈 소개 문구 A';
  });
  await adminPage.click('#site-edit-save-btn');
  await expect(adminPage.locator('#home-hero-subtext')).toContainText('홈 소개 문구 A');

  await adminPage.evaluate(() => {
    const text = document.getElementById('home-hero-subtext');
    if (text) text.innerHTML = '홈 소개 문구 B';
  });
  await adminPage.evaluate(async () => {
    const payload = {
      textEdits: { 'id:home-hero-subtext': '홈 소개 문구 B' },
      imageEdits: {},
    };
    const saved = await saveSiteEditorPayloadToServer(payload);
    resetSiteEditorDomToDefaults();
    applySiteEditorPayload(saved);
    cacheSiteEditorPayload(saved);
  });
  await expect(adminPage.locator('#home-hero-subtext')).toContainText('홈 소개 문구 B');

  const viewerContext = await browser.newContext({ serviceWorkers: 'block' });
  await viewerContext.route('**/api/**', routeApi);
  const viewerPage = await viewerContext.newPage();
  await viewerPage.goto('/');
  await expect(viewerPage.locator('#home-hero-subtext')).toContainText('홈 소개 문구 B');

  await adminPage.click('#site-edit-history-refresh-btn');
  const optionCount = await adminPage.locator('#site-edit-history-select option').count();
  expect(optionCount).toBeGreaterThan(1);

  const targetHistoryId = await adminPage.evaluate(async () => {
    const items = await fetchSiteEditorHistoryFromServer(30);
    const found = items.find((item) => {
      const state = item && item.state ? item.state : {};
      const textEdits = state && state.textEdits ? state.textEdits : {};
      return textEdits['id:home-hero-subtext'] === '홈 소개 문구 A';
    });
    return Number(found && found.id ? found.id : 0);
  });
  expect(targetHistoryId).toBeGreaterThan(0);
  await adminPage.selectOption('#site-edit-history-select', String(targetHistoryId));
  await adminPage.click('#site-edit-history-restore-btn');
  await expect(adminPage.locator('#home-hero-subtext')).toContainText('홈 소개 문구 A');

  await viewerPage.reload();
  await expect(viewerPage.locator('#home-hero-subtext')).toContainText('홈 소개 문구 A');

  await adminContext.close();
  await viewerContext.close();
});
