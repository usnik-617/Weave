const { test, expect } = require('@playwright/test');

function uniqueId() {
  return `${Date.now()}${Math.floor(Math.random() * 10000)}`;
}

test('역할/닉네임 정책 기본 동작', async ({ request }) => {
  const uid = uniqueId();
  const short = uid.slice(-6);
  const signupPayload = {
    name: '테스트유저',
    nickname: `닉${short}`,
    email: `user${uid}@example.com`,
    birthDate: '2000.01.01',
    phone: '010-1111-2222',
    username: `user${uid}`,
    password: 'Password!123',
  };

  const signup = await request.post('/api/auth/signup', { data: signupPayload });
  expect(signup.ok()).toBeTruthy();
  const signupJson = await signup.json();
  expect(signupJson.user.role).toBe('GENERAL');
  expect(signupJson.user.status).toBe('active');

  const firstNickname = `변경${short}`;
  const patch1 = await request.patch('/api/me/nickname', { data: { nickname: firstNickname } });
  expect(patch1.ok()).toBeTruthy();
  const patchJson = await patch1.json();
  expect(patchJson.data.user.nickname).toBe(firstNickname);

  const secondNickname = `재변${short}`;
  const patch2 = await request.patch('/api/me/nickname', { data: { nickname: secondNickname } });
  expect(patch2.status()).toBe(403);

  const memberRequest = await request.post('/api/role-requests/member', { data: {} });
  expect(memberRequest.status()).toBe(201);

  const duplicateRequest = await request.post('/api/role-requests/member', { data: {} });
  expect(duplicateRequest.status()).toBe(409);
});
