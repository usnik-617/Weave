function formatEventDateRange(startDatetime, endDatetime) {
  const start = formatKoreanDate(startDatetime || '');
  const end = formatKoreanDate(endDatetime || startDatetime || '');
  if (!startDatetime) return '-';
  if (!endDatetime || endDatetime === startDatetime) return start;
  return `${start} ~ ${end}`;
}

function canJoinEvent(user) {
  const role = String(user?.role || '').toUpperCase();
  return !!(user && user.status === 'active' && ['MEMBER', 'EXECUTIVE', 'LEADER', 'VICE_LEADER', 'ADMIN'].includes(role));
}

async function loadVolunteerEvents() {
  const listEl = document.getElementById('events-list');
  if (!listEl) return;
  listEl.innerHTML = Array.from({ length: 3 }).map(() => `
    <div class="border rounded p-3">
      <div class="skeleton-line w-50 mb-2"></div>
      <div class="skeleton-line w-75 mb-2"></div>
      <div class="skeleton-line w-25"></div>
    </div>
  `).join('');
  try {
    const data = await apiRequest('/events?page=1&pageSize=10', { method: 'GET' });
    volunteerEvents = Array.isArray(data.items) ? data.items : [];
    renderVolunteerEvents();
  } catch (error) {
    volunteerEvents = [];
    renderNetworkError(listEl, () => {
      loadVolunteerEvents().catch(() => {});
    });
  }
}

function renderVolunteerEvents() {
  const listEl = document.getElementById('events-list');
  if (!listEl) return;
  if (!volunteerEvents.length) {
    listEl.innerHTML = '<div class="small text-muted">등록된 봉사 일정이 없습니다.</div>';
    return;
  }
  listEl.innerHTML = '';
  volunteerEvents.forEach((eventItem) => {
    const card = document.createElement('div');
    card.className = 'border rounded p-3';
    const capacity = Number(eventItem.capacity || eventItem.maxParticipants || 0);
    const participantCount = Number(eventItem.participantCount || 0);
    const isRegistered = String(eventItem.myStatus || '').toLowerCase() === 'registered';
    const dateText = formatEventDateRange(eventItem.startDatetime || eventItem.eventDate, eventItem.endDatetime || eventItem.eventDate);
    card.innerHTML = `
      <div class="d-flex justify-content-between align-items-start gap-2 flex-wrap">
        <div>
          <div class="fw-semibold">${escapeHtml(eventItem.title || '제목 없음')}</div>
          <div class="small text-muted mt-1">${escapeHtml(dateText)}</div>
          <div class="small text-muted">장소: ${escapeHtml(eventItem.location || '-')}</div>
          <div class="small text-muted">참여 인원: ${participantCount}${capacity > 0 ? ` / ${capacity}` : ''}</div>
        </div>
        <div class="d-flex gap-2 align-items-center">
          <button class="btn btn-sm btn-outline-primary" data-event-open-id="${eventItem.id}">상세보기</button>
          ${isRegistered ? '<span class="badge text-bg-light border">참여중</span>' : ''}
        </div>
      </div>
    `;
    listEl.appendChild(card);
  });

  listEl.querySelectorAll('[data-event-open-id]').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const eventId = Number(btn.dataset.eventOpenId || 0);
      if (!eventId) return;
      openEventDetail(eventId);
    });
  });
}

