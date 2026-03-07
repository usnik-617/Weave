  // ============ MAIN NAVIGATION ============
  document.addEventListener('DOMContentLoaded', function() {
    const navLinks = document.querySelectorAll('[data-panel]');
    const statsSection = document.getElementById('home-stats');

    function syncHomeStats(panelId) {
      if (!statsSection) return;
      statsSection.style.display = panelId === 'home' ? 'block' : 'none';
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
        const panelId = link.dataset.panel;
        
        document.querySelectorAll('[class*="panel"]').forEach(p => {
          p.classList.remove('panel-active');
        });
        const target = document.getElementById(panelId);
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
          window.scrollTo({ top: 0, behavior: 'smooth' });
        }
        
        navLinks.forEach(l => l.classList.remove('active'));
        link.classList.add('active');
        setActiveNavStates(panelId);
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
        const panelId = tabBtn.dataset.panel;
        if (!panelId) return;
        movePanel(panelId);
        if (panelId === 'news') {
          const tabType = tabBtn.dataset.newsTab || 'notice';
          activateNewsTab(tabType);
        }
        if (panelId === 'activities') {
          openActivitiesOverviewTab();
          await loadVolunteerEvents().catch(() => {});
        }
        if (panelId === 'myinfo' && !getCurrentUser()) {
          const loginModalEl = document.getElementById('loginModal');
          if (loginModalEl) {
            const loginModal = bootstrap.Modal.getInstance(loginModalEl) || new bootstrap.Modal(loginModalEl);
            loginModal.show();
          }
        }
      });
    });

    document.getElementById('home').classList.add('panel-active');
    setActiveNavStates('home');
    syncHomeStats('home');
    // About sub-tab handling
    const btnLogo = document.getElementById('btn-logo');
    const btnAwards = document.getElementById('btn-awards');
    const btnRules = document.getElementById('btn-rules');
    const btnHistory = document.getElementById('btn-history');
    const btnRelatedSites = document.getElementById('btn-relatedsites');
    const btnFees = document.getElementById('btn-fees');
    const logoPanel = document.getElementById('logo-panel');
    const relatedSitesPanel = document.getElementById('relatedsites-panel');
    const awardsPanel = document.getElementById('awards-panel');
    const rulesPanel = document.getElementById('rules-panel');
    const historyPanel = document.getElementById('history-panel');
    const feesPanel = document.getElementById('fees-panel');

    function hideAllAbout() {
      [logoPanel, relatedSitesPanel, awardsPanel, rulesPanel, historyPanel, feesPanel].forEach(p => p && p.classList.add('d-none'));
      [btnLogo, btnRelatedSites, btnAwards, btnRules, btnHistory, btnFees].forEach(b => b && b.classList.remove('active'));
    }

    function showLogo() {
      hideAllAbout();
      logoPanel.classList.remove('d-none');
      btnLogo.classList.add('active');
    }

    function showAwards() {
      hideAllAbout();
      awardsPanel.classList.remove('d-none');
      btnAwards.classList.add('active');
    }

    function showRelatedSites() {
      hideAllAbout();
      relatedSitesPanel.classList.remove('d-none');
      btnRelatedSites.classList.add('active');
    }

    function showRules() {
      hideAllAbout();
      rulesPanel.classList.remove('d-none');
      btnRules.classList.add('active');
    }

    function showHistory() {
      hideAllAbout();
      historyPanel.classList.remove('d-none');
      btnHistory.classList.add('active');
    }

    function showFees() {
      hideAllAbout();
      feesPanel.classList.remove('d-none');
      btnFees.classList.add('active');
    }

    if (btnLogo && btnRelatedSites && btnAwards && btnRules && btnHistory && btnFees) {
      btnLogo.addEventListener('click', showLogo);
      btnRelatedSites.addEventListener('click', showRelatedSites);
      btnAwards.addEventListener('click', showAwards);
      btnRules.addEventListener('click', showRules);
      btnHistory.addEventListener('click', showHistory);
      btnFees.addEventListener('click', showFees);
      // default
      showHistory();
    }

    document.querySelectorAll('[data-about-tab]').forEach(item => {
      item.addEventListener('click', (e) => {
        e.preventDefault();
        const tab = item.dataset.aboutTab;
        document.querySelectorAll('[class*="panel"]').forEach(p => p.classList.remove('panel-active'));
        document.getElementById('about').classList.add('panel-active');
        syncHomeStats('about');
        if (tab === 'logo') showLogo();
        if (tab === 'relatedsites') showRelatedSites();
        if (tab === 'awards') showAwards();
        if (tab === 'rules') showRules();
        if (tab === 'history') showHistory();
        if (tab === 'fees') showFees();
      });
    });

    document.querySelectorAll('[data-gallery-filter]').forEach(item => {
      item.addEventListener('click', (e) => {
        e.preventDefault();
        document.querySelectorAll('[class*="panel"]').forEach(p => p.classList.remove('panel-active'));
        document.getElementById('gallery').classList.add('panel-active');
        syncHomeStats('gallery');
        galleryCurrentFilter = item.dataset.galleryFilter;
        galleryCurrentPage = 1;
        renderGallery();
      });
    });

    document.querySelectorAll('[data-news-tab]').forEach(item => {
      item.addEventListener('click', (e) => {
        e.preventDefault();
        document.querySelectorAll('[class*="panel"]').forEach(p => p.classList.remove('panel-active'));
        document.getElementById('news').classList.add('panel-active');
        syncHomeStats('news');
        if (item.dataset.newsTab === 'faq') {
          document.getElementById('faq-tab-btn').click();
        } else if (item.dataset.newsTab === 'qna') {
          const qnaTabBtn = document.getElementById('qna-tab-btn');
          if (qnaTabBtn) qnaTabBtn.click();
        } else {
          document.getElementById('notice-tab-btn').click();
        }
      });
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
    header.classList.toggle('scrolled', window.scrollY > 50);
  });
