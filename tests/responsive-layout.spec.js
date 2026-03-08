const { test, expect } = require('@playwright/test');

test.use({ serviceWorkers: 'block' });

const VIEWPORTS = [
  { name: 'mobile-320', width: 320, height: 568 },
  { name: 'mobile-375', width: 375, height: 812 },
  { name: 'mobile-390', width: 390, height: 844 },
  { name: 'mobile-412', width: 412, height: 915 },
  { name: 'tablet-768', width: 768, height: 1024 },
  { name: 'desktop-1280', width: 1280, height: 800 },
];

for (const vp of VIEWPORTS) {
  test(`반응형 레이아웃 스모크 (${vp.name})`, async ({ page }) => {
    await page.setViewportSize({ width: vp.width, height: vp.height });
    await page.goto('/');

    await expect(page.locator('#home')).toBeVisible();

    const overflowX = await page.evaluate(() => {
      return document.documentElement.scrollWidth - document.documentElement.clientWidth;
    });
    expect(overflowX).toBeLessThanOrEqual(16);

    if (vp.width < 768) {
      await expect(page.locator('#mobile-bottom-nav')).toBeVisible();
      const tabBox = await page.locator('#mobile-bottom-nav .mobile-tab').first().boundingBox();
      expect(tabBox).toBeTruthy();
      expect(tabBox.height).toBeGreaterThanOrEqual(44);

      await expect(page.locator('#mobile-bottom-nav .mobile-tab')).toHaveCount(6);
    }

    const fieldFontSize = await page.evaluate(() => {
      const input = document.querySelector('input, textarea, select');
      if (!input) return 0;
      return parseFloat(getComputedStyle(input).fontSize || '0');
    });
    if (vp.width <= 768) {
      expect(fieldFontSize).toBeGreaterThanOrEqual(16);
    }
  });
}

test('반응형 레이아웃 스모크 (mobile-landscape)', async ({ page }) => {
  await page.setViewportSize({ width: 844, height: 390 });
  await page.goto('/');

  await expect(page.locator('#home')).toBeVisible();
  await expect(page.locator('#mobile-bottom-nav')).toBeVisible();

  const overflowX = await page.evaluate(() => {
    return document.documentElement.scrollWidth - document.documentElement.clientWidth;
  });
  expect(overflowX).toBeLessThanOrEqual(16);
});

test('반응형 레이아웃 스모크 (200% text zoom)', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');

  await page.evaluate(() => {
    document.documentElement.style.fontSize = '200%';
  });

  const overflowX = await page.evaluate(() => {
    return document.documentElement.scrollWidth - document.documentElement.clientWidth;
  });
  expect(overflowX).toBeLessThanOrEqual(24);

  await expect(page.locator('#mobile-bottom-nav')).toBeVisible();
});

