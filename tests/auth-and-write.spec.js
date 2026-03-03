const { test, expect } = require('@playwright/test');

test('회원가입/로그인 및 글쓰기 패널 전환', async ({ page }) => {
  await page.goto('/');

  const uid = Date.now();
  const username = `user${uid}`;
  const email = `user${uid}@example.com`;

  await page.getByRole('button', { name: '회원가입' }).click();
  await page.locator('#signup-form [name="name"]').fill('테스트유저');
  await page.locator('#signup-form [name="email"]').fill(email);
  await page.locator('#signup-form [name="birthdate"]').fill('2000.01.01');
  await page.locator('#signup-form [name="phone"]').fill('010-1111-2222');
  await page.locator('#signup-form [name="emailConfirm"]').fill(email);
  await page.locator('#signup-form [name="username"]').fill(username);
  await page.locator('#signup-form [name="password"]').fill('Password!123');
  await page.locator('#signup-form [name="confirm-password"]').fill('Password!123');
  await page.locator('#terms-agree').check();
  await page.locator('#privacy-agree').check();

  page.once('dialog', async (dialog) => {
    await dialog.accept();
  });
  await page.locator('#signup-submit-btn').click();

  await expect(page.locator('#user-profile')).toHaveClass(/show/);
  await expect(page.locator('#my-info-btn')).toBeVisible();

  await page.getByRole('button', { name: '소식' }).click().catch(() => {});
  await page.locator('#news-write-btn').click();

  await expect(page.locator('#write')).toHaveClass(/panel-active/);
  await expect(page.locator('#add-news-form')).toBeVisible();
});
