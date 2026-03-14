  // ============ MAIN NAVIGATION ============
  document.addEventListener('DOMContentLoaded', function() {
    const navLinks = document.querySelectorAll('[data-panel]');
    const statsSection = document.getElementById('home-stats');
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const offcanvasToggleBtn = document.querySelector('[data-bs-target="#mobileMenuDrawer"]');
    const mobileBreadcrumbEl = document.getElementById('mobile-menu-breadcrumb');
    const lastTriggerByModal = new Map();
    const expandedCellStateKey = 'weave.mobileExpandedCells';
    const panelLabelMap = {
      home: '홈',
      about: '소개',
      activities: '활동',
      gallery: '갤러리',
      news: '소식',
      join: '참여',
      myinfo: '내 정보',
      'ops-dashboard': '운영 대시보드'
    };
    const aboutTabLabelMap = {
      history: '연혁',
      executives: '임원진',
      logo: '로고',
      relatedsites: '관련사이트',
      rules: '규칙및규약',
      awards: '상장수여기준',
      fees: '회비'
    };
    const newsTabLabelMap = {
      notice: '공지사항',
      faq: 'FAQ',
      qna: 'Q&A'
    };
    const activitiesTabLabelMap = {
      overview: '활동소개',
      calendar: '캘린더'
    };
    let activeAboutTab = 'history';
    let activeNewsTab = 'notice';
    let activeActivitiesTab = 'overview';
    let skeletonStartAt = 0;
    let lastScrollY = 0;
    let navScrollTicking = false;

    const getExpandedState = () => {
      try {
        return JSON.parse(window.sessionStorage.getItem(expandedCellStateKey) || '{}');
      } catch (_error) {
        return {};
      }
    };

    const setExpandedState = (nextState) => {
      try {
        window.sessionStorage.setItem(expandedCellStateKey, JSON.stringify(nextState));
      } catch (_error) {
        // Ignore storage exceptions to keep navigation stable.
      }
    };

    function resolveCellKey(cell) {
      const row = cell.closest('tr');
      const parentTable = cell.closest('table');
      if (!(row instanceof HTMLElement)) return '';
      const tableId = String(parentTable?.id || 'table');
      const first = String(row.children[0]?.textContent || '').trim().slice(0, 32);
      const main = String(cell.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 84);
      return `${tableId}:${first}:${main}`;
    }

    function updateMobileBreadcrumb(panelId, subLabel) {
      if (!(mobileBreadcrumbEl instanceof HTMLElement)) return;
      const panelLabel = panelLabelMap[String(panelId || 'home')] || panelLabelMap.home;
      mobileBreadcrumbEl.textContent = subLabel ? `${panelLabel} / ${subLabel}` : panelLabel;
    }

    function scrollToTopByPreference() {
      window.scrollTo({ top: 0, behavior: prefersReducedMotion ? 'auto' : 'smooth' });
    }

    function setMainBackgroundInert(inertOn) {
      const rootTargets = [
        document.getElementById('main-content'),
        document.getElementById('navbar'),
        document.querySelector('footer')
      ].filter((el) => el instanceof HTMLElement);
      rootTargets.forEach((el) => {
        if (inertOn) {
          el.setAttribute('inert', '');
          el.setAttribute('aria-hidden', 'true');
        } else {
          el.removeAttribute('inert');
          el.removeAttribute('aria-hidden');
        }
      });
    }

    function refreshMobileBottomNavHeight() {
      const nav = document.getElementById('mobile-bottom-nav');
      if (!(nav instanceof HTMLElement)) return;
      if (window.matchMedia('(min-width: 769px)').matches) return;
      const rect = nav.getBoundingClientRect();
      const measured = Math.max(64, Math.round(rect.height || 0));
      document.documentElement.style.setProperty('--mobile-bottom-nav-height', `${measured}px`);
    }

    function readRouteState() {
      if (typeof readInitialAppUrlState === 'function') {
        const base = readInitialAppUrlState() || {};
        const aboutTab = new URL(window.location.href).searchParams.get('aboutTab') || '';
        return {
          panel: String(base.panel || ''),
          newsTab: String(base.newsTab || ''),
          aboutTab: String(aboutTab || '')
        };
      }
      const url = new URL(window.location.href);
      return {
        panel: String(url.searchParams.get('panel') || ''),
        newsTab: String(url.searchParams.get('newsTab') || ''),
        aboutTab: String(url.searchParams.get('aboutTab') || '')
      };
    }

    function syncRouteState(panelId, extras = {}, replaceOnly = false) {
      if (typeof updateAppUrlState === 'function') {
        updateAppUrlState({
          panel: panelId || 'home',
          newsTab: extras.newsTab || '',
          aboutTab: extras.aboutTab || ''
        });
      }
      syncHashForPanel(panelId, replaceOnly);
    }

    function syncHashForPanel(panelId, replace = false) {
      const normalized = String(panelId || '').trim();
      if (!normalized) return;
      const nextHash = `#${normalized}`;
      if (window.location.hash === nextHash) return;
      const nextUrl = `${window.location.pathname}${window.location.search}${nextHash}`;
      const statePayload = { panelId: normalized, scrollTop: window.scrollY || 0 };
      if (replace) {
        window.history.replaceState(statePayload, '', nextUrl);
      } else {
        window.history.pushState(statePayload, '', nextUrl);
      }
    }

    function syncHeaderCompactState() {
      const authButtons = document.getElementById('auth-buttons');
      const userProfile = document.getElementById('user-profile');
      const hasAuthUi = !!(
        (authButtons && getComputedStyle(authButtons).display !== 'none')
        || (userProfile && getComputedStyle(userProfile).display !== 'none')
      );
      document.body.classList.toggle('header-auth-compact', hasAuthUi);
    }

    function dispatchPanelChanged(panelId, extras = {}) {
      document.dispatchEvent(new CustomEvent('weave:panel-changed', {
        detail: {
          panel: String(panelId || 'home'),
          newsTab: String(extras.newsTab || activeNewsTab || ''),
          aboutTab: String(extras.aboutTab || activeAboutTab || '')
        }
      }));
    }

    function syncMobileMenuQuickActions() {
      const loginBtn = document.getElementById('mobile-menu-login-btn');
      const signupBtn = document.getElementById('mobile-menu-signup-btn');
      const myInfoLink = document.getElementById('mobile-menu-myinfo-link');
      if (!(loginBtn instanceof HTMLElement)) return;
      const isLoggedIn = !!getCurrentUser();
      if (myInfoLink instanceof HTMLElement) {
        myInfoLink.classList.toggle('d-none', !isLoggedIn);
      }
      if (isLoggedIn) {
        loginBtn.textContent = '내 정보';
        loginBtn.setAttribute('aria-label', '내 정보로 이동');
        loginBtn.classList.remove('btn-outline-primary');
        loginBtn.classList.add('btn-primary');
        if (signupBtn instanceof HTMLElement) signupBtn.classList.add('d-none');
      } else {
        loginBtn.textContent = '로그인';
        loginBtn.setAttribute('aria-label', '로그인 열기');
        loginBtn.classList.remove('btn-primary');
        loginBtn.classList.add('btn-outline-primary');
        if (signupBtn instanceof HTMLElement) signupBtn.classList.remove('d-none');
      }
    }

    function applyInitialSkeletons() {
      skeletonStartAt = Date.now();
      const galleryGrid = document.getElementById('gallery-grid');
      if (galleryGrid && !galleryGrid.children.length) {
        const cardCount = window.matchMedia('(max-width: 576px)').matches ? 2 : 3;
        const wrapper = document.createElement('div');
        wrapper.className = 'row g-3';
        wrapper.setAttribute('data-skeleton', 'gallery');
        for (let i = 0; i < cardCount; i += 1) {
          const col = document.createElement('div');
          col.className = 'col-12 col-sm-6 col-lg-4';
          col.innerHTML = '<div class="skeleton-block skeleton-card"></div>';
          wrapper.appendChild(col);
        }
        galleryGrid.appendChild(wrapper);
      }

      const tableCols = {
        'news-table-body': 5,
        'faq-table-body': 3,
        'qna-table-body': 3
      };
      Object.entries(tableCols).forEach(([id, colspan]) => {
        const tbody = document.getElementById(id);
        if (!(tbody instanceof HTMLElement)) return;
        if (tbody.children.length > 0) return;
        const row = document.createElement('tr');
        row.setAttribute('data-skeleton-row', '1');
        const cell = document.createElement('td');
        cell.colSpan = colspan;
        cell.innerHTML = '<span class="skeleton-line d-block"></span>';
        row.appendChild(cell);
        tbody.appendChild(row);
      });
    }

    function clearResolvedSkeletons() {
      const elapsed = Date.now() - skeletonStartAt;
      if (skeletonStartAt && elapsed < 300) {
        window.setTimeout(clearResolvedSkeletons, 300 - elapsed);
        return;
      }
      const galleryGrid = document.getElementById('gallery-grid');
      if (galleryGrid) {
        const hasRealGalleryChild = Array.from(galleryGrid.children).some((node) => node.getAttribute('data-skeleton') !== 'gallery');
        if (hasRealGalleryChild) {
          galleryGrid.querySelectorAll('[data-skeleton="gallery"]').forEach((node) => node.remove());
        }
      }

      ['news-table-body', 'faq-table-body', 'qna-table-body'].forEach((id) => {
        const tbody = document.getElementById(id);
        if (!(tbody instanceof HTMLElement)) return;
        const hasRealRow = Array.from(tbody.children).some((node) => node.getAttribute('data-skeleton-row') !== '1');
        if (hasRealRow) {
          tbody.querySelectorAll('[data-skeleton-row="1"]').forEach((node) => node.remove());
        }
      });
    }

    function updateOffcanvasActive(panelId) {
      document.querySelectorAll('#mobileMenuDrawer [data-offcanvas-link]').forEach((el) => {
        el.classList.remove('is-active');
        el.setAttribute('aria-current', 'false');
      });
      document.querySelectorAll('#mobileMenuDrawer button.list-group-item[data-bs-target]').forEach((el) => {
        el.classList.remove('is-active');
        el.setAttribute('aria-current', 'false');
      });
      const activeTopLevelItem = document.querySelector(`#mobileMenuDrawer [data-offcanvas-link="${panelId}"]:not([data-offcanvas-group])`);
      let activeLabel = String(activeTopLevelItem?.textContent || '').trim();
      const livePanel = document.querySelector('.panel-active')?.id || panelId;
      if (livePanel === 'news-detail' || livePanel === 'qna-detail') activeLabel = '상세 보기';
      if (livePanel === 'gallery-detail') activeLabel = '사진 상세';
      if (panelId === 'about') activeLabel = aboutTabLabelMap[activeAboutTab] || activeLabel;
      if (panelId === 'news') activeLabel = newsTabLabelMap[activeNewsTab] || activeLabel;
      if (panelId === 'activities') {
        const isCalendar = !document.getElementById('activities-calendar-pane')?.classList.contains('d-none');
        activeActivitiesTab = isCalendar ? 'calendar' : 'overview';
        activeLabel = activitiesTabLabelMap[activeActivitiesTab] || activeLabel;
      }
      if (activeTopLevelItem instanceof HTMLElement) {
        activeTopLevelItem.classList.add('is-active');
        activeTopLevelItem.setAttribute('aria-current', 'page');
      }
      const groupHeaderMap = {
        about: '#mobileMenuDrawer button[data-bs-target="#mobile-menu-about"]',
        news: '#mobileMenuDrawer button[data-bs-target="#mobile-menu-news"]',
        activities: '#mobileMenuDrawer button[data-bs-target="#mobile-menu-activities"]'
      };
      const activeGroupHeader = groupHeaderMap[panelId] ? document.querySelector(groupHeaderMap[panelId]) : null;
      if (activeGroupHeader instanceof HTMLElement) {
        activeGroupHeader.classList.add('is-active');
        activeGroupHeader.setAttribute('aria-current', 'page');
      }
      if (panelId === 'about') {
        const exact = document.querySelector(`#mobileMenuDrawer [data-offcanvas-group="about"][data-about-tab="${activeAboutTab}"]`);
        if (exact instanceof HTMLElement) {
          exact.classList.add('is-active');
          exact.setAttribute('aria-current', 'page');
        }
      }
      if (panelId === 'news') {
        const exact = document.querySelector(`#mobileMenuDrawer [data-offcanvas-group="news"][data-news-tab="${activeNewsTab}"]`);
        if (exact instanceof HTMLElement) {
          exact.classList.add('is-active');
          exact.setAttribute('aria-current', 'page');
        }
      }
      if (panelId === 'activities') {
        const exact = document.querySelector(`#mobileMenuDrawer [data-offcanvas-group="activities"][data-activities-tab="${activeActivitiesTab}"]`);
        if (exact instanceof HTMLElement) {
          exact.classList.add('is-active');
          exact.setAttribute('aria-current', 'page');
        }
      }
      updateMobileBreadcrumb(panelId, activeLabel && activeLabel !== panelLabelMap[panelId] ? activeLabel : '');

      const aboutExpanded = panelId === 'about';
      const newsExpanded = panelId === 'news';
      const activitiesExpanded = panelId === 'activities';
      const aboutCollapseEl = document.getElementById('mobile-menu-about');
      const newsCollapseEl = document.getElementById('mobile-menu-news');
      const activitiesCollapseEl = document.getElementById('mobile-menu-activities');
      if (aboutCollapseEl) {
        const collapse = bootstrap.Collapse.getOrCreateInstance(aboutCollapseEl, { toggle: false });
        if (aboutExpanded) collapse.show(); else collapse.hide();
      }
      if (newsCollapseEl) {
        const collapse = bootstrap.Collapse.getOrCreateInstance(newsCollapseEl, { toggle: false });
        if (newsExpanded) collapse.show(); else collapse.hide();
      }
      if (activitiesCollapseEl) {
        const collapse = bootstrap.Collapse.getOrCreateInstance(activitiesCollapseEl, { toggle: false });
        if (activitiesExpanded) collapse.show(); else collapse.hide();
      }
    }

    function applyResponsiveTableLabels() {
      const tableLabelMap = {
        'news-table': ['title', 'author', 'date', 'views', 'likes'],
        'faq-table': ['question', 'author', 'date'],
        'qna-table': ['question', 'author', 'date']
      };
      document.querySelectorAll('table').forEach((table) => {
        const headerCells = Array.from(table.querySelectorAll('thead th'));
        if (!headerCells.length) return;
        const labels = headerCells.map((th) => String(th.textContent || '').trim());
        const keyMap = tableLabelMap[String(table.id || '')] || [];
        table.querySelectorAll('tbody tr').forEach((row) => {
          Array.from(row.children).forEach((cell, idx) => {
            if (!(cell instanceof HTMLElement)) return;
            const label = labels[idx] || '';
            const colKey = keyMap[idx] || `col-${idx + 1}`;
            cell.setAttribute('data-col-key', colKey);
            const normalizedLabel = String(label || '').replace(/\s+/g, ' ').trim();
            const fallbackLabelMap = {
              number: '번호',
              title: '글제목',
              question: '질문',
              author: '작성자',
              date: '날짜',
              views: '조회',
              likes: '추천',
              status: '상태',
              manage: '관리'
            };
            cell.setAttribute('data-label', normalizedLabel || fallbackLabelMap[colKey] || '항목');

            const expandable = colKey === 'title' || colKey === 'question';
            if (expandable && String(cell.textContent || '').trim().length > 42) {
              const cellKey = resolveCellKey(cell);
              const expandedState = getExpandedState();
              if (cellKey && expandedState[cellKey]) {
                cell.classList.add('is-expanded');
              }
              let toggle = cell.querySelector('.mobile-cell-expand-btn');
              if (!toggle) {
                toggle = document.createElement('button');
                toggle.type = 'button';
                toggle.className = 'btn btn-sm btn-outline-secondary mobile-cell-expand-btn ms-2';
                toggle.textContent = cell.classList.contains('is-expanded') ? '접기' : '더보기';
                toggle.addEventListener('click', (event) => {
                  event.preventDefault();
                  const expanded = cell.classList.toggle('is-expanded');
                  toggle.textContent = expanded ? '접기' : '더보기';
                  if (cellKey) {
                    const nextState = getExpandedState();
                    if (expanded) nextState[cellKey] = 1;
                    else delete nextState[cellKey];
                    setExpandedState(nextState);
                  }
                });
                cell.appendChild(toggle);
              }
            }
          });
        });
      });
    }

    function handleOrientationRefresh() {
      applyInitialSkeletons();
      applyResponsiveTableLabels();
      clearResolvedSkeletons();
      syncHeaderCompactState();
      refreshMobileBottomNavHeight();
      const activePanel = document.querySelector('.panel-active')?.id || 'home';
      updateOffcanvasActive(resolveNavPanelId(activePanel));
    }

    function syncMobileNavByScroll() {
      navScrollTicking = false;
      if (window.matchMedia('(min-width: 769px)').matches || prefersReducedMotion) {
        document.body.classList.remove('scroll-down-hide-nav');
        lastScrollY = window.scrollY || 0;
        return;
      }
      const currentY = window.scrollY || 0;
      const delta = currentY - lastScrollY;
      const closeToTop = currentY < 72;
      const hasKeyboard = document.body.classList.contains('keyboard-open');
      if (hasKeyboard || closeToTop || delta < -6) {
        document.body.classList.remove('scroll-down-hide-nav');
      } else if (delta > 8) {
        document.body.classList.add('scroll-down-hide-nav');
      }
      lastScrollY = currentY;
    }

    function queueMobileNavScrollSync() {
      if (navScrollTicking) return;
      navScrollTicking = true;
      window.requestAnimationFrame(syncMobileNavByScroll);
    }

    applyResponsiveTableLabels();
    applyInitialSkeletons();
    clearResolvedSkeletons();
    const tableObserver = new MutationObserver(() => {
      applyResponsiveTableLabels();
      clearResolvedSkeletons();
    });
    ['news-table-body', 'faq-table-body', 'qna-table-body', 'ops-pending-users-body'].forEach((id) => {
      const target = document.getElementById(id);
      if (target) tableObserver.observe(target, { childList: true, subtree: true });
    });
    document.addEventListener('weave:table-refresh', () => {
      applyResponsiveTableLabels();
      clearResolvedSkeletons();
    });

    [
      ['notice-tab-btn', 'notice'],
      ['faq-tab-btn', 'faq'],
      ['qna-tab-btn', 'qna']
    ].forEach(([id, tab]) => {
      const btn = document.getElementById(id);
      if (!btn) return;
      btn.addEventListener('click', () => {
        activeNewsTab = tab;
        const currentPanel = document.querySelector('.panel-active')?.id || '';
        if (currentPanel === 'news') {
          updateOffcanvasActive('news');
          syncRouteState('news', { newsTab: activeNewsTab });
        }
      });
    });

    function syncHomeStats(panelId) {
      if (!statsSection) return;
      statsSection.style.display = panelId === 'home' ? 'block' : 'none';
      document.body.classList.toggle('panel-home-active', panelId === 'home');
      const homeCalendarPreview = document.getElementById('home-calendar-preview');
      const homeNoticeCarousel = document.getElementById('home-notice-carousel');
      if (homeCalendarPreview) {
        homeCalendarPreview.style.display = panelId === 'home' ? 'block' : 'none';
      }
      if (homeNoticeCarousel) {
        homeNoticeCarousel.style.display = panelId === 'home' && getHomeNoticeItems().length ? 'block' : 'none';
      }
    }
    
    navLinks.forEach(link => {
      link.addEventListener('click', (e) => {
        e.preventDefault();
        const panelId = String(link.dataset.panel || '').trim();
        if (!panelId) return;
        const target = document.getElementById(panelId);
        const alreadyActivePanel = !!(target && target.classList.contains('panel-active'));
        const alreadyActiveLink = link.classList.contains('active');

        if (alreadyActivePanel && alreadyActiveLink && panelId !== 'news') {
          scrollToTopByPreference();
          setActiveNavStates(panelId);
          updateOffcanvasActive(panelId);
          syncRouteState(panelId, { newsTab: panelId === 'news' ? activeNewsTab : '', aboutTab: panelId === 'about' ? activeAboutTab : '' });
          dispatchPanelChanged(panelId);
          return;
        }
        
        document.querySelectorAll('[class*="panel"]').forEach(p => {
          p.classList.remove('panel-active');
        });
        if (target) {
          target.classList.add('panel-active');
          if (panelId === 'about') {
            showHistory();
          }
          if (panelId === 'activities') {
            openActivitiesOverviewTab();
          }
          if (panelId === 'ops-dashboard') {
            loadOpsDashboard().catch(() => {});
          }
          syncHomeStats(panelId);
          scrollToTopByPreference();
        }
        
        navLinks.forEach(l => l.classList.remove('active'));
        link.classList.add('active');
        setActiveNavStates(panelId);
        updateOffcanvasActive(panelId);
        syncRouteState(panelId, { newsTab: panelId === 'news' ? activeNewsTab : '', aboutTab: panelId === 'about' ? activeAboutTab : '' });
        dispatchPanelChanged(panelId);
      });
    });

    const sessionLoginBtn = document.getElementById('session-expired-login-btn');
    const sessionCancelBtn = document.getElementById('session-expired-cancel-btn');
    if (sessionLoginBtn) {
      sessionLoginBtn.addEventListener('click', () => {
        const sessionModal = bootstrap.Modal.getInstance(document.getElementById('sessionExpiredModal'));
        if (sessionModal) sessionModal.hide();
        const loginModalEl = document.getElementById('loginModal');
        if (loginModalEl) {
          const loginModal = bootstrap.Modal.getInstance(loginModalEl) || new bootstrap.Modal(loginModalEl);
          loginModal.show();
        }
      });
    }
    if (sessionCancelBtn) {
      sessionCancelBtn.addEventListener('click', () => {
        SESSION_EXPIRED_SHOWN = false;
      });
    }
    const sessionModalEl = document.getElementById('sessionExpiredModal');
    if (sessionModalEl) {
      sessionModalEl.addEventListener('hidden.bs.modal', () => {
        SESSION_EXPIRED_SHOWN = false;
      });
    }

    document.querySelectorAll('#mobile-bottom-nav .mobile-tab').forEach((tabBtn) => {
      tabBtn.addEventListener('click', async () => {
        const mobileAction = tabBtn.dataset.mobileAction;
        if (mobileAction === 'open-menu') {
          const drawerEl = document.getElementById('mobileMenuDrawer');
          if (drawerEl) {
            const drawer = bootstrap.Offcanvas.getInstance(drawerEl) || new bootstrap.Offcanvas(drawerEl);
            drawer.show();
          }
          return;
        }
        const panelId = tabBtn.dataset.panel;
        if (!panelId) return;
        const currentPanel = document.querySelector('.panel-active')?.id || '';
        if (currentPanel === panelId && panelId !== 'news') {
          updateOffcanvasActive(panelId);
          scrollToTopByPreference();
          syncRouteState(panelId, { newsTab: panelId === 'news' ? activeNewsTab : '', aboutTab: panelId === 'about' ? activeAboutTab : '' });
          dispatchPanelChanged(panelId);
          return;
        }
        if (currentPanel === 'news' && panelId === 'news') {
          const tabType = tabBtn.dataset.newsTab || 'notice';
          activateNewsTab(tabType);
          activeNewsTab = tabType;
          scrollToTopByPreference();
          updateOffcanvasActive(panelId);
          syncRouteState(panelId, { newsTab: tabType });
          dispatchPanelChanged(panelId, { newsTab: tabType });
          return;
        }
        if (panelId === 'myinfo' && !getCurrentUser()) {
          const loginModalEl = document.getElementById('loginModal');
          if (loginModalEl) {
            const loginModal = bootstrap.Modal.getInstance(loginModalEl) || new bootstrap.Modal(loginModalEl);
            loginModal.show();
          }
          return;
        }
        movePanel(panelId);
        if (panelId === 'news') {
          const tabType = tabBtn.dataset.newsTab || 'notice';
          activateNewsTab(tabType);
          activeNewsTab = tabType;
        }
        if (panelId === 'activities') {
          openActivitiesOverviewTab();
          await loadVolunteerEvents().catch(() => {});
        }
        updateOffcanvasActive(panelId);
        syncRouteState(panelId, { newsTab: panelId === 'news' ? activeNewsTab : '', aboutTab: panelId === 'about' ? activeAboutTab : '' });
        dispatchPanelChanged(panelId);
      });
    });

    document.getElementById('home')?.classList.add('panel-active');
    setActiveNavStates('home');
    syncHomeStats('home');
    updateOffcanvasActive('home');
    syncMobileMenuQuickActions();
    syncHeaderCompactState();

    const initialState = readRouteState();
    if (initialState.newsTab && newsTabLabelMap[initialState.newsTab]) {
      activeNewsTab = initialState.newsTab;
    }
    if (initialState.aboutTab && aboutTabLabelMap[initialState.aboutTab]) {
      activeAboutTab = initialState.aboutTab;
    }
    const initialHashPanel = String(window.location.hash || '').replace('#', '').trim();
    const initialPanel = initialHashPanel || initialState.panel;
    let bootstrapPanel = 'home';
    if (initialPanel && panelLabelMap[initialPanel] && initialPanel !== 'home') {
      movePanel(initialPanel);
      setActiveNavStates(initialPanel);
      if (initialPanel === 'news') activateNewsTab(activeNewsTab);
      if (initialPanel === 'about') {
        if (activeAboutTab === 'executives') showExecutives();
        else if (activeAboutTab === 'logo') showLogo();
        else if (activeAboutTab === 'relatedsites') showRelatedSites();
        else if (activeAboutTab === 'awards') showAwards();
        else if (activeAboutTab === 'rules') showRules();
        else if (activeAboutTab === 'fees') showFees();
        else showHistory();
      }
      updateOffcanvasActive(initialPanel);
      bootstrapPanel = initialPanel;
    }
    syncRouteState(bootstrapPanel, {
      newsTab: bootstrapPanel === 'news' ? activeNewsTab : '',
      aboutTab: bootstrapPanel === 'about' ? activeAboutTab : ''
    }, true);
    dispatchPanelChanged(bootstrapPanel, {
      newsTab: activeNewsTab,
      aboutTab: activeAboutTab
    });

    window.addEventListener('popstate', (event) => {
      const panelFromHash = String(window.location.hash || '').replace('#', '').trim();
      const state = readRouteState();
      const panel = panelFromHash || state.panel;
      if (!panel || !panelLabelMap[panel]) return;
      if (state.newsTab && newsTabLabelMap[state.newsTab]) activeNewsTab = state.newsTab;
      if (state.aboutTab && aboutTabLabelMap[state.aboutTab]) activeAboutTab = state.aboutTab;
      movePanel(panel);
      setActiveNavStates(panel);
      if (panel === 'news') activateNewsTab(activeNewsTab);
      if (panel === 'about') {
        if (activeAboutTab === 'executives') showExecutives();
        else if (activeAboutTab === 'logo') showLogo();
        else if (activeAboutTab === 'relatedsites') showRelatedSites();
        else if (activeAboutTab === 'awards') showAwards();
        else if (activeAboutTab === 'rules') showRules();
        else if (activeAboutTab === 'fees') showFees();
        else showHistory();
      }
      updateOffcanvasActive(panel);
      const restoreTop = Number(event?.state?.scrollTop || 0);
      window.scrollTo(0, Math.max(0, restoreTop));
      dispatchPanelChanged(panel);
    });

    if ('scrollRestoration' in history) {
      history.scrollRestoration = 'manual';
    }

    window.addEventListener('orientationchange', () => {
      window.setTimeout(handleOrientationRefresh, 120);
    });
    window.addEventListener('scroll', queueMobileNavScrollSync, { passive: true });
    window.addEventListener('resize', queueMobileNavScrollSync, { passive: true });
    document.addEventListener('weave:panel-changed', () => {
      document.body.classList.remove('scroll-down-hide-nav');
      lastScrollY = window.scrollY || 0;
    });
    syncMobileNavByScroll();

    const mobileMenuLoginBtn = document.getElementById('mobile-menu-login-btn');
    const mobileMenuSignupBtn = document.getElementById('mobile-menu-signup-btn');
    if (mobileMenuLoginBtn) {
      mobileMenuLoginBtn.addEventListener('click', (e) => {
        e.preventDefault();
        const drawerEl = document.getElementById('mobileMenuDrawer');
        const drawer = drawerEl ? bootstrap.Offcanvas.getInstance(drawerEl) : null;
        if (getCurrentUser()) {
          movePanel('myinfo');
          setActiveNavStates('myinfo');
          updateOffcanvasActive('myinfo');
          if (drawer) drawer.hide();
          return;
        }
        const loginModalEl = document.getElementById('loginModal');
        if (loginModalEl) {
          if (drawer) drawer.hide();
          const loginModal = bootstrap.Modal.getInstance(loginModalEl) || new bootstrap.Modal(loginModalEl);
          loginModal.show();
        }
      });
    }
    if (mobileMenuSignupBtn) {
      mobileMenuSignupBtn.addEventListener('click', (e) => {
        e.preventDefault();
        if (getCurrentUser()) return;
        const drawerEl = document.getElementById('mobileMenuDrawer');
        const drawer = drawerEl ? bootstrap.Offcanvas.getInstance(drawerEl) : null;
        const signupModalEl = document.getElementById('signupModal');
        if (signupModalEl) {
          if (drawer) drawer.hide();
          const signupModal = bootstrap.Modal.getInstance(signupModalEl) || new bootstrap.Modal(signupModalEl);
          signupModal.show();
        }
      });
    }
    // About sub-tab handling
    const btnLogo = document.getElementById('btn-logo');
    const btnAwards = document.getElementById('btn-awards');
    const btnRules = document.getElementById('btn-rules');
    const btnHistory = document.getElementById('btn-history');
    const btnExecutives = document.getElementById('btn-executives');
    const btnRelatedSites = document.getElementById('btn-relatedsites');
    const btnFees = document.getElementById('btn-fees');
    const logoPanel = document.getElementById('logo-panel');
    const executivesPanel = document.getElementById('executives-panel');
    const relatedSitesPanel = document.getElementById('relatedsites-panel');
    const awardsPanel = document.getElementById('awards-panel');
    const rulesPanel = document.getElementById('rules-panel');
    const historyPanel = document.getElementById('history-panel');
    const feesPanel = document.getElementById('fees-panel');

    function hideAllAbout() {
      [logoPanel, executivesPanel, relatedSitesPanel, awardsPanel, rulesPanel, historyPanel, feesPanel].forEach(p => p && p.classList.add('d-none'));
      [btnLogo, btnExecutives, btnRelatedSites, btnAwards, btnRules, btnHistory, btnFees].forEach(b => b && b.classList.remove('active'));
    }

    function showLogo() {
      hideAllAbout();
      logoPanel?.classList.remove('d-none');
      btnLogo?.classList.add('active');
    }

    function showAwards() {
      hideAllAbout();
      awardsPanel?.classList.remove('d-none');
      btnAwards?.classList.add('active');
    }

    function showRelatedSites() {
      hideAllAbout();
      relatedSitesPanel?.classList.remove('d-none');
      btnRelatedSites?.classList.add('active');
    }

    function showRules() {
      hideAllAbout();
      rulesPanel?.classList.remove('d-none');
      btnRules?.classList.add('active');
    }

    function showHistory() {
      hideAllAbout();
      historyPanel?.classList.remove('d-none');
      btnHistory?.classList.add('active');
    }

    function showExecutives() {
      hideAllAbout();
      executivesPanel?.classList.remove('d-none');
      btnExecutives?.classList.add('active');
      if (typeof renderExecutives === 'function') renderExecutives();
    }

    function showFees() {
      hideAllAbout();
      feesPanel?.classList.remove('d-none');
      btnFees?.classList.add('active');
    }

    if (btnLogo) btnLogo.addEventListener('click', showLogo);
    if (btnExecutives) btnExecutives.addEventListener('click', showExecutives);
    if (btnRelatedSites) btnRelatedSites.addEventListener('click', showRelatedSites);
    if (btnAwards) btnAwards.addEventListener('click', showAwards);
    if (btnRules) btnRules.addEventListener('click', showRules);
    if (btnHistory) btnHistory.addEventListener('click', showHistory);
    if (btnFees) btnFees.addEventListener('click', showFees);
    // 기본 패널은 연혁
    if (historyPanel && btnHistory) showHistory();

    const routeAfterAboutInit = readRouteState();
    if ((document.querySelector('.panel-active')?.id || '') === 'about') {
      const tab = String(routeAfterAboutInit.aboutTab || activeAboutTab || 'history');
      activeAboutTab = tab;
      if (tab === 'executives') showExecutives();
      else if (tab === 'logo') showLogo();
      else if (tab === 'relatedsites') showRelatedSites();
      else if (tab === 'awards') showAwards();
      else if (tab === 'rules') showRules();
      else if (tab === 'fees') showFees();
      else showHistory();
      updateOffcanvasActive('about');
    }

    document.querySelectorAll('[data-about-tab]').forEach(item => {
      item.addEventListener('click', (e) => {
        e.preventDefault();
        const tab = String(item.dataset.aboutTab || 'history');
        document.querySelectorAll('[class*="panel"]').forEach(p => p.classList.remove('panel-active'));
        document.getElementById('about')?.classList.add('panel-active');
        syncHomeStats('about');
        if (tab === 'logo') showLogo();
        else if (tab === 'executives') showExecutives();
        else if (tab === 'relatedsites') showRelatedSites();
        else if (tab === 'awards') showAwards();
        else if (tab === 'rules') showRules();
        else if (tab === 'fees') showFees();
        else showHistory();
        activeAboutTab = aboutTabLabelMap[tab] ? tab : 'history';
        const drawerEl = document.getElementById('mobileMenuDrawer');
        const drawer = drawerEl ? bootstrap.Offcanvas.getInstance(drawerEl) : null;
        if (drawer) drawer.hide();
        updateOffcanvasActive('about');
        syncRouteState('about', { aboutTab: activeAboutTab });
      });
    });

    document.querySelectorAll('[data-gallery-filter]').forEach(item => {
      item.addEventListener('click', (e) => {
        e.preventDefault();
        document.querySelectorAll('[class*="panel"]').forEach(p => p.classList.remove('panel-active'));
        document.getElementById('gallery')?.classList.add('panel-active');
        syncHomeStats('gallery');
        galleryCurrentFilter = item.dataset.galleryFilter;
        galleryCurrentPage = 1;
        renderGallery();
        const drawerEl = document.getElementById('mobileMenuDrawer');
        const drawer = drawerEl ? bootstrap.Offcanvas.getInstance(drawerEl) : null;
        if (drawer) drawer.hide();
        updateOffcanvasActive('gallery');
      });
    });

    document.querySelectorAll('[data-news-tab]').forEach(item => {
      item.addEventListener('click', (e) => {
        e.preventDefault();
        document.querySelectorAll('[class*="panel"]').forEach(p => p.classList.remove('panel-active'));
        document.getElementById('news')?.classList.add('panel-active');
        syncHomeStats('news');
        if (item.dataset.newsTab === 'faq') {
          const faqTabBtn = document.getElementById('faq-tab-btn');
          if (faqTabBtn instanceof HTMLElement) faqTabBtn.click();
          activeNewsTab = 'faq';
        } else if (item.dataset.newsTab === 'qna') {
          const qnaTabBtn = document.getElementById('qna-tab-btn');
          if (qnaTabBtn) qnaTabBtn.click();
          activeNewsTab = 'qna';
        } else {
          const noticeTabBtn = document.getElementById('notice-tab-btn');
          if (noticeTabBtn instanceof HTMLElement) noticeTabBtn.click();
          activeNewsTab = 'notice';
        }
        const drawerEl = document.getElementById('mobileMenuDrawer');
        const drawer = drawerEl ? bootstrap.Offcanvas.getInstance(drawerEl) : null;
        if (drawer) drawer.hide();
        updateOffcanvasActive('news');
        syncRouteState('news', { newsTab: activeNewsTab });
      });
    });

    [
      ['activities-overview-tab-btn', 'overview'],
      ['activities-calendar-tab-btn', 'calendar']
    ].forEach(([id, tab]) => {
      const btn = document.getElementById(id);
      if (!btn) return;
      btn.addEventListener('click', () => {
        activeActivitiesTab = tab;
        const currentPanel = document.querySelector('.panel-active')?.id || '';
        if (currentPanel === 'activities') {
          updateOffcanvasActive('activities');
          syncRouteState('activities');
        }
      });
    });

    document.querySelectorAll('[data-activities-tab]').forEach(item => {
      item.addEventListener('click', async (e) => {
        e.preventDefault();
        const targetTab = String(item.dataset.activitiesTab || 'overview');
        document.querySelectorAll('[class*="panel"]').forEach(p => p.classList.remove('panel-active'));
        document.getElementById('activities')?.classList.add('panel-active');
        syncHomeStats('activities');
        if (targetTab === 'calendar') {
          activeActivitiesTab = 'calendar';
          openActivitiesCalendarTab();
          await loadActivitiesCalendar().catch(() => {});
        } else {
          activeActivitiesTab = 'overview';
          openActivitiesOverviewTab();
        }
        const drawerEl = document.getElementById('mobileMenuDrawer');
        const drawer = drawerEl ? bootstrap.Offcanvas.getInstance(drawerEl) : null;
        if (drawer) drawer.hide();
        updateOffcanvasActive('activities');
        syncRouteState('activities');
      });
    });

    document.querySelectorAll('#mobileMenuDrawer [data-panel], #mobileMenuDrawer [data-about-tab], #mobileMenuDrawer [data-news-tab], #mobileMenuDrawer [data-activities-tab]').forEach((item) => {
      item.addEventListener('click', () => {
        const drawerEl = document.getElementById('mobileMenuDrawer');
        const drawer = drawerEl ? bootstrap.Offcanvas.getInstance(drawerEl) : null;
        if (drawer) drawer.hide();
      });
    });

    const drawerEl = document.getElementById('mobileMenuDrawer');
    if (drawerEl) {
      drawerEl.addEventListener('shown.bs.offcanvas', () => {
        setMainBackgroundInert(true);
        syncMobileMenuQuickActions();
        syncHeaderCompactState();
        refreshMobileBottomNavHeight();
        const active = drawerEl.querySelector('[data-offcanvas-link].is-active');
        const firstLink = drawerEl.querySelector('[data-offcanvas-link]');
        const target = active || firstLink;
        if (target instanceof HTMLElement) target.focus();
      });
      drawerEl.addEventListener('hidden.bs.offcanvas', () => {
        setMainBackgroundInert(false);
        if (offcanvasToggleBtn instanceof HTMLElement) {
          offcanvasToggleBtn.focus();
        }
      });
    }

    if ('ResizeObserver' in window) {
      const nav = document.getElementById('mobile-bottom-nav');
      if (nav instanceof HTMLElement) {
        const navResizeObserver = new ResizeObserver(() => {
          refreshMobileBottomNavHeight();
        });
        navResizeObserver.observe(nav);
      }
    }
    refreshMobileBottomNavHeight();

    document.querySelectorAll('.modal').forEach((modalEl) => {
      modalEl.addEventListener('show.bs.modal', () => {
        const active = document.activeElement;
        if (active instanceof HTMLElement) {
          lastTriggerByModal.set(modalEl.id, active);
        }
      });
      modalEl.addEventListener('hidden.bs.modal', () => {
        const previous = lastTriggerByModal.get(modalEl.id);
        if (previous instanceof HTMLElement) {
          window.setTimeout(() => previous.focus(), 0);
        }
      });
    });

    document.addEventListener('weave:user-state-changed', () => {
      syncMobileMenuQuickActions();
      syncHeaderCompactState();
    });

    document.addEventListener('weave:panel-changed', (event) => {
      const panel = String(event?.detail?.panel || '');
      if (panel === 'join' && typeof setJoinActionPanel === 'function') {
        setJoinActionPanel('honor');
      }
      if (panel === 'myinfo' && typeof markCurrentUserNotificationsRead === 'function') {
        markCurrentUserNotificationsRead();
      }
      if (panel === 'myinfo' && typeof renderMyNotifications === 'function') {
        renderMyNotifications();
      }
      if (panel === 'myinfo' && typeof renderMyActivitySummary === 'function') {
        renderMyActivitySummary();
      }
    });

    ['logout-btn-profile', 'session-expired-login-btn', 'session-expired-cancel-btn'].forEach((id) => {
      const el = document.getElementById(id);
      if (el) {
        el.addEventListener('click', () => {
          window.setTimeout(() => {
            syncMobileMenuQuickActions();
            syncHeaderCompactState();
          }, 80);
        });
      }
    });

    window.addEventListener('focus', () => {
      syncMobileMenuQuickActions();
      syncHeaderCompactState();
    });

    document.addEventListener('visibilitychange', () => {
      if (!document.hidden) {
        syncMobileMenuQuickActions();
        syncHeaderCompactState();
      }
    });
  });

  // ============ GALLERY FILTERING ============
  document.addEventListener('DOMContentLoaded', function() {
    const filterBtns = document.querySelectorAll('.gallery-filter button');
    filterBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        filterBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        galleryCurrentFilter = btn.dataset.filter;
        galleryCurrentPage = 1;
        renderGallery();
      });
    });
  });

  // ============ SCROLL EFFECT ============
  window.addEventListener('scroll', () => {
    const header = document.querySelector('.site-header');
    if (header instanceof HTMLElement) header.classList.toggle('scrolled', window.scrollY > 50);
  });