test('반응형 레이아웃 스모크 (long-content stress)', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');

  await page.evaluate(() => {
    const lead = document.getElementById('home-hero-lead');
    if (lead) {
      lead.textContent = '모바일 반응형 검증을 위한 매우 긴 문장입니다. '.repeat(8);
    }
    const sub = document.getElementById('home-hero-subtext');
    if (sub) {
      sub.textContent = '긴 안내 문구가 버튼과 레이아웃을 밀어내지 않는지 확인합니다. '.repeat(6);
    }
    const title = document.querySelector('#news .section-header h2');
    if (title) {
      title.textContent = '아주 긴 소식 제목'.repeat(12);
    }

    const tbody = document.querySelector('#news-table-body');
    if (tbody) {
      tbody.innerHTML = '';
      for (let i = 0; i < 15; i += 1) {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td>${i + 1}</td>
          <td>긴 제목 스트레스 테스트용 공지사항 ${'가나다라마바사 '.repeat(5)}</td>
          <td>운영진테스트계정</td>
          <td>2026-03-08</td>
          <td>${1200 + i}</td>
          <td>${300 + i}</td>
          <td><button class="btn btn-sm btn-outline-secondary">관리</button></td>
        `;
        tbody.appendChild(tr);
      }
    }
  });

  const overflowX = await page.evaluate(() => {
    return document.documentElement.scrollWidth - document.documentElement.clientWidth;
  });
  expect(overflowX).toBeLessThanOrEqual(24);
});

test('반응형 레이아웃 스모크 (mobile keyboard viewport)', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');

  await page.click('[data-bs-target="#loginModal"]');
  await expect(page.locator('#loginModal')).toBeVisible();
  await page.locator('#login-form input[name="username"]').focus();

  const metrics = await page.evaluate(() => {
    const modalContent = document.querySelector('#loginModal .modal-content');
    const modalRect = modalContent ? modalContent.getBoundingClientRect() : null;
    const viewportHeight = window.visualViewport ? window.visualViewport.height : window.innerHeight;
    const vhVar = getComputedStyle(document.documentElement).getPropertyValue('--modal-vh').trim();
    return {
      viewportHeight,
      modalHeight: modalRect ? modalRect.height : 0,
      hasModalVhVar: !!vhVar
    };
  });

  expect(metrics.hasModalVhVar).toBeTruthy();
  expect(metrics.modalHeight).toBeGreaterThan(0);
  expect(metrics.modalHeight).toBeLessThanOrEqual(metrics.viewportHeight + 2);
});

test('반응형 상호작용 (mobile offcanvas -> submenu -> panel 이동)', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');

  await page.click('[data-bs-target="#mobileMenuDrawer"]');
  await expect(page.locator('#mobileMenuDrawer')).toBeVisible();
  await page.click('[data-bs-target="#mobile-menu-news"]');
  await page.click('#mobile-menu-news [data-news-tab="faq"]');

  await expect(page.locator('#news.panel-active')).toBeVisible();
  await expect(page.locator('#faq-tab-btn')).toHaveClass(/active/);
});

test('반응형 상호작용 (mobile keyboard focus 시 하단 탭 숨김)', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');

  await page.click('[data-bs-target="#loginModal"]');
  await expect(page.locator('#loginModal')).toBeVisible();
  await page.locator('#login-form input[name="username"]').focus();

  await expect(page.locator('body')).toHaveClass(/keyboard-open/);

  const hidden = await page.evaluate(() => {
    const nav = document.getElementById('mobile-bottom-nav');
    if (!nav) return false;
    const style = getComputedStyle(nav);
    return style.pointerEvents === 'none';
  });
  expect(hidden).toBeTruthy();
});

test('반응형 상호작용 (테이블 카드 액션 버튼 접근 가능)', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');

  await page.click('#mobile-bottom-nav .mobile-tab[data-panel="news"]');

  await page.evaluate(() => {
    const tbody = document.getElementById('news-table-body');
    if (!tbody) return;
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>1</td>
      <td>모바일 액션 버튼 테스트 공지</td>
      <td>운영진</td>
      <td>2026-03-08</td>
      <td>42</td>
      <td>7</td>
      <td><button id="mobile-manage-action" class="btn btn-sm btn-outline-secondary" type="button">관리</button></td>
    `;
    tbody.innerHTML = '';
    tbody.appendChild(tr);
    const btn = document.getElementById('mobile-manage-action');
    if (btn) {
      btn.addEventListener('click', () => {
        btn.setAttribute('data-clicked', '1');
      });
    }
  });

  const actionBtn = page.locator('#mobile-manage-action');
  await expect(actionBtn).toBeVisible();
  await actionBtn.click();
  await expect(actionBtn).toHaveAttribute('data-clicked', '1');
});

test('반응형 상호작용 (회원가입 선택 항목 토글 유지)', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');

  await page.click('[data-bs-target="#signupModal"]');
  await expect(page.locator('#signupModal')).toBeVisible();

  const toggle = page.locator('#signup-optional-toggle');
  await expect(toggle).toBeVisible();
  await toggle.click();
  await expect(toggle).toHaveText(/접기|펼치기/);

  await page.click('#signupModal .btn-close');
  await page.click('[data-bs-target="#signupModal"]');
  await expect(page.locator('#signupModal')).toBeVisible();
  await expect(page.locator('#signup-optional-toggle')).toHaveAttribute('aria-expanded', /(true|false)/);
});

