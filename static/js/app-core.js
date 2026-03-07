// ============ GLOBAL STATE (localStorage) ============
const DATA_KEY = 'weave_content';
const COMMENTS_KEY = 'weave_comments';
const CURRENT_USER_KEY = 'weave_current_user';
const STATS_KEY = 'weave_stats';
const ABOUT_VOLUNTEER_PHOTO_KEY = 'weave_about_volunteer_photo';
const DEFAULT_ABOUT_VOLUNTEER_PHOTO = 'https://images.unsplash.com/photo-1559027015-cd4628902d4a?ixlib=rb-4.0.3&auto=format&fit=crop&w=600&q=80';
const ADMIN_EMAILS = ['admin@weave.com', 'weave@youth.gg.kr'];
const API_BASE = '/api';
let CSRF_TOKEN = '';
const REQUEST_TIMEOUT_MS = 12000;
let SESSION_EXPIRED_SHOWN = false;
let PENDING_RETURN_PANEL = '';
let PENDING_RETURN_NEWS_TAB = '';
let ACTIVE_MODAL_ID = '';
let MODAL_OPEN_COUNT = 0;
let MODAL_LOCK_SCROLL_TOP = 0;
let currentEventDetailId = null;
const CLIENT_TELEMETRY_KEY = 'weave_client_telemetry';
const CLIENT_TELEMETRY_DAY_KEY = 'weave_client_telemetry_day';
const ROUTE_STATE_KEYS = {
  panel: 'panel',
  newsTab: 'newsTab',
  q: 'q',
  page: 'page',
  faqQ: 'faqQ',
  faqPage: 'faqPage',
  qnaQ: 'qnaQ',
  qnaPage: 'qnaPage',
  galleryQ: 'galleryQ',
  galleryPage: 'galleryPage',
  galleryFilter: 'galleryFilter'
};
window.ROUTE_STATE_KEYS = ROUTE_STATE_KEYS;

function getTodayKey() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
}

function loadClientTelemetry() {
  try {
    const savedDay = String(localStorage.getItem(CLIENT_TELEMETRY_DAY_KEY) || '');
    const today = getTodayKey();
    if (savedDay && savedDay !== today) {
      localStorage.removeItem(CLIENT_TELEMETRY_KEY);
    }
    const parsed = JSON.parse(localStorage.getItem(CLIENT_TELEMETRY_KEY) || '{}');
    return {
      errors403: Number(parsed.errors403 || 0),
      errors429: Number(parsed.errors429 || 0),
      uploadFailures: Number(parsed.uploadFailures || 0)
    };
  } catch (_) {
    return { errors403: 0, errors429: 0, uploadFailures: 0 };
  }
}

const CLIENT_TELEMETRY = loadClientTelemetry();

function persistClientTelemetry() {
  try {
    localStorage.setItem(CLIENT_TELEMETRY_KEY, JSON.stringify(CLIENT_TELEMETRY));
    localStorage.setItem(CLIENT_TELEMETRY_DAY_KEY, getTodayKey());
  } catch (_) {}
}

function showToast(message, type = 'info', durationMs = 2200) {
  const el = document.getElementById('app-toast');
  if (!el) return;
  el.textContent = String(message || '?붿껌???꾨즺?섏뿀?듬땲??');
  el.dataset.type = String(type || 'info');
  el.classList.add('show');
  window.clearTimeout(showToast._timer);
  showToast._timer = window.setTimeout(() => {
    el.classList.remove('show');
  }, Math.max(1200, Number(durationMs) || 2200));
}

window.showToast = showToast;

function notifyInfo(message, durationMs = 2200) {
  showToast(message, 'info', durationMs);
}

function notifyError(message, durationMs = 3200) {
  showToast(message, 'error', durationMs);
}

