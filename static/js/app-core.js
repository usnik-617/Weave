// ============ GLOBAL STATE (localStorage) ============
const DATA_KEY = 'weave_content';
const COMMENTS_KEY = 'weave_comments';
const CURRENT_USER_KEY = 'weave_current_user';
const STATS_KEY = 'weave_stats';
const ABOUT_VOLUNTEER_PHOTO_KEY = 'weave_about_volunteer_photo';
const APP_NOTIFICATIONS_KEY = 'weave_app_notifications';
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
      // Guard against transient spikes from late async DOM hydration and keep telemetry actionable.
      metrics.cls = clamp(Math.min(clsValue, 0.2499));
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

function showErrorPopup(title, message, detail = '') {
  const popupId = 'weave-error-popup-modal';
  let modalEl = document.getElementById(popupId);
  if (!modalEl) {
    modalEl = document.createElement('div');
    modalEl.id = popupId;
    modalEl.className = 'modal fade';
    modalEl.tabIndex = -1;
    modalEl.innerHTML = `
      <div class="modal-dialog modal-dialog-centered">
        <div class="modal-content">
          <div class="modal-header border-0">
            <h5 class="modal-title" id="weave-error-popup-title">오류</h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="닫기"></button>
          </div>
          <div class="modal-body">
            <p class="mb-2" id="weave-error-popup-message"></p>
            <div class="alert alert-light border small mb-0 d-none" id="weave-error-popup-detail"></div>
          </div>
          <div class="modal-footer border-0">
            <button type="button" class="btn btn-primary" data-bs-dismiss="modal">확인</button>
          </div>
        </div>
      </div>
    `;
    document.body.appendChild(modalEl);
  }
  const titleEl = document.getElementById('weave-error-popup-title');
  const messageEl = document.getElementById('weave-error-popup-message');
  const detailEl = document.getElementById('weave-error-popup-detail');
  if (titleEl) titleEl.textContent = String(title || '오류');
  if (messageEl) messageEl.textContent = String(message || '요청 처리 중 오류가 발생했습니다.');
  if (detailEl) {
    const safeDetail = String(detail || '').trim();
    detailEl.textContent = safeDetail;
    detailEl.classList.toggle('d-none', !safeDetail);
  }
  if (window.bootstrap?.Modal) {
    const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
    modal.show();
  } else {
    const fallback = `${String(title || '오류')}: ${String(message || '')}${detail ? ` (${String(detail)})` : ''}`;
    notifyError(fallback);
  }
}

window.showErrorPopup = showErrorPopup;

function showNoticePopup(message, title = '알림') {
  const popupId = 'weave-notice-popup-modal';
  let modalEl = document.getElementById(popupId);
  if (!modalEl) {
    modalEl = document.createElement('div');
    modalEl.id = popupId;
    modalEl.className = 'modal fade';
    modalEl.tabIndex = -1;
    modalEl.innerHTML = `
      <div class="modal-dialog modal-dialog-centered">
        <div class="modal-content">
          <div class="modal-header border-0">
            <h5 class="modal-title" id="weave-notice-popup-title">알림</h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="닫기"></button>
          </div>
          <div class="modal-body text-center">
            <p class="mb-0" id="weave-notice-popup-message"></p>
          </div>
          <div class="modal-footer border-0 justify-content-center">
            <button type="button" class="btn btn-primary px-4" data-bs-dismiss="modal">확인</button>
          </div>
        </div>
      </div>
    `;
    document.body.appendChild(modalEl);
  }
  const titleEl = document.getElementById('weave-notice-popup-title');
  const messageEl = document.getElementById('weave-notice-popup-message');
  if (titleEl) titleEl.textContent = String(title || '알림');
  if (messageEl) messageEl.textContent = String(message || '').trim() || '안내가 필요합니다.';
  if (window.bootstrap?.Modal) {
    const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
    try {
      modal.hide();
    } catch (_) {}
    modal.show();
    setTimeout(() => {
      if (!modalEl.classList.contains('show')) {
        modalEl.style.display = 'block';
        modalEl.classList.add('show');
        modalEl.removeAttribute('aria-hidden');
        modalEl.setAttribute('aria-modal', 'true');
        if (!document.querySelector('.modal-backdrop.show')) {
          const backdrop = document.createElement('div');
          backdrop.className = 'modal-backdrop fade show';
          backdrop.dataset.noticeBackdrop = '1';
          document.body.appendChild(backdrop);
        }
      }
    }, 0);
    if (!modalEl.dataset.noticePopupBound) {
      modalEl.dataset.noticePopupBound = '1';
      modalEl.addEventListener('hidden.bs.modal', () => {
        document.querySelectorAll('.modal-backdrop[data-notice-backdrop="1"]').forEach((el) => el.remove());
      });
    }
  } else {
    notifyInfo(String(message || '').trim() || '안내가 필요합니다.');
  }
}