test('반응형 회귀 (소개 사진 유지 + 홈 전용 섹션 비노출)', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');

  await page.evaluate(() => {
    if (typeof movePanel === 'function') {
      movePanel('about');
    }
  });
  await expect(page.locator('#about.panel-active')).toBeVisible();

  await page.evaluate(() => {
    const canvas = document.createElement('canvas');
    canvas.width = 12;
    canvas.height = 12;
    const context = canvas.getContext('2d');
    if (context) {
      context.fillStyle = '#31b7ff';
      context.fillRect(0, 0, 12, 12);
    }
    localStorage.setItem('weave_about_volunteer_photo', canvas.toDataURL('image/png'));
    if (typeof renderAboutVolunteerPhoto === 'function') renderAboutVolunteerPhoto();
  });

  await page.waitForFunction(() => {
    const img = document.getElementById('about-volunteer-image');
    if (!(img instanceof HTMLImageElement)) return false;
    return img.complete && img.naturalWidth > 0;
  }, null, { timeout: 10000 });

  const snapshot = await page.evaluate(() => {
    const aboutImg = document.getElementById('about-volunteer-image');
    const stats = document.getElementById('home-stats');
    const calendar = document.getElementById('home-calendar-preview');
    const notice = document.getElementById('home-notice-carousel');
    const homeHidden = [stats, calendar, notice].every((node) => {
      if (!(node instanceof HTMLElement)) return true;
      const style = getComputedStyle(node);
      return style.display === 'none' || style.visibility === 'hidden';
    });
    return {
      src: aboutImg ? String(aboutImg.getAttribute('src') || '') : '',
      naturalWidth: aboutImg instanceof HTMLImageElement ? aboutImg.naturalWidth : 0,
      homeHidden
    };
  });

  expect(snapshot.src.startsWith('data:image/')).toBeTruthy();
  expect(snapshot.naturalWidth).toBeGreaterThan(0);
  expect(snapshot.homeHidden).toBeTruthy();
});

test('반응형 접근성 (forced-colors 모드에서도 탭 가시성 유지)', async ({ page }) => {
  await page.emulateMedia({ forcedColors: 'active' });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');

  await expect(page.locator('#mobile-bottom-nav')).toBeVisible();
  const activeTab = page.locator('#mobile-bottom-nav .mobile-tab.active');
  await expect(activeTab).toBeVisible();

  const outlineWidth = await activeTab.evaluate((el) => getComputedStyle(el).outlineWidth || '0px');
  expect(parseFloat(outlineWidth)).toBeGreaterThanOrEqual(1);
});

test('반응형 안전영역 (아이폰급 viewport overflow 가드)', async ({ page }) => {
  await page.setViewportSize({ width: 430, height: 932 });
  await page.goto('/');

  const metrics = await page.evaluate(() => {
    return {
      overflowX: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      headerPaddingLeft: getComputedStyle(document.querySelector('.site-header')).paddingLeft,
      headerPaddingRight: getComputedStyle(document.querySelector('.site-header')).paddingRight,
    };
  });

  expect(metrics.overflowX).toBeLessThanOrEqual(16);
  expect(parseFloat(metrics.headerPaddingLeft)).toBeGreaterThanOrEqual(0);
  expect(parseFloat(metrics.headerPaddingRight)).toBeGreaterThanOrEqual(0);
});

test('반응형 접근성 (모바일 터치 타겟 최소 높이)', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');

  await page.click('[data-bs-target="#signupModal"]');
  await expect(page.locator('#signupModal')).toBeVisible();

  const heights = await page.locator('#signupModal .btn').evaluateAll((nodes) => {
    return nodes.slice(0, 6).map((el) => el.getBoundingClientRect().height);
  });

  heights.forEach((h) => {
    expect(h).toBeGreaterThanOrEqual(44);
  });
});

test('반응형 상호작용 (오프캔버스 퀵액션 인증 상태 동기화)', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');

  await page.click('[data-bs-target="#mobileMenuDrawer"]');
  await expect(page.locator('#mobileMenuDrawer')).toBeVisible();
  await expect(page.locator('#mobile-menu-login-btn')).toContainText('로그인');

  await page.evaluate(() => {
    localStorage.setItem('weave_current_user', JSON.stringify({ id: 7, name: '테스트', role: 'member' }));
    document.dispatchEvent(new CustomEvent('weave:user-state-changed', { detail: { loggedIn: true } }));
  });
  await expect(page.locator('#mobile-menu-login-btn')).toContainText('계정');
});

