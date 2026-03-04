const { test, expect } = require('@playwright/test');

function uniqueId() {
  return `${Date.now()}${Math.floor(Math.random() * 10000)}`;
}

async function signup(request, suffix, nickname) {
  const payload = {
    name: '테스트유저',
    nickname,
    email: `user${suffix}@example.com`,
    birthDate: '2000.01.01',
    phone: '010-1111-2222',
    username: `user${suffix}`,
    password: 'Password!123',
  };
  return request.post('/api/auth/signup', { data: payload });
}

test('업로드 정책 + 닉네임 중복 정책 검증', async ({ request }) => {
  const base = uniqueId();

  const nickA = `닉${String(base).slice(-6)}`;
  const signupA = await signup(request, `${base}a`, nickA);
  expect(signupA.ok()).toBeTruthy();

  const signupDup = await signup(request, `${base}b`, nickA);
  expect(signupDup.status()).toBe(409);

  const nickB = `별명${String(base + 1).slice(-6)}`;
  const signupB = await signup(request, `${base}c`, nickB);
  expect(signupB.ok()).toBeTruthy();

  const loginA = await request.post('/api/auth/login', {
    data: { username: `user${base}a`, password: 'Password!123' },
  });
  expect(loginA.ok()).toBeTruthy();

  const changeDup = await request.post('/api/user/nickname', { data: { nickname: nickB } });
  expect(changeDup.status()).toBe(409);

  const adminLogin = await request.post('/api/auth/login', {
    data: { username: 'admin', password: 'Weave!2026' },
  });
  expect(adminLogin.ok()).toBeTruthy();

  const noticeTitle = `공지-${base}`;
  const noticeCreate = await request.post('/api/posts', {
    data: {
      category: 'notice',
      title: noticeTitle,
      content: '공지 본문',
      is_important: false,
    },
  });
  expect(noticeCreate.status()).toBe(201);
  const noticeCreateJson = await noticeCreate.json();
  const noticePostId = Number(noticeCreateJson?.data?.post_id || noticeCreateJson?.post_id || 0);
  expect(noticePostId).toBeGreaterThan(0);

  const galleryTitle = `갤러리-${base}`;
  const galleryCreate = await request.post('/api/posts', {
    data: {
      category: 'gallery',
      title: galleryTitle,
      content: '갤러리 본문',
    },
  });
  expect(galleryCreate.status()).toBe(201);
  const galleryCreateJson = await galleryCreate.json();
  const galleryPostId = Number(galleryCreateJson?.data?.post_id || galleryCreateJson?.post_id || 0);
  expect(galleryPostId).toBeGreaterThan(0);

  const pdfBuffer = Buffer.from('%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n', 'utf-8');

  const noticePdfUpload = await request.post(`/api/posts/${noticePostId}/files`, {
    multipart: {
      file: {
        name: 'notice-test.pdf',
        mimeType: 'application/pdf',
        buffer: pdfBuffer,
      },
    },
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

  const galleryPdfUpload = await request.post(`/api/posts/${galleryPostId}/files`, {
    multipart: {
      file: {
        name: 'gallery-test.pdf',
        mimeType: 'application/pdf',
        buffer: pdfBuffer,
      },
    },
  });
  expect(galleryPdfUpload.status()).toBe(400);
  const galleryPdfJson = await galleryPdfUpload.json();
  expect(String(galleryPdfJson.error || '')).toContain('갤러리는');
  expect(String(galleryPdfJson.error || '')).toContain('업로드할 수 있습니다');

  const pngBuffer = Buffer.from(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO6pOukAAAAASUVORK5CYII=',
    'base64'
  );
  const galleryImageUpload = await request.post(`/api/posts/${galleryPostId}/files`, {
    multipart: {
      file: {
        name: 'gallery-test.png',
        mimeType: 'image/png',
        buffer: pngBuffer,
      },
    },
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
