function getCalendarMonthLabel(baseDate = calendarBaseDate) {
  return `${baseDate.getFullYear()}년 ${baseDate.getMonth() + 1}월`;
}

function toSafeActivityId(value) {
  const id = Number(value);
  return Number.isFinite(id) && id > 0 ? id : 0;
}

function toSafeDateKey(value) {
  const raw = String(value || '').trim();
  return /^\d{4}-\d{2}-\d{2}$/.test(raw) ? raw : '';
}

function movePanel(panelId) {
  const nextPanelId = String(panelId || '').trim() || 'home';
  const previousActive = document.querySelector('.panel-active');
  if (previousActive && previousActive.id) {
    try {
      const scrollY = Math.max(0, window.scrollY || window.pageYOffset || 0);
      sessionStorage.setItem(`weave:panel-scroll:${previousActive.id}`, String(scrollY));
    } catch (e) {
      // QuotaExceeded 등 예외 무시
    }
  }
  document.querySelectorAll('[class*="panel"]').forEach(p => p.classList.remove('panel-active'));
  const target = document.getElementById(nextPanelId);
  if (target) target.classList.add('panel-active');
  const statsSection = document.getElementById('home-stats');
  const homeCalendarPreview = document.getElementById('home-calendar-preview');
  const homeNoticeCarousel = document.getElementById('home-notice-carousel');
  if (statsSection) statsSection.style.display = nextPanelId === 'home' ? 'block' : 'none';
  if (homeCalendarPreview) homeCalendarPreview.style.display = nextPanelId === 'home' ? 'block' : 'none';
  if (homeNoticeCarousel) homeNoticeCarousel.style.display = nextPanelId === 'home' && getHomeNoticeItems().length ? 'block' : 'none';
  if (document.body) document.body.classList.toggle('panel-home-active', nextPanelId === 'home');
  if (nextPanelId === 'home' && !homeNoticePaused) {
    startHomeNoticeAutoRotate();
  } else {
    stopHomeNoticeAutoRotate();
  }
  setActiveNavStates(nextPanelId);
  if (typeof updateAppUrlState === 'function') {
    updateAppUrlState({ panel: nextPanelId });
  }
  document.dispatchEvent(new CustomEvent('weave:panel-changed', {
    detail: {
      panel: nextPanelId,
      newsTab: String(currentNewsTab || 'notice')
    }
  }));
  const isMobile = window.matchMedia && window.matchMedia('(max-width: 768px)').matches;
  if (isMobile) {
    window.scrollTo({ top: 0, behavior: 'smooth' });
    return;
  }
  let restoreTop = 0;
  try {
    const raw = sessionStorage.getItem(`weave:panel-scroll:${nextPanelId}`);
    const parsed = Number(raw || 0);
    restoreTop = Number.isFinite(parsed) && parsed >= 0 ? parsed : 0;
  } catch (e) {
    restoreTop = 0;
  }
  window.scrollTo({ top: restoreTop, behavior: 'auto' });
}

function activateNewsTab(tabName) {
  const noticeTabBtn = document.getElementById('notice-tab-btn');
  const faqTabBtn = document.getElementById('faq-tab-btn');
  const qnaTabBtn = document.getElementById('qna-tab-btn');
  if (tabName === 'faq' && faqTabBtn instanceof HTMLElement) {
    faqTabBtn.click();
    return;
  }
  if (tabName === 'qna' && qnaTabBtn instanceof HTMLElement) {
    qnaTabBtn.click();
    return;
  }
  if (noticeTabBtn instanceof HTMLElement) noticeTabBtn.click();
}

function openQnaAnswerEditor(id) {
  const user = getCurrentUser();
  if (!isStaffUser(user)) {
    notifyMessage('Q&A 답변은 운영자만 작성할 수 있습니다.');
    return;
  }
  const data = getContent();
  const qnaId = toSafeActivityId(id);
  const item = (data.qna || []).find((q) => toSafeActivityId(q.id) === qnaId);
  if (!item) return;

  currentQnaAnswerId = qnaId;
  const editIdEl = document.getElementById('qna-answer-edit-id');
  const metaEl = document.getElementById('qna-answer-meta');
  const questionEl = document.getElementById('qna-answer-question');
  if (editIdEl) editIdEl.value = String(qnaId);
  if (metaEl) metaEl.textContent = `${item.author || '-'} | ${item.date || ''}`;
  if (questionEl) questionEl.innerHTML = sanitizeRichHtml(item.content || '');
  setEditorHtml('qna-answer-editor', item.answer || '');
  movePanel('qna-answer');
}

function openActivitiesCalendarTab() {
  const overviewPane = document.getElementById('activities-overview-pane');
  const calendarPane = document.getElementById('activities-calendar-pane');
  const overviewBtn = document.getElementById('activities-overview-tab-btn');
  const calendarBtn = document.getElementById('activities-calendar-tab-btn');
  if (overviewPane) overviewPane.classList.add('d-none');
  if (calendarPane) calendarPane.classList.remove('d-none');
  if (overviewBtn) {
    overviewBtn.classList.remove('active', 'btn-primary');
    overviewBtn.classList.add('btn-outline-primary');
  }
  if (calendarBtn) {
    calendarBtn.classList.add('active', 'btn-primary');
    calendarBtn.classList.remove('btn-outline-primary');
  }
  updateCalendarCreateVisibility();
}

function openActivitiesOverviewTab() {
  const overviewPane = document.getElementById('activities-overview-pane');
  const calendarPane = document.getElementById('activities-calendar-pane');
  const overviewBtn = document.getElementById('activities-overview-tab-btn');
  const calendarBtn = document.getElementById('activities-calendar-tab-btn');
  if (overviewPane) overviewPane.classList.remove('d-none');
  if (calendarPane) calendarPane.classList.add('d-none');
  if (overviewBtn) {
    overviewBtn.classList.add('active', 'btn-primary');
    overviewBtn.classList.remove('btn-outline-primary');
  }
  if (calendarBtn) {
    calendarBtn.classList.remove('active', 'btn-primary');
    calendarBtn.classList.add('btn-outline-primary');
  }
}

