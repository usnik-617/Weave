const ABOUT_EXECUTIVES_KEY = 'weave.about.executives.v1';
const ABOUT_EXECUTIVES_MAX_ITEMS = 40;
const ABOUT_EXECUTIVE_NAME_MAX = 40;
const ABOUT_EXECUTIVE_ROLE_MAX = 60;
const ABOUT_EXECUTIVE_BIO_MAX = 400;
const ABOUT_EXECUTIVE_PHOTO_MAX_BYTES = 5 * 1024 * 1024;
const ABOUT_EXECUTIVE_FALLBACK_PHOTO = 'https://images.unsplash.com/photo-1494790108377-be9c29b29330?auto=format&fit=crop&w=720&q=80';

const ABOUT_EXECUTIVES_DEFAULT = [
  {
    name: '강인수',
    role: '단장',
    bio: '봉사단의 방향과 연간 활동 기획을 총괄합니다.',
    photo: 'https://images.unsplash.com/photo-1566492031773-4f4e44671857?auto=format&fit=crop&w=720&q=80'
  },
  {
    name: '강예진',
    role: '부단장',
    bio: '운영 조율과 현장 실행을 지원하며 팀워크를 강화합니다.',
    photo: 'https://images.unsplash.com/photo-1544005313-94ddf0286df2?auto=format&fit=crop&w=720&q=80'
  },
  {
    name: '이주영',
    role: '기획부장',
    bio: '정기 봉사 프로그램과 프로젝트를 설계하고 관리합니다.',
    photo: 'https://images.unsplash.com/photo-1500648767791-00dcc994a43e?auto=format&fit=crop&w=720&q=80'
  },
  {
    name: '서지훈',
    role: '홍보부장',
    bio: '콘텐츠 제작과 대외 소통으로 봉사단의 활동을 확산합니다.',
    photo: 'https://images.unsplash.com/photo-1541534401786-2077eed87a72?auto=format&fit=crop&w=720&q=80'
  }
];

let pendingExecutivePhotoIndex = -1;

function escapeExecutiveHtml(value) {
  return String(value || '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function normalizeExecutive(item) {
  const raw = item || {};
  const rawPhoto = String(raw.photo || '').trim();
  const safePhoto = (rawPhoto.startsWith('data:image/') || /^(https?:)?\/\//i.test(rawPhoto)) ? rawPhoto : '';
  return {
    name: String(raw.name || '').trim().slice(0, ABOUT_EXECUTIVE_NAME_MAX) || '이름 미정',
    role: String(raw.role || '').trim().slice(0, ABOUT_EXECUTIVE_ROLE_MAX) || '직책 미정',
    bio: String(raw.bio || '').trim().slice(0, ABOUT_EXECUTIVE_BIO_MAX) || '소개 문구를 입력해 주세요.',
    photo: safePhoto
  };
}

function getStoredExecutives() {
  try {
    const parsed = JSON.parse(localStorage.getItem(ABOUT_EXECUTIVES_KEY) || '[]');
    if (!Array.isArray(parsed) || !parsed.length) {
      return ABOUT_EXECUTIVES_DEFAULT.map((item) => ({ ...item }));
    }
    return parsed.slice(0, ABOUT_EXECUTIVES_MAX_ITEMS).map(normalizeExecutive);
  } catch (_error) {
    return ABOUT_EXECUTIVES_DEFAULT.map((item) => ({ ...item }));
  }
}

function saveExecutives(list) {
  const safeList = Array.isArray(list)
    ? list.slice(0, ABOUT_EXECUTIVES_MAX_ITEMS).map(normalizeExecutive)
    : ABOUT_EXECUTIVES_DEFAULT.map((item) => ({ ...item }));
  try {
    localStorage.setItem(ABOUT_EXECUTIVES_KEY, JSON.stringify(safeList));
  } catch (_error) {
    if (typeof notifyMessage === 'function') {
      notifyMessage('임원 정보를 저장하지 못했습니다. 저장 공간을 확인해 주세요.');
    }
  }
  return safeList;
}

function readExecutiveImage(file) {
  if (!file) return Promise.resolve('');
  if (!/^image\//i.test(String(file.type || ''))) {
    if (typeof notifyMessage === 'function') notifyMessage('이미지 파일만 업로드할 수 있습니다.');
    return Promise.resolve('');
  }
  if (Number(file.size || 0) > ABOUT_EXECUTIVE_PHOTO_MAX_BYTES) {
    if (typeof notifyMessage === 'function') notifyMessage('이미지 용량은 5MB 이하만 허용됩니다.');
    return Promise.resolve('');
  }
  if (typeof readImageFileToDataUrlAsync === 'function') return readImageFileToDataUrlAsync(file);
  return new Promise((resolve) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ''));
    reader.onerror = () => resolve('');
    reader.readAsDataURL(file);
  });
}

function isExecutivesAdmin() {
  const user = typeof getCurrentUser === 'function' ? getCurrentUser() : null;
  return !!(user && typeof isAdminUser === 'function' && isAdminUser(user));
}