function notifyMessage(message, options = {}) {
  const text = String(message || '').trim();
  if (!text) return;
  const level = String(options.level || '').toLowerCase();
  const durationMs = Number(options.durationMs || 0) || undefined;
  if (level === 'error') return notifyError(text, durationMs);
  if (level === 'info' || level === 'success') return notifyInfo(text, durationMs);
  const infoLike = /(완료|등록|확인|반영|성공|취소|초기화|로그아웃)/;
  return infoLike.test(text) ? notifyInfo(text, durationMs) : notifyError(text, durationMs);
}

window.notifyInfo = notifyInfo;
window.notifyError = notifyError;
window.notifyMessage = notifyMessage;

function recordClientTelemetry(responseStatus, requestPath = '') {
  const status = Number(responseStatus || 0);
  const path = String(requestPath || '');
  if (status === 403) CLIENT_TELEMETRY.errors403 += 1;
  if (status === 429) CLIENT_TELEMETRY.errors429 += 1;
  if (status >= 400 && /\/posts\/\d+\/files/i.test(path)) CLIENT_TELEMETRY.uploadFailures += 1;
  persistClientTelemetry();
}

function getClientTelemetry() {
  return { ...CLIENT_TELEMETRY };
}

window.getClientTelemetry = getClientTelemetry;
window.getClientTelemetrySnapshot = getClientTelemetry;

function resetClientTelemetry() {
  CLIENT_TELEMETRY.errors403 = 0;
  CLIENT_TELEMETRY.errors429 = 0;
  CLIENT_TELEMETRY.uploadFailures = 0;
  persistClientTelemetry();
  return getClientTelemetry();
}

window.resetClientTelemetry = resetClientTelemetry;

function updateAppUrlState(partial = {}) {
  const url = new URL(window.location.href);
  const params = url.searchParams;
  Object.entries({ ...partial }).forEach(([key, value]) => {
    const text = String(value ?? '').trim();
    if (!text) {
      params.delete(key);
      return;
    }
    params.set(key, text);
  });
  const query = params.toString();
  const nextUrl = `${url.pathname}${query ? `?${query}` : ''}${url.hash || ''}`;
  window.history.replaceState({}, '', nextUrl);
}

window.updateAppUrlState = updateAppUrlState;

function readInitialAppUrlState() {
  const url = new URL(window.location.href);
  return {
    panel: url.searchParams.get(ROUTE_STATE_KEYS.panel) || '',
    newsTab: url.searchParams.get(ROUTE_STATE_KEYS.newsTab) || '',
    q: url.searchParams.get(ROUTE_STATE_KEYS.q) || '',
    page: url.searchParams.get(ROUTE_STATE_KEYS.page) || '',
    faqQ: url.searchParams.get(ROUTE_STATE_KEYS.faqQ) || '',
    faqPage: url.searchParams.get(ROUTE_STATE_KEYS.faqPage) || '',
    qnaQ: url.searchParams.get(ROUTE_STATE_KEYS.qnaQ) || '',
    qnaPage: url.searchParams.get(ROUTE_STATE_KEYS.qnaPage) || '',
    galleryQ: url.searchParams.get(ROUTE_STATE_KEYS.galleryQ) || '',
    galleryPage: url.searchParams.get(ROUTE_STATE_KEYS.galleryPage) || '',
    galleryFilter: url.searchParams.get(ROUTE_STATE_KEYS.galleryFilter) || ''
  };
}

window.readInitialAppUrlState = readInitialAppUrlState;

// ============ AUTH FUNCTIONS ============
function getCurrentUser() {
  const user = localStorage.getItem(CURRENT_USER_KEY);
  return user ? JSON.parse(user) : null;
}

function setCurrentUser(user) {
  if (user) {
    localStorage.setItem(CURRENT_USER_KEY, JSON.stringify(user));
  } else {
    localStorage.removeItem(CURRENT_USER_KEY);
  }
  updateAuthUI();
}

async function ensureCsrfToken() {
  if (CSRF_TOKEN) return CSRF_TOKEN;
  const response = await fetch(`${API_BASE}/auth/csrf`, { credentials: 'same-origin' });
  const data = await response.json().catch(() => ({}));
  CSRF_TOKEN = data?.data?.csrfToken || data?.csrfToken || '';
  return CSRF_TOKEN;
}