function updateCalendarModeButtons() {
  return;
}

function toIsoFromDatetimeLocal(value) {
  if (!value) return '';
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return '';
  return dt.toISOString();
}

function toDatetimeLocal(value) {
  if (!value) return '';
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return '';
  const y = dt.getFullYear();
  const m = String(dt.getMonth() + 1).padStart(2, '0');
  const d = String(dt.getDate()).padStart(2, '0');
  const hh = String(dt.getHours()).padStart(2, '0');
  const mm = String(dt.getMinutes()).padStart(2, '0');
  return `${y}-${m}-${d}T${hh}:${mm}`;
}

function updateCalendarCreateVisibility() {
  const card = document.getElementById('calendar-create-card');
  const user = getCurrentUser();
  if (!card) return;
  card.classList.toggle('d-none', !(user && user.status === 'active' && isStaffUser(user)));
  const form = document.getElementById('calendar-create-form');
  if (form && user) {
    form.manager.value = user.name || user.username || '';
  }
}

async function loadActivitiesCalendar() {
  const dateParam = formatDateOnly(calendarBaseDate);
  let data = null;

  try {
    data = await apiRequest(`/activities?view=month&date=${dateParam}`, { method: 'GET' });
    const baseItems = Array.isArray(data.items) ? data.items : [];
    calendarActivities = [...baseItems]
      .filter((item) => {
        const key = toSafeDateKey(formatDateOnly(item?.startAt));
        return key && key.slice(0, 7) === dateParam.slice(0, 7);
      })
      .sort((a, b) => new Date(a?.startAt).getTime() - new Date(b?.startAt).getTime());
  } catch (_) {
    calendarActivities = [];
    data = { range: null };
  }
  renderActivitiesCalendarGrid(data.range || null);
  if (!calendarSelectedDate) {
    calendarSelectedDate = dateParam;
  }
  await renderActivitiesDayList(calendarSelectedDate);
  renderHomeCalendarPreview();
}

function renderActivitiesCalendarGrid(range) {
  const grid = document.getElementById('calendar-grid');
  const label = document.getElementById('calendar-current-label');
  if (!grid || !label) return;

  const monthLabel = getCalendarMonthLabel(calendarBaseDate);
  label.innerText = monthLabel;

  const mapByDate = {};
  calendarActivities.forEach((item) => {
    const key = toSafeDateKey(formatDateOnly(item?.startAt));
    if (!key) return;
    if (!mapByDate[key]) mapByDate[key] = [];
    mapByDate[key].push(item);
  });

  const dayNames = ['일', '월', '화', '수', '목', '금', '토'];
  const headers = dayNames.map(name => `<div class="weave-calendar-cell header">${name}</div>`).join('');

  const buildDayCell = (dayNumber, key, items) => {
    const selected = calendarSelectedDate === key ? 'selected' : '';
    const hasActivity = items.length > 0 ? 'has-activity' : '';
    const title = items.length > 0
      ? (items.length > 1 ? `${items[0].title || '제목 없음'} 외 ${items.length - 1}건` : (items[0].title || '제목 없음'))
      : '';
    return `<button class="weave-calendar-cell day ${selected} ${hasActivity}" data-date="${key}"><span class="day-main"><span class="day-num">${dayNumber}</span><span class="day-title">${escapeHtml(title)}</span></span><span class="day-count">${items.length ? `${items.length}건` : ''}</span></button>`;
  };

  let cells = '';
  const first = new Date(calendarBaseDate.getFullYear(), calendarBaseDate.getMonth(), 1);
  const last = new Date(calendarBaseDate.getFullYear(), calendarBaseDate.getMonth() + 1, 0);
  const firstDay = first.getDay();
  const totalDays = last.getDate();
  for (let i = 0; i < firstDay; i++) {
    cells += '<div class="weave-calendar-cell empty"></div>';
  }
  for (let day = 1; day <= totalDays; day++) {
    const current = new Date(calendarBaseDate.getFullYear(), calendarBaseDate.getMonth(), day);
    const key = formatDateOnly(current);
    const items = mapByDate[key] || [];
    cells += buildDayCell(day, key, items);
  }

  grid.innerHTML = `<div class="weave-calendar-table">${headers}${cells}</div>`;
  grid.querySelectorAll('[data-date]').forEach(btn => {
    btn.addEventListener('click', async () => {
      const dateKey = toSafeDateKey(btn.dataset.date);
      if (!dateKey) return;
      calendarSelectedDate = dateKey;
      const dateItems = mapByDate[dateKey] || [];
      renderActivitiesCalendarGrid(range);
      await renderActivitiesDayList(calendarSelectedDate);
      await openCalendarDatePopup(dateKey, dateItems);
    });
  });
}

function getModalInstanceById(modalId) {
  const modalEl = document.getElementById(modalId);
  if (!modalEl || typeof bootstrap === 'undefined' || !bootstrap.Modal) return null;
  return bootstrap.Modal.getInstance(modalEl) || new bootstrap.Modal(modalEl);
}

function buildActivityActionButtons(item, user, currentStatus) {
  return '';
}

async function getMyActivityHistoryMap(user = getCurrentUser()) {
  const map = {};
  if (!user || user.status !== 'active') return map;
  try {
    const my = await apiRequest('/me/history', { method: 'GET' });
    (my.items || []).forEach(entry => {
      map[String(entry.activityId)] = entry.status;
    });
  } catch (_) {}
  return map;
}

