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
const CLIENT_PERF_KEY = 'weave_client_perf';
const ROUTE_STATE_KEYS = {
  panel: 'panel',
  newsTab: 'newsTab',
  aboutTab: 'aboutTab',
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

function safeJsonParse(value, fallback = null) {
  if (typeof value !== 'string' || !value.trim()) return fallback;
  try {
    return JSON.parse(value);
  } catch (_) {
    return fallback;
  }
}

function safeStorageGet(key, fallback = '') {
  try {
    const value = localStorage.getItem(key);
    return value == null ? fallback : value;
  } catch (_) {
    return fallback;
  }
}

function safeStorageSet(key, value) {
  try {
    localStorage.setItem(key, value);
    return true;
  } catch (_) {
    return false;
  }
}

function safeStorageRemove(key) {
  try {
    localStorage.removeItem(key);
    return true;
  } catch (_) {
    return false;
  }
}

function getTodayKey() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
}

function loadClientTelemetry() {
  try {
    const savedDay = String(safeStorageGet(CLIENT_TELEMETRY_DAY_KEY, '') || '');
    const today = getTodayKey();
    if (savedDay && savedDay !== today) {
      safeStorageRemove(CLIENT_TELEMETRY_KEY);
    }
    const parsed = safeJsonParse(safeStorageGet(CLIENT_TELEMETRY_KEY, '{}'), {}) || {};
    const toSafeCounter = (value) => {
      const num = Number(value || 0);
      return Number.isFinite(num) && num >= 0 ? num : 0;
    };
    return {
      errors403: toSafeCounter(parsed.errors403),
      errors429: toSafeCounter(parsed.errors429),
      uploadFailures: toSafeCounter(parsed.uploadFailures)
    };
  } catch (_) {
    return { errors403: 0, errors429: 0, uploadFailures: 0 };
  }
}

const CLIENT_TELEMETRY = loadClientTelemetry();

function initClientPerfMetrics() {
  if (window.__WEAVE_PERF_INIT__) return;
  window.__WEAVE_PERF_INIT__ = true;
  const metrics = { fcp: 0, lcp: 0, cls: 0, ts: Date.now(), panel: 'home', analytics: {} };
  const clamp = (value) => (Number.isFinite(value) ? Number(value.toFixed(4)) : 0);
  try {
    const paintObserver = new PerformanceObserver((list) => {
      list.getEntries().forEach((entry) => {
        if (entry.name === 'first-contentful-paint') {
          metrics.fcp = clamp(entry.startTime);
        }
      });
    });
    paintObserver.observe({ type: 'paint', buffered: true });
  } catch (_) {}

  try {
    const lcpObserver = new PerformanceObserver((list) => {
      const entries = list.getEntries();
      const last = entries[entries.length - 1];
      if (last) metrics.lcp = clamp(last.startTime || last.renderTime || 0);
    });
    lcpObserver.observe({ type: 'largest-contentful-paint', buffered: true });
  } catch (_) {}

  try {
    let clsValue = 0;
    const clsObserver = new PerformanceObserver((list) => {
      list.getEntries().forEach((entry) => {
        if (!entry.hadRecentInput) clsValue += Number(entry.value || 0);
      });
      metrics.cls = clamp(clsValue);
    });
    clsObserver.observe({ type: 'layout-shift', buffered: true });
  } catch (_) {}

  window.addEventListener('pagehide', () => {
    try {
      safeStorageSet(CLIENT_PERF_KEY, JSON.stringify(metrics));
    } catch (_) {}
  });

  const syncPanelTag = () => {
    const activePanel = document.querySelector('.panel.panel-active')?.id
      || String(window.location.hash || '').replace('#', '')
      || 'home';
    metrics.panel = resolveNavPanelId(activePanel || 'home');
  };
  syncPanelTag();
  window.addEventListener('hashchange', syncPanelTag);
  window.addEventListener('popstate', syncPanelTag);
  document.addEventListener('weave:panel-changed', syncPanelTag);

  document.addEventListener('click', (event) => {
    const target = event.target instanceof HTMLElement ? event.target.closest('[data-analytics]') : null;
    if (!(target instanceof HTMLElement)) return;
    const key = String(target.dataset.analytics || '').trim();
    if (!key) return;
    metrics.analytics[key] = Number(metrics.analytics[key] || 0) + 1;
  }, true);

  window.__weavePerfMetrics = metrics;
}
initClientPerfMetrics();