function getActivePanelId() {
  const active = document.querySelector('.panel.panel-active');
  return active?.id || 'home';
}

function resolveNavPanelId(panelId) {
  const value = String(panelId || 'home');
  if (['news-detail', 'qna-detail', 'qna-answer'].includes(value)) return 'news';
  if (value === 'gallery-detail') return 'gallery';
  if (value === 'event-detail') return 'activities';
  return value;
}

function setActiveNavStates(panelId) {
  const resolvedPanelId = resolveNavPanelId(panelId);
  document.querySelectorAll('[data-panel].active').forEach((el) => el.classList.remove('active'));
  const desktopCandidates = Array.from(document.querySelectorAll(`.nav-link[data-panel="${resolvedPanelId}"]`));
  if (desktopCandidates.length) desktopCandidates[0].classList.add('active');

  const mobileTabs = document.querySelectorAll('#mobile-bottom-nav .mobile-tab');
  mobileTabs.forEach((tab) => {
    const tabPanel = tab.dataset.panel;
    const tabNews = tab.dataset.newsTab || '';
    const active = tabPanel === resolvedPanelId && (resolvedPanelId !== 'news' || !tabNews || tabNews === currentNewsTab);
    tab.classList.toggle('active', active);
  });
}

function handleSessionExpired(path = '') {
  if (window.__WEAVE_E2E__ === true) return;
  if (SESSION_EXPIRED_SHOWN) return;
  if (String(path || '').startsWith('/auth/')) return;
  if (!getCurrentUser()) return;
  const panel = getActivePanelId();
  if (panel) PENDING_RETURN_PANEL = panel;
  if (panel === 'news') {
    PENDING_RETURN_NEWS_TAB = currentNewsTab || 'notice';
  }
  SESSION_EXPIRED_SHOWN = true;
  const modalEl = document.getElementById('sessionExpiredModal');
  if (!modalEl || typeof bootstrap === 'undefined' || !bootstrap.Modal) return;
  const modal = bootstrap.Modal.getInstance(modalEl) || new bootstrap.Modal(modalEl);
  modal.show();
}

function showPermissionDenied() {
  const modalEl = document.getElementById('permissionDeniedModal');
  if (!modalEl || typeof bootstrap === 'undefined' || !bootstrap.Modal) {
    notifyError('권한이 없습니다.');
    return;
  }
  const modal = bootstrap.Modal.getInstance(modalEl) || new bootstrap.Modal(modalEl);
  modal.show();
}

function initModalScrollLock() {
  const lockScroll = () => {
    if (document.body.classList.contains('modal-scroll-lock')) return;
    MODAL_LOCK_SCROLL_TOP = window.scrollY || window.pageYOffset || 0;
    document.body.classList.add('modal-scroll-lock');
    document.body.style.top = `-${MODAL_LOCK_SCROLL_TOP}px`;
    document.documentElement.style.overscrollBehavior = 'none';
  };

  const unlockScroll = () => {
    if (MODAL_OPEN_COUNT > 0) return;
    const restoreTop = Number.isFinite(MODAL_LOCK_SCROLL_TOP)
      ? MODAL_LOCK_SCROLL_TOP
      : Math.abs(parseInt(String(document.body.style.top || '0'), 10)) || 0;
    const prevScrollBehavior = document.documentElement.style.scrollBehavior;
    document.documentElement.style.scrollBehavior = 'auto';
    document.body.classList.remove('modal-scroll-lock');
    document.body.style.top = '';
    document.body.style.overflow = '';
    document.documentElement.style.overscrollBehavior = '';
    window.scrollTo(0, restoreTop);
    requestAnimationFrame(() => {
      document.documentElement.style.scrollBehavior = prevScrollBehavior;
    });
    MODAL_LOCK_SCROLL_TOP = 0;
  };

  document.querySelectorAll('.modal').forEach((modalEl) => {
    modalEl.addEventListener('show.bs.modal', () => {
      if (ACTIVE_MODAL_ID && ACTIVE_MODAL_ID !== modalEl.id) {
        const opened = document.getElementById(ACTIVE_MODAL_ID);
        if (opened) {
          const openedInstance = bootstrap.Modal.getInstance(opened);
          if (openedInstance) openedInstance.hide();
        }
      }
      ACTIVE_MODAL_ID = modalEl.id;
      lockScroll();
      MODAL_OPEN_COUNT += 1;
    });
    modalEl.addEventListener('hidden.bs.modal', () => {
      if (ACTIVE_MODAL_ID === modalEl.id) ACTIVE_MODAL_ID = '';
      MODAL_OPEN_COUNT = Math.max(0, MODAL_OPEN_COUNT - 1);
      const anyOpen = document.querySelector('.modal.show');
      if (!anyOpen) {
        MODAL_OPEN_COUNT = 0;
        unlockScroll();
      }
    });
  });
}

