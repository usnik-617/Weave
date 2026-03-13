  // Initialize WOW animations
  new WOW().init();

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
  const WRITE_TEMPLATES_KEY = 'weave_write_templates';
  const DEFAULT_WRITE_TEMPLATES = {
    news: '',
    gallery: ''
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
  let faqSearchKeyword = '';
  let qnaSearchKeyword = '';
  let gallerySearchKeyword = '';
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
    if (!item || typeof item !== 'object') return false;
    const authorText = typeof item.author === 'string' ? item.author.trim() : '';
    const authorObjRole = String(item.author?.role || '').toUpperCase();
    if (authorObjRole && ['EXECUTIVE', 'LEADER', 'VICE_LEADER', 'ADMIN'].includes(authorObjRole)) {
      return true;
    }
    if (authorText) return true;
    return false;
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

  function getContent() {
    const data = localStorage.getItem(DATA_KEY);
    if (!data) return normalizeContent(DEFAULT_DATA);
    try {
      const parsed = JSON.parse(data);
      const normalized = normalizeContent(parsed);
      const beforeCount = Array.isArray(parsed?.gallery) ? parsed.gallery.length : 0;
      const afterCount = Array.isArray(normalized?.gallery) ? normalized.gallery.length : 0;
      if (beforeCount !== afterCount) {
        localStorage.setItem(DATA_KEY, JSON.stringify(normalized));
      }
      return normalized;
    } catch (_) {
      return normalizeContent(DEFAULT_DATA);
    }
  }

  function saveContent(data) {
    // news에 activityId가 있는 경우 activities에 자동 연동
    const safeData = normalizeContent(data);
    if (Array.isArray(safeData.news)) {
      safeData.activities = Array.isArray(safeData.activities) ? safeData.activities : [];
      safeData.news.forEach(newsItem => {
        const activityId = Number(newsItem.activityId || newsItem.activity_id || 0);
        if (activityId > 0 && newsItem.date) {
          // 기존 activities에서 동일 id 찾기
          const idx = safeData.activities.findIndex(a => Number(a.id) === activityId);
          const newActivity = {
            id: activityId,
            title: newsItem.title || '봉사 일정',
            startAt: newsItem.date,
            description: newsItem.content || '',
            linkedNewsId: newsItem.id
          };
          if (idx >= 0) {
            safeData.activities[idx] = { ...safeData.activities[idx], ...newActivity };
          } else {
            safeData.activities.push(newActivity);
          }
        }
      });
    }
    localStorage.setItem(DATA_KEY, JSON.stringify(safeData));
  }

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

  function getWriteTemplates() {
    try {
      const parsed = JSON.parse(localStorage.getItem(WRITE_TEMPLATES_KEY) || '{}');
      return {
        news: String(parsed.news || DEFAULT_WRITE_TEMPLATES.news),
        gallery: String(parsed.gallery || DEFAULT_WRITE_TEMPLATES.gallery)
      };
    } catch (_) {
      return { ...DEFAULT_WRITE_TEMPLATES };
    }
  }

  function saveWriteTemplates(next) {
    const payload = {
      news: String(next?.news || ''),
      gallery: String(next?.gallery || '')
    };
    localStorage.setItem(WRITE_TEMPLATES_KEY, JSON.stringify(payload));
  }

  function updateWriteTemplateVisibility() {
    const wrap = document.getElementById('write-template-admin-wrap');
    if (!wrap) return;
    const user = getCurrentUser();
    const canManage = !!(user && user.status === 'active' && isStaffUser(user));
    wrap.classList.toggle('d-none', !canManage);
  }

  function applyTemplateToEditor(editorId, templateType) {
    const editor = document.getElementById(editorId);
    if (!editor) return;
    const templates = getWriteTemplates();
    const template = String(templates?.[templateType] || '').trim();
    if (!template) {
      notifyMessage('저장된 템플릿이 없습니다. 먼저 템플릿을 저장해주세요.');
      return;
    }
    const current = String(editor.innerHTML || '').trim();
    if (current && !confirm('현재 내용을 템플릿으로 덮어쓸까요?')) {
      return;
    }
    editor.innerHTML = template;
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
    if (Number.isNaN(date.getTime())) return value;
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
    return `${y}/${d}/${m} ${hh}:${mm}`;
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
    if (dateEl) dateEl.textContent = payload.date || '-';
    if (volunteerEl) volunteerEl.textContent = payload.volunteer || '';
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