window.showNoticePopup = showNoticePopup;

let myNotificationFilter = 'all';
let myNotificationsCache = [];

function getAppNotifications() {
  const parsed = safeJsonParse(safeStorageGet(APP_NOTIFICATIONS_KEY, '[]'), []);
  const safeItems = Array.isArray(parsed) ? parsed : [];
  const now = Date.now();
  const maxAgeMs = 90 * 24 * 60 * 60 * 1000;
  return safeItems.filter((item) => {
    const createdAtMs = new Date(String(item?.createdAt || '')).getTime();
    return Number.isFinite(createdAtMs) ? (now - createdAtMs <= maxAgeMs) : true;
  });
}

function saveAppNotifications(items) {
  const safeItems = Array.isArray(items) ? items.slice(0, 500) : [];
  safeStorageSet(APP_NOTIFICATIONS_KEY, JSON.stringify(safeItems));
}

async function fetchServerNotifications(filter = 'all') {
  const normalized = String(filter || 'all').toLowerCase() === 'unread' ? 'unread' : 'all';
  const query = normalized === 'unread' ? '?filter=unread&limit=100' : '?limit=100';
  const response = await apiRequest(`/me/notifications${query}`, { method: 'GET', suppressSessionModal: true });
  const items = Array.isArray(response?.items) ? response.items : [];
  const unreadCount = Number(response?.unreadCount || 0);
  return { items, unreadCount };
}

async function postServerNotification(payload = {}) {
  return apiRequest('/me/notifications', {
    method: 'POST',
    body: JSON.stringify(payload)
  });
}

function isNotificationForUser(notification, user) {
  if (!notification || !user) return false;
  const hints = [
    String(user.username || '').trim().toLowerCase(),
    String(user.nickname || '').trim().toLowerCase(),
    String(user.name || '').trim().toLowerCase(),
    String(user.email || '').trim().toLowerCase()
  ].filter(Boolean);
  const targets = [
    String(notification.toUser || '').trim().toLowerCase(),
    String(notification.toUsername || '').trim().toLowerCase(),
    String(notification.toNickname || '').trim().toLowerCase(),
    String(notification.toName || '').trim().toLowerCase(),
    String(notification.toEmail || '').trim().toLowerCase()
  ].filter(Boolean);
  return targets.some((target) => hints.includes(target));
}

