  // Initialize WOW animations
  if (typeof WOW !== 'undefined') {
    new WOW().init();
  }

  // core state/auth/api helpers moved to static/js/app-core.js

  const DEFAULT_DATA = {
    news: [
      { id: 1, title: '2026년 발대식 안내', author: '관리자', date: '2026-02-01', views: 0, image: 'logo.png', content: '2026년 발대식 일정 및 안내사항입니다.' },
      { id: 2, title: '2월 플로깅 활동 공지', author: '관리자', date: '2026-02-15', views: 0, image: 'logo.png', content: '2월 플로깅 장소 및 준비물 안내입니다.' }
    ],
    faq: [
      { id: 1, title: '위브는 누구나 참여할 수 있나요?', author: '관리자', date: '2026-02-01', views: 0, content: '만 19~39세 남양주시 거주/근무/재학 청년이 참여할 수 있습니다.' },
      { id: 2, title: '활동 일정은 어디서 확인하나요?', author: '관리자', date: '2026-02-03', views: 0, content: '소식 탭 공지사항과 공식 SNS에서 확인 가능합니다.' }
    ],
    qna: [],
    gallery: []
  };

  const NEWS_PAGE_SIZE = 10;
  const FAQ_PAGE_SIZE = 10;
  const QNA_PAGE_SIZE = 10;
  let calendarBaseDate = new Date();
  let calendarSelectedDate = null;
  let calendarActivities = [];
  let focusedActivityDateKey = '';
  let pendingRecurrenceCancelGroupId = '';
  let editingActivityId = null;
  let newsCurrentPage = 1;
  let faqCurrentPage = 1;
  let qnaCurrentPage = 1;
  let newsSearchKeyword = '';
  let newsSortMode = 'latest';
  let faqSearchKeyword = '';
  let qnaSearchKeyword = '';
  let gallerySearchKeyword = '';
  let gallerySortMode = 'latest';
  let currentNewsTab = 'notice';
  const GALLERY_PAGE_SIZE = 9;
  let galleryCurrentPage = 1;
  let galleryCurrentFilter = '*';
  let currentNewsDetailId = null;
  let currentGalleryDetailId = null;
  let currentQnaAnswerId = null;
  let opsPendingPage = 1;
  const OPS_PENDING_PAGE_SIZE = 10;
  let opsPendingSortBy = 'id';
  let opsPendingSortDir = 'desc';
  let opsPendingSearchKeyword = '';
  let homeNoticeItems = [];
  let homeNoticeIndex = 0;
  let homeNoticeTimer = null;
  let homeNoticePaused = false;
  let volunteerEvents = [];

  function isOperatorGalleryPost(item) {
    return !!(item && typeof item === 'object');
  }

  function normalizeGalleryItems(items) {
    const rawItems = Array.isArray(items) ? items : [];
    return rawItems.filter(isOperatorGalleryPost);
  }

  function normalizeContent(data) {
    const safe = (data && typeof data === 'object') ? { ...data } : {};
    safe.news = Array.isArray(safe.news) ? safe.news : [];
    safe.faq = Array.isArray(safe.faq) ? safe.faq : [];
    safe.qna = Array.isArray(safe.qna) ? safe.qna : [];
    safe.gallery = normalizeGalleryItems(safe.gallery);
    return safe;
  }

  function cloneContent(data) {
    try {
      return JSON.parse(JSON.stringify(normalizeContent(data)));
    } catch (_) {
      return normalizeContent(data);
    }
  }

  function stripInlineDataImagesFromHtml(html) {
    const raw = String(html || '');
    if (!raw || !raw.includes('data:image/')) return raw;
    return raw.replace(/<img[^>]+src=["']data:image\/[^"']+["'][^>]*>/gi, '');
  }

  function compactContentForPersistentStorage(data) {
    const compacted = cloneContent(data);
    const sections = ['news', 'faq', 'qna', 'gallery'];
    sections.forEach((section) => {
      const items = Array.isArray(compacted[section]) ? compacted[section] : [];
      items.forEach((item) => {
        if (!item || typeof item !== 'object') return;
        if (typeof item.content === 'string' && item.content.includes('data:image/')) {
          item.content = stripInlineDataImagesFromHtml(item.content);
        }
        if (Array.isArray(item.images)) {
          item.images = item.images.filter((src) => typeof src === 'string' && !src.startsWith('data:image/'));
        }
        if (typeof item.image === 'string' && item.image.startsWith('data:image/')) {
          item.image = '';
        }
        if (typeof item.thumb_url === 'string' && item.thumb_url.startsWith('data:image/')) {
          item.thumb_url = '';
        }
        if (typeof item.thumbnail_url === 'string' && item.thumbnail_url.startsWith('data:image/')) {
          item.thumbnail_url = '';
        }
      });
    });
    return compacted;
  }

  function getContent() {
    if (window.__WEAVE_RUNTIME_CONTENT && typeof window.__WEAVE_RUNTIME_CONTENT === 'object') {
      return normalizeContent(window.__WEAVE_RUNTIME_CONTENT);
    }
    const data = localStorage.getItem(DATA_KEY);
    const sessionData = sessionStorage.getItem(DATA_KEY);
    if (!data && !sessionData) return normalizeContent(DEFAULT_DATA);
    try {
      const parsed = JSON.parse(data || sessionData || '{}');
      const normalized = normalizeContent(parsed);
      window.__WEAVE_RUNTIME_CONTENT = normalized;
      const beforeCount = Array.isArray(parsed?.gallery) ? parsed.gallery.length : 0;
      const afterCount = Array.isArray(normalized?.gallery) ? normalized.gallery.length : 0;
      if (beforeCount !== afterCount) {
        try {
          localStorage.setItem(DATA_KEY, JSON.stringify(normalized));
        } catch (_) {}
      }
      return normalized;
    } catch (_) {
      return normalizeContent(DEFAULT_DATA);
    }
  }

  function saveContent(data) {
    const normalized = normalizeContent(data);
    window.__WEAVE_RUNTIME_CONTENT = normalized;
    const compacted = compactContentForPersistentStorage(normalized);
    const serialized = JSON.stringify(compacted);
    try {
      localStorage.setItem(DATA_KEY, serialized);
      try {
        sessionStorage.removeItem(DATA_KEY);
      } catch (_) {}
      return true;
    } catch (_) {
      try {
        sessionStorage.setItem(DATA_KEY, serialized);
        return true;
      } catch (_) {
        return false;
      }
    }
  }

  async function hydrateContentFromServerIfEmpty(options = {}) {
    const force = !!options.force;
    const local = getContent();
    const localCount =
      (Array.isArray(local.news) ? local.news.length : 0)
      + (Array.isArray(local.faq) ? local.faq.length : 0)
      + (Array.isArray(local.qna) ? local.qna.length : 0)
      + (Array.isArray(local.gallery) ? local.gallery.length : 0);
    if ((!force && localCount > 0) || typeof apiRequest !== 'function') return false;

    const mapPostItem = (item) => {
      const id = Number(item?.id || 0) || Date.now();
      const createdAt = String(item?.created_at || item?.updated_at || '').trim();
      const authorObj = item?.author && typeof item.author === 'object' ? item.author : null;
      const authorName = String(authorObj?.nickname || item?.author_name || '관리자');
      const isoDate = createdAt ? new Date(createdAt) : new Date();
      const dateKey = Number.isNaN(isoDate.getTime()) ? getTodayString() : isoDate.toISOString().slice(0, 10);
      return {
        id,
        title: String(item?.title || '제목 없음'),
        author: authorName,
        date: dateKey,
        views: Number(item?.views || 0) || 0,
        image: String(item?.image_url || item?.thumb_url || 'logo.png'),
        image_url: String(item?.image_url || ''),
        thumb_url: String(item?.thumb_url || ''),
        content: String(item?.content || ''),
        publishAt: String(item?.publish_at || ''),
        volunteerStartDate: String(item?.volunteerStartDate || ''),
        volunteerEndDate: String(item?.volunteerEndDate || '')
      };
    };

    try {
      const [noticeRes, faqRes, qnaRes, galleryRes] = await Promise.all([
        apiRequest('/posts?category=notice&page=1&pageSize=200', { method: 'GET', suppressSessionModal: true }),
        apiRequest('/posts?category=faq&page=1&pageSize=200', { method: 'GET', suppressSessionModal: true }),
        apiRequest('/posts?category=qna&page=1&pageSize=200', { method: 'GET', suppressSessionModal: true }),
        apiRequest('/posts?category=gallery&page=1&pageSize=200', { method: 'GET', suppressSessionModal: true })
      ]);
      const next = {
        news: (noticeRes?.items || []).map(mapPostItem),
        faq: (faqRes?.items || []).map(mapPostItem),
        qna: (qnaRes?.items || []).map((item) => ({
          ...mapPostItem(item),
          isSecret: !!item?.is_secret,
          answer: String(item?.answer || '')
        })),
        gallery: (galleryRes?.items || []).map((item) => {
          const mapped = mapPostItem(item);
          const activityStartDate = String(item?.volunteerStartDate || item?.activityStartDate || '').trim();
          const activityEndDate = String(item?.volunteerEndDate || item?.activityEndDate || activityStartDate || '').trim();
          const yearBase = activityStartDate || String(item?.created_at || Date.now());
          const parsedYear = new Date(yearBase);
          const year = Number.isNaN(parsedYear.getTime()) ? new Date().getFullYear() : parsedYear.getFullYear();
          return {
            ...mapped,
            year,
            category: `y${year}`,
            image: String(item?.image_url || item?.thumb_url || mapped.image || 'logo.png'),
            thumbnail_url: String(item?.thumb_url || ''),
            thumb_url: String(item?.thumb_url || ''),
            activityStartDate,
            activityEndDate
          };
        })
      };
      const fetchedCount =
        next.news.length + next.faq.length + next.qna.length + next.gallery.length;
      if (fetchedCount > 0) {
        try {
          saveContent(next);
          return true;
        } catch (_) {
          return false;
        }
      }
      return false;
    } catch (_) {
      return false;
    }
  }

  window.hydrateContentFromServerIfEmpty = hydrateContentFromServerIfEmpty;
  window.hydrateContentFromServer = (options = {}) => hydrateContentFromServerIfEmpty({ ...options, force: true });

  function getTodayString() {
    return new Date().toISOString().slice(0, 10);
  }

  function toDatetimeLocalInput(value, fallbackTime = '09:00') {
    const raw = String(value || '').trim();
    if (!raw) return '';
    if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(raw)) return raw;
    if (/^\d{4}-\d{2}-\d{2}$/.test(raw)) return `${raw}T${fallbackTime}`;
    const parsed = new Date(raw);
    if (Number.isNaN(parsed.getTime())) return '';
    const y = parsed.getFullYear();
    const m = String(parsed.getMonth() + 1).padStart(2, '0');
    const d = String(parsed.getDate()).padStart(2, '0');
    const hh = String(parsed.getHours()).padStart(2, '0');
    const mm = String(parsed.getMinutes()).padStart(2, '0');
    return `${y}-${m}-${d}T${hh}:${mm}`;
  }

  async function loadGalleryActivityOptions(selectedId = '') {
    const select = document.getElementById('gallery-activity-select');
    if (!select) return;
    const selected = String(selectedId || '');
    const previous = String(select.value || selected);
    select.innerHTML = '<option value="">선택 안 함</option>';
    try {
      const data = await apiRequest('/activities?all=1', { method: 'GET' });
      const items = Array.isArray(data?.items) ? data.items : [];
      items
        .filter(item => !item.isCancelled)
        .sort((a, b) => new Date(b.startAt).getTime() - new Date(a.startAt).getTime())
        .forEach((item) => {
          const option = document.createElement('option');
          option.value = String(item.id || '');
          option.dataset.startAt = String(item.startAt || '');
          option.textContent = `${formatKoreanDate(item.startAt)} · ${item.title || '제목 없음'}`;
          select.appendChild(option);
        });
    } catch (_) {}
    const targetValue = selected || previous;
    if (targetValue) select.value = targetValue;
  }

  function formatDateOnly(value) {
    const date = value ? new Date(value) : new Date();
    const y = date.getFullYear();
    const m = String(date.getMonth() + 1).padStart(2, '0');
    const d = String(date.getDate()).padStart(2, '0');
    return `${y}-${m}-${d}`;
  }

  function formatKoreanDate(value) {
    if (!value) return '-';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return String(value)
        .replace('T', ' ')
        .replace(/\.\d{1,3}Z?$/, '')
        .trim();
    }
    return date.toLocaleString('ko-KR', {
      year: 'numeric',
      month: 'numeric',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  }

  function formatDetailDateTime(value) {
    const raw = String(value || '').trim();
    const normalized = /^\d{4}-\d{2}-\d{2}$/.test(raw) ? `${raw}T00:00:00` : raw;
    const date = normalized ? new Date(normalized) : new Date();
    if (Number.isNaN(date.getTime())) return '-';
    const y = date.getFullYear();
    const d = String(date.getDate()).padStart(2, '0');
    const m = String(date.getMonth() + 1).padStart(2, '0');
    const hh = String(date.getHours()).padStart(2, '0');
    const mm = String(date.getMinutes()).padStart(2, '0');
    return `${y}/${m}/${d} ${hh}:${mm}`;
  }

  function getDdayInfo(targetValue) {
    const raw = String(targetValue || '').trim();
    if (!raw) return { label: '', className: '', diffDays: null };
    const date = new Date(raw);
    if (Number.isNaN(date.getTime())) return { label: '', className: '', diffDays: null };
    const today = new Date();
    const startOfToday = new Date(today.getFullYear(), today.getMonth(), today.getDate());
    const targetDay = new Date(date.getFullYear(), date.getMonth(), date.getDate());
    const diffDays = Math.floor((targetDay.getTime() - startOfToday.getTime()) / 86400000);
    if (diffDays === 0) return { label: 'D-day', className: 'dday-today', diffDays };
    if (diffDays > 0) return { label: `D-${diffDays}`, className: 'dday-open', diffDays };
    return { label: '', className: '', diffDays };
  }

  function getAboutVolunteerPhoto() {
    const raw = String(localStorage.getItem(ABOUT_VOLUNTEER_PHOTO_KEY) || '').trim();
    if (!raw || /^(null|undefined|\[object\s+object\])$/i.test(raw)) {
      return DEFAULT_ABOUT_VOLUNTEER_PHOTO;
    }
    return raw;
  }

  function updateDetailMeta(prefix, payload = {}) {
    const authorEl = document.getElementById(`${prefix}-detail-author`);
    const dateEl = document.getElementById(`${prefix}-detail-date`);
    const volunteerEl = document.getElementById(`${prefix}-detail-volunteer`);
    const statsEl = document.getElementById(`${prefix}-detail-stats`);
    if (authorEl) authorEl.textContent = payload.author || '-';
    if (dateEl) dateEl.textContent = `작성 일자 : ${payload.date || '-'}`;
    if (volunteerEl) {
      if (payload.volunteerHtml) {
        volunteerEl.innerHTML = payload.volunteerHtml;
      } else {
        const existingInline = volunteerEl.querySelector('.detail-volunteer-inline');
        if (existingInline) {
          const valueEl = existingInline.querySelector('.detail-meta-value');
          if (valueEl) valueEl.textContent = payload.volunteer || '';
          else volunteerEl.textContent = payload.volunteer || '';
        } else {
          volunteerEl.textContent = payload.volunteer || '';
        }
      }
    }
    if (statsEl) statsEl.textContent = `[조회수 ${payload.views || 0} 추천 수 ${payload.recommends || 0} 댓글 ${payload.comments || 0}]`;
  }

  function expandDateRange(startDate, endDate) {
    const start = startDate ? new Date(`${startDate}T00:00:00`) : null;
    const end = endDate ? new Date(`${endDate}T00:00:00`) : null;
    if (!start || Number.isNaN(start.getTime())) return [];
    const safeEnd = !end || Number.isNaN(end.getTime()) ? start : end;
    if (safeEnd.getTime() < start.getTime()) return [];
    const days = [];
    const cursor = new Date(start);
    while (cursor.getTime() <= safeEnd.getTime()) {
      days.push(formatDateOnly(cursor));
      cursor.setDate(cursor.getDate() + 1);
    }
    return days;
  }

  // activities/ops/home-calendar helpers moved to static/js/app-activities-ops.js

  // calendar/event/join helpers moved to static/js/app-calendar-events.js
  // news/gallery render & detail helpers moved to static/js/app-news-gallery.js

  // editor/upload/write-form helpers moved to static/js/app-editor-upload.js

