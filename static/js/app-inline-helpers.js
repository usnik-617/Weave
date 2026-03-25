function syncRouteStateSafeFromGlobals() {
  if (typeof syncNewsRouteState === 'function') {
    syncNewsRouteState();
    return;
  }
  if (typeof updateAppUrlState === 'function') {
    updateAppUrlState({
      panel: 'news',
      newsTab: currentNewsTab,
      q: newsSearchKeyword,
      page: String(newsCurrentPage)
    });
  }
}

function bindSearchControlsFromGlobals({ inputEl, buttonEl, onApply, onRender, routeSync }) {
  if (!inputEl || typeof onApply !== 'function' || typeof onRender !== 'function') return;
  const syncFn = typeof routeSync === 'function'
    ? routeSync
    : syncRouteStateSafeFromGlobals;
  const run = () => {
    onApply(String(inputEl.value || '').trim());
    onRender();
    syncFn();
  };
  if (buttonEl) buttonEl.addEventListener('click', run);
  inputEl.addEventListener('keydown', (event) => {
    if (event.key !== 'Enter') return;
    run();
  });
}

window.syncRouteStateSafeFromGlobals = syncRouteStateSafeFromGlobals;
window.bindSearchControlsFromGlobals = bindSearchControlsFromGlobals;

function initOpsDashboardBindingsFromGlobals() {
  if (window.__opsDashboardBindingsInitialized) return;
  window.__opsDashboardBindingsInitialized = true;

  const opsRefreshBtn = document.getElementById('ops-dashboard-refresh-btn');
  const opsTelemetryResetBtn = document.getElementById('ops-client-telemetry-reset-btn');
  const opsPendingSearchInput = document.getElementById('ops-pending-search');
  const opsPendingSearchBtn = document.getElementById('ops-pending-search-btn');
  const opsRoleSearchName = document.getElementById('ops-role-search-name');
  const opsRoleSearchPhone = document.getElementById('ops-role-search-phone');
  const opsRoleSearchBtn = document.getElementById('ops-role-search-btn');
  const opsBtn = document.getElementById('ops-dashboard-btn');

  if (opsRefreshBtn) {
    opsRefreshBtn.addEventListener('click', async () => {
      await loadOpsDashboard(opsPendingPage);
    });
  }

  if (opsTelemetryResetBtn) {
    opsTelemetryResetBtn.addEventListener('click', async () => {
      if (typeof resetClientTelemetry === 'function') {
        resetClientTelemetry();
      }
      await loadOpsDashboard(opsPendingPage);
      if (typeof notifyInfo === 'function') {
        notifyInfo('클라이언트 카운터를 초기화했습니다.');
      }
    });
  }

  if (opsPendingSearchBtn && opsPendingSearchInput) {
    const runSearch = async () => {
      opsPendingSearchKeyword = String(opsPendingSearchInput.value || '').trim();
      await loadOpsDashboard(1);
    };
    opsPendingSearchBtn.addEventListener('click', runSearch);
    opsPendingSearchInput.addEventListener('keydown', async (event) => {
      if (event.key !== 'Enter') return;
      await runSearch();
    });
  }

  document.querySelectorAll('[data-ops-sort]').forEach((btn) => {
    btn.addEventListener('click', async (event) => {
      event.preventDefault();
      const nextSortBy = String(btn.getAttribute('data-ops-sort') || 'id');
      if (opsPendingSortBy === nextSortBy) {
        opsPendingSortDir = opsPendingSortDir === 'asc' ? 'desc' : 'asc';
      } else {
        opsPendingSortBy = nextSortBy;
        opsPendingSortDir = 'asc';
      }
      await loadOpsDashboard(1);
    });
  });

  if (opsBtn) {
    opsBtn.addEventListener('click', async (event) => {
      event.preventDefault();
      movePanel('ops-dashboard');
      await loadOpsDashboard(1);
    });
  }
}

window.initOpsDashboardBindingsFromGlobals = initOpsDashboardBindingsFromGlobals;