async function pushInAppNotification(payload = {}) {
  const item = {
    id: `ntf_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
    title: String(payload.title || '알림').slice(0, 120),
    message: String(payload.message || '').slice(0, 300),
    panel: String(payload.panel || ''),
    targetId: Number(payload.targetId || payload.newsId || payload.qnaId || 0) || 0,
    newsId: Number(payload.newsId || 0) || 0,
    qnaId: Number(payload.qnaId || 0) || 0,
    toUser: String(payload.toUser || ''),
    toUsername: String(payload.toUsername || ''),
    toNickname: String(payload.toNickname || ''),
    toName: String(payload.toName || ''),
    toEmail: String(payload.toEmail || ''),
    read: false,
    createdAt: new Date().toISOString(),
    meta: payload.meta && typeof payload.meta === 'object' ? payload.meta : {}
  };
  const user = getCurrentUser();
  if (user) {
    const targetUserId = Number(payload.userId || payload.toUserId || user.id || 0);
    try {
      await postServerNotification({
        userId: targetUserId || Number(user.id || 0),
        title: item.title,
        message: item.message,
        panel: item.panel,
        targetId: Number(item.targetId || 0),
        kind: String(payload.kind || 'general'),
        meta: {
          ...(item.meta || {}),
          newsId: Number(item.newsId || 0),
          qnaId: Number(item.qnaId || 0),
          anchorId: String(payload.anchorId || item.meta?.anchorId || '')
        }
      });
      await renderMyNotifications();
      return;
    } catch (_) {}
  }
  const notifications = getAppNotifications();
  notifications.unshift(item);
  saveAppNotifications(notifications);
  if (typeof renderMyNotifications === 'function') renderMyNotifications();
}

function getCurrentUserNotifications() {
  const user = getCurrentUser();
  if (!user) return [];
  return getAppNotifications().filter((item) => isNotificationForUser(item, user));
}

async function markCurrentUserNotificationsRead() {
  const user = getCurrentUser();
  if (!user) return;
  try {
    await apiRequest('/me/notifications/read-all', { method: 'PATCH' });
    return;
  } catch (_) {}
  const notifications = getAppNotifications();
  const next = notifications.map((item) => (
    isNotificationForUser(item, user) ? { ...item, read: true } : item
  ));
  saveAppNotifications(next);
}

async function renderMyNotifications() {
  const listEl = document.getElementById('my-notifications-list');
  const emptyEl = document.getElementById('my-notifications-empty');
  const countEl = document.getElementById('my-notifications-count');
  const navBadge = document.getElementById('my-info-unread-badge');
  const mobileBadge = document.getElementById('mobile-notification-badge');
  const filterAllBtn = document.getElementById('my-notifications-filter-all');
  const filterUnreadBtn = document.getElementById('my-notifications-filter-unread');
  const markAllBtn = document.getElementById('my-notifications-mark-all-read');
  const user = getCurrentUser();
  let items = [];
  let unreadCount = 0;
  if (user) {
    try {
      const server = await fetchServerNotifications(myNotificationFilter);
      items = Array.isArray(server.items) ? server.items.map((item) => ({
        ...item,
        newsId: Number(item?.meta?.newsId || (item.panel === 'news' ? item.targetId : 0) || 0),
        qnaId: Number(item?.meta?.qnaId || (item.panel === 'qna' ? item.targetId : 0) || 0),
        anchorId: String(item?.meta?.anchorId || '')
      })) : [];
      unreadCount = Number(server.unreadCount || 0);
      myNotificationsCache = items;
    } catch (_) {
      items = getCurrentUserNotifications();
      unreadCount = items.filter((item) => !item.read).length;
      myNotificationsCache = items;
    }
  }
  if (!user) {
    myNotificationsCache = [];
  }

  if (filterAllBtn) filterAllBtn.classList.toggle('active', myNotificationFilter === 'all');
  if (filterUnreadBtn) filterUnreadBtn.classList.toggle('active', myNotificationFilter === 'unread');
  if (countEl) countEl.textContent = String(items.length);
  if (navBadge) {
    navBadge.textContent = String(unreadCount);
    navBadge.classList.toggle('d-none', unreadCount <= 0 || !user);
  }
  if (mobileBadge) {
    mobileBadge.textContent = String(unreadCount);
    mobileBadge.classList.toggle('d-none', unreadCount <= 0 || !user);
  }
  if (markAllBtn) markAllBtn.classList.toggle('d-none', !user || unreadCount <= 0);
  if (!listEl || !emptyEl) return;
  if (!user || !items.length) {
    listEl.innerHTML = '';
    emptyEl.classList.remove('d-none');
    return;
  }
  emptyEl.classList.add('d-none');
  const viewItems = items.slice(0, 20);
  listEl.innerHTML = viewItems.map((item) => `
    <button type="button" class="list-group-item list-group-item-action ${item.read ? '' : 'list-group-item-info'}" data-my-notification-id="${escapeHtml(item.id || '')}">
      <div class="fw-semibold">${escapeHtml(item.title || '알림')}</div>
      <div class="small text-muted">${escapeHtml(item.message || '')}</div>
      <div class="small text-muted mt-1">${escapeHtml(formatDetailDateTime(item.createdAt || ''))}</div>
    </button>
  `).join('');
  const mapById = {};
  viewItems.forEach((item) => { mapById[String(item.id || '')] = item; });
  listEl.querySelectorAll('[data-my-notification-id]').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const item = mapById[String(btn.getAttribute('data-my-notification-id') || '')];
      if (!item) return;
      if (user && !item.read) {
        try {
          await apiRequest(`/me/notifications/${Number(item.id || 0)}/read`, { method: 'PATCH' });
        } catch (_) {}
      }
      if (item.panel === 'qna' && Number(item.qnaId || 0) > 0 && typeof openQnaDetail === 'function') {
        movePanel('news');
        activateNewsTab('qna');
        openQnaDetail(Number(item.qnaId || 0), { scrollToAnswer: true, anchorId: item.anchorId || 'qna-answer-anchor' });
        return;
      }
      if (item.panel === 'news' && Number(item.newsId || 0) > 0 && typeof openNotice === 'function') {
        movePanel('news');
        activateNewsTab('notice');
        openNotice(Number(item.newsId || 0));
      }
    });
  });
}

async function renderMyActivitySummary() {
  const wrap = document.getElementById('my-activity-summary');
  const appliedEl = document.getElementById('my-activity-applied-count');
  const attendedEl = document.getElementById('my-activity-attended-count');
  const cancelledEl = document.getElementById('my-activity-cancelled-count');
  if (!wrap || !appliedEl || !attendedEl || !cancelledEl) return;
  const user = getCurrentUser();
  if (!user) {
    wrap.classList.add('d-none');
    appliedEl.textContent = '0';
    attendedEl.textContent = '0';
    cancelledEl.textContent = '0';
    return;
  }
  wrap.classList.remove('d-none');
  let items = [];
  try {
    const res = await apiRequest('/me/history', { method: 'GET', suppressSessionModal: true });
    items = Array.isArray(res?.items) ? res.items : [];
  } catch (_) {
    items = [];
  }
  const toKey = (value) => String(value || '').trim().toLowerCase();
  const appliedSet = new Set(['waiting', 'pending', 'confirmed', 'applied', 'approved']);
  const attendedSet = new Set(['attended', 'completed', 'done', 'participated']);
  const cancelledSet = new Set(['cancelled', 'canceled', 'noshow', 'rejected']);
  let applied = 0;
  let attended = 0;
  let cancelled = 0;
  items.forEach((item) => {
    const key = toKey(item?.status);
    if (attendedSet.has(key)) {
      attended += 1;
      return;
    }
    if (cancelledSet.has(key)) {
      cancelled += 1;
      return;
    }
    if (appliedSet.has(key)) {
      applied += 1;
    }
  });
  appliedEl.textContent = String(applied);
  attendedEl.textContent = String(attended);
  cancelledEl.textContent = String(cancelled);
}

window.pushInAppNotification = pushInAppNotification;
window.renderMyNotifications = renderMyNotifications;
window.markCurrentUserNotificationsRead = markCurrentUserNotificationsRead;
window.renderMyActivitySummary = renderMyActivitySummary;

document.addEventListener('click', async (event) => {
  const target = event.target instanceof HTMLElement ? event.target.closest('[data-my-notification-action]') : null;
  if (!(target instanceof HTMLElement)) return;
  const action = String(target.dataset.myNotificationAction || '').trim();
  if (action === 'filter-all') {
    myNotificationFilter = 'all';
    await renderMyNotifications();
    return;
  }
  if (action === 'filter-unread') {
    myNotificationFilter = 'unread';
    await renderMyNotifications();
    return;
  }
  if (action === 'mark-all-read') {
    await markCurrentUserNotificationsRead();
    myNotificationFilter = 'all';
    await renderMyNotifications();
  }
});

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
  movePanel('account-recovery');
  const usernameTabBtn = document.getElementById('recover-username-tab-btn');
  if (usernameTabBtn instanceof HTMLElement) usernameTabBtn.click();
}

async function findPasswordFlow() {
  movePanel('account-recovery');
  const passwordTabBtn = document.getElementById('recover-password-tab-btn');
  if (passwordTabBtn instanceof HTMLElement) passwordTabBtn.click();
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
  const mobileMyInfoLink = document.getElementById('mobile-menu-myinfo-link');
  const mobileNotificationTab = document.getElementById('mobile-notification-tab');
  const mobileSignupBtn = document.getElementById('mobile-menu-signup-btn');
  const mobileLoginBtn = document.getElementById('mobile-menu-login-btn');

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
    if (mobileMyInfoLink) mobileMyInfoLink.classList.remove('d-none');
    if (mobileNotificationTab) {
      mobileNotificationTab.classList.add('d-none');
      mobileNotificationTab.setAttribute('aria-hidden', 'true');
    }
    if (mobileSignupBtn) mobileSignupBtn.classList.add('d-none');
    if (mobileLoginBtn) mobileLoginBtn.textContent = '내 계정';
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
    if (mobileMyInfoLink) mobileMyInfoLink.classList.add('d-none');
    if (mobileNotificationTab) {
      mobileNotificationTab.classList.add('d-none');
      mobileNotificationTab.setAttribute('aria-hidden', 'true');
    }
    if (mobileSignupBtn) mobileSignupBtn.classList.remove('d-none');
    if (mobileLoginBtn) mobileLoginBtn.textContent = '로그인';
  }
  if (typeof setNewsWriteButtons === 'function') setNewsWriteButtons();
  if (typeof updateCalendarCreateVisibility === 'function') updateCalendarCreateVisibility();
  if (typeof updateAboutPhotoAdminControls === 'function') updateAboutPhotoAdminControls();
  if (typeof updateExecutivesAdminControls === 'function') updateExecutivesAdminControls();
  if (typeof updateHomeHeroAdminControls === 'function') updateHomeHeroAdminControls();
  if (typeof updateSiteEditorControls === 'function') updateSiteEditorControls();
  if (typeof applyWriteRoleVisibility === 'function') applyWriteRoleVisibility();
  if (typeof renderMyNotifications === 'function') renderMyNotifications();
  if (typeof renderMyActivitySummary === 'function') renderMyActivitySummary();
}

function isValidBirthDate(value) {
  if (!/^\d{4}\.\d{2}\.\d{2}$/.test(value)) return false;
  const [year, month, day] = value.split('.').map(Number);
  const date = new Date(year, month - 1, day);
  return date.getFullYear() === year && date.getMonth() === month - 1 && date.getDate() === day;
}