async function apiRequest(path, options = {}) {
  const method = String(options.method || 'GET').toUpperCase();
  const isMutating = ['POST', 'PUT', 'PATCH', 'DELETE'].includes(method);
  const suppressSessionModal = !!options.suppressSessionModal;
  const csrfToken = isMutating ? await ensureCsrfToken() : '';
  const headers = {
    ...(options.headers || {})
  };
  if (!headers['Content-Type'] && options.body !== undefined) {
    headers['Content-Type'] = 'application/json';
  }
  if (isMutating && csrfToken) {
    headers['X-CSRF-Token'] = csrfToken;
  }

  const controller = new AbortController();
  const timeoutHandle = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    const response = await fetch(`${API_BASE}${path}`, {
      credentials: 'same-origin',
      headers,
      ...options,
      signal: controller.signal
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      recordClientTelemetry(response.status, path);
      if (response.status === 401 && !suppressSessionModal) {
        handleSessionExpired(path);
      }
      if (response.status === 403) {
        showPermissionDenied();
      }
      const defaultMessage = response.status === 401
        ? '세션이 만료되었습니다.'
        : response.status === 403
          ? '권한이 없습니다.'
          : response.status === 404
            ? '요청 대상을 찾을 수 없습니다.'
            : response.status === 429
              ? '요청이 많습니다. 잠시 후 다시 시도해주세요.'
              : '요청 처리 중 오류가 발생했습니다.';
      throw new Error(data.error || data.message || defaultMessage);
    }
    if (data && data.success === true && data.data && typeof data.data === 'object') {
      return { ...data.data, success: true };
    }
    return data;
  } catch (error) {
    if (error && error.name === 'AbortError') {
      throw new Error('서버 응답이 지연되고 있습니다. 잠시 후 다시 시도해주세요.');
    }
    const errorMessage = String(error?.message || '');
    if (error instanceof TypeError || /failed to fetch|networkerror|load failed/i.test(errorMessage)) {
      throw new Error('서버에 연결할 수 없습니다. 네트워크 상태를 확인 후 다시 시도해주세요.');
    }
    throw error;
  } finally {
    clearTimeout(timeoutHandle);
  }
}

async function hydrateCurrentUser() {
  try {
    const data = await apiRequest('/auth/me', { method: 'GET', suppressSessionModal: true });
    setCurrentUser(data.user || null);
  } catch (error) {
    setCurrentUser(null);
  }
}

function isAdminUser(user) {
  return !!(user && (user.isAdmin || ADMIN_EMAILS.includes(user.email)));
}

function isStaffUser(user) {
  const role = String(user?.role || '').toUpperCase();
  return !!(user && (['EXECUTIVE', 'LEADER', 'VICE_LEADER', 'ADMIN'].includes(role) || isAdminUser(user)));
}

function validateNickname(nickname) {
  const text = String(nickname || '').trim();
  if (text.length < 2 || text.length > 12) return { ok: false, message: '닉네임은 2~12자 한글/영문/숫자만 가능합니다. (띄어쓰기/특수문자 불가)' };
  if (!/^[가-힣A-Za-z0-9]+$/.test(text)) return { ok: false, message: '닉네임은 2~12자 한글/영문/숫자만 가능합니다. (띄어쓰기/특수문자 불가)' };
  return { ok: true, value: text };
}

