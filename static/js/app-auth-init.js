  // ============ LOGIN / SIGNUP ============
  document.addEventListener('DOMContentLoaded', async function() {
    if ('serviceWorker' in navigator) {
      const assetVersion = String(document.querySelector('meta[name="weave-asset-version"]')?.content || '').trim();
      const swUrl = assetVersion ? `/sw.js?v=${encodeURIComponent(assetVersion)}` : '/sw.js';
      navigator.serviceWorker.register(swUrl)
        .then((registration) => registration.update().catch(() => {}))
        .catch(() => {});
    }
    initModalScrollLock();
    const applyViewportUnitVars = () => {
      const viewportHeight = window.visualViewport ? window.visualViewport.height : window.innerHeight;
      const onePercent = Math.max(viewportHeight * 0.01, 1);
      document.documentElement.style.setProperty('--vh', `${onePercent}px`);
      document.documentElement.style.setProperty('--modal-vh', `${onePercent}px`);
      document.documentElement.style.setProperty('--panel-vh', `${onePercent}px`);
    };
    applyViewportUnitVars();
    window.addEventListener('resize', applyViewportUnitVars);
    if (window.visualViewport) {
      window.visualViewport.addEventListener('resize', applyViewportUnitVars);
      window.visualViewport.addEventListener('scroll', applyViewportUnitVars);
    }

    const mobileBottomNav = document.getElementById('mobile-bottom-nav');
    const mobileModals = ['loginModal', 'signupModal'].map((id) => document.getElementById(id)).filter(Boolean);
    const modalReturnFocusMap = new Map();
    document.addEventListener('click', (event) => {
      const target = event.target;
      if (!(target instanceof HTMLElement)) return;
      const trigger = target.closest('[data-bs-target="#loginModal"], [data-bs-target="#signupModal"]');
      if (!(trigger instanceof HTMLElement)) return;
      const modalSelector = String(trigger.getAttribute('data-bs-target') || '');
      if (!modalSelector) return;
      modalReturnFocusMap.set(modalSelector, trigger);
    });
    const baselineViewportHeight = window.visualViewport ? window.visualViewport.height : window.innerHeight;
    const baselineInnerHeight = window.innerHeight;
    const keyboardThreshold = Math.max(130, baselineViewportHeight * 0.15);
    let modalInputFocused = false;

    const syncKeyboardAwareNav = () => {
      const isMobileViewport = window.matchMedia('(max-width: 768px)').matches;
      const currentViewportHeight = window.visualViewport ? window.visualViewport.height : window.innerHeight;
      const viewportScale = window.visualViewport ? Number(window.visualViewport.scale || 1) : 1;
      const activeInput = document.activeElement instanceof HTMLElement
        ? document.activeElement.closest('input, textarea, select, [contenteditable="true"]')
        : null;
      const activeRect = activeInput instanceof HTMLElement ? activeInput.getBoundingClientRect() : null;
      const nearBottomInput = !!(activeRect && activeRect.bottom > currentViewportHeight * 0.62);
      const fallbackHeightDrop = Math.max(0, baselineInnerHeight - window.innerHeight);
      const keyboardLikelyWithoutVisualViewport = !window.visualViewport
        && fallbackHeightDrop > Math.max(120, baselineInnerHeight * 0.18)
        && nearBottomInput;
      const keyboardLikelyOpen = (baselineViewportHeight - currentViewportHeight) > keyboardThreshold
        && nearBottomInput
        && viewportScale <= 1.05;
      const shouldHideNav = isMobileViewport && (keyboardLikelyOpen || keyboardLikelyWithoutVisualViewport || modalInputFocused);
      document.body.classList.toggle('keyboard-open', shouldHideNav);
      if (mobileBottomNav) {
        mobileBottomNav.setAttribute('aria-hidden', shouldHideNav ? 'true' : 'false');
      }
    };

    document.addEventListener('focusin', (event) => {
      const target = event.target;
      if (!(target instanceof HTMLElement)) return;
      if (window.matchMedia('(max-width: 768px)').matches
        && target.matches('input, textarea, select, [contenteditable="true"]')) {
        modalInputFocused = true;
        const inModalBody = target.closest('.modal .modal-body');
        if (inModalBody instanceof HTMLElement) {
          window.setTimeout(() => {
            target.scrollIntoView({ block: 'center', inline: 'nearest', behavior: 'auto' });
          }, 40);
        }
        syncKeyboardAwareNav();
      }
    });

    document.addEventListener('focusout', () => {
      window.setTimeout(() => {
        const active = document.activeElement;
        const stillInAuthModal = active instanceof HTMLElement
          && !!active.closest('#loginModal, #signupModal');
        modalInputFocused = stillInAuthModal;
        syncKeyboardAwareNav();
      }, 0);
    });

    mobileModals.forEach((modalEl) => {
      modalEl.addEventListener('hidden.bs.modal', () => {
        modalInputFocused = false;
        const selector = `#${modalEl.id}`;
        const returnFocusTarget = modalReturnFocusMap.get(selector);
        if (returnFocusTarget instanceof HTMLElement) {
          window.setTimeout(() => {
            returnFocusTarget.focus();
          }, 0);
        }
        syncKeyboardAwareNav();
      });
    });

    window.addEventListener('resize', syncKeyboardAwareNav);
    window.addEventListener('orientationchange', () => {
      window.setTimeout(() => {
        applyViewportUnitVars();
        syncKeyboardAwareNav();
      }, 100);
    });
    if (window.visualViewport) {
      window.visualViewport.addEventListener('resize', syncKeyboardAwareNav);
      window.visualViewport.addEventListener('scroll', syncKeyboardAwareNav);
    }
    syncKeyboardAwareNav();

    renderAboutVolunteerPhoto();
    bindAboutPhotoUploader();

    const reducedDataMedia = window.matchMedia ? window.matchMedia('(prefers-reduced-data: reduce)') : null;
    const computeReducedData = () => {
      const saveData = !!(navigator.connection && navigator.connection.saveData);
      return saveData || !!(reducedDataMedia && reducedDataMedia.matches);
    };
    let prefersReducedData = computeReducedData();
    document.body.classList.toggle('reduced-data-mode', prefersReducedData);
    const criticalImageIds = new Set(['home-hero-image', 'logo-img']);

    const downshiftImageUrlForReducedData = (rawUrl) => {
      const value = String(rawUrl || '').trim();
      if (!value || value.startsWith('data:')) return value;
      try {
        const parsed = new URL(value, window.location.origin);
        const isLocalUpload = parsed.origin === window.location.origin && /\/uploads\//i.test(parsed.pathname);
        if (isLocalUpload) {
          const width = Number(parsed.searchParams.get('w') || parsed.searchParams.get('width') || 960);
          parsed.searchParams.set('w', String(Math.max(360, Math.floor(width * 0.7))));
          parsed.searchParams.set('q', '60');
          return parsed.toString();
        }
        if (!/unsplash\.com$/i.test(parsed.hostname) && !/images\.unsplash\.com$/i.test(parsed.hostname)) {
          return value;
        }
        const width = Number(parsed.searchParams.get('w') || parsed.searchParams.get('width') || 0);
        if (width > 0) {
          parsed.searchParams.set('w', String(Math.max(280, Math.floor(width * 0.72))));
        }
        parsed.searchParams.set('q', '58');
        return parsed.toString();
      } catch (_error) {
        return value;
      }
    };

    let reducedDataObserver = null;
    const getImagePriorityTier = (img) => {
      if (!(img instanceof HTMLImageElement)) return 'low';
      const sectionId = String(img.closest('section')?.id || '');
      if (criticalImageIds.has(String(img.id || ''))) return 'high';
      if (sectionId === 'home' || sectionId === 'home-notice-carousel') return 'high';
      if (sectionId === 'about' || sectionId === 'home-calendar-preview') return 'auto';
      return 'low';
    };

    const applyReducedDataToImage = (img, forceReducedData = prefersReducedData) => {
      if (!(img instanceof HTMLImageElement)) return;
      const isCritical = criticalImageIds.has(String(img.id || ''));
      const priorityTier = getImagePriorityTier(img);
      if (forceReducedData) {
        if (!isCritical) {
          img.setAttribute('loading', 'lazy');
          img.setAttribute('fetchpriority', 'low');
          ['src', 'srcset', 'data-src', 'data-srcset'].forEach((attr) => {
            const current = img.getAttribute(attr);
            if (!current) return;
            if (attr.includes('srcset')) {
              const compact = current.split(',').map((part) => {
                const pieces = part.trim().split(/\s+/);
                const nextUrl = downshiftImageUrlForReducedData(pieces[0]);
                return [nextUrl, ...pieces.slice(1)].join(' ').trim();
              }).join(', ');
              img.setAttribute(attr, compact);
            } else {
              img.setAttribute(attr, downshiftImageUrlForReducedData(current));
            }
          });
        } else {
          img.setAttribute('fetchpriority', 'high');
          img.setAttribute('loading', 'eager');
        }
      } else {
        if (priorityTier === 'high') {
          img.setAttribute('fetchpriority', 'high');
          img.setAttribute('loading', 'eager');
        } else if (priorityTier === 'auto') {
          img.setAttribute('fetchpriority', 'auto');
        } else {
          img.setAttribute('fetchpriority', 'low');
          if (!isCritical) img.setAttribute('loading', 'lazy');
        }
      }
      if (!img.hasAttribute('loading') && !isCritical) {
        img.setAttribute('loading', 'lazy');
      }
      if (!img.hasAttribute('decoding')) {
        img.setAttribute('decoding', 'async');
      }
    };

    const applyReducedDataImagePolicy = (forceReducedData = prefersReducedData) => {
      if (reducedDataObserver) {
        reducedDataObserver.disconnect();
        reducedDataObserver = null;
      }
      const allImages = Array.from(document.querySelectorAll('img'));
      if (forceReducedData && window.__WEAVE_E2E__ === true) {
        allImages.forEach((img) => applyReducedDataToImage(img, true));
        return;
      }
      if (forceReducedData && 'IntersectionObserver' in window) {
        reducedDataObserver = new IntersectionObserver((entries) => {
          entries.forEach((entry) => {
            if (!entry.isIntersecting) return;
            applyReducedDataToImage(entry.target, true);
            reducedDataObserver.unobserve(entry.target);
          });
        }, { rootMargin: '280px 0px 280px 0px', threshold: 0.01 });
        allImages.forEach((img) => {
          const isCritical = criticalImageIds.has(String(img.id || ''));
          if (isCritical) {
            applyReducedDataToImage(img, true);
            return;
          }
          reducedDataObserver.observe(img);
        });
        return;
      }
      allImages.forEach((img) => {
        applyReducedDataToImage(img, forceReducedData);
      });
    };
    window.__applyReducedDataImagePolicy = applyReducedDataImagePolicy;
    applyReducedDataImagePolicy(prefersReducedData);

    const shouldWarnResponsiveImage = /localhost|127\.0\.0\.1/i.test(window.location.hostname)
      || window.location.port === '5111';
    if (shouldWarnResponsiveImage) {
      document.querySelectorAll('img').forEach((img) => {
        const hasSrcSet = img.hasAttribute('srcset');
        const hasSizes = img.hasAttribute('sizes');
        if (!hasSrcSet || !hasSizes) {
          const key = img.id || img.alt || img.getAttribute('src') || 'unknown-image';
          console.warn('[weave-responsive] 이미지 반응형 속성 점검 필요:', key, {
            hasSrcSet,
            hasSizes
          });
        }
      });
    }

    const notifyServiceWorkerReducedData = (enabled) => {
      if (!('serviceWorker' in navigator)) return;
      navigator.serviceWorker.ready.then((registration) => {
        if (!registration.active) return;
        registration.active.postMessage({
          type: 'WEAVE_REDUCED_DATA_MODE',
          enabled: !!enabled
        });
      }).catch(() => {});
    };

    const applyReducedDataMode = () => {
      prefersReducedData = computeReducedData();
      document.body.classList.toggle('reduced-data-mode', prefersReducedData);
      applyReducedDataImagePolicy(prefersReducedData);
      notifyServiceWorkerReducedData(prefersReducedData);
    };

    if (reducedDataMedia && typeof reducedDataMedia.addEventListener === 'function') {
      reducedDataMedia.addEventListener('change', applyReducedDataMode);
    }
    if (navigator.connection && typeof navigator.connection.addEventListener === 'function') {
      navigator.connection.addEventListener('change', applyReducedDataMode);
    }
    document.addEventListener('weave:panel-changed', () => {
      if (prefersReducedData) applyReducedDataImagePolicy(true);
    });
    applyReducedDataMode();

    const sessionSummary = document.getElementById('session-expired-summary');
    if (sessionSummary instanceof HTMLElement) {
      sessionSummary.textContent = document.querySelector('.rich-editor, [contenteditable="true"]')
        ? '작성 중인 내용은 자동 저장되지 않았을 수 있습니다. 저장 후 다시 로그인하는 것을 권장합니다.'
        : '진행 중 작업이 있다면 다시 로그인 후 상태를 확인해주세요.';
    }

    const sanitizeNicknameInput = (inputEl) => {
      if (!inputEl) return;
      const invalidCharsPattern = /[^가-힣A-Za-z0-9]/g;
      const inlineErrorEl = inputEl.id === 'nickname-change-input'
        ? document.getElementById('nickname-change-error')
        : null;

      inputEl.addEventListener('beforeinput', (event) => {
        const incoming = String(event.data || '');
        if (!incoming) return;
        if (invalidCharsPattern.test(incoming)) {
          event.preventDefault();
        }
      });

      inputEl.addEventListener('paste', (event) => {
        const pasted = String((event.clipboardData || window.clipboardData)?.getData('text') || '');
        if (!pasted) return;
        const sanitized = pasted.replace(invalidCharsPattern, '');
        if (sanitized === pasted) return;
        event.preventDefault();
        const start = inputEl.selectionStart ?? inputEl.value.length;
        const end = inputEl.selectionEnd ?? start;
        inputEl.setRangeText(sanitized, start, end, 'end');
        inputEl.dispatchEvent(new Event('input', { bubbles: true }));
      });

      inputEl.addEventListener('input', () => {
        const next = String(inputEl.value || '').replace(invalidCharsPattern, '').slice(0, 12);
        if (inputEl.value !== next) inputEl.value = next;
        const check = validateNickname(next);
        inputEl.setCustomValidity(check.ok || !next ? '' : check.message);
        inputEl.classList.toggle('is-invalid', !!next && !check.ok);
        if (inlineErrorEl) {
          inlineErrorEl.classList.toggle('d-none', !(!!next && !check.ok));
        }
      });
      inputEl.setAttribute('autocapitalize', 'off');
      inputEl.setAttribute('autocomplete', 'nickname');
      inputEl.setAttribute('inputmode', 'text');
      inputEl.setAttribute('spellcheck', 'false');
    };

    const signupNickname = document.querySelector('#signup-form [name="nickname"]');
    sanitizeNicknameInput(signupNickname);
    sanitizeNicknameInput(document.getElementById('nickname-change-input'));

    document.querySelectorAll('input, textarea').forEach((el) => {
      if (!el.getAttribute('autocapitalize')) el.setAttribute('autocapitalize', 'off');
      if (el.type === 'email') {
        el.setAttribute('inputmode', 'email');
        el.setAttribute('autocomplete', el.getAttribute('name') === 'emailConfirm' ? 'email' : 'email');
      }
      if (el.type === 'password') {
        if (!el.getAttribute('autocomplete')) {
          el.setAttribute('autocomplete', 'current-password');
        }
      }
      if (el.name === 'birthdate') el.setAttribute('inputmode', 'numeric');
      if (el.name === 'phone') {
        el.setAttribute('inputmode', 'tel');
        el.setAttribute('autocomplete', 'tel');
      }
      if (el.name === 'username') {
        el.setAttribute('autocorrect', 'off');
        el.setAttribute('spellcheck', 'false');
        if (!el.getAttribute('enterkeyhint')) el.setAttribute('enterkeyhint', 'next');
      }
      if (el.name === 'password' && !el.getAttribute('enterkeyhint')) {
        const inLoginForm = !!el.closest('#login-form');
        el.setAttribute('enterkeyhint', inLoginForm ? 'go' : 'next');
      }
      if (el.name === 'author') {
        el.setAttribute('autocomplete', 'nickname');
        el.setAttribute('autocapitalize', 'off');
        el.setAttribute('spellcheck', 'false');
      }
      if (el.name === 'phone' && !el.getAttribute('enterkeyhint')) {
        el.setAttribute('enterkeyhint', 'next');
      }
      if (el.type === 'search' || el.classList.contains('responsive-search-input')) {
        el.setAttribute('inputmode', 'search');
        if (!el.getAttribute('enterkeyhint')) el.setAttribute('enterkeyhint', 'search');
      }
    });

    const showLoginCredentialErrorPopup = () => {
      const popupId = 'weave-login-credential-popup';
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
                <h5 class="modal-title">로그인 오류</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="닫기"></button>
              </div>
              <div class="modal-body">
                <p class="mb-0">ID나 PW를 확인해주세요</p>
              </div>
              <div class="modal-footer border-0">
                <button type="button" class="btn btn-primary" data-bs-dismiss="modal">닫기</button>
              </div>
            </div>
          </div>
        `;
        document.body.appendChild(modalEl);
      }
      if (window.bootstrap?.Modal) {
        const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
        modal.show();
      } else {
        notifyMessage('ID나 PW를 확인해주세요');
      }
    };

    const getModalInstanceSafe = (id) => {
      if (!window.bootstrap?.Modal) return null;
      const el = document.getElementById(id);
      if (!el) return null;
      return bootstrap.Modal.getInstance(el);
    };

    const loginForm = document.getElementById('login-form');
    if (loginForm) {
      loginForm.onsubmit = async (e) => {
        e.preventDefault();
        const identifier = e.target.username.value.trim();
        const password = e.target.password.value;
        const submitBtn = loginForm.querySelector('button[type="submit"]');
        if (submitBtn) submitBtn.disabled = true;
        try {
          const data = await apiRequest('/auth/login', {
            method: 'POST',
            body: JSON.stringify({ username: identifier, password })
          });
          setCurrentUser(data.user);
          document.dispatchEvent(new CustomEvent('weave:user-state-changed', { detail: { loggedIn: true } }));
          const loginModal = getModalInstanceSafe('loginModal');
          if (loginModal) loginModal.hide();
          if (PENDING_RETURN_PANEL) {
            movePanel(PENDING_RETURN_PANEL);
            if (PENDING_RETURN_PANEL === 'news' && PENDING_RETURN_NEWS_TAB) {
              activateNewsTab(PENDING_RETURN_NEWS_TAB);
            }
            PENDING_RETURN_PANEL = '';
            PENDING_RETURN_NEWS_TAB = '';
          }
          SESSION_EXPIRED_SHOWN = false;
          e.target.reset();
          notifyMessage(data.pending ? (data.message || '가입 승인 대기 중입니다.') : `${data.user.name}님 환영합니다!`);
        } catch (error) {
          const status = Number(error?.status || 0);
          if (status === 401 || status === 403 || status === 423) {
            showLoginCredentialErrorPopup();
          } else {
            notifyMessage(error?.message || '로그인 처리 중 오류가 발생했습니다.');
          }
        } finally {
          if (submitBtn) submitBtn.disabled = false;
        }
      };
    }

    const openFindUsernameLink = document.getElementById('open-find-username-link');
    const openFindPasswordLink = document.getElementById('open-find-password-link');
    const accountRecoveryBackBtn = document.getElementById('account-recovery-back-btn');
    const recoverUsernameTabBtn = document.getElementById('recover-username-tab-btn');
    const recoverPasswordTabBtn = document.getElementById('recover-password-tab-btn');
    const recoverUsernamePane = document.getElementById('recover-username-pane');
    const recoverPasswordPane = document.getElementById('recover-password-pane');
    const recoverUsernameForm = document.getElementById('recover-username-form');
    const recoverPasswordForm = document.getElementById('recover-password-form');
    const recoverUsernameResult = document.getElementById('recover-username-result');
    const recoverPasswordResult = document.getElementById('recover-password-result');
    const accountRecoveryTitle = document.getElementById('account-recovery-title');
    const accountRecoverySubtitle = document.getElementById('account-recovery-subtitle');

    const switchRecoveryTab = (tab) => {
      const isUsername = tab !== 'password';
      recoverUsernameTabBtn?.classList.toggle('active', isUsername);
      recoverPasswordTabBtn?.classList.toggle('active', !isUsername);
      recoverUsernamePane?.classList.toggle('d-none', !isUsername);
      recoverPasswordPane?.classList.toggle('d-none', isUsername);
      if (accountRecoveryTitle) {
        accountRecoveryTitle.textContent = isUsername ? '아이디 찾기' : '비밀번호 재설정';
      }
      if (accountRecoverySubtitle) {
        accountRecoverySubtitle.textContent = isUsername
          ? '가입 시 등록한 이메일 또는 연락처로 아이디를 확인하세요.'
          : '아이디와 본인 확인 정보로 새 비밀번호를 설정하세요.';
      }
      if (recoverUsernameResult) recoverUsernameResult.classList.add('d-none');
      if (recoverPasswordResult) recoverPasswordResult.classList.add('d-none');
    };

    if (openFindUsernameLink) {
      openFindUsernameLink.addEventListener('click', (e) => {
        e.preventDefault();
        const loginModal = getModalInstanceSafe('loginModal');
        if (loginModal) loginModal.hide();
        switchRecoveryTab('username');
        movePanel('account-recovery');
      });
    }
    if (openFindPasswordLink) {
      openFindPasswordLink.addEventListener('click', (e) => {
        e.preventDefault();
        const loginModal = getModalInstanceSafe('loginModal');
        if (loginModal) loginModal.hide();
        switchRecoveryTab('password');
        movePanel('account-recovery');
      });
    }
    if (recoverUsernameTabBtn) {
      recoverUsernameTabBtn.addEventListener('click', () => switchRecoveryTab('username'));
    }
    if (recoverPasswordTabBtn) {
      recoverPasswordTabBtn.addEventListener('click', () => switchRecoveryTab('password'));
    }
    if (accountRecoveryBackBtn) {
      accountRecoveryBackBtn.addEventListener('click', () => {
        movePanel('home');
      });
    }
    switchRecoveryTab('username');
    if (recoverUsernameForm) {
      recoverUsernameForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const contact = String(e.target.contact?.value || '').trim();
        if (!contact) return;
        try {
          const data = await apiRequest('/auth/find-username', {
            method: 'POST',
            body: JSON.stringify({ contact })
          });
          if (recoverUsernameResult) {
            recoverUsernameResult.classList.remove('d-none');
            recoverUsernameResult.textContent = `가입된 아이디: ${data.username || '-'}`;
            recoverUsernameResult.classList.remove('alert-danger');
            recoverUsernameResult.classList.add('alert-info');
          }
        } catch (error) {
          if (recoverUsernameResult) {
            recoverUsernameResult.classList.remove('d-none');
            recoverUsernameResult.textContent = error.message || '일치하는 계정을 찾지 못했습니다.';
            recoverUsernameResult.classList.remove('alert-info');
            recoverUsernameResult.classList.add('alert-danger');
          }
        }
      });
    }
    if (recoverPasswordForm) {
      recoverPasswordForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const username = String(e.target.username?.value || '').trim();
        const contact = String(e.target.contact?.value || '').trim();
        const newPassword = String(e.target.newPassword?.value || '').trim();
        const confirmPassword = String(e.target.confirmPassword?.value || '').trim();
        if (!username || !contact || !newPassword || !confirmPassword) return;
        if (newPassword !== confirmPassword) {
          notifyMessage('새 비밀번호와 확인 비밀번호가 일치하지 않습니다.');
          return;
        }
        if (newPassword.length < 8 || !/[A-Z]/.test(newPassword) || !/[^A-Za-z0-9]/.test(newPassword)) {
          notifyMessage('새 비밀번호는 8자 이상이며 대문자/특수문자를 포함해야 합니다.');
          return;
        }
        try {
          const data = await apiRequest('/auth/reset-password', {
            method: 'POST',
            body: JSON.stringify({ username, contact, newPassword })
          });
          if (recoverPasswordResult) {
            recoverPasswordResult.classList.remove('d-none');
            recoverPasswordResult.textContent = data.message || '비밀번호가 재설정되었습니다.';
            recoverPasswordResult.classList.remove('alert-danger');
            recoverPasswordResult.classList.add('alert-info');
          }
          e.target.reset();
        } catch (error) {
          if (recoverPasswordResult) {
            recoverPasswordResult.classList.remove('d-none');
            recoverPasswordResult.textContent = error.message || '비밀번호 재설정에 실패했습니다.';
            recoverPasswordResult.classList.remove('alert-info');
            recoverPasswordResult.classList.add('alert-danger');
          }
        }
      });
    }

    const signupForm = document.getElementById('signup-form');
    if (signupForm) {
      const optionalFieldNodes = Array.from(signupForm.querySelectorAll('.signup-optional-field'));
      const optionalToggleBtn = document.getElementById('signup-optional-toggle');
      const optionalStateKey = 'weave.signupOptional.expanded';
      const persistedOptional = window.sessionStorage.getItem(optionalStateKey);
      let optionalExpanded = persistedOptional == null
        ? !window.matchMedia('(max-width: 576px)').matches
        : persistedOptional === '1';

      const syncOptionalFields = () => {
        optionalFieldNodes.forEach((node) => {
          node.classList.toggle('is-collapsed', !optionalExpanded);
        });
        if (optionalToggleBtn) {
          optionalToggleBtn.textContent = optionalExpanded ? '접기' : '펼치기';
          optionalToggleBtn.setAttribute('aria-expanded', optionalExpanded ? 'true' : 'false');
        }
        window.sessionStorage.setItem(optionalStateKey, optionalExpanded ? '1' : '0');
      };

      if (optionalToggleBtn) {
        optionalToggleBtn.addEventListener('click', () => {
          optionalExpanded = !optionalExpanded;
          syncOptionalFields();
        });
      }

      const optionalMedia = window.matchMedia('(max-width: 576px)');
      optionalMedia.addEventListener('change', () => {
        const persisted = window.sessionStorage.getItem(optionalStateKey);
        optionalExpanded = persisted == null ? !optionalMedia.matches : persisted === '1';
        syncOptionalFields();
      });
      syncOptionalFields();

      const signupSubmitBtn = document.getElementById('signup-submit-btn');
      const signupInputs = signupForm.querySelectorAll('input');

      function updateSignupSubmitState() {
        const nicknameInput = signupForm.querySelector('[name="nickname"]');
        const usernameInput = signupForm.querySelector('[name="username"]');
        if (nicknameInput && usernameInput && !String(nicknameInput.value || '').trim()) {
          const fallback = String(usernameInput.value || '').replace(/[^가-힣A-Za-z0-9]/g, '').slice(0, 12);
          if (fallback) nicknameInput.value = fallback;
        }
        const requiredFilled = Array.from(signupInputs).every(input => {
          if (!input.required) return true;
          if (input.type === 'checkbox') return input.checked;
          return String(input.value || '').trim().length > 0;
        });
        if (signupSubmitBtn) {
          signupSubmitBtn.disabled = false;
          signupSubmitBtn.classList.toggle('btn-secondary', !requiredFilled);
          signupSubmitBtn.classList.toggle('btn-primary', requiredFilled);
        }
      }

      signupInputs.forEach(input => {
        input.addEventListener('input', updateSignupSubmitState);
        input.addEventListener('change', updateSignupSubmitState);
      });

      const passwordInput = signupForm.querySelector('[name="password"]');
      if (passwordInput) passwordInput.setAttribute('autocomplete', 'new-password');
      const confirmPasswordInput = signupForm.querySelector('[name="confirm-password"]');
      if (confirmPasswordInput) confirmPasswordInput.setAttribute('autocomplete', 'new-password');
      if (signupNickname) {
        signupNickname.addEventListener('blur', () => {
          const check = validateNickname(signupNickname.value);
          signupNickname.setCustomValidity(check.ok ? '' : check.message);
          signupNickname.classList.toggle('is-invalid', !check.ok);
        });
      }

      updateSignupSubmitState();

      signupForm.onsubmit = async (e) => {
        e.preventDefault();
        const name = e.target.name.value.trim();
        const nickname = e.target.nickname.value.trim();
        const email = e.target.email.value.trim();
        const birthDate = e.target.birthdate.value.trim();
        const phone = e.target.phone.value.trim();
        const emailConfirm = e.target.emailConfirm.value.trim();
        const username = e.target.username.value.trim();
        const password = e.target.password.value;
        const confirmPassword = e.target['confirm-password'].value;
        const generation = e.target.generation.value.trim();
        const interests = e.target.interests.value.trim();
        const certificates = e.target.certificates.value.trim();
        const availability = e.target.availability.value.trim();

        const nicknameCheck = validateNickname(nickname);
        if (!nicknameCheck.ok) {
          notifyMessage(nicknameCheck.message);
          return;
        }

        if (password !== confirmPassword) {
          notifyMessage('비밀번호가 일치하지 않습니다.');
          return;
        }
        if (password.length < 8 || !/[A-Z]/.test(password) || !/[^A-Za-z0-9]/.test(password)) {
          notifyMessage('비밀번호는 8자 이상이며 대문자/특수문자를 포함해야 합니다.');
          return;
        }
        if (!isValidBirthDate(birthDate)) {
          notifyMessage('생년월일은 yyyy.mm.dd 형식으로 정확히 입력해주세요.');
          return;
        }
        if (!/^01[0-9]-?\d{3,4}-?\d{4}$/.test(phone)) {
          notifyMessage('연락처 형식이 올바르지 않습니다. (예: 010-1234-5678)');
          return;
        }
        if (email !== emailConfirm) {
          notifyMessage('이메일과 이메일 확인 값이 일치하지 않습니다.');
          return;
        }
        if (!e.target.termsAgree.checked || !e.target.privacyAgree.checked) {
          notifyMessage('이용약관 및 개인정보처리방침 필수 동의가 필요합니다.');
          return;
        }
        try {
          const data = await apiRequest('/auth/signup', {
            method: 'POST',
            body: JSON.stringify({
              name,
              nickname,
              username,
              email,
              phone,
              birthDate,
              password,
              generation,
              interests,
              certificates,
              availability
            })
          });

          setCurrentUser(data.user);
          const signupModal = getModalInstanceSafe('signupModal');
          if (signupModal) signupModal.hide();
          e.target.reset();
          notifyMessage(data.message || `${name}님, 가입 신청이 완료되었습니다.`);
          updateSignupSubmitState();
        } catch (error) {
          notifyMessage(error.message || '회원가입 중 오류가 발생했습니다.');
        }
      };
    }

    // LOGOUT HANDLER (from navbar)
    const logoutBtn = document.getElementById('logout-btn');
    if (logoutBtn) {
      logoutBtn.addEventListener('click', async () => {
        try {
          await apiRequest('/auth/logout', { method: 'POST' });
        } catch (_) {}
        setCurrentUser(null);
        movePanel('home');
        if (typeof renderHomeNoticeCarousel === 'function') renderHomeNoticeCarousel();
        if (typeof loadActivitiesCalendar === 'function') loadActivitiesCalendar().catch(() => {});
        notifyMessage('로그아웃되었습니다.');
      });
    }

    // MY INFO BUTTON
    const myInfoBtn = document.getElementById('my-info-btn');
    if (myInfoBtn) {
      myInfoBtn.addEventListener('click', (e) => {
        e.preventDefault();
        movePanel('myinfo');
        if (typeof markCurrentUserNotificationsRead === 'function') {
          markCurrentUserNotificationsRead();
        }
        if (typeof renderMyNotifications === 'function') renderMyNotifications();
      });
    }

    const nicknameChangeBtn = document.getElementById('nickname-change-btn');
    if (nicknameChangeBtn) {
      nicknameChangeBtn.addEventListener('click', async () => {
        const user = getCurrentUser();
        if (!user) {
          notifyMessage('로그인이 필요합니다.');
          return;
        }
        const input = document.getElementById('nickname-change-input');
        const help = document.getElementById('nickname-change-help');
        const nickname = input?.value?.trim() || '';
        const check = validateNickname(nickname);
        if (!check.ok) {
          notifyMessage(check.message);
          return;
        }
        try {
          const data = await apiRequest('/me/nickname', {
            method: 'PATCH',
            body: JSON.stringify({ nickname })
          });
          if (data.user) setCurrentUser(data.user);
          if (help) help.textContent = '닉네임이 변경되었습니다.';
          if (input) input.value = '';
        } catch (error) {
          const detail = /next_allowed_at/.test(String(error.message || '')) ? ` (${error.message})` : '';
          if (help) help.textContent = `변경 실패: ${error.message || '알 수 없는 오류'}${detail}`;
          notifyMessage(error.message || '닉네임 변경에 실패했습니다.');
        }
      });
    }

    // LOGOUT FROM PROFILE PAGE
    const logoutBtnProfile = document.getElementById('logout-btn-profile');
    if (logoutBtnProfile) {
      logoutBtnProfile.addEventListener('click', async () => {
        try {
          await apiRequest('/auth/logout', { method: 'POST' });
        } catch (_) {}
        setCurrentUser(null);
        movePanel('home');
        if (typeof renderHomeNoticeCarousel === 'function') renderHomeNoticeCarousel();
        if (typeof loadActivitiesCalendar === 'function') loadActivitiesCalendar().catch(() => {});
        notifyMessage('로그아웃되었습니다.');
      });
    }

    // Initial auth UI update
    await hydrateCurrentUser();
    updateAuthUI();
  });