function buildActivityDetailMarkup(item, user, status = '', extraClass = '') {
  const statusLabel = status ? `<span class="badge text-bg-light border">${status}</span>` : '';
  const descriptionHtml = sanitizeRichHtml(item.description || '');
  return `
    <div class="border rounded p-3 bg-white${extraClass}">
      <div class="d-flex justify-content-between align-items-start gap-2">
        <div>
          <div class="fw-bold">${escapeHtml(item.title || '제목 없음')}</div>
          <div class="small text-muted">${formatKoreanDate(item.startAt)} ~ ${formatKoreanDate(item.endAt)}</div>
        </div>
        ${statusLabel}
      </div>
      ${item.recurrenceGroupId ? `<div class="small mt-1"><span class="badge text-bg-light border">반복그룹: ${escapeHtml(item.recurrenceGroupId)}</span></div>` : ''}
      <div class="small mt-2">장소: ${escapeHtml(item.place || '-')} / 집결: ${escapeHtml(item.gatherTime || '-')} / 담당자: ${escapeHtml(item.manager || '-')} / 모집: ${item.recruitmentLimit || 0}명</div>
      <div class="small text-muted">준비물: ${escapeHtml(item.supplies || '-')}</div>
      ${descriptionHtml ? `<div class="small mt-2 activity-description-body">${descriptionHtml}</div>` : ''}
      ${buildActivityActionButtons(item, user, status)}
    </div>
  `;
}

function sanitizeRichHtml(rawHtml) {
  const wrapper = document.createElement('div');
  wrapper.innerHTML = String(rawHtml || '');
  wrapper.querySelectorAll('script,style,iframe,object,embed').forEach(node => node.remove());
  wrapper.querySelectorAll('*').forEach((node) => {
    Array.from(node.attributes || []).forEach((attr) => {
      const attrName = String(attr.name || '').toLowerCase();
      const attrValue = String(attr.value || '').trim();
      if (attrName.startsWith('on')) node.removeAttribute(attr.name);
      if ((attrName === 'href' || attrName === 'src') && /^javascript:/i.test(attrValue)) {
        node.removeAttribute(attr.name);
      }
    });
  });
  return wrapper.innerHTML;
}

function openCalendarActivityDetailModal(item, user, status = '') {
  const body = document.getElementById('calendar-activity-detail-body');
  const leftActionWrap = document.getElementById('calendar-activity-action-left');
  const noticeBtn = document.getElementById('calendar-activity-notice-btn');
  const galleryBtn = document.getElementById('calendar-activity-gallery-btn');
  const editBtn = document.getElementById('calendar-activity-edit-btn');
  const deleteBtn = document.getElementById('calendar-activity-delete-btn');
  if (!body || !item) return;
  const activityId = toSafeActivityId(item.id);
  const hasActionableId = Number.isFinite(activityId) && activityId > 0;
  body.innerHTML = buildActivityDetailMarkup(item, user, status);
  if (leftActionWrap) {
    leftActionWrap.innerHTML = '';
    const canApply = !!(hasActionableId && item.sourceType !== 'notice' && user && user.status === 'active' && (!status || ['cancelled', 'noshow'].includes(status)));
    const canCancel = !!(hasActionableId && item.sourceType !== 'notice' && user && user.status === 'active' && ['waiting', 'confirmed'].includes(status || ''));
    const canBulkCancel = !!(hasActionableId && item.sourceType !== 'notice' && user && user.status === 'active' && isStaffUser(user) && item.recurrenceGroupId);

    if (canApply) {
      const applyBtn = document.createElement('button');
      applyBtn.type = 'button';
      applyBtn.className = 'btn btn-sm btn-primary';
      applyBtn.textContent = '신청';
      applyBtn.addEventListener('click', async () => {
        await applyActivity(activityId);
      });
      leftActionWrap.appendChild(applyBtn);
    }
    if (canCancel) {
      const cancelBtn = document.createElement('button');
      cancelBtn.type = 'button';
      cancelBtn.className = 'btn btn-sm btn-outline-danger';
      cancelBtn.textContent = '취소';
      cancelBtn.addEventListener('click', async () => {
        await cancelActivity(activityId);
      });
      leftActionWrap.appendChild(cancelBtn);
    }
    if (canBulkCancel) {
      const bulkCancelBtn = document.createElement('button');
      bulkCancelBtn.type = 'button';
      bulkCancelBtn.className = 'btn btn-sm btn-outline-warning';
      bulkCancelBtn.textContent = '반복 일괄취소';
      bulkCancelBtn.addEventListener('click', async () => {
        await openRecurrenceCancelModal(String(item.recurrenceGroupId || ''));
      });
      leftActionWrap.appendChild(bulkCancelBtn);
    }
  }

  const canManageActivity = !!(hasActionableId && user && user.status === 'active' && isStaffUser(user) && item.sourceType !== 'notice');
  if (editBtn) {
    editBtn.classList.toggle('d-none', !canManageActivity);
    editBtn.onclick = canManageActivity
      ? (() => {
          startEditCalendarActivity({ ...item, id: activityId });
        })
      : null;
  }
  if (deleteBtn) {
    deleteBtn.classList.toggle('d-none', !canManageActivity);
    deleteBtn.onclick = canManageActivity
      ? (() => {
          deleteCalendarActivity(activityId);
        })
      : null;
  }
  if (noticeBtn) {
    const isNoticeSource = item && item.sourceType === 'notice' && Number(item.sourceNoticeId || 0) > 0;
    noticeBtn.classList.toggle('d-none', !isNoticeSource);
    noticeBtn.onclick = () => {
      const detailModal = getModalInstanceById('calendarActivityDetailModal');
      if (detailModal) detailModal.hide();
      const noticeId = toSafeActivityId(item.sourceNoticeId);
      if (noticeId && typeof openNotice === 'function') openNotice(noticeId);
    };
  }
  if (galleryBtn) {
    const galleryItems = (getContent().gallery || []);
    const linkedGallery = galleryItems
      .filter((entry) => toSafeActivityId(entry.activityId || entry.activity_id) === activityId)
      .sort((a, b) => Number(b.id || 0) - Number(a.id || 0))[0] || null;
    galleryBtn.classList.toggle('d-none', !linkedGallery);
    galleryBtn.onclick = linkedGallery
      ? (() => {
          const detailModal = getModalInstanceById('calendarActivityDetailModal');
          if (detailModal) detailModal.hide();
          setTimeout(() => {
            const galleryId = toSafeActivityId(linkedGallery.id);
            if (galleryId && typeof openGalleryDetail === 'function') openGalleryDetail(galleryId);
          }, 160);
        })
      : null;
  }
  const detailModal = getModalInstanceById('calendarActivityDetailModal');
  if (detailModal) detailModal.show();
}