function openEventDetail(eventId) {
  const eventItem = (volunteerEvents || []).find((item) => Number(item.id) === Number(eventId));
  if (!eventItem) return;
  currentEventDetailId = Number(eventId);
  const capacity = Number(eventItem.capacity || eventItem.maxParticipants || 0);
  const participantCount = Number(eventItem.participantCount || 0);
  const isRegistered = String(eventItem.myStatus || '').toLowerCase() === 'registered';
  const titleEl = document.getElementById('event-detail-title');
  const placeEl = document.getElementById('event-detail-place');
  const dateEl = document.getElementById('event-detail-date');
  const capEl = document.getElementById('event-detail-capacity');
  const statusEl = document.getElementById('event-detail-status');
  const contentEl = document.getElementById('event-detail-content');
  if (titleEl) titleEl.textContent = eventItem.title || '제목 없음';
  if (placeEl) placeEl.textContent = `장소: ${eventItem.location || '-'}`;
  if (dateEl) dateEl.textContent = formatEventDateRange(eventItem.startDatetime || eventItem.eventDate, eventItem.endDatetime || eventItem.eventDate);
  if (capEl) capEl.textContent = `참여 인원: ${participantCount}${capacity > 0 ? ` / ${capacity}` : ''}`;
  if (statusEl) statusEl.textContent = isRegistered ? '현재 상태: 참여중' : '현재 상태: 미참여';
  if (contentEl) contentEl.textContent = eventItem.description || '상세 설명이 없습니다.';
  const ctaBtn = document.getElementById('event-detail-cta-btn');
  const user = getCurrentUser();
  const isFull = capacity > 0 && participantCount >= capacity;
  const canAct = canJoinEvent(user);
  if (ctaBtn) {
    ctaBtn.textContent = isRegistered ? '참여 취소' : '참여 신청';
    ctaBtn.disabled = !canAct || (!isRegistered && isFull);
    ctaBtn.classList.toggle('btn-danger', isRegistered);
    ctaBtn.classList.toggle('btn-primary', !isRegistered);
    ctaBtn.onclick = async () => {
      await submitVolunteerEventAction(eventItem.id, isRegistered ? 'cancel' : 'join');
      await loadVolunteerEvents();
      openEventDetail(eventItem.id);
    };
  }
  movePanel('event-detail');
}

async function submitVolunteerEventAction(eventId, action) {
  const user = getCurrentUser();
  if (!canJoinEvent(user)) {
    notifyMessage('단원 이상만 참여 신청/취소할 수 있습니다.');
    return;
  }
  const path = action === 'cancel' ? `/events/${eventId}/cancel` : `/events/${eventId}/join`;
  try {
    await apiRequest(path, { method: 'POST' });
    await loadVolunteerEvents();
  } catch (error) {
    notifyMessage(error.message || '요청 처리 중 오류가 발생했습니다.');
  }
}

function setJoinActionPanel(panelName) {
  const inquiryPanel = document.getElementById('join-inquiry-panel');
  const sponsorPanel = document.getElementById('join-sponsor-panel');
  const inquiryBtn = document.getElementById('join-inquiry-btn');
  const sponsorBtn = document.getElementById('join-sponsor-btn');
  if (!inquiryPanel || !sponsorPanel || !inquiryBtn || !sponsorBtn) return;

  const showInquiry = panelName !== 'sponsor';
  inquiryPanel.classList.toggle('d-none', !showInquiry);
  sponsorPanel.classList.toggle('d-none', showInquiry);

  inquiryBtn.classList.toggle('btn-light', showInquiry);
  inquiryBtn.classList.toggle('btn-outline-light', !showInquiry);
  sponsorBtn.classList.toggle('btn-light', !showInquiry);
  sponsorBtn.classList.toggle('btn-outline-light', showInquiry);
}

async function copyDonationAccount() {
  const accountInput = document.getElementById('donation-account');
  const result = document.getElementById('copy-donation-account-result');
  if (!accountInput || !result) return;

  const accountText = accountInput.value || '';
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(accountText);
    } else {
      accountInput.removeAttribute('readonly');
      accountInput.select();
      document.execCommand('copy');
      accountInput.setAttribute('readonly', 'readonly');
    }
    result.textContent = '계좌번호가 복사되었습니다.';
  } catch (error) {
    result.textContent = '복사에 실패했습니다. 계좌번호를 직접 선택해 복사해 주세요.';
  }
}

