  // ============ LOGIN / SIGNUP ============
  document.addEventListener('DOMContentLoaded', async function() {
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.register('/sw.js').catch(() => {});
    }
    initModalScrollLock();
    renderAboutVolunteerPhoto();
    bindAboutPhotoUploader();

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
        el.setAttribute('autocomplete', 'current-password');
      }
      if (el.name === 'birthdate') el.setAttribute('inputmode', 'numeric');
      if (el.name === 'phone') {
        el.setAttribute('inputmode', 'tel');
        el.setAttribute('autocomplete', 'tel');
      }
      if (el.name === 'username') {
        el.setAttribute('autocorrect', 'off');
        el.setAttribute('spellcheck', 'false');
      }
      if (el.name === 'author') {
        el.setAttribute('autocomplete', 'nickname');
        el.setAttribute('autocapitalize', 'off');
        el.setAttribute('spellcheck', 'false');
      }
    });

    const loginForm = document.getElementById('login-form');
    if (loginForm) {
      loginForm.onsubmit = async (e) => {
        e.preventDefault();
        const identifier = e.target.username.value.trim();
        const password = e.target.password.value;
        try {
          const data = await apiRequest('/auth/login', {
            method: 'POST',
            body: JSON.stringify({ username: identifier, password })
          });
          setCurrentUser(data.user);
          const loginModal = bootstrap.Modal.getInstance(document.getElementById('loginModal'));
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
          notifyMessage(error.message || '아이디 또는 비밀번호가 틀렸습니다.');
        }
      };
    }

    const signupForm = document.getElementById('signup-form');
    if (signupForm) {
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
          const signupModal = bootstrap.Modal.getInstance(document.getElementById('signupModal'));
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
        notifyMessage('로그아웃되었습니다.');
      });
    }

    // MY INFO BUTTON
    const myInfoBtn = document.getElementById('my-info-btn');
    if (myInfoBtn) {
      myInfoBtn.addEventListener('click', (e) => {
        e.preventDefault();
        movePanel('myinfo');
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
        document.querySelectorAll('[class*="panel"]').forEach(p => {
          p.classList.remove('panel-active');
        });
        document.getElementById('home').classList.add('panel-active');
        const statsSection = document.getElementById('home-stats');
        if (statsSection) statsSection.style.display = 'block';
        notifyMessage('로그아웃되었습니다.');
      });
    }

    // Initial auth UI update
    await hydrateCurrentUser();
    updateAuthUI();
  });