function openCalendarActivityListModal(dateKey, items, user, historyMap) {
  const titleEl = document.getElementById('calendar-activity-list-title');
  const listEl = document.getElementById('calendar-activity-list');
  if (!titleEl || !listEl) return;

  titleEl.innerText = `${dateKey} 일정 목록 (${items.length}건)`;
  listEl.innerHTML = items.map(item => `
    <button class="btn btn-outline-primary text-start" data-calendar-activity-id="${toSafeActivityId(item.id)}">
      <div class="fw-semibold">${escapeHtml(item.title || '제목 없음')}</div>
      <div class="small text-muted">${formatKoreanDate(item.startAt)} ~ ${formatKoreanDate(item.endAt)}</div>
    </button>
  `).join('');

  const listModal = getModalInstanceById('calendarActivityListModal');
  if (listModal) listModal.show();

  const itemMap = {};
  items.forEach(item => {
    itemMap[String(toSafeActivityId(item.id))] = item;
  });

  listEl.querySelectorAll('[data-calendar-activity-id]').forEach(btn => {
    btn.addEventListener('click', () => {
      const selected = itemMap[String(toSafeActivityId(btn.dataset.calendarActivityId))];
      if (!selected) return;
      const status = historyMap[String(selected.id)] || '';
      if (listModal) listModal.hide();
      setTimeout(() => {
        openCalendarActivityDetailModal(selected, user, status);
      }, 160);
    });
  });
}

async function openCalendarDatePopup(dateKey, items) {
  if (!Array.isArray(items) || !items.length) return;
  const user = getCurrentUser();
  const historyMap = await getMyActivityHistoryMap(user);
  if (items.length === 1) {
    const onlyItem = items[0];
    openCalendarActivityDetailModal(onlyItem, user, historyMap[String(onlyItem.id)] || '');
    return;
  }
  openCalendarActivityListModal(dateKey, items, user, historyMap);
}

async function renderActivitiesDayList(dateKey) {
  const dayDetail = document.getElementById('calendar-day-detail');
  const dayList = document.getElementById('calendar-day-list');
  if (!dayDetail || !dayList) return;

  const safeDateKey = toSafeDateKey(dateKey) || formatDateOnly(calendarSelectedDate || new Date());
  dayDetail.innerText = `${safeDateKey} 일정`;
  const user = getCurrentUser();
  const items = calendarActivities.filter((item) => toSafeDateKey(formatDateOnly(item.startAt)) === safeDateKey);
  if (!items.length) {
    dayList.innerHTML = '<div class="text-muted small">등록된 활동이 없습니다.</div>';
    return;
  }

  const myHistoryMap = await getMyActivityHistoryMap(user);

  dayList.innerHTML = items.map(item => {
    const status = myHistoryMap[String(toSafeActivityId(item.id))] || '';
    const highlightClass = focusedActivityDateKey && formatDateOnly(item.startAt) === focusedActivityDateKey
      ? ' activity-focus-highlight'
      : '';
    return buildActivityDetailMarkup(item, user, status, highlightClass);
  }).join('');

  if (focusedActivityDateKey === dateKey) {
    setTimeout(() => {
      dayList.querySelectorAll('.activity-focus-highlight').forEach(el => {
        el.classList.remove('activity-focus-highlight');
      });
      focusedActivityDateKey = '';
    }, 2500);
  }
}

async function applyActivity(activityId) {
  const id = toSafeActivityId(activityId);
  if (!id) return;
  try {
    const data = await apiRequest(`/activities/${id}/apply`, { method: 'POST' });
    notifyMessage(`신청 완료 (${data.status})`);
    await loadActivitiesCalendar();
  } catch (error) {
    notifyMessage(error.message || '신청에 실패했습니다.');
  }
}

async function cancelActivity(activityId) {
  const id = toSafeActivityId(activityId);
  if (!id) return;
  try {
    await apiRequest(`/activities/${id}/cancel`, { method: 'POST' });
    notifyMessage('신청을 취소했습니다.');
    await loadActivitiesCalendar();
  } catch (error) {
    notifyMessage(error.message || '취소에 실패했습니다.');
  }
}

