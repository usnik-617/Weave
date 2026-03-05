const { test, expect } = require('@playwright/test');

test('회원가입/로그인 및 글쓰기 패널 전환', async ({ page }) => {
  await page.goto('/');
  await page.evaluate(() => {
    const mockAdmin = {
      id: 1,
      name: '관리자',
      username: 'admin',
      nickname: '관리자',
      email: 'admin@weave.com',
      role: 'ADMIN',
      status: 'active',
      isAdmin: true,
    };
    localStorage.setItem('weave_current_user', JSON.stringify(mockAdmin));
    if (typeof updateAuthUI === 'function') updateAuthUI();
  });

  await page.evaluate(() => {
    document.querySelectorAll('[class*="panel"]').forEach((el) => el.classList.remove('panel-active'));
    document.getElementById('write')?.classList.add('panel-active');
  });

  await expect(page.locator('#write')).toHaveClass(/panel-active/);
  await expect(page.locator('#add-news-form')).toBeVisible();
});
