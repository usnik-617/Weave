const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

const ADMIN_USERNAME = 'admin';
const ADMIN_PASSWORD = 'Weave!2026';
const UPLOAD_ROOT = path.resolve(__dirname, '..', 'uploads');

test.describe.configure({ mode: 'serial' });

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

async function login(request, username, password) {
  for (let attempt = 0; attempt < 3; attempt++) {
    const csrfToken = await getCsrfToken(request);
    const response = await request.post('/api/auth/login?playwright_test=1', {
      data: { username, password },
      headers: { 'X-CSRF-Token': csrfToken, 'X-Playwright-Test': '1' },
    });
    if (response.ok()) {
      return jsonBody(response);
    }
    const status = response.status();
    const text = await response.text();
    if (status === 429 && attempt < 2) {
      await new Promise((resolve) => setTimeout(resolve, 200));
      continue;
    }
    throw new Error(`login failed(${status}): ${text}`);
  }
  throw new Error('login failed after retries');
}

async function signup(request, seed) {
  const csrfToken = await getCsrfToken(request);
  const short = String(seed).slice(-6);
  const payload = {
    name: `테스트${short}`,
    nickname: `n${short}`,
    email: `u${short}@example.com`,
    birthDate: '2000.01.01',
    phone: `010-${String(seed).slice(-4)}-${String(seed + 7).slice(-4)}`,
    username: `u${short}`,
    password: 'Password!123',
  };
  const response = await request.post('/api/auth/signup', {
    data: payload,
    headers: { 'X-CSRF-Token': csrfToken },
  });
  expect(response.ok(), await response.text()).toBeTruthy();
  return payload;
}

async function getCurrentUser(request) {
  const response = await request.get('/api/auth/me');
  expect(response.ok()).toBeTruthy();
  const body = await jsonBody(response);
  return body?.data?.user || body?.user;
}

async function createPostAsAdmin(request, payload) {
  await login(request, ADMIN_USERNAME, ADMIN_PASSWORD);
  const csrfToken = await getCsrfToken(request);
  const response = await request.post('/api/posts', {
    data: payload,
    headers: { 'X-CSRF-Token': csrfToken },
  });
  expect(response.status(), await response.text()).toBe(201);
  const body = await jsonBody(response);
  return body?.data?.post_id || body?.post_id;
}

function listAllFiles(dir) {
  if (!fs.existsSync(dir)) return [];
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  return entries.flatMap((entry) => {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) return listAllFiles(fullPath);
    return [fullPath];
  });
}

test('scheduled posts are hidden by default and visible with admin include_scheduled', async ({ request }) => {
  await login(request, ADMIN_USERNAME, ADMIN_PASSWORD);

  const now = new Date();
  const future = new Date(now.getTime() + 72 * 60 * 60 * 1000).toISOString().replace('Z', '');
  const title = `예약공지-${Date.now()}`;

  const csrfToken = await getCsrfToken(request);
  const createResponse = await request.post('/api/posts', {
    data: {
      category: 'notice',
      title,
      content: '예약 발행 테스트',
      publish_at: future,
    },
    headers: { 'X-CSRF-Token': csrfToken },
  });
  expect(createResponse.status(), await createResponse.text()).toBe(201);
  const created = await jsonBody(createResponse);
  const postId = created?.data?.post_id || created?.post_id;
  expect(postId).toBeTruthy();

  const listDefault = await request.get('/api/posts?type=notice&pageSize=100');
  expect(listDefault.ok()).toBeTruthy();
  const defaultBody = await jsonBody(listDefault);
  const defaultItems = defaultBody?.data?.items || defaultBody?.items || [];
  const foundInDefault = defaultItems.some((item) => item.id === postId || item.title === title);
  expect(foundInDefault).toBeFalsy();

  const listWithScheduled = await request.get('/api/posts?type=notice&pageSize=100&include_scheduled=true');
  expect(listWithScheduled.ok()).toBeTruthy();
  const withBody = await jsonBody(listWithScheduled);
  const withItems = withBody?.data?.items || withBody?.items || [];
  const scheduledItem = withItems.find((item) => item.id === postId || item.title === title);
  expect(scheduledItem).toBeTruthy();
  expect(String(scheduledItem.status || '').toLowerCase()).toBe('scheduled');
});