function renderHomeCalendarPreview() {
  const monthLabelEl = document.getElementById('home-calendar-current-label');
  const summaryEl = document.getElementById('home-calendar-summary');
  const listEl = document.getElementById('home-calendar-list');
  const miniGrid = document.getElementById('home-calendar-mini-grid');
  if (!summaryEl || !listEl) return;

  // 데이터가 없거나 에러일 때 안내 메시지
  if (!Array.isArray(calendarActivities) || calendarActivities.length === 0) {
    summaryEl.innerHTML = '<div class="alert alert-warning mb-2">이번 달 활동 데이터가 없습니다. 관리자에게 문의해 주세요.</div>';
    listEl.innerHTML = '';
    if (miniGrid) miniGrid.innerHTML = '';
    return;
  }

  if (monthLabelEl) {
    monthLabelEl.innerText = getCalendarMonthLabel(calendarBaseDate);
  }

  if (miniGrid) {
    const mapByDate = {};
    calendarActivities.forEach(item => {
      const key = toSafeDateKey(formatDateOnly(item.startAt));
      if (!key) return;
      if (!mapByDate[key]) mapByDate[key] = [];
      mapByDate[key].push(item);
    });
    const base = new Date(calendarBaseDate.getFullYear(), calendarBaseDate.getMonth(), 1);
    const firstDay = base.getDay();
    const totalDays = new Date(base.getFullYear(), base.getMonth() + 1, 0).getDate();
    let cells = '';
    for (let i = 0; i < firstDay; i++) {
      cells += '<div class="weave-calendar-cell empty"></div>';
    }
    for (let day = 1; day <= totalDays; day++) {
      const current = new Date(base.getFullYear(), base.getMonth(), day);
      const key = formatDateOnly(current);
      const items = mapByDate[key] || [];
      const title = items.length > 0
        ? (items.length > 1 ? `${items[0].title || '제목 없음'} 외 ${items.length - 1}건` : (items[0].title || '제목 없음'))
        : '';
      const hasActivity = items.length > 0 ? 'has-activity' : '';
      if (items.length > 0) {
        cells += `<button class="weave-calendar-cell day ${hasActivity}" data-home-calendar-date="${key}"><span class="day-main"><span class="day-num">${day}</span><span class="day-title">${escapeHtml(title)}</span></span><span class="day-count">${items.length}건</span></button>`;
      } else {
        cells += `<div class="weave-calendar-cell day"><span class="day-main"><span class="day-num">${day}</span><span class="day-title"></span></span><span class="day-count"></span></div>`;
      }
    }
    miniGrid.innerHTML = `<div class="weave-calendar-table">${['일','월','화','수','목','금','토'].map(name => `<div class="weave-calendar-cell header">${name}</div>`).join('')}${cells}</div>`;
    miniGrid.querySelectorAll('[data-home-calendar-date]').forEach(btn => {
      btn.addEventListener('click', async () => {
        const dateKey = toSafeDateKey(btn.dataset.homeCalendarDate);
        if (!dateKey) return;
        const items = mapByDate[dateKey] || [];
        calendarSelectedDate = dateKey;
        await openCalendarDatePopup(dateKey, items);
      });
    });
  }

  const upcoming = [...calendarActivities]
    .sort((a, b) => new Date(a.startAt).getTime() - new Date(b.startAt).getTime())
    .slice(0, 5);

  summaryEl.innerText = `이번 기간 활동 ${calendarActivities.length}건`;
  if (!upcoming.length) {
    listEl.innerHTML = '<div class="text-muted small">예정된 활동이 없습니다.</div>';
    return;
  }

  listEl.innerHTML = upcoming.map(item => `
    <button class="btn btn-light text-start border" data-home-activity-date="${toSafeDateKey(formatDateOnly(item.startAt))}">
      <div class="fw-semibold">${escapeHtml(item.title || '제목 없음')}</div>
      <div class="small text-muted">${escapeHtml(formatKoreanDate(item.startAt))} · ${escapeHtml(item.place || '-')}</div>
    </button>
  `).join('');

  listEl.querySelectorAll('[data-home-activity-date]').forEach(btn => {
    btn.addEventListener('click', async () => {
      const selectedDate = toSafeDateKey(btn.dataset.homeActivityDate);
      if (!selectedDate) return;
      movePanel('activities');
      openActivitiesCalendarTab();
      calendarSelectedDate = selectedDate;
      await loadActivitiesCalendar();
    });
  });
}

function getHomeNoticeItems() {
  const content = getContent();
  return (content.news || [])
    .filter(item => (item.postTab || 'notice') === 'notice' && !!item.featuredOnHome)
    .sort((a, b) => Number(b.id || 0) - Number(a.id || 0))
    .slice(0, 5);
}

function stopHomeNoticeAutoRotate() {
  if (homeNoticeTimer) {
    clearInterval(homeNoticeTimer);
    homeNoticeTimer = null;
  }
}

function startHomeNoticeAutoRotate() {
  stopHomeNoticeAutoRotate();
  if (homeNoticePaused || homeNoticeItems.length <= 1) return;
  homeNoticeTimer = setInterval(() => {
    homeNoticeIndex = (homeNoticeIndex + 1) % homeNoticeItems.length;
    renderHomeNoticeCarousel();
  }, 6000);
}

function renderHomeNoticeCarousel() {
  const track = document.getElementById('home-notice-track');
  const dots = document.getElementById('home-notice-dots');
  const toggleBtn = document.getElementById('home-notice-toggle-btn');
  const section = document.getElementById('home-notice-carousel');
  if (!track || !dots || !toggleBtn) return;

  homeNoticeItems = getHomeNoticeItems();
  const homePanel = document.getElementById('home');
  const isHomePanelActive = !!(homePanel && homePanel.classList.contains('panel-active'));
  if (section) section.style.display = isHomePanelActive && homeNoticeItems.length ? 'block' : 'none';
  if (!homeNoticeItems.length) {
    track.innerHTML = '<div class="alert alert-warning mb-2">홈에 노출할 공지 데이터가 없습니다.</div>';
    dots.innerHTML = '';
    toggleBtn.textContent = homeNoticePaused ? '재생' : '일시정지';
    stopHomeNoticeAutoRotate();
    return;
  }
  if (homeNoticeIndex >= homeNoticeItems.length) homeNoticeIndex = 0;
  const current = homeNoticeItems[homeNoticeIndex];
  const contentPreview = stripHtml(current.content || '').slice(0, 100);
  track.innerHTML = `
    <button type="button" class="btn btn-link text-start p-0 w-100" data-home-notice-open="${current.id}">
      <div class="fw-semibold">${escapeHtml(current.title || '제목 없음')}</div>
      ${contentPreview ? `<div class="small text-muted mt-1">${escapeHtml(contentPreview)}${contentPreview.length >= 100 ? '…' : ''}</div>` : ''}
      <div class="small text-muted mt-1">${escapeHtml(formatAuthorDisplay(current.author || '관리자', getCurrentUser()))} · ${escapeHtml(current.date || '')}</div>
    </button>
  `;
  const openBtn = track.querySelector('[data-home-notice-open]');
  if (openBtn) {
    openBtn.addEventListener('click', () => {
      goToNoticeFromHome(Number(current.id || 0));
    });
  }

  dots.innerHTML = homeNoticeItems.map((_, idx) => {
    const activeClass = idx === homeNoticeIndex ? 'btn-primary' : 'btn-outline-secondary';
    return `<button type="button" class="btn btn-sm ${activeClass}" data-home-notice-dot="${idx}" aria-label="공지 ${idx + 1}"></button>`;
  }).join('');
  dots.querySelectorAll('[data-home-notice-dot]').forEach(btn => {
    btn.addEventListener('click', () => {
      homeNoticeIndex = Number(btn.dataset.homeNoticeDot || 0);
      renderHomeNoticeCarousel();
      if (!homeNoticePaused) startHomeNoticeAutoRotate();
    });
  });

  toggleBtn.textContent = homeNoticePaused ? '재생' : '일시정지';
  if (!homeNoticePaused) startHomeNoticeAutoRotate();
}

