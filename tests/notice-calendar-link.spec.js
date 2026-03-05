const { test, expect } = require('@playwright/test');

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

async function loginAsAdmin(request) {
  const csrfToken = await getCsrfToken(request);
  const response = await request.post('/api/auth/login?playwright_test=1', {
    data: { username: 'admin', password: 'Weave!2026' },
    headers: { 'X-CSRF-Token': csrfToken, 'X-Playwright-Test': '1' },
  });
  expect(response.ok(), await response.text()).toBeTruthy();
}

async function createNoticeWithVolunteerDate(request, title) {
  await loginAsAdmin(request);
  const csrfToken = await getCsrfToken(request);
  const response = await request.post('/api/posts', {
    data: {
      category: 'notice',
      title,
      content: '실제 일정: 2026-04-11~2026-04-12 / 장소: 가평',
      volunteerStartDate: '2026-04-11',
      volunteerEndDate: '2026-04-12',
      author: '관리자',
    },
    headers: { 'X-CSRF-Token': csrfToken },
  });
  expect(response.status(), await response.text()).toBe(201);
}

test('관리자 공지 봉사 날짜가 캘린더에 연동된다', async ({ request }) => {
  const unique = Date.now();
  const title = `위브 워크샵 안내 ${unique}`;

  await createNoticeWithVolunteerDate(request, title);

  const calendarResponse = await request.get('/api/activities?date=2026-04-11&view=month');
  expect(calendarResponse.ok(), await calendarResponse.text()).toBeTruthy();
  const calendarBody = await jsonBody(calendarResponse);
  const items = calendarBody?.items || calendarBody?.data?.items || [];

  const created = items.find((item) => item.title === title);
  expect(created).toBeTruthy();
  expect(String(created.startAt || '')).toContain('2026-04-11');
  expect(String(created.endAt || '')).toContain('2026-04-12');
  expect(String(created.description || '')).toContain('가평');
});
