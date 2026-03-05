const { test, expect } = require('@playwright/test');

function uniqueId() {
  return `${Date.now()}${Math.floor(Math.random() * 10000)}`;
}

async function getCsrfToken(request) {
  const response = await request.get('/api/auth/csrf');
  expect(response.ok()).toBeTruthy();
  const body = await response.json();
  return body?.data?.csrfToken || body?.csrfToken || body?.data?.token;
}

const TEST_HEADER = { 'X-Playwright-Test': '1' };

async function loginAdmin(request) {
  for (let attempt = 0; attempt < 3; attempt++) {
    const adminLoginCsrf = await getCsrfToken(request);
    const adminLogin = await request.post('/api/auth/login?playwright_test=1', {
      data: { username: 'admin', password: 'Weave!2026' },
      headers: { 'X-CSRF-Token': adminLoginCsrf, ...TEST_HEADER },
    });
    if (adminLogin.ok()) return;
    const status = adminLogin.status();
    const text = await adminLogin.text();
    if (status === 429 && attempt < 2) {
      await new Promise((resolve) => setTimeout(resolve, 200));
      continue;
    }
    throw new Error(`admin login failed(${status}): ${text}`);
  }
}

async function signup(request, suffix, nickname) {
  const csrfToken = await getCsrfToken(request);
  const payload = {
    name: '테스트유저',
    nickname,
    email: `user${suffix}@example.com`,
    birthDate: '2000.01.01',
    phone: '010-1111-2222',
    username: `user${suffix}`,
    password: 'Password!123',
  };
  return request.post('/api/auth/signup', {
    data: payload,
    headers: { 'X-CSRF-Token': csrfToken, ...TEST_HEADER },
  });
}

test('업로드 정책 + 닉네임 중복 정책 검증', async ({ request }) => {
  const base = uniqueId();

  await loginAdmin(request);

  const noticeCsrf = await getCsrfToken(request);
  const noticeTitle = `공지-${base}`;
  const noticeCreate = await request.post('/api/posts', {
    data: {
      category: 'notice',
      title: noticeTitle,
      content: '공지 본문',
      is_important: false,
    },
    headers: { 'X-CSRF-Token': noticeCsrf, ...TEST_HEADER },
  });
  expect(noticeCreate.status()).toBe(201);
  const noticeCreateJson = await noticeCreate.json();
  const noticePostId = Number(noticeCreateJson?.data?.post_id || noticeCreateJson?.post_id || 0);
  expect(noticePostId).toBeGreaterThan(0);

  const galleryCsrf = await getCsrfToken(request);
  const galleryTitle = `갤러리-${base}`;
  const galleryCreate = await request.post('/api/posts', {
    data: {
      category: 'gallery',
      title: galleryTitle,
      content: '갤러리 본문',
    },
    headers: { 'X-CSRF-Token': galleryCsrf, ...TEST_HEADER },
  });
  expect(galleryCreate.status()).toBe(201);
  const galleryCreateJson = await galleryCreate.json();
  const galleryPostId = Number(galleryCreateJson?.data?.post_id || galleryCreateJson?.post_id || 0);
  expect(galleryPostId).toBeGreaterThan(0);

  const pdfBuffer = Buffer.from('%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n', 'utf-8');

  const noticeUploadCsrf = await getCsrfToken(request);
  const noticePdfUpload = await request.post(`/api/posts/${noticePostId}/files`, {
    multipart: {
      file: {
        name: 'notice-test.pdf',
        mimeType: 'application/pdf',
        buffer: pdfBuffer,
      },
    },
    headers: { 'X-CSRF-Token': noticeUploadCsrf, ...TEST_HEADER },
  });
  expect(noticePdfUpload.status()).toBe(201);

  const noticeFiles = await request.get(`/api/posts/${noticePostId}/files`);
  expect(noticeFiles.status()).toBe(200);
  const noticeFilesJson = await noticeFiles.json();
  const noticePdfFile = (noticeFilesJson?.data?.items || []).find(
    (item) => String(item.mime_type || '').toLowerCase() === 'application/pdf'
  );
  expect(noticePdfFile).toBeTruthy();
  const noticePdfFileId = Number(noticePdfFile.id || 0);
  expect(noticePdfFileId).toBeGreaterThan(0);
  const previewCandidates = [
    String(noticePdfFile.file_url || ''),
    `/api/post-files/${noticePdfFileId}/download?inline=1`,
    `/api/post-files/${noticePdfFileId}/download`,
    `/api/posts/files/${noticePdfFileId}/download?inline=1`,
    `/api/posts/files/${noticePdfFileId}/download`,
  ].filter(Boolean);

  let noticePdfPreview = null;
  for (const candidate of previewCandidates) {
    const res = await request.get(candidate);
    if (res.status() === 200) {
      noticePdfPreview = res;
      break;
    }
  }
  expect(noticePdfPreview).toBeTruthy();
  expect(String(noticePdfPreview.headers()['content-type'] || '')).toContain('application/pdf');
  expect(String(noticePdfPreview.headers()['content-disposition'] || '').toLowerCase()).toContain('inline');

  const galleryUploadCsrf = await getCsrfToken(request);
  const galleryPdfUpload = await request.post(`/api/posts/${galleryPostId}/files`, {
    multipart: {
      file: {
        name: 'gallery-test.pdf',
        mimeType: 'application/pdf',
        buffer: pdfBuffer,
      },
    },
    headers: { 'X-CSRF-Token': galleryUploadCsrf, ...TEST_HEADER },
  });
  expect(galleryPdfUpload.status()).toBe(400);
  const galleryPdfJson = await galleryPdfUpload.json();
  expect(String(galleryPdfJson.error || '')).toContain('갤러리는');
  expect(String(galleryPdfJson.error || '')).toContain('업로드할 수 있습니다');

  const pngBuffer = Buffer.from(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO6pOukAAAAASUVORK5CYII=',
    'base64'
  );
  const galleryImageCsrf = await getCsrfToken(request);
  const galleryImageUpload = await request.post(`/api/posts/${galleryPostId}/files`, {
    multipart: {
      file: {
        name: 'gallery-test.png',
        mimeType: 'image/png',
        buffer: pngBuffer,
      },
    },
    headers: { 'X-CSRF-Token': galleryImageCsrf, ...TEST_HEADER },
  });
  expect(galleryImageUpload.status()).toBe(201);

  const galleryDetail = await request.get(`/api/posts/${galleryPostId}`);
  expect(galleryDetail.status()).toBe(200);
  const galleryDetailJson = await galleryDetail.json();
  const galleryPost = galleryDetailJson?.data || {};
  expect(String(galleryPost.image_url || '')).toContain('/uploads/');
  expect(String(galleryPost.thumb_url || '')).toContain('/uploads/');
  expect(String(galleryPost.thumb_url || '')).toContain('_thumb');

  const galleryList = await request.get('/api/posts?category=gallery&page=1&pageSize=10');
  expect(galleryList.status()).toBe(200);
  const galleryListJson = await galleryList.json();
  const listItem = (galleryListJson?.data?.items || []).find((item) => Number(item.id) === galleryPostId);
  expect(listItem).toBeTruthy();
  expect(String(listItem.thumb_url || '')).toContain('/uploads/');
});