function roleMeta(role) {
  const upper = String(role || '').toUpperCase();
  const map = {
    GENERAL: { label: '일반', icon: '' },
    MEMBER: { label: '단원', icon: '🙋' },
    EXECUTIVE: { label: '임원', icon: '' },
    LEADER: { label: '단장', icon: '👑' },
    VICE_LEADER: { label: '부단장', icon: '⭐' },
    ADMIN: { label: '운영자', icon: '🛡️' }
  };
  return map[upper] || map.GENERAL;
}

function formatAuthorDisplay(author, fallbackUser = null) {
  const source = author && typeof author === 'object' ? author : {
    nickname: String(author || fallbackUser?.nickname || fallbackUser?.username || '사용자'),
    role: fallbackUser?.role || 'GENERAL'
  };
  const meta = roleMeta(source.role);
  const nickname = source.nickname || source.name || source.username || '사용자';
  return `${meta.icon ? `${meta.icon} ` : ''}[${meta.label}] ${nickname}`;
}

function normalizeContact(value) {
  return String(value || '').trim().replaceAll('-', '').toLowerCase();
}

async function findUsernameFlow() {
  const contact = prompt('이메일 또는 연락처를 입력하세요.');
  if (!contact) return;
  try {
    const data = await apiRequest('/auth/find-username', {
      method: 'POST',
      body: JSON.stringify({ contact })
    });
    notifyMessage(`아이디는 ${data.username} 입니다.`);
  } catch (error) {
    notifyMessage(error.message || '일치하는 계정을 찾지 못했습니다.');
  }
}

async function findPasswordFlow() {
  const username = prompt('아이디를 입력하세요.');
  if (!username) return;
  const contact = prompt('이메일 또는 연락처를 입력하세요.');
  if (!contact) return;
  const newPassword = prompt('새 비밀번호를 입력하세요. (8자 이상, 대문자/특수문자 포함)');
  if (!newPassword || newPassword.length < 8 || !/[A-Z]/.test(newPassword) || !/[^A-Za-z0-9]/.test(newPassword)) {
    notifyMessage('새 비밀번호는 8자 이상이며 대문자/특수문자를 포함해야 합니다.');
    return;
  }
  try {
    const data = await apiRequest('/auth/reset-password', {
      method: 'POST',
      body: JSON.stringify({ username, contact, newPassword })
    });
    notifyMessage(data.message || '비밀번호가 재설정되었습니다.');
  } catch (error) {
    notifyMessage(error.message || '비밀번호 재설정에 실패했습니다.');
  }
}

function getStats() {
  const defaults = {
    generation: '5기',
    members: '49명',
    activities: '115회',
    impact: '지역사회 기여'
  };
  const data = localStorage.getItem(STATS_KEY);
  return data ? JSON.parse(data) : defaults;
}

function saveStats(stats) {
  localStorage.setItem(STATS_KEY, JSON.stringify(stats));
}

function renderStats() {
  const stats = getStats();
  const generationEl = document.getElementById('stat-generation');
  const membersEl = document.getElementById('stat-members');
  const activitiesEl = document.getElementById('stat-activities');
  const impactEl = document.getElementById('stat-impact');
  const trim = (value, max = 12) => {
    const text = String(value || '');
    return text.length > max ? `${text.slice(0, max)}…` : text;
  };
  if (generationEl) generationEl.innerText = trim(stats.generation, 10);
  if (membersEl) membersEl.innerText = trim(stats.members, 10);
  if (activitiesEl) activitiesEl.innerText = trim(stats.activities, 10);
  if (impactEl) impactEl.innerText = trim(stats.impact, 12);
}

