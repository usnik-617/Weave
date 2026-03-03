const { test, expect } = require('@playwright/test');

test('관리자 공지 봉사 날짜가 캘린더에 연동된다', async ({ page }) => {
  await page.goto('/');

  page.once('dialog', async (dialog) => {
    await dialog.accept();
  });
  await page.getByRole('button', { name: '로그인' }).click();
  await page.locator('#login-form [name="username"]').fill('admin');
  await page.locator('#login-form [name="password"]').fill('Weave!2026');
  await page.locator('#login-form button[type="submit"]').click();

  await expect(page.locator('#user-profile')).toHaveClass(/show/);

  await page.getByRole('link', { name: '소식' }).click();
  await expect(page.locator('#news-write-btn')).toBeVisible();

  await page.locator('#news-write-btn').click();
  await expect(page.locator('#add-news-form')).toBeVisible();

  const unique = Date.now();
  const title = `위브 워크샵 안내 ${unique}`;

  await page.locator('#add-news-form [name="title"]').fill(title);
  await page.locator('#add-news-form [name="postTab"]').selectOption('notice');
  await page.locator('#add-news-form [name="volunteerStartDate"]').fill('2026-04-11');
  await page.locator('#add-news-form [name="volunteerEndDate"]').fill('2026-04-12');
  await page.locator('#add-news-form [name="author"]').fill('관리자');
  await page.locator('#news-editor').fill('실제 일정: 2026-04-11~2026-04-12 / 장소: 가평');

  page.once('dialog', async (dialog) => {
    await dialog.accept();
  });
  await page.locator('#add-news-form button[type="submit"]').click();

  await page.getByRole('link', { name: '활동' }).click();
  await page.locator('#activities-calendar-tab-btn').click();

  await page.locator('#calendar-next-btn').click();
  await expect(page.locator('#calendar-current-label')).toContainText('2026년 4월');

  const dayCell = page.locator('#calendar-grid [data-date="2026-04-11"]');
  const dayCell2 = page.locator('#calendar-grid [data-date="2026-04-12"]');
  await expect(dayCell).toBeVisible();
  await expect(dayCell2).toBeVisible();
  await expect(dayCell).toContainText('워크샵 안내');
  await expect(dayCell2).toContainText('워크샵 안내');

  await dayCell.click();
  await expect(page.locator('#calendarActivityDetailModal')).toHaveClass(/show/);
  await expect(page.locator('#calendar-activity-detail-body')).toContainText(title);
  await expect(page.locator('#calendar-activity-detail-body')).toContainText('가평');
});