function initWriteEntryBindingsFromGlobals() {
  if (window.__writeEntryBindingsInitialized) return;
  window.__writeEntryBindingsInitialized = true;

  const newsWriteBtn = document.getElementById('news-write-btn');
  const faqWriteBtn = document.getElementById('faq-write-btn');
  const qnaWriteBtn = document.getElementById('qna-write-btn');
  const galleryWriteBtn = document.getElementById('gallery-write-btn');
  const writeBackBtn = document.getElementById('write-back-btn');
  const galleryBackBtn = document.getElementById('gallery-back-btn');
  const opsRoleSearchName = document.getElementById('ops-role-search-name');
  const opsRoleSearchPhone = document.getElementById('ops-role-search-phone');
  const opsRoleSearchBtn = document.getElementById('ops-role-search-btn');

  if (newsWriteBtn) {
    newsWriteBtn.addEventListener('click', () => {
      const user = getCurrentUser();
      if (!user || user.status !== 'active' || !isStaffUser(user)) {
        notifyMessage('운영진/관리자(정식 단원)만 공지 작성이 가능합니다.');
        return;
      }
      resetWriteForms();
      const form = document.getElementById('add-news-form');
      form.editId.value = '';
      form.author.value = user.nickname || user.username || user.name;
      form.postTab.value = 'notice';
      form.isSecret.checked = false;
      updateVolunteerDateFieldVisibility(form);
      openWritePanel('news-admin');
    });
  }

  if (faqWriteBtn) {
    faqWriteBtn.addEventListener('click', () => {
      const user = getCurrentUser();
      if (!isAdminUser(user)) {
        notifyMessage('FAQ 작성은 관리자만 가능합니다.');
        return;
      }
      resetWriteForms();
      const form = document.getElementById('add-news-form');
      form.author.value = user.nickname || user.username || user.name;
      form.postTab.value = 'faq';
      form.isSecret.checked = false;
      updateVolunteerDateFieldVisibility(form);
      openWritePanel('news-admin');
    });
  }

  if (qnaWriteBtn) {
    qnaWriteBtn.addEventListener('click', () => {
      const user = getCurrentUser();
      if (!user || user.status !== 'active') {
        notifyMessage('정식 단원 승인 후 Q&A 작성이 가능합니다.');
        return;
      }
      resetWriteForms();
      const form = document.getElementById('add-news-form');
      form.author.value = user.nickname || user.username || user.name;
      form.postTab.value = 'qna';
      form.isSecret.checked = false;
      updateVolunteerDateFieldVisibility(form);
      openWritePanel('news-admin');
    });
  }

  if (galleryWriteBtn) {
    galleryWriteBtn.addEventListener('click', () => {
      const user = getCurrentUser();
      if (!user || user.status !== 'active' || !isStaffUser(user)) {
        notifyMessage('운영진/관리자(정식 단원)만 갤러리 업로드가 가능합니다.');
        return;
      }
      resetWriteForms();
      const form = document.getElementById('add-gallery-form');
      form.editId.value = '';
      ensureGalleryYearOptions();
      openWritePanel('gallery-admin');
    });
  }

  if (opsRoleSearchBtn && opsRoleSearchName && opsRoleSearchPhone) {
    const runRoleSearch = async () => {
      if (typeof searchOpsUsersByIdentity === 'function') {
        await searchOpsUsersByIdentity();
      }
    };
    opsRoleSearchBtn.addEventListener('click', runRoleSearch);
    [opsRoleSearchName, opsRoleSearchPhone].forEach((inputEl) => {
      inputEl.addEventListener('keydown', async (event) => {
        if (event.key !== 'Enter') return;
        await runRoleSearch();
      });
    });
  }

  if (writeBackBtn) {
    writeBackBtn.addEventListener('click', () => {
      document.querySelectorAll('[class*="panel"]').forEach((p) => p.classList.remove('panel-active'));
      document.getElementById('news').classList.add('panel-active');
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });
  }

  if (galleryBackBtn) {
    galleryBackBtn.addEventListener('click', () => {
      document.querySelectorAll('[class*="panel"]').forEach((p) => p.classList.remove('panel-active'));
      document.getElementById('gallery').classList.add('panel-active');
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });
  }
}

window.initWriteEntryBindingsFromGlobals = initWriteEntryBindingsFromGlobals;