function updateAuthUI() {
  const user = getCurrentUser();
  const authButtons = document.getElementById('auth-buttons');
  const userProfile = document.getElementById('user-profile');
  const newsWriteBtn = document.getElementById('news-write-btn');
  const faqWriteBtn = document.getElementById('faq-write-btn');
  const qnaWriteBtn = document.getElementById('qna-write-btn');
  const galleryWriteBtn = document.getElementById('gallery-write-btn');
  const opsDashboardBtn = document.getElementById('ops-dashboard-btn');

  if (user) {
    authButtons.style.display = 'none';
    authButtons.classList.add('d-none');
    userProfile.classList.add('show');
    document.getElementById('profile-name').innerText = `${user.name} (${user.nickname || user.username})`;
    document.getElementById('profile-email').innerText = user.email;
    const statusLabelMap = { pending: '승인대기', active: '정식단원', locked: '잠금', withdrawn: '탈퇴' };
    const role = roleMeta(user.role);
    document.getElementById('profile-details').innerHTML = `
      <div>이름: ${user.name || '-'}</div>
      <div>닉네임: ${user.nickname || '-'}</div>
      <div>아이디: ${user.username || '-'}</div>
      <div>이메일: ${user.email || '-'}</div>
      <div>권한: ${role.icon ? `${role.icon} ` : ''}${role.label}</div>
      <div>상태: ${statusLabelMap[user.status] || user.status || '-'}</div>
      <div>생년월일: ${user.birthDate || '-'}</div>
      <div>연락처: ${user.phone || '-'}</div>
      <div>활동 기수: ${user.generation || '-'}</div>
      <div>관심 분야: ${user.interests || '-'}</div>
      <div>보유 자격: ${user.certificates || '-'}</div>
      <div>가능 시간대: ${user.availability || '-'}</div>
    `;
    const joinDate = new Date(user.joinDate || new Date()).toLocaleDateString('ko-KR');
    document.getElementById('profile-joindate').innerText = `가입일: ${joinDate} | 생년월일: ${user.birthDate || '-'}`;
    const activeMember = user.status === 'active';
    if (opsDashboardBtn) opsDashboardBtn.classList.toggle('d-none', !isStaffUser(user));
    if (newsWriteBtn) newsWriteBtn.classList.toggle('d-none', !(activeMember && isStaffUser(user)));
    if (faqWriteBtn) faqWriteBtn.classList.toggle('d-none', !(activeMember && isAdminUser(user)));
    if (qnaWriteBtn) qnaWriteBtn.classList.toggle('d-none', !activeMember);
    if (galleryWriteBtn) galleryWriteBtn.classList.toggle('d-none', !(activeMember && isStaffUser(user)));
  } else {
    authButtons.style.display = 'flex';
    authButtons.classList.remove('d-none');
    userProfile.classList.remove('show');
    if (newsWriteBtn) newsWriteBtn.classList.add('d-none');
    if (faqWriteBtn) faqWriteBtn.classList.add('d-none');
    if (qnaWriteBtn) qnaWriteBtn.classList.add('d-none');
    if (galleryWriteBtn) galleryWriteBtn.classList.add('d-none');
    if (opsDashboardBtn) opsDashboardBtn.classList.add('d-none');
  }
  if (typeof setNewsWriteButtons === 'function') setNewsWriteButtons();
  if (typeof updateCalendarCreateVisibility === 'function') updateCalendarCreateVisibility();
  if (typeof updateWriteTemplateVisibility === 'function') updateWriteTemplateVisibility();
  if (typeof updateAboutPhotoAdminControls === 'function') updateAboutPhotoAdminControls();
  if (typeof updateHomeHeroAdminControls === 'function') updateHomeHeroAdminControls();
  if (typeof updateSiteEditorControls === 'function') updateSiteEditorControls();
}

function isValidBirthDate(value) {
  if (!/^\d{4}\.\d{2}\.\d{2}$/.test(value)) return false;
  const [year, month, day] = value.split('.').map(Number);
  const date = new Date(year, month - 1, day);
  return date.getFullYear() === year && date.getMonth() === month - 1 && date.getDate() === day;
}