function syncOfflineBannerState() {
  const isOnline = navigator.onLine !== false;
  if (document.body) document.body.classList.toggle('offline-mode', !isOnline);
  const banner = document.getElementById('offline-banner');
  if (banner instanceof HTMLElement) {
    banner.textContent = isOnline
      ? '네트워크가 복구되었습니다.'
      : '오프라인 상태입니다. 네트워크 연결을 확인해주세요.';
  }
}

window.addEventListener('online', () => {
  syncOfflineBannerState();
  notifyInfo('네트워크 연결이 복구되었습니다.', 1800);
});

window.addEventListener('offline', () => {
  syncOfflineBannerState();
  notifyError('현재 오프라인 상태입니다.', 2200);
});

document.addEventListener('DOMContentLoaded', () => {
  syncOfflineBannerState();
});

function persistClientTelemetry() {
  try {
    safeStorageSet(CLIENT_TELEMETRY_KEY, JSON.stringify(CLIENT_TELEMETRY));
    safeStorageSet(CLIENT_TELEMETRY_DAY_KEY, getTodayKey());
  } catch (_) {}
}

function showToast(message, type = 'info', durationMs = 2200) {
  const el = document.getElementById('app-toast');
  if (!el) return;
  el.textContent = String(message || '요청이 처리되었습니다.').trim().slice(0, 240);
  const normalizedType = ['info', 'error'].includes(String(type || '').toLowerCase()) ? String(type).toLowerCase() : 'info';
  el.dataset.type = normalizedType;
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
  try {
    window.history.replaceState({}, '', nextUrl);
  } catch (_) {}
}

window.updateAppUrlState = updateAppUrlState;

