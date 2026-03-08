  const HOME_HERO_KEY = 'weave_home_hero';
  const DEFAULT_HOME_HERO = {
    image: 'logo.png',
    leadText: '남양주의 청년 봉사자들이 <strong>연결(Weave)하고 성장</strong>하는 커뮤니티',
    subText: '함께 나누고, 함께 성장하고, 함께 변화하는 지역사회',
    imageOffsetX: 0,
    imageOffsetY: 0,
    backgroundImage: 'Background.jpg',
    backgroundPosX: 50,
    backgroundPosY: 45
  };

  function getHomeHeroConfig() {
    const fallback = { ...DEFAULT_HOME_HERO };
    const raw = localStorage.getItem(HOME_HERO_KEY);
    if (!raw) return fallback;
    try {
      const parsed = JSON.parse(raw);
      return {
        image: fallback.image,
        leadText: String(parsed?.leadText || fallback.leadText),
        subText: String(parsed?.subText || fallback.subText),
        imageOffsetX: Number.isFinite(Number(parsed?.imageOffsetX)) ? Number(parsed.imageOffsetX) : fallback.imageOffsetX,
        imageOffsetY: Number.isFinite(Number(parsed?.imageOffsetY)) ? Number(parsed.imageOffsetY) : fallback.imageOffsetY,
        backgroundImage: String(parsed?.backgroundImage || fallback.backgroundImage),
        backgroundPosX: Number.isFinite(Number(parsed?.backgroundPosX)) ? Number(parsed.backgroundPosX) : fallback.backgroundPosX,
        backgroundPosY: Number.isFinite(Number(parsed?.backgroundPosY)) ? Number(parsed.backgroundPosY) : fallback.backgroundPosY
      };
    } catch (_) {
      return fallback;
    }
  }

  function saveHomeHeroConfig(payload = {}) {
    const current = getHomeHeroConfig();
    const next = {
      image: DEFAULT_HOME_HERO.image,
      leadText: String(payload.leadText || current.leadText || DEFAULT_HOME_HERO.leadText),
      subText: String(payload.subText || current.subText || DEFAULT_HOME_HERO.subText),
      imageOffsetX: Number.isFinite(Number(payload.imageOffsetX)) ? Number(payload.imageOffsetX) : Number(current.imageOffsetX || DEFAULT_HOME_HERO.imageOffsetX),
      imageOffsetY: Number.isFinite(Number(payload.imageOffsetY)) ? Number(payload.imageOffsetY) : Number(current.imageOffsetY || DEFAULT_HOME_HERO.imageOffsetY),
      backgroundImage: String(payload.backgroundImage || current.backgroundImage || DEFAULT_HOME_HERO.backgroundImage),
      backgroundPosX: Number.isFinite(Number(payload.backgroundPosX)) ? Number(payload.backgroundPosX) : Number(current.backgroundPosX || DEFAULT_HOME_HERO.backgroundPosX),
      backgroundPosY: Number.isFinite(Number(payload.backgroundPosY)) ? Number(payload.backgroundPosY) : Number(current.backgroundPosY || DEFAULT_HOME_HERO.backgroundPosY)
    };
    localStorage.setItem(HOME_HERO_KEY, JSON.stringify(next));
    return next;
  }

  function toCssUrlValue(pathValue) {
    const text = String(pathValue || '').replace(/'/g, "\\'");
    return `url('${text}')`;
  }

  function renderHomeHeroConfig() {
    const homeHero = getHomeHeroConfig();
    const imageEl = document.getElementById('home-hero-image');
    const leadEl = document.getElementById('home-hero-lead');
    const subEl = document.getElementById('home-hero-subtext');
    const previewEl = document.getElementById('home-hero-image-preview');
    const bgPreviewEl = document.getElementById('home-hero-bg-preview');
    const positionX = Math.max(-120, Math.min(120, Number(homeHero.imageOffsetX || 0)));
    const positionY = Math.max(-120, Math.min(120, Number(homeHero.imageOffsetY || 0)));
    const bgPosX = Math.max(0, Math.min(100, Number(homeHero.backgroundPosX || 50)));
    const bgPosY = Math.max(0, Math.min(100, Number(homeHero.backgroundPosY || 45)));
    if (imageEl) {
      const requestedSrc = String(homeHero.image || DEFAULT_HOME_HERO.image).trim() || DEFAULT_HOME_HERO.image;
      const picture = imageEl.closest('picture');
      if (picture) {
        picture.querySelectorAll('source').forEach((sourceEl) => {
          if (!sourceEl.dataset.defaultSrcset) {
            sourceEl.dataset.defaultSrcset = String(sourceEl.getAttribute('srcset') || '');
          }
          // Keep hero image deterministic: dynamic admin/site-editor value should win over static source sets.
          sourceEl.removeAttribute('srcset');
        });
      }
      imageEl.removeAttribute('srcset');
      imageEl.src = requestedSrc;
      imageEl.onerror = () => {
        imageEl.onerror = null;
        imageEl.src = DEFAULT_HOME_HERO.image;
      };
    }
    if (imageEl) imageEl.style.transform = `translate(${positionX}px, ${positionY}px)`;
    if (leadEl) leadEl.innerHTML = homeHero.leadText;
    if (subEl) subEl.textContent = homeHero.subText;
    document.documentElement.style.setProperty('--hero-bg-image', toCssUrlValue(homeHero.backgroundImage || DEFAULT_HOME_HERO.backgroundImage));
    document.documentElement.style.setProperty('--hero-bg-pos-x', `${bgPosX}%`);
    document.documentElement.style.setProperty('--hero-bg-pos-y', `${bgPosY}%`);
    if (previewEl) {
      previewEl.src = homeHero.image;
      previewEl.style.transform = `translate(${Math.round(positionX * 0.25)}px, ${Math.round(positionY * 0.25)}px)`;
      previewEl.classList.remove('d-none');
    }
    if (bgPreviewEl) {
      bgPreviewEl.style.backgroundImage = toCssUrlValue(homeHero.backgroundImage || DEFAULT_HOME_HERO.backgroundImage);
      bgPreviewEl.style.backgroundPosition = `${bgPosX}% ${bgPosY}%`;
    }
    const posXInput = document.getElementById('home-hero-position-x');
    const posYInput = document.getElementById('home-hero-position-y');
    const posXNumberInput = document.getElementById('home-hero-position-x-number');
    const posYNumberInput = document.getElementById('home-hero-position-y-number');
    const bgPosXInput = document.getElementById('home-hero-bg-position-x');
    const bgPosYInput = document.getElementById('home-hero-bg-position-y');
    const bgPosXNumberInput = document.getElementById('home-hero-bg-position-x-number');
    const bgPosYNumberInput = document.getElementById('home-hero-bg-position-y-number');
    if (posXInput) posXInput.value = String(positionX);
    if (posYInput) posYInput.value = String(positionY);
    if (posXNumberInput) posXNumberInput.value = String(positionX);
    if (posYNumberInput) posYNumberInput.value = String(positionY);
    if (bgPosXInput) bgPosXInput.value = String(bgPosX);
    if (bgPosYInput) bgPosYInput.value = String(bgPosY);
    if (bgPosXNumberInput) bgPosXNumberInput.value = String(bgPosX);
    if (bgPosYNumberInput) bgPosYNumberInput.value = String(bgPosY);
  }

  function canManageHomeHero(user) {
    return !!(user && user.status === 'active' && isAdminUser(user));
  }

  function updateHomeHeroAdminControls() {
    const tools = document.getElementById('home-hero-admin-tools');
    const user = getCurrentUser();
    if (tools) tools.classList.toggle('d-none', !canManageHomeHero(user));
  }

  const SITE_TEXT_EDITS_KEY = 'weave_site_text_edits_v1';
  const SITE_IMAGE_EDITS_KEY = 'weave_site_image_edits_v1';
  const siteEditorConfig = window.WEAVE_SITE_EDITOR_CONFIG || {};
  const SITE_EDIT_ROOT_SELECTOR = Array.isArray(siteEditorConfig.rootSelectors)
    ? siteEditorConfig.rootSelectors.join(', ')
    : '#home, #home-stats, #home-notice-carousel, #about, #activities, #gallery, #news, #join, footer';
  const SITE_EDIT_TEXT_SELECTOR = Array.isArray(siteEditorConfig.textSelectors)
    ? siteEditorConfig.textSelectors.join(', ')
    : '#home-hero-lead, #home-hero-subtext, #stat-generation, #stat-members, #stat-activities, #stat-impact, #home-stats .stat-label';
  const SITE_EDIT_IMAGE_SELECTOR = Array.isArray(siteEditorConfig.imageSelectors)
    ? siteEditorConfig.imageSelectors.join(', ')
    : '#home-hero-image, #about-volunteer-image, #logo-panel img';
  let siteEditMode = false;
  let siteEditorImageInput = null;
  let siteEditorPendingImageKey = '';
  let siteEditorHistoryItems = [];
  let siteEditorUpdatedAt = '';
  let siteEditorSaveInFlight = false;
  const siteEditorTextDefaults = new Map();
  const siteEditorImageDefaults = new Map();
  const siteEditorControls = siteEditorConfig.controls || {};

  function canManageSiteEditor(user) {
    return !!(user && user.status === 'active' && isAdminUser(user));
  }

  function buildSiteEditorKey(element) {
    if (!element || !element.tagName) return '';
    if (element.id) return `id:${element.id}`;
    const parts = [];
    let node = element;
    while (node && node.nodeType === 1 && node !== document.body) {
      const tag = node.tagName.toLowerCase();
      let index = 1;
      let prev = node.previousElementSibling;
      while (prev) {
        if (prev.tagName === node.tagName) index += 1;
        prev = prev.previousElementSibling;
      }
      parts.unshift(`${tag}:nth-of-type(${index})`);
      if (node.id) {
        parts.unshift(`#${node.id}`);
        break;
      }
      node = node.parentElement;
    }
    return parts.join('>');
  }

  function sanitizeSiteEditableHtml(value) {
    if (typeof window.weaveSanitizeSiteEditableHtml === 'function') {
      return window.weaveSanitizeSiteEditableHtml(value);
    }
    const html = String(value || '');
    const parser = new DOMParser();
    const doc = parser.parseFromString(`<div>${html}</div>`, 'text/html');
    const root = doc.body.firstElementChild;
    if (!root) return '';
    root.querySelectorAll('script, style, iframe, object, embed').forEach((node) => node.remove());
    root.querySelectorAll('*').forEach((node) => {
      Array.from(node.attributes).forEach((attr) => {
        const name = String(attr.name || '').toLowerCase();
        const valueText = String(attr.value || '');
        if (name.startsWith('on')) {
          node.removeAttribute(attr.name);
          return;
        }
        if ((name === 'href' || name === 'src') && /^\s*javascript:/i.test(valueText)) {
          node.removeAttribute(attr.name);
        }
      });
    });
    return root.innerHTML;
  }

  function collectSiteEditorTextElements() {
    const nodes = [];
    document.querySelectorAll(SITE_EDIT_ROOT_SELECTOR).forEach((root) => {
      root.querySelectorAll(SITE_EDIT_TEXT_SELECTOR).forEach((element) => {
        if (element.closest('#home-hero-admin-tools, #about-photo-admin-tools, #join form')) return;
        const key = buildSiteEditorKey(element);
        if (!key) return;
        nodes.push(element);
      });
    });
    return nodes;
  }

  function collectSiteEditorImageElements() {
    const nodes = [];
    document.querySelectorAll(SITE_EDIT_ROOT_SELECTOR).forEach((root) => {
      root.querySelectorAll(SITE_EDIT_IMAGE_SELECTOR).forEach((element) => {
        if (element.closest('#home-hero-admin-tools, #about-photo-admin-tools')) return;
        const src = String(element.getAttribute('src') || '').trim();
        if (!src) return;
        const key = buildSiteEditorKey(element);
        if (!key) return;
        nodes.push(element);
      });
    });
    return nodes;
  }

  function loadSiteEditorMap(storageKey) {
    try {
      const raw = localStorage.getItem(storageKey);
      if (!raw) return {};
      const parsed = JSON.parse(raw);
      return parsed && typeof parsed === 'object' ? parsed : {};
    } catch (_) {
      return {};
    }
  }

  function snapshotSiteEditorDefaults() {
    siteEditorTextDefaults.clear();
    siteEditorImageDefaults.clear();
    collectSiteEditorTextElements().forEach((element) => {
      const key = buildSiteEditorKey(element);
      if (!key || siteEditorTextDefaults.has(key)) return;
      siteEditorTextDefaults.set(key, element.innerHTML);
    });
    collectSiteEditorImageElements().forEach((element) => {
      const key = buildSiteEditorKey(element);
      if (!key || siteEditorImageDefaults.has(key)) return;
      siteEditorImageDefaults.set(key, String(element.getAttribute('src') || ''));
    });
  }

  function applySiteEditorPayload(payload = {}) {
    const safeTextMap = payload && typeof payload.textEdits === 'object' && payload.textEdits
      ? payload.textEdits
      : {};
    const safeImageMap = payload && typeof payload.imageEdits === 'object' && payload.imageEdits
      ? payload.imageEdits
      : {};

    collectSiteEditorTextElements().forEach((element) => {
      const key = buildSiteEditorKey(element);
      if (!key || !(key in safeTextMap)) return;
      element.innerHTML = sanitizeSiteEditableHtml(safeTextMap[key]);
    });

    collectSiteEditorImageElements().forEach((element) => {
      const key = buildSiteEditorKey(element);
      if (!key || !(key in safeImageMap)) return;
      const next = String(safeImageMap[key] || '').trim();
      if (next) element.setAttribute('src', next);
    });
  }

  function buildSiteEditorPayloadFromDom() {
    const textMap = {};
    const imageMap = {};
    collectSiteEditorTextElements().forEach((element) => {
      const key = buildSiteEditorKey(element);
      if (!key) return;
      const html = sanitizeSiteEditableHtml(element.innerHTML || '');
      const defaultHtml = siteEditorTextDefaults.get(key);
      if (defaultHtml !== undefined && html === defaultHtml) return;
      textMap[key] = html;
    });
    collectSiteEditorImageElements().forEach((element) => {
      const key = buildSiteEditorKey(element);
      if (!key) return;
      const src = String(element.getAttribute('src') || '').trim();
      const defaultSrc = String(siteEditorImageDefaults.get(key) || '').trim();
      if (defaultSrc && src === defaultSrc) return;
      if (src) imageMap[key] = src;
    });

    return {
      textEdits: textMap,
      imageEdits: imageMap,
    };
  }

  function cacheSiteEditorPayload(payload = {}) {
    const textEdits = payload && payload.textEdits && typeof payload.textEdits === 'object'
      ? payload.textEdits
      : {};
    const imageEdits = payload && payload.imageEdits && typeof payload.imageEdits === 'object'
      ? payload.imageEdits
      : {};
    localStorage.setItem(SITE_TEXT_EDITS_KEY, JSON.stringify(textEdits));
    localStorage.setItem(SITE_IMAGE_EDITS_KEY, JSON.stringify(imageEdits));
  }

  function loadCachedSiteEditorPayload() {
    return {
      textEdits: loadSiteEditorMap(SITE_TEXT_EDITS_KEY),
      imageEdits: loadSiteEditorMap(SITE_IMAGE_EDITS_KEY),
    };
  }

  function resetSiteEditorDomToDefaults() {
    collectSiteEditorTextElements().forEach((element) => {
      const key = buildSiteEditorKey(element);
      if (!key || !siteEditorTextDefaults.has(key)) return;
      element.innerHTML = String(siteEditorTextDefaults.get(key) || '');
    });
    collectSiteEditorImageElements().forEach((element) => {
      const key = buildSiteEditorKey(element);
      if (!key || !siteEditorImageDefaults.has(key)) return;
      element.setAttribute('src', String(siteEditorImageDefaults.get(key) || ''));
    });
  }

  function normalizeSiteEditorServerState(response) {
    const state = response && response.state ? response.state : { textEdits: {}, imageEdits: {} };
    const updatedAt = String((response && response.updatedAt) || '');
    return { state, updatedAt };
  }

  async function fetchSiteEditorPayloadFromServer() {
    const response = await apiRequest('/content/site-editor', { method: 'GET' });
    return normalizeSiteEditorServerState(response);
  }

  async function saveSiteEditorPayloadToServer(payload) {
    const response = await apiRequest('/content/site-editor', {
      method: 'PUT',
      body: JSON.stringify({
        state: payload || { textEdits: {}, imageEdits: {} },
        ifMatchUpdatedAt: siteEditorUpdatedAt || undefined,
      }),
    });
    return normalizeSiteEditorServerState(response);
  }

  async function resetSiteEditorPayloadOnServer() {
    const response = await apiRequest('/content/site-editor', { method: 'DELETE' });
    return normalizeSiteEditorServerState(response);
  }

  async function undoSiteEditorPayloadOnServer() {
    const response = await apiRequest('/content/site-editor/undo', {
      method: 'POST',
      body: JSON.stringify({}),
    });
    return normalizeSiteEditorServerState(response);
  }

  async function fetchSiteEditorHistoryFromServer(limit = 20) {
    const response = await apiRequest(`/content/site-editor/history?limit=${Math.max(1, Math.min(100, Number(limit) || 20))}`, {
      method: 'GET',
    });
    return Array.isArray(response && response.items) ? response.items : [];
  }

  async function restoreSiteEditorHistoryOnServer(historyId) {
    const response = await apiRequest('/content/site-editor/restore', {
      method: 'POST',
      body: JSON.stringify({ historyId: Number(historyId) || 0 }),
    });
    return normalizeSiteEditorServerState(response);
  }

  function formatSiteEditorHistoryLabel(item) {
    const id = Number(item?.id || 0);
    const action = String(item?.action || 'save');
    const createdAtRaw = String(item?.createdAt || '');
    const createdAt = createdAtRaw ? createdAtRaw.replace('T', ' ').slice(0, 16) : '-';
    const username = String(item?.createdByUsername || item?.createdBy || '-');
    return `#${id} ${action} ${createdAt} ${username}`;
  }

  async function refreshSiteEditorHistoryOptions() {
    const select = document.getElementById('site-edit-history-select');
    if (!select) return;
    const user = getCurrentUser();
    if (!canManageSiteEditor(user)) {
      select.innerHTML = '';
      return;
    }
    try {
      const items = await fetchSiteEditorHistoryFromServer(30);
      siteEditorHistoryItems = items;
      const options = [`<option value="">복원할 이력 선택</option>`];
      items.forEach((item) => {
        const value = Number(item?.id || 0);
        if (!value) return;
        options.push(`<option value="${value}">${formatSiteEditorHistoryLabel(item)}</option>`);
      });
      select.innerHTML = options.join('');
    } catch (_) {
      siteEditorHistoryItems = [];
      select.innerHTML = '<option value="">이력 조회 실패</option>';
    }
  }

  async function hydrateSiteEditorContent() {
    resetSiteEditorDomToDefaults();
    try {
      const serverData = await fetchSiteEditorPayloadFromServer();
      siteEditorUpdatedAt = serverData.updatedAt;
      applySiteEditorPayload(serverData.state);
      cacheSiteEditorPayload(serverData.state);
    } catch (_) {
      applySiteEditorPayload(loadCachedSiteEditorPayload());
    }
    renderAboutVolunteerPhoto();
  }

  function setSiteEditMode(active) {
    const user = getCurrentUser();
    if (active && !canManageSiteEditor(user)) {
      notifyMessage('권한이 없습니다.');
      return;
    }
    siteEditMode = !!active;
    document.body.classList.toggle('site-edit-mode', siteEditMode);
    collectSiteEditorTextElements().forEach((element) => {
      element.setAttribute('contenteditable', siteEditMode ? 'true' : 'false');
      element.classList.toggle('site-editable-text', siteEditMode);
      element.setAttribute('spellcheck', siteEditMode ? 'true' : 'false');
      element.setAttribute('role', siteEditMode ? 'textbox' : 'presentation');
      if (siteEditMode) {
        element.setAttribute('tabindex', '0');
        if (!element.getAttribute('aria-label')) {
          element.setAttribute('aria-label', '편집 가능한 텍스트 블록');
        }
      } else {
        element.removeAttribute('tabindex');
      }
    });
    collectSiteEditorImageElements().forEach((element) => {
      element.classList.toggle('site-editable-image', siteEditMode);
    });
    const toggleBtn = document.getElementById('site-edit-toggle-btn');
    if (toggleBtn) {
      toggleBtn.classList.toggle('btn-warning', siteEditMode);
      toggleBtn.classList.toggle('btn-outline-light', !siteEditMode);
      toggleBtn.textContent = siteEditMode ? '편집 종료' : '페이지 편집';
    }
  }

  function updateSiteEditorControls() {
    const user = getCurrentUser();
    const canManage = canManageSiteEditor(user);
    const toggleBtn = document.querySelector(siteEditorControls.toggleButton || '#site-edit-toggle-btn');
    const saveBtn = document.querySelector(siteEditorControls.saveButton || '#site-edit-save-btn');
    const undoBtn = document.querySelector(siteEditorControls.undoButton || '#site-edit-undo-btn');
    const historySelect = document.querySelector(siteEditorControls.historySelect || '#site-edit-history-select');
    const historyRestoreBtn = document.querySelector(siteEditorControls.historyRestoreButton || '#site-edit-history-restore-btn');
    const historyRefreshBtn = document.querySelector(siteEditorControls.historyRefreshButton || '#site-edit-history-refresh-btn');
    const resetBtn = document.querySelector(siteEditorControls.resetButton || '#site-edit-reset-btn');
    if (toggleBtn) toggleBtn.classList.toggle('d-none', !canManage);
    if (saveBtn) saveBtn.classList.toggle('d-none', !canManage);
    if (undoBtn) undoBtn.classList.toggle('d-none', !canManage);
    if (historySelect) historySelect.classList.toggle('d-none', !canManage);
    if (historyRestoreBtn) historyRestoreBtn.classList.toggle('d-none', !canManage);
    if (historyRefreshBtn) historyRefreshBtn.classList.toggle('d-none', !canManage);
    if (resetBtn) resetBtn.classList.toggle('d-none', !canManage);
    if (!canManage && siteEditMode) setSiteEditMode(false);
  }

  function initSiteEditorImageInput() {
    if (siteEditorImageInput) return siteEditorImageInput;
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = 'image/*';
    input.className = 'd-none';
    input.id = 'site-editor-image-input';
    input.addEventListener('change', (event) => {
      const file = event.target.files && event.target.files[0];
      if (!file || !siteEditorPendingImageKey) {
        event.target.value = '';
        return;
      }
      const applyDataUrl = (dataUrl) => {
        collectSiteEditorImageElements().forEach((imageEl) => {
          const key = buildSiteEditorKey(imageEl);
          if (key === siteEditorPendingImageKey) {
            imageEl.setAttribute('src', String(dataUrl || ''));
          }
        });
      };
      if (typeof readImageFileToDataUrl === 'function') {
        readImageFileToDataUrl(file, async (dataUrl) => {
          try {
            if (typeof resizeImageDataUrlToMaxBytes === 'function') {
              const optimized = await resizeImageDataUrlToMaxBytes(String(dataUrl || ''));
              applyDataUrl(optimized);
            } else {
              applyDataUrl(String(dataUrl || ''));
            }
          } catch (_) {
            applyDataUrl(String(dataUrl || ''));
          }
        });
      } else {
        const reader = new FileReader();
        reader.onload = () => applyDataUrl(String(reader.result || ''));
        reader.readAsDataURL(file);
      }
      event.target.value = '';
    });
    document.body.appendChild(input);
    siteEditorImageInput = input;
    return siteEditorImageInput;
  }

  function bindSiteEditorControls() {
    const toggleBtn = document.querySelector(siteEditorControls.toggleButton || '#site-edit-toggle-btn');
    const saveBtn = document.querySelector(siteEditorControls.saveButton || '#site-edit-save-btn');
    const undoBtn = document.querySelector(siteEditorControls.undoButton || '#site-edit-undo-btn');
    const historySelect = document.querySelector(siteEditorControls.historySelect || '#site-edit-history-select');
    const historyRestoreBtn = document.querySelector(siteEditorControls.historyRestoreButton || '#site-edit-history-restore-btn');
    const historyRefreshBtn = document.querySelector(siteEditorControls.historyRefreshButton || '#site-edit-history-refresh-btn');
    const resetBtn = document.querySelector(siteEditorControls.resetButton || '#site-edit-reset-btn');
    if (toggleBtn) {
      toggleBtn.addEventListener('click', () => {
        setSiteEditMode(!siteEditMode);
      });
    }
    if (saveBtn) {
      saveBtn.addEventListener('click', async () => {
        if (siteEditorSaveInFlight) return;
        const user = getCurrentUser();
        if (!canManageSiteEditor(user)) {
          notifyMessage('권한이 없습니다.');
          return;
        }
        try {
          siteEditorSaveInFlight = true;
          saveBtn.disabled = true;
          const payload = buildSiteEditorPayloadFromDom();
          const saved = await saveSiteEditorPayloadToServer(payload);
          siteEditorUpdatedAt = saved.updatedAt;
          resetSiteEditorDomToDefaults();
          applySiteEditorPayload(saved.state);
          cacheSiteEditorPayload(saved.state);
          await refreshSiteEditorHistoryOptions();
          notifyMessage('페이지 편집 내용이 저장되었습니다.');
        } catch (error) {
          const message = String(error?.message || '');
          if (/먼저 저장|409/.test(message)) {
            await hydrateSiteEditorContent();
            notifyMessage('다른 관리자가 먼저 저장했습니다. 최신 상태로 갱신했습니다.');
          } else {
            notifyMessage(error.message || '페이지 편집 저장에 실패했습니다.');
          }
        } finally {
          siteEditorSaveInFlight = false;
          saveBtn.disabled = false;
        }
      });
    }
    if (undoBtn) {
      undoBtn.addEventListener('click', async () => {
        const user = getCurrentUser();
        if (!canManageSiteEditor(user)) {
          notifyMessage('권한이 없습니다.');
          return;
        }
        try {
          const restored = await undoSiteEditorPayloadOnServer();
          siteEditorUpdatedAt = restored.updatedAt;
          resetSiteEditorDomToDefaults();
          applySiteEditorPayload(restored.state);
          cacheSiteEditorPayload(restored.state);
          await refreshSiteEditorHistoryOptions();
          notifyMessage('최근 수정 이력을 되돌렸습니다.');
        } catch (error) {
          notifyMessage(error.message || '되돌리기에 실패했습니다.');
        }
      });
    }
    if (historyRefreshBtn) {
      historyRefreshBtn.addEventListener('click', async () => {
        const user = getCurrentUser();
        if (!canManageSiteEditor(user)) {
          notifyMessage('권한이 없습니다.');
          return;
        }
        await refreshSiteEditorHistoryOptions();
        notifyMessage('수정 이력 목록을 새로고침했습니다.');
      });
    }
    if (historyRestoreBtn) {
      historyRestoreBtn.addEventListener('click', async () => {
        const user = getCurrentUser();
        if (!canManageSiteEditor(user)) {
          notifyMessage('권한이 없습니다.');
          return;
        }
        const historyId = Number(historySelect?.value || 0);
        if (!historyId) {
          notifyMessage('복원할 이력을 선택해주세요.');
          return;
        }
        try {
          const restored = await restoreSiteEditorHistoryOnServer(historyId);
          siteEditorUpdatedAt = restored.updatedAt;
          resetSiteEditorDomToDefaults();
          applySiteEditorPayload(restored.state);
          cacheSiteEditorPayload(restored.state);
          await refreshSiteEditorHistoryOptions();
          notifyMessage('선택한 수정 이력을 복원했습니다.');
        } catch (error) {
          notifyMessage(error.message || '이력 복원에 실패했습니다.');
        }
      });
    }
    if (resetBtn) {
      resetBtn.addEventListener('click', async () => {
        const user = getCurrentUser();
        if (!canManageSiteEditor(user)) {
          notifyMessage('권한이 없습니다.');
          return;
        }
        try {
          const resetState = await resetSiteEditorPayloadOnServer();
          siteEditorUpdatedAt = resetState.updatedAt;
          resetSiteEditorDomToDefaults();
          applySiteEditorPayload(resetState.state);
          cacheSiteEditorPayload(resetState.state);
          await refreshSiteEditorHistoryOptions();
          notifyMessage('페이지 편집 내용을 초기화했습니다.');
        } catch (error) {
          notifyMessage(error.message || '초기화에 실패했습니다.');
        }
      });
    }

    document.addEventListener('click', (event) => {
      if (!siteEditMode) return;
      const target = event.target;
      if (!(target instanceof HTMLElement)) return;
      const editableImage = target.closest('.site-editable-image');
      if (!editableImage) return;
      event.preventDefault();
      const key = buildSiteEditorKey(editableImage);
      if (!key) return;
      siteEditorPendingImageKey = key;
      const input = initSiteEditorImageInput();
      input.click();
    });
  }

  async function initSiteContentEditor() {
    snapshotSiteEditorDefaults();
    await hydrateSiteEditorContent();
    initSiteEditorImageInput();
    bindSiteEditorControls();
    updateSiteEditorControls();
    await refreshSiteEditorHistoryOptions();
  }

  function applyHomeHeroBackgroundData(dataUrl) {
    if (!dataUrl) return;
    try {
      saveHomeHeroConfig({ backgroundImage: dataUrl });
      renderHomeHeroConfig();
      notifyMessage('홈 배경 이미지가 변경되었습니다.');
    } catch (error) {
      notifyMessage('배경 이미지 저장에 실패했습니다.');
    }
  }

  function applyHomeHeroBackgroundFile(file) {
    if (!file) return;
    const user = getCurrentUser();
    if (!canManageHomeHero(user)) {
      notifyMessage('권한이 없습니다.');
      return;
    }
    const fallbackRead = () => {
      const reader = new FileReader();
      reader.onload = () => applyHomeHeroBackgroundData(String(reader.result || ''));
      reader.onerror = () => notifyMessage('이미지 파일을 읽지 못했습니다.');
      reader.readAsDataURL(file);
    };
    if (typeof readImageFileToDataUrl === 'function') {
      readImageFileToDataUrl(file, async (dataUrl) => {
        try {
          if (typeof resizeImageDataUrlToMaxBytes === 'function') {
            const optimized = await resizeImageDataUrlToMaxBytes(String(dataUrl || ''));
            applyHomeHeroBackgroundData(optimized);
            return;
          }
        } catch (_) {}
        applyHomeHeroBackgroundData(String(dataUrl || ''));
      });
      return;
    }
    fallbackRead();
  }

  function renderAboutVolunteerPhoto() {
    const img = document.getElementById('about-volunteer-image');
    if (!img) return;
    const picture = img.closest('picture');
    if (picture) {
      // Ensure dynamic uploaded image is not overridden by static <source srcset> candidates.
      picture.querySelectorAll('source').forEach((sourceEl) => sourceEl.removeAttribute('srcset'));
      img.removeAttribute('srcset');
      img.removeAttribute('sizes');
    }
    const stored = String(getAboutVolunteerPhoto() || '').trim();
    const safeSrc = stored && !/^(null|undefined|\[object\s+object\])$/i.test(stored)
      ? stored
      : DEFAULT_ABOUT_VOLUNTEER_PHOTO;
    img.src = safeSrc;
    img.onerror = () => {
      img.onerror = null;
      img.src = DEFAULT_ABOUT_VOLUNTEER_PHOTO;
      try {
        localStorage.removeItem(ABOUT_VOLUNTEER_PHOTO_KEY);
      } catch (_) {}
    };
  }

  function updateAboutPhotoAdminControls() {
    const tools = document.getElementById('about-photo-admin-tools');
    const user = getCurrentUser();
    const canManage = !!(user && user.status === 'active' && isStaffUser(user));
    if (tools) tools.classList.toggle('d-none', !canManage);
  }