function stripHtml(value) {
  const div = document.createElement('div');
  div.innerHTML = String(value || '');
  return (div.textContent || div.innerText || '').replace(/\s+/g, ' ').trim();
}

function goToNoticeFromHome(id) {
  const noticeId = toSafeActivityId(id);
  if (!noticeId) return;
  movePanel('news');
  activateNewsTab('notice');
  if (typeof openNotice === 'function') openNotice(noticeId);
}

async function focusCalendarDate(dateValue) {
  if (!dateValue) return;
  const target = new Date(dateValue);
  if (Number.isNaN(target.getTime())) return;

  calendarBaseDate = new Date(target.getFullYear(), target.getMonth(), 1);
  calendarSelectedDate = formatDateOnly(target);
  focusedActivityDateKey = calendarSelectedDate;
  movePanel('activities');
  openActivitiesCalendarTab();
  await loadActivitiesCalendar();
}

async function openCalendarActivityFromGallery(activityId, fallbackDate = '') {
  const targetId = Number(activityId || 0);
  if (!Number.isFinite(targetId) || targetId <= 0) return;
  const target = calendarActivities.find(item => Number(item.id || 0) === targetId);
  if (!target) {
    const parsedFallback = fallbackDate ? new Date(fallbackDate) : null;
    calendarBaseDate = parsedFallback && !Number.isNaN(parsedFallback.getTime())
      ? new Date(parsedFallback.getFullYear(), parsedFallback.getMonth(), 1)
      : new Date();
    await loadActivitiesCalendar();
  }
  const resolved = calendarActivities.find(item => Number(item.id || 0) === targetId);
  if (!resolved) {
    notifyMessage('연동된 봉사 일정을 찾을 수 없습니다.');
    return;
  }
  const startAt = new Date(resolved.startAt);
  calendarBaseDate = new Date(startAt.getFullYear(), startAt.getMonth(), 1);
  calendarSelectedDate = formatDateOnly(resolved.startAt);
  focusedActivityDateKey = calendarSelectedDate;
  movePanel('activities');
  openActivitiesCalendarTab();
  await loadActivitiesCalendar();
  const user = getCurrentUser();
  const historyMap = await getMyActivityHistoryMap(user);
  openCalendarActivityDetailModal(resolved, user, historyMap[String(resolved.id)] || '');
}

async function loadOpsDashboard(page = opsPendingPage) {
  opsPendingPage = Math.max(1, Number(page) || 1);
  try {
    const [dash, pending] = await Promise.all([
      apiRequest('/admin/dashboard', { method: 'GET' }),
      apiRequest(`/admin/pending-users?page=${opsPendingPage}&pageSize=${OPS_PENDING_PAGE_SIZE}&sortBy=${encodeURIComponent(opsPendingSortBy)}&sortDir=${encodeURIComponent(opsPendingSortDir)}&q=${encodeURIComponent(opsPendingSearchKeyword || '')}`, { method: 'GET' })
    ]);
    const info = dash.dashboard || {};
    const setText = (id, value) => {
      const el = document.getElementById(id);
      if (el) el.innerText = String(value ?? 0);
    };
    setText('ops-card-today', info.todaySchedule);
    setText('ops-card-pending', info.pendingApprovals);
    setText('ops-card-waiting', info.waitingApplications);
    setText('ops-card-noshow', info.noshowCount);
    setText('ops-card-notices', info.scheduledNotices);
    setText('ops-card-qna', info.qnaUnanswered);
    setText('ops-card-expense', info.expenseAlerts);
    if (typeof getClientTelemetrySnapshot === 'function') {
      const telemetry = getClientTelemetrySnapshot();
      setText('ops-card-client-403', telemetry.errors403 || 0);
      setText('ops-card-client-429', telemetry.errors429 || 0);
      setText('ops-card-client-upload-fail', telemetry.uploadFailures || 0);
    }

    const rows = pending.items || [];
    const tbody = document.getElementById('ops-pending-users-body');
    const count = document.getElementById('ops-pending-count');
    const pagination = pending.pagination || {};
    const total = Number(pagination.total ?? rows.length);
    const pageNo = Number(pagination.page ?? opsPendingPage);
    const totalPages = Number(pagination.totalPages ?? 1);
    const sortBy = String(pagination.sortBy || opsPendingSortBy || 'id');
    const sortDir = String(pagination.sortDir || opsPendingSortDir || 'desc');
    const pager = document.getElementById('ops-pending-pagination');

    if (count) count.innerText = `${total}건`;
    opsPendingSortBy = sortBy;
    opsPendingSortDir = sortDir;
    opsPendingPage = pageNo;

    document.querySelectorAll('[data-ops-sort]').forEach(btn => {
      const key = btn.getAttribute('data-ops-sort') || '';
      const marker = key === sortBy ? (sortDir === 'asc' ? ' ▲' : ' ▼') : '';
      btn.textContent = `${btn.textContent.replace(/\s[▲▼]$/, '')}${marker}`;
    });

    if (pager) {
      pager.innerHTML = '';
      const appendPage = (label, disabled, targetPage, active = false) => {
        const li = document.createElement('li');
        li.className = `page-item ${disabled ? 'disabled' : ''} ${active ? 'active' : ''}`.trim();
        const a = document.createElement('a');
        a.className = 'page-link';
        a.href = '#';
        a.textContent = label;
        a.addEventListener('click', async (e) => {
          e.preventDefault();
          if (disabled) return;
          await loadOpsDashboard(targetPage);
        });
        li.appendChild(a);
        pager.appendChild(li);
      };

      appendPage('이전', pageNo <= 1, pageNo - 1);
      for (let pageIndex = 1; pageIndex <= totalPages; pageIndex++) {
        appendPage(String(pageIndex), false, pageIndex, pageIndex === pageNo);
      }
      appendPage('다음', pageNo >= totalPages, pageNo + 1);
    }

    if (tbody) {
      tbody.innerHTML = rows.length ? rows.map(user => `
        <tr>
          <td>${escapeHtml(user.name || '-')}</td>
          <td>${escapeHtml(user.username || '-')}</td>
          <td>${escapeHtml(user.generation || '-')}</td>
          <td>${escapeHtml(user.interests || '-')}</td>
          <td>${escapeHtml(user.status || '-')}</td>
          <td>
            <div class="d-flex gap-1">
              <button class="btn btn-sm btn-outline-success" onclick="approvePendingUser(${toSafeActivityId(user.id)}, 'member')">단원 승인</button>
              <button class="btn btn-sm btn-outline-primary" onclick="approvePendingUser(${toSafeActivityId(user.id)}, 'staff')">운영진 승인</button>
              <button class="btn btn-sm btn-outline-danger" onclick="rejectPendingUser(${toSafeActivityId(user.id)})">반려</button>
            </div>
          </td>
        </tr>
      `).join('') : '<tr><td colspan="6" class="text-center text-muted">승인 대기 사용자가 없습니다.</td></tr>';
    }
  } catch (error) {
    const tbody = document.getElementById('ops-pending-users-body');
    if (tbody) tbody.innerHTML = `<tr><td colspan="6" class="text-center text-danger">${error.message || '대시보드를 불러오지 못했습니다.'}</td></tr>`;
    const pager = document.getElementById('ops-pending-pagination');
    if (pager) pager.innerHTML = '';
  }
}