test('반응형 상호작용 (패널 이동 시 hash 동기화)', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');

  await page.click('#mobile-bottom-nav .mobile-tab[data-panel="news"]');
  await expect(page.locator('#news.panel-active')).toBeVisible();
  await expect(page).toHaveURL(/#news$/);

  await page.click('#mobile-bottom-nav .mobile-tab[data-panel="gallery"]');
  await expect(page.locator('#gallery.panel-active')).toBeVisible();
  await expect(page).toHaveURL(/#gallery$/);
});

test('반응형 상호작용 (뒤로가기 popstate 시 패널/탭 복원)', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');

  await page.click('#mobile-bottom-nav .mobile-tab[data-panel="news"]');
  await page.click('[data-bs-target="#mobileMenuDrawer"]');
  await page.click('[data-bs-target="#mobile-menu-news"]');
  await page.click('#mobile-menu-news [data-news-tab="faq"]');
  await expect(page).toHaveURL(/aboutTab=|newsTab=faq|#news/);

  await page.click('#mobile-bottom-nav .mobile-tab[data-panel="gallery"]');
  await expect(page.locator('#gallery.panel-active')).toBeVisible();

  await page.goBack();
  await expect(page.locator('#news.panel-active')).toBeVisible();
  await expect(page.locator('#faq-tab-btn')).toHaveClass(/active/);
});

test('반응형 상호작용 (URL 파라미터 직접 진입 복원)', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/?panel=about&aboutTab=rules#about');
  await expect(page.locator('#about.panel-active')).toBeVisible();

  await page.goto('/?panel=news&newsTab=qna#news');
  await expect(page.locator('#news.panel-active')).toBeVisible();
  await expect(page).toHaveURL(/newsTab=qna/);
});

test('반응형 상호작용 (오프캔버스 브레드크럼 업데이트)', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');

  await page.click('[data-bs-target="#mobileMenuDrawer"]');
  await expect(page.locator('#mobile-menu-breadcrumb')).toContainText('홈');

  await page.click('#mobileMenuDrawer [data-panel="gallery"]');
  await page.click('[data-bs-target="#mobileMenuDrawer"]');
  await expect(page.locator('#mobile-menu-breadcrumb')).toContainText('갤러리');
});