function renderExecutives() {
  const listEl = document.getElementById('executives-list');
  if (!(listEl instanceof HTMLElement)) return;

  const isAdmin = isExecutivesAdmin();
  const executives = getStoredExecutives();

  listEl.innerHTML = executives.map((item, index) => {
    const safeName = escapeExecutiveHtml(item.name);
    const safeRole = escapeExecutiveHtml(item.role);
    const safeBio = escapeExecutiveHtml(item.bio);
    const safePhoto = escapeExecutiveHtml(item.photo || ABOUT_EXECUTIVE_FALLBACK_PHOTO);

    if (!isAdmin) {
      return `
      <div class="col-12 col-sm-6 col-lg-4">
        <article class="executive-card h-100">
          <img class="executive-photo" src="${safePhoto}" alt="${safeName} 사진" loading="lazy" decoding="async">
          <div class="p-3">
            <h5 class="fw-bold mb-1">${safeName}</h5>
            <p class="text-primary fw-semibold mb-2">${safeRole}</p>
            <p class="text-muted mb-0">${safeBio}</p>
          </div>
        </article>
      </div>`;
    }

    return `
    <div class="col-12 col-sm-6 col-lg-4">
      <article class="executive-card h-100 executive-card-admin" data-executive-index="${index}">
        <img class="executive-photo" src="${safePhoto}" alt="${safeName} 사진" loading="lazy" decoding="async">
        <div class="p-3 d-flex flex-column gap-2">
          <input class="form-control form-control-sm" data-executive-field="name" data-executive-index="${index}" value="${safeName}" placeholder="이름">
          <input class="form-control form-control-sm" data-executive-field="role" data-executive-index="${index}" value="${safeRole}" placeholder="직책">
          <textarea class="form-control form-control-sm" data-executive-field="bio" data-executive-index="${index}" rows="3" placeholder="소개">${safeBio}</textarea>
          <div class="d-flex gap-2">
            <button type="button" class="btn btn-sm btn-outline-primary flex-fill" data-executive-photo-btn="${index}" aria-label="${safeName} 사진 변경">사진</button>
            <button type="button" class="btn btn-sm btn-outline-danger flex-fill" data-executive-delete-btn="${index}">삭제</button>
          </div>
        </div>
      </article>
    </div>`;
  }).join('');

  if (!executives.length) {
    listEl.innerHTML = '<div class="col-12"><div class="alert alert-light border text-muted mb-0">등록된 임원이 없습니다.</div></div>';
  }

  if (!isAdmin) return;

  listEl.querySelectorAll('[data-executive-field]').forEach((input) => {
    input.addEventListener('change', () => {
      const idx = Number(input.getAttribute('data-executive-index'));
      const field = String(input.getAttribute('data-executive-field') || '');
      if (!Number.isInteger(idx) || idx < 0 || !field) return;
      const current = getStoredExecutives();
      if (!current[idx]) return;
      current[idx][field] = String(input.value || '').trim();
      saveExecutives(current);
      renderExecutives();
    });
  });

  listEl.querySelectorAll('[data-executive-delete-btn]').forEach((button) => {
    button.addEventListener('click', () => {
      const idx = Number(button.getAttribute('data-executive-delete-btn'));
      const current = getStoredExecutives();
      if (!Number.isInteger(idx) || idx < 0 || idx >= current.length) return;
      if (!confirm('이 임원 정보를 삭제하시겠습니까?')) return;
      current.splice(idx, 1);
      saveExecutives(current);
      renderExecutives();
    });
  });

  listEl.querySelectorAll('[data-executive-photo-btn]').forEach((button) => {
    button.addEventListener('click', () => {
      const idx = Number(button.getAttribute('data-executive-photo-btn'));
      if (!Number.isInteger(idx) || idx < 0) return;
      pendingExecutivePhotoIndex = idx;
      const fileInput = document.getElementById('executive-photo-input');
      if (fileInput instanceof HTMLInputElement) fileInput.click();
    });
  });
}

function updateExecutivesAdminControls() {
  const tools = document.getElementById('executives-admin-tools');
  if (tools) tools.classList.toggle('d-none', !isExecutivesAdmin());
  renderExecutives();
}

function initExecutivesSection() {
  const addBtn = document.getElementById('executive-add-btn');
  const photoInput = document.getElementById('executive-photo-input');

  if (addBtn instanceof HTMLElement) {
    addBtn.addEventListener('click', () => {
      const current = getStoredExecutives();
      if (current.length >= ABOUT_EXECUTIVES_MAX_ITEMS) {
        if (typeof notifyMessage === 'function') notifyMessage('임원은 최대 40명까지 등록할 수 있습니다.');
        return;
      }
      current.push({
        name: '새 임원',
        role: '직책 입력',
        bio: '임원 소개를 입력해 주세요.',
        photo: ''
      });
      saveExecutives(current);
      renderExecutives();
    });
  }

  if (photoInput instanceof HTMLInputElement) {
    photoInput.addEventListener('change', async () => {
      const file = photoInput.files && photoInput.files[0];
      if (!file) return;
      const idx = pendingExecutivePhotoIndex;
      pendingExecutivePhotoIndex = -1;
      photoInput.value = '';
      const imageData = await readExecutiveImage(file);
      if (!imageData) return;
      const current = getStoredExecutives();
      if (!Number.isInteger(idx) || idx < 0 || idx >= current.length) return;
      current[idx].photo = imageData;
      saveExecutives(current);
      renderExecutives();
    });
  }

  updateExecutivesAdminControls();
}

window.updateExecutivesAdminControls = updateExecutivesAdminControls;
window.renderExecutives = renderExecutives;

document.addEventListener('DOMContentLoaded', initExecutivesSection);