async function approvePendingUser(userId, role = 'member') {
  const id = toSafeActivityId(userId);
  if (!id) return;
  const nextRole = role === 'staff' ? 'staff' : 'member';
  if (!confirm('해당 사용자를 승인하시겠습니까?')) return;
  try {
    await apiRequest(`/admin/users/${id}/approve`, {
      method: 'POST',
      body: JSON.stringify({ role: nextRole })
    });
    await loadOpsDashboard(opsPendingPage);
  } catch (error) {
    notifyMessage(error.message || '승인에 실패했습니다.');
  }
}

async function rejectPendingUser(userId) {
  const id = toSafeActivityId(userId);
  if (!id) return;
  if (!confirm('해당 가입 신청을 반려하시겠습니까?')) return;
  try {
    await apiRequest(`/admin/users/${id}/reject`, { method: 'POST' });
    await loadOpsDashboard(opsPendingPage);
  } catch (error) {
    notifyMessage(error.message || '반려에 실패했습니다.');
  }
}

async function createActivityFromCalendar(event) {
  event.preventDefault();
  const user = getCurrentUser();
  if (!user || user.status !== 'active' || !isStaffUser(user)) {
    notifyMessage('운영진/관리자 권한이 필요합니다.');
    return;
  }

  const form = event.target;
  syncEditorToInput(form, 'activity-editor', { markRepresentative: true });
  const payload = {
    title: form.title.value.trim(),
    startAt: toIsoFromDatetimeLocal(form.startAt.value),
    endAt: toIsoFromDatetimeLocal(form.endAt.value),
    description: String(form.content?.value || '').trim(),
    place: form.place.value.trim(),
    gatherTime: form.gatherTime.value.trim(),
    supplies: form.supplies.value.trim(),
    manager: form.manager.value.trim() || (user.name || user.username || ''),
    recruitmentLimit: Number(form.recruitmentLimit.value || 0)
  };
  const repeatWeeks = Number(form.repeatWeeks.value || 0);
  const recurrenceGroupId = repeatWeeks > 0
    ? `grp_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
    : '';

  if (!payload.title || !payload.startAt || !payload.endAt) {
    notifyMessage('제목/시작/종료 시간을 입력해주세요.');
    return;
  }
  if (payload.title.length > 120) {
    notifyMessage('활동 제목은 120자 이하여야 합니다.');
    return;
  }
  if (new Date(payload.endAt).getTime() <= new Date(payload.startAt).getTime()) {
    notifyMessage('종료 시간은 시작 시간보다 늦어야 합니다.');
    return;
  }
  if (payload.recruitmentLimit < 0 || payload.recruitmentLimit > 1000) {
    notifyMessage('모집 인원은 0~1000 범위여야 합니다.');
    return;
  }
  if (repeatWeeks < 0 || repeatWeeks > 12) {
    notifyMessage('반복 주 수는 0~12 사이로 입력해주세요.');
    return;
  }

  try {
    if (editingActivityId) {
      await apiRequest(`/activities/${editingActivityId}`, {
        method: 'PUT',
        body: JSON.stringify(payload)
      });
      editingActivityId = null;
      const submitBtn = form.querySelector('button[type="submit"]');
      if (submitBtn) submitBtn.textContent = '등록';
      if (form.repeatWeeks) form.repeatWeeks.disabled = false;
      form.repeatWeeks.value = '0';
      calendarBaseDate = new Date(payload.startAt);
      calendarSelectedDate = formatDateOnly(payload.startAt);
      form.reset();
      setEditorHtml('activity-editor', '');
      if (form.content) form.content.value = '';
      if (form.activityAttachmentFiles) form.activityAttachmentFiles.value = '';
      form.manager.value = user.name || user.username || '';
      await loadActivitiesCalendar();
      notifyMessage('일정이 수정되었습니다.');
      return;
    }

    const startDate = new Date(payload.startAt);
    const endDate = new Date(payload.endAt);
    const requests = [];
    for (let week = 0; week <= repeatWeeks; week++) {
      const shiftedStart = new Date(startDate);
      const shiftedEnd = new Date(endDate);
      shiftedStart.setDate(shiftedStart.getDate() + week * 7);
      shiftedEnd.setDate(shiftedEnd.getDate() + week * 7);
      requests.push(
        apiRequest('/activities', {
          method: 'POST',
          body: JSON.stringify({
            ...payload,
            recurrenceGroupId,
            startAt: shiftedStart.toISOString(),
            endAt: shiftedEnd.toISOString()
          })
        })
      );
    }
    await Promise.all(requests);
    calendarBaseDate = new Date(payload.startAt);
    calendarSelectedDate = formatDateOnly(payload.startAt);
    form.reset();
    setEditorHtml('activity-editor', '');
    if (form.content) form.content.value = '';
    if (form.activityAttachmentFiles) form.activityAttachmentFiles.value = '';
    form.manager.value = user.name || user.username || '';
    await loadActivitiesCalendar();
    notifyMessage(`일정이 등록되었습니다. (총 ${repeatWeeks + 1}건) 같은 화면에서 바로 신청할 수 있습니다.`);
  } catch (error) {
    notifyMessage(error.message || '일정 등록에 실패했습니다.');
  }
}

function startEditCalendarActivity(item) {
  if (!item || !Number(item.id)) return;
  const form = document.getElementById('calendar-create-form');
  if (!form) return;
  editingActivityId = Number(item.id);
  form.title.value = item.title || '';
  form.startAt.value = toDatetimeLocal(item.startAt);
  form.endAt.value = toDatetimeLocal(item.endAt);
  form.place.value = item.place || '';
  form.gatherTime.value = item.gatherTime || '';
  form.supplies.value = item.supplies || '';
  setEditorHtml('activity-editor', item.description || '');
  if (form.content) form.content.value = item.description || '';
  if (form.activityAttachmentFiles) form.activityAttachmentFiles.value = '';
  form.manager.value = item.manager || (getCurrentUser()?.name || getCurrentUser()?.username || '');
  form.recruitmentLimit.value = Number(item.recruitmentLimit || 0);
  form.repeatWeeks.value = '0';
  form.repeatWeeks.disabled = true;
  const submitBtn = form.querySelector('button[type="submit"]');
  if (submitBtn) submitBtn.textContent = '수정 저장';
  const detailModal = getModalInstanceById('calendarActivityDetailModal');
  if (detailModal) detailModal.hide();
  movePanel('activities');
  openActivitiesCalendarTab();
  const activitiesSection = document.getElementById('activities');
  activitiesSection?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  setTimeout(() => {
    form.title?.focus();
  }, 120);
}

async function deleteCalendarActivity(activityId) {
  const id = Number(activityId || 0);
  if (!id) return;
  if (!confirm('해당 일정을 삭제하시겠습니까?')) return;
  try {
    await apiRequest(`/activities/${id}`, { method: 'DELETE' });
    const detailModal = getModalInstanceById('calendarActivityDetailModal');
    if (detailModal) detailModal.hide();
    await loadActivitiesCalendar();
    notifyMessage('일정이 삭제되었습니다.');
  } catch (error) {
    notifyMessage(error.message || '일정 삭제에 실패했습니다.');
  }
}

async function openRecurrenceCancelModal(groupId) {
  const user = getCurrentUser();
  if (!user || user.status !== 'active' || !isStaffUser(user)) {
    notifyMessage('운영진/관리자만 일괄 취소할 수 있습니다.');
    return;
  }
  if (!groupId) return;
  pendingRecurrenceCancelGroupId = groupId;

  const summary = document.getElementById('recurrence-cancel-summary');
  const confirmBtn = document.getElementById('recurrence-cancel-confirm-btn');
  const previewList = document.getElementById('recurrence-cancel-preview-list');
  if (summary) summary.innerText = '영향도를 불러오는 중입니다...';
  if (confirmBtn) confirmBtn.disabled = true;
  if (previewList) previewList.innerHTML = '<li class="text-muted">불러오는 중...</li>';

  try {
    const impact = await apiRequest(`/activities/recurrence/${groupId}/impact`, { method: 'GET' });
    const activityCount = impact?.impact?.activityCount ?? 0;
    const applicationCount = impact?.impact?.applicationCount ?? 0;
    const previewItems = impact?.impact?.previewItems || [];
    if (summary) {
      summary.innerText = `반복 그룹 ${groupId} 취소 시, 일정 ${activityCount}건 / 신청 ${applicationCount}건이 함께 취소됩니다.`;
    }
    if (confirmBtn) confirmBtn.disabled = activityCount <= 0;
    if (previewList) {
      if (!previewItems.length) {
        previewList.innerHTML = '<li class="text-muted">표시할 일정이 없습니다.</li>';
      } else {
        previewList.innerHTML = previewItems.map(item => {
          const startAt = formatKoreanDate(item.startAt);
          const dateKey = formatDateOnly(item.startAt);
          return `
            <li>
              <button type="button" class="btn btn-link btn-sm p-0 text-start" data-impact-date="${dateKey}">
                ${item.title} · ${startAt} · 신청 ${item.applicationCount}건
              </button>
            </li>
          `;
        }).join('');

        previewList.querySelectorAll('[data-impact-date]').forEach(btn => {
          btn.addEventListener('click', async () => {
            const dateKey = btn.dataset.impactDate;
            const modalEl = document.getElementById('recurrenceCancelModal');
            if (modalEl) {
              const modal = bootstrap.Modal.getInstance(modalEl);
              if (modal) modal.hide();
            }
            await focusCalendarDate(dateKey);
          });
        });
      }
    }
  } catch (error) {
    if (summary) {
      summary.innerText = error.message || '영향도를 확인하지 못했습니다.';
    }
    if (confirmBtn) confirmBtn.disabled = true;
    if (previewList) previewList.innerHTML = '<li class="text-danger">목록을 불러오지 못했습니다.</li>';
  }

  const modalEl = document.getElementById('recurrenceCancelModal');
  if (modalEl) {
    const modal = new bootstrap.Modal(modalEl);
    modal.show();
  }
}

async function executeRecurrenceCancel() {
  if (!pendingRecurrenceCancelGroupId) return;
  try {
    const data = await apiRequest(`/activities/recurrence/${pendingRecurrenceCancelGroupId}/cancel`, { method: 'POST' });
    const modalEl = document.getElementById('recurrenceCancelModal');
    if (modalEl) {
      const modal = bootstrap.Modal.getInstance(modalEl);
      if (modal) modal.hide();
    }
    pendingRecurrenceCancelGroupId = '';
    await loadActivitiesCalendar();
    notifyMessage(data.message || '반복 그룹이 취소되었습니다.');
  } catch (error) {
    notifyMessage(error.message || '일괄 취소에 실패했습니다.');
  }
}