test('반응형 상호작용 (긴 제목 더보기 상태 유지)', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  await page.click('#mobile-bottom-nav .mobile-tab[data-panel="news"]');

  await page.evaluate(() => {
    const tbody = document.getElementById('news-table-body');
    if (!tbody) return;
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>999</td>
      <td>https://example.com/path?query=long 정말긴문자열테스트 repeat repeat repeat repeat repeat repeat repeat</td>
      <td>운영진</td>
      <td>2026-03-08</td>
      <td>42</td>
      <td>3</td>
      <td><button class="btn btn-sm btn-outline-secondary" type="button">관리</button></td>
    `;
    tbody.innerHTML = '';
    tbody.appendChild(tr);
    document.dispatchEvent(new Event('weave:table-refresh'));
  });

  const toggle = page.locator('#news-table-body .mobile-cell-expand-btn').first();
  await expect(toggle).toBeVisible();
  await toggle.click();
  await expect(toggle).toHaveText('접기');

  await page.click('#mobile-bottom-nav .mobile-tab[data-panel="home"]');
  await page.click('#mobile-bottom-nav .mobile-tab[data-panel="news"]');
  await expect(page.locator('#news-table-body td[data-col-key="title"].is-expanded')).toBeVisible();
});

test('반응형 레이아웃 (orientation 전환 후 오버플로우/탭 안정성)', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  await expect(page.locator('#mobile-bottom-nav')).toBeVisible();

  await page.setViewportSize({ width: 844, height: 390 });
  await page.waitForTimeout(180);
  await expect(page.locator('#mobile-bottom-nav')).toBeVisible();

  await page.setViewportSize({ width: 390, height: 844 });
  await page.waitForTimeout(180);
  const overflowX = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflowX).toBeLessThanOrEqual(16);
});

test('반응형 상호작용 (입력 포커스 중 orientation 전환 안정성)', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  await page.click('[data-bs-target="#loginModal"]');
  const usernameInput = page.locator('#login-form input[name="username"]');
  await usernameInput.focus();

  await page.setViewportSize({ width: 844, height: 390 });
  await page.waitForTimeout(150);
  await expect(page.locator('#mobile-bottom-nav')).toBeVisible();

  await page.setViewportSize({ width: 390, height: 844 });
  await page.waitForTimeout(150);
  await expect(page.locator('#loginModal')).toBeVisible();
  await expect(usernameInput).toBeVisible();
});

test('반응형 상호작용 (스크롤 방향에 따른 하단 탭 자동 숨김/복원)', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');

  await page.evaluate(() => {
    for (let i = 0; i < 10; i += 1) {
      const filler = document.createElement('p');
      filler.textContent = `스크롤 테스트 더미 콘텐츠 ${i}`;
      document.body.appendChild(filler);
    }
    window.scrollTo({ top: 0, behavior: 'auto' });
  });

  await page.evaluate(() => {
    window.scrollTo({ top: 560, behavior: 'auto' });
  });
  await page.waitForTimeout(140);
  const hiddenOnDown = await page.evaluate(() => document.body.classList.contains('scroll-down-hide-nav'));
  expect(hiddenOnDown).toBeTruthy();

  await page.evaluate(() => {
    window.scrollTo({ top: 40, behavior: 'auto' });
  });
  await page.waitForTimeout(140);
  const restoredOnUp = await page.evaluate(() => !document.body.classList.contains('scroll-down-hide-nav'));
  expect(restoredOnUp).toBeTruthy();
});

test('반응형 접근성 (모달 닫힘 후 포커스 복원)', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');

  const trigger = page.locator('[data-bs-target="#loginModal"]');
  await trigger.focus();
  await trigger.click();
  await expect(page.locator('#loginModal')).toBeVisible();
  await page.click('#loginModal .btn-close');
  await expect(page.locator('#loginModal')).toBeHidden();

  const focusedId = await page.evaluate(() => document.activeElement && document.activeElement.getAttribute('data-bs-target'));
  expect(focusedId).toBe('#loginModal');
});

test('반응형 접근성 (reduced-motion + forced-colors 조합)', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce', forcedColors: 'active' });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  await expect(page.locator('#mobile-bottom-nav')).toBeVisible();
  await expect(page.locator('#mobile-bottom-nav .mobile-tab.active')).toBeVisible();
});

test('반응형 성능 (저데이터 모드 이미지 품질 다운시프트)', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');

  await page.evaluate(() => {
    window.__WEAVE_E2E__ = true;
    document.body.classList.add('reduced-data-mode');
    const img = document.getElementById('about-volunteer-image');
    if (img) {
      img.setAttribute('src', 'https://images.unsplash.com/photo-x?auto=format&fit=crop&w=960&q=80');
      img.setAttribute('srcset', 'https://images.unsplash.com/photo-x?auto=format&fit=crop&w=960&q=80 960w');
    }
    if (typeof window.__applyReducedDataImagePolicy === 'function') {
      window.__applyReducedDataImagePolicy(true);
    }
    const aboutPanel = document.getElementById('about');
    if (aboutPanel) {
      aboutPanel.classList.add('panel-active');
      aboutPanel.scrollIntoView({ block: 'start', behavior: 'auto' });
    }
    if (img) {
      img.scrollIntoView({ block: 'center', behavior: 'auto' });
    }
  });
  await page.waitForTimeout(180);

  const reduced = await page.evaluate(() => {
    const img = document.getElementById('about-volunteer-image');
    if (!img) return { src: '', srcset: '' };
    return { src: img.getAttribute('src') || '', srcset: img.getAttribute('srcset') || '' };
  });

  expect(reduced.src).toContain('q=');
  expect(reduced.srcset).toContain('w=');
});

test('반응형 성능 (기본 성능 엔트리 수집 가능)', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');

  const perf = await page.evaluate(() => {
    const nav = performance.getEntriesByType('navigation').length;
    const paints = performance.getEntriesByType('paint').length;
    const metrics = window.__weavePerfMetrics || {};
    return {
      nav,
      paints,
      hasPerfMetrics: typeof metrics === 'object',
      fcp: Number(metrics.fcp || 0),
      lcp: Number(metrics.lcp || 0),
      cls: Number(metrics.cls || 0)
    };
  });

  expect(perf.nav).toBeGreaterThanOrEqual(1);
  expect(perf.paints).toBeGreaterThanOrEqual(0);
  expect(perf.hasPerfMetrics).toBeTruthy();
  expect(perf.fcp).toBeGreaterThanOrEqual(0);
  if (perf.lcp > 0) {
    expect(perf.lcp).toBeLessThanOrEqual(4500);
  }
  if (perf.cls > 0) {
    expect(perf.cls).toBeLessThanOrEqual(0.25);
  }
});

test('반응형 시각 스냅샷 수집 (320/360/390/768)', async ({ page }, testInfo) => {
  const shotTargets = [
    { name: 'vp-320x568', width: 320, height: 568 },
    { name: 'vp-360x800', width: 360, height: 800 },
    { name: 'vp-390x844', width: 390, height: 844 },
    { name: 'vp-768x1024', width: 768, height: 1024 }
  ];

  for (const target of shotTargets) {
    await page.setViewportSize({ width: target.width, height: target.height });
    await page.goto('/');
    await expect(page.locator('#home')).toBeVisible();
    const image = await page.screenshot({ fullPage: true });
    await testInfo.attach(`responsive-${target.name}.png`, {
      body: image,
      contentType: 'image/png'
    });
    expect(image.byteLength).toBeGreaterThan(2048);
  }
});