function readInitialAppUrlState() {
  let url = null;
  try {
    url = new URL(window.location.href);
  } catch (_) {
    return {
      panel: '', newsTab: '', aboutTab: '', q: '', page: '', faqQ: '', faqPage: '',
      qnaQ: '', qnaPage: '', galleryQ: '', galleryPage: '', galleryFilter: ''
    };
  }
  return {
    panel: url.searchParams.get(ROUTE_STATE_KEYS.panel) || '',
    newsTab: url.searchParams.get(ROUTE_STATE_KEYS.newsTab) || '',
    aboutTab: url.searchParams.get(ROUTE_STATE_KEYS.aboutTab) || '',
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
  const parsed = safeJsonParse(safeStorageGet(CURRENT_USER_KEY, ''), null);
  if (!parsed || typeof parsed !== 'object') return null;
  return parsed;
}

function setCurrentUser(user) {
  if (user) {
    safeStorageSet(CURRENT_USER_KEY, JSON.stringify(user));
    try {
      sessionStorage.setItem(CURRENT_USER_KEY, JSON.stringify(user));
    } catch (_) {}
  } else {
    safeStorageRemove(CURRENT_USER_KEY);
    try {
      sessionStorage.removeItem(CURRENT_USER_KEY);
    } catch (_) {}
    // 로그아웃 시 세션스토리지 전체 초기화(권장)
    try {
      sessionStorage.clear();
    } catch (_) {}
  }
  updateAuthUI();
}

async function ensureCsrfToken() {
  if (CSRF_TOKEN) return CSRF_TOKEN;
  const response = await fetch(`${API_BASE}/auth/csrf`, { credentials: 'same-origin' });
  if (!response.ok) {
    throw new Error('보안 토큰을 가져오지 못했습니다. 다시 시도해주세요.');
  }
  const data = await response.json().catch(() => ({}));
  CSRF_TOKEN = data?.data?.csrfToken || data?.csrfToken || '';
  if (!CSRF_TOKEN) {
    throw new Error('보안 토큰이 유효하지 않습니다. 페이지를 새로고침 해주세요.');
  }
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
  document.querySelectorAll('[data-panel][aria-current]').forEach((el) => {
    el.setAttribute('aria-current', 'false');
  });
  const desktopCandidates = Array.from(document.querySelectorAll(`.nav-link[data-panel="${resolvedPanelId}"]`));
  if (desktopCandidates.length) {
    desktopCandidates[0].classList.add('active');
    desktopCandidates[0].setAttribute('aria-current', 'page');
  }

  const routeState = (typeof readInitialAppUrlState === 'function') ? readInitialAppUrlState() : {};
  const currentAboutTab = String(routeState.aboutTab || 'history');
  const currentNewsRouteTab = String(routeState.newsTab || currentNewsTab || 'notice');
  document.querySelectorAll('.nav-submenu a').forEach((el) => {
    const matchPanel = el.dataset.panel === resolvedPanelId;
    const matchAbout = resolvedPanelId === 'about' && el.dataset.aboutTab === currentAboutTab;
    const matchNews = resolvedPanelId === 'news' && el.dataset.newsTab === currentNewsRouteTab;
    const match = matchPanel && (matchAbout || matchNews);
    el.classList.toggle('active', !!match);
    el.setAttribute('aria-current', match ? 'page' : 'false');
  });

  const mobileTabs = document.querySelectorAll('#mobile-bottom-nav .mobile-tab');
  mobileTabs.forEach((tab) => {
    const tabPanel = tab.dataset.panel;
    const tabNews = tab.dataset.newsTab || '';
    const active = tabPanel === resolvedPanelId && (resolvedPanelId !== 'news' || !tabNews || tabNews === currentNewsTab);
    tab.classList.toggle('active', active);
    tab.setAttribute('aria-current', active ? 'page' : 'false');
  });
}

function handleSessionExpired(path = '') {
  if (window.__WEAVE_E2E__ === true) return;
  if (SESSION_EXPIRED_SHOWN) return;
  if (String(path || '').startsWith('/auth/')) return;
  if (!getCurrentUser()) return;
  setCurrentUser(null);
  movePanel('home');
  const panel = getActivePanelId();
  if (panel) PENDING_RETURN_PANEL = panel;
  if (panel === 'news') {
    PENDING_RETURN_NEWS_TAB = currentNewsTab || 'notice';
  }
  SESSION_EXPIRED_SHOWN = true;
  const modalEl = document.getElementById('sessionExpiredModal');
  if (!modalEl || typeof bootstrap === 'undefined' || !bootstrap.Modal) {
    SESSION_EXPIRED_SHOWN = false;
    notifyError('세션이 만료되었습니다. 다시 로그인해주세요.');
    return;
  }
  if (!modalEl.dataset.sessionExpiredBound) {
    modalEl.dataset.sessionExpiredBound = '1';
    modalEl.addEventListener('hidden.bs.modal', () => {
      SESSION_EXPIRED_SHOWN = false;
    });
  }
  if (modalEl.classList.contains('show')) return;
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
          if (typeof bootstrap === 'undefined' || !bootstrap.Modal) return;
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
  const isFormDataBody = typeof FormData !== 'undefined' && options.body instanceof FormData;
  const isStringBody = typeof options.body === 'string';
  const looksLikeJsonString = isStringBody && /^[\s\r\n]*[\[{]/.test(options.body);
  if (!headers['Content-Type'] && options.body !== undefined && !isFormDataBody) {
    if (!isStringBody || looksLikeJsonString) {
      headers['Content-Type'] = 'application/json';
    }
  }
  let requestBody = options.body;
  if (requestBody !== undefined && !isFormDataBody && headers['Content-Type'] === 'application/json' && typeof requestBody !== 'string') {
    requestBody = JSON.stringify(requestBody);
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
      body: requestBody,
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
  const role = String(user?.role || '').toUpperCase();
  return !!(user && (user.isAdmin || role === 'ADMIN' || ADMIN_EMAILS.includes(user.email)));
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
  const parsed = safeJsonParse(safeStorageGet(STATS_KEY, ''), null);
  if (!parsed || typeof parsed !== 'object') return defaults;
  return {
    generation: String(parsed.generation || defaults.generation),
    members: String(parsed.members || defaults.members),
    activities: String(parsed.activities || defaults.activities),
    impact: String(parsed.impact || defaults.impact)
  };
}

function saveStats(stats) {
  safeStorageSet(STATS_KEY, JSON.stringify(stats || {}));
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
  const profileNameEl = document.getElementById('profile-name');
  const profileEmailEl = document.getElementById('profile-email');
  const profileDetailsEl = document.getElementById('profile-details');
  const profileJoinDateEl = document.getElementById('profile-joindate');

  if (user) {
    if (authButtons) {
      authButtons.style.display = 'none';
      authButtons.classList.add('d-none');
    }
    if (userProfile) userProfile.classList.add('show');
    if (profileNameEl) profileNameEl.innerText = `${user.name || '-'} (${user.nickname || user.username || '-'})`;
    if (profileEmailEl) profileEmailEl.innerText = user.email || '-';
    const statusLabelMap = { pending: '승인대기', active: '정식단원', locked: '잠금', withdrawn: '탈퇴' };
    const role = roleMeta(user.role);
    if (profileDetailsEl) {
      profileDetailsEl.innerHTML = `
        <div>이름: ${escapeHtml(user.name || '-')}</div>
        <div>닉네임: ${escapeHtml(user.nickname || '-')}</div>
        <div>아이디: ${escapeHtml(user.username || '-')}</div>
        <div>이메일: ${escapeHtml(user.email || '-')}</div>
        <div>권한: ${role.icon ? `${escapeHtml(role.icon)} ` : ''}${escapeHtml(role.label)}</div>
        <div>상태: ${escapeHtml(statusLabelMap[user.status] || user.status || '-')}</div>
        <div>생년월일: ${escapeHtml(user.birthDate || '-')}</div>
        <div>연락처: ${escapeHtml(user.phone || '-')}</div>
        <div>활동 기수: ${escapeHtml(user.generation || '-')}</div>
        <div>관심 분야: ${escapeHtml(user.interests || '-')}</div>
        <div>보유 자격: ${escapeHtml(user.certificates || '-')}</div>
        <div>가능 시간대: ${escapeHtml(user.availability || '-')}</div>
      `;
    }
    const joinDate = new Date(user.joinDate || new Date()).toLocaleDateString('ko-KR');
    if (profileJoinDateEl) profileJoinDateEl.innerText = `가입일: ${joinDate} | 생년월일: ${user.birthDate || '-'}`;
    const activeMember = user.status === 'active';
    if (opsDashboardBtn) opsDashboardBtn.classList.toggle('d-none', !isStaffUser(user));
    if (newsWriteBtn) newsWriteBtn.classList.toggle('d-none', !(activeMember && isStaffUser(user)));
    if (faqWriteBtn) faqWriteBtn.classList.toggle('d-none', !(activeMember && isAdminUser(user)));
    if (qnaWriteBtn) qnaWriteBtn.classList.toggle('d-none', !activeMember);
    if (galleryWriteBtn) galleryWriteBtn.classList.toggle('d-none', !(activeMember && isStaffUser(user)));
  } else {
    if (authButtons) {
      authButtons.style.display = 'flex';
      authButtons.classList.remove('d-none');
    }
    if (userProfile) userProfile.classList.remove('show');
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
  if (typeof updateExecutivesAdminControls === 'function') updateExecutivesAdminControls();
  if (typeof updateHomeHeroAdminControls === 'function') updateHomeHeroAdminControls();
  if (typeof updateSiteEditorControls === 'function') updateSiteEditorControls();
}

function isValidBirthDate(value) {
  if (!/^\d{4}\.\d{2}\.\d{2}$/.test(value)) return false;
  const [year, month, day] = value.split('.').map(Number);
  const date = new Date(year, month - 1, day);
  return date.getFullYear() === year && date.getMonth() === month - 1 && date.getDate() === day;
}