test('upload dedup stores one physical file for identical content', async ({ request }) => {
  const postId = await createPostAsAdmin(request, {
    category: 'notice',
    title: `첨부중복-${Date.now()}`,
    content: 'dedup test',
  });

  const beforeCount = listAllFiles(UPLOAD_ROOT).length;
  const content = Buffer.from(`same-binary-${Date.now()}`);

  const csrfToken1 = await getCsrfToken(request);
  const upload1 = await request.post(`/api/posts/${postId}/files`, {
    multipart: {
      file: {
        name: 'proof.pdf',
        mimeType: 'application/pdf',
        buffer: content,
      },
    },
    headers: { 'X-CSRF-Token': csrfToken1 },
  });
  expect(upload1.status(), await upload1.text()).toBe(201);

  const csrfToken2 = await getCsrfToken(request);
  const upload2 = await request.post(`/api/posts/${postId}/files`, {
    multipart: {
      file: {
        name: 'proof-again.pdf',
        mimeType: 'application/pdf',
        buffer: content,
      },
    },
    headers: { 'X-CSRF-Token': csrfToken2 },
  });
  expect(upload2.status(), await upload2.text()).toBe(201);

  const listResponse = await request.get(`/api/posts/${postId}/files`);
  expect(listResponse.ok()).toBeTruthy();
  const listBody = await jsonBody(listResponse);
  const items = listBody?.data?.items || listBody?.items || [];
  expect(items.length).toBeGreaterThanOrEqual(2);

  const afterCount = listAllFiles(UPLOAD_ROOT).length;
  expect(afterCount - beforeCount).toBe(1);
});

test('attendance marking updates volunteer summary aggregation', async ({ request }) => {
  await login(request, ADMIN_USERNAME, ADMIN_PASSWORD);
  const me = await getCurrentUser(request);
  expect(me?.id).toBeTruthy();

  const beforeProfileRes = await request.get('/api/user/profile');
  expect(beforeProfileRes.ok()).toBeTruthy();
  const beforeProfile = await jsonBody(beforeProfileRes);
  const beforeSummary = beforeProfile?.data?.volunteerSummary || beforeProfile?.volunteerSummary || {};
  const beforeHours = Number(beforeSummary.totalVolunteerHours || 0);
  const beforeEvents = Number(beforeSummary.totalEventsAttended || 0);

  const base = new Date(Date.now() + 24 * 60 * 60 * 1000);
  const start = new Date(base);
  start.setHours(9, 0, 0, 0);
  const end = new Date(base);
  end.setHours(11, 0, 0, 0);

  const csrfTokenEvent = await getCsrfToken(request);
  const createEvent = await request.post('/api/events', {
    data: {
      title: `출결집계-${Date.now()}`,
      description: 'attendance aggregation test',
      start_datetime: start.toISOString(),
      end_datetime: end.toISOString(),
      capacity: 10,
    },
    headers: { 'X-CSRF-Token': csrfTokenEvent },
  });
  expect(createEvent.status(), await createEvent.text()).toBe(201);
  const eventBody = await jsonBody(createEvent);
  const eventId = eventBody?.data?.event_id || eventBody?.event_id;
  expect(eventId).toBeTruthy();

  const csrfTokenJoin = await getCsrfToken(request);
  const joinRes = await request.post(`/api/events/${eventId}/join`, {
    headers: { 'X-CSRF-Token': csrfTokenJoin },
  });
  expect(joinRes.ok(), await joinRes.text()).toBeTruthy();

  const csrfTokenAttendance = await getCsrfToken(request);
  const attendanceRes = await request.post(`/api/events/${eventId}/attendance`, {
    data: {
      user_id: me.id,
      status: 'attended',
    },
    headers: { 'X-CSRF-Token': csrfTokenAttendance },
  });
  expect(attendanceRes.ok(), await attendanceRes.text()).toBeTruthy();

  const afterProfileRes = await request.get('/api/user/profile');
  expect(afterProfileRes.ok()).toBeTruthy();
  const afterProfile = await jsonBody(afterProfileRes);
  const afterSummary = afterProfile?.data?.volunteerSummary || afterProfile?.volunteerSummary || {};
  const afterHours = Number(afterSummary.totalVolunteerHours || 0);
  const afterEvents = Number(afterSummary.totalEventsAttended || 0);

  expect(afterHours).toBeGreaterThan(beforeHours);
  expect(afterEvents).toBeGreaterThan(beforeEvents);
});

test('general user is forbidden to create events (role restriction)', async ({ request }) => {
  const seed = Date.now();
  const user = await signup(request, seed);

  const csrfToken = await getCsrfToken(request);
  const createEventRes = await request.post('/api/events', {
    data: {
      title: `권한테스트-${seed}`,
      start_datetime: new Date(Date.now() + 48 * 60 * 60 * 1000).toISOString(),
      end_datetime: new Date(Date.now() + 49 * 60 * 60 * 1000).toISOString(),
      capacity: 5,
    },
    headers: { 'X-CSRF-Token': csrfToken },
  });

  expect(createEventRes.status(), await createEventRes.text()).toBe(403);

  const meRes = await request.get('/api/auth/me');
  const meBody = await jsonBody(meRes);
  expect(meBody?.data?.user?.username || meBody?.user?.username).toBe(user.username);
});
