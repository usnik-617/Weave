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
  const honorPanel = document.getElementById('join-honor-panel');
  const inquiryPanel = document.getElementById('join-inquiry-panel');
  const sponsorPanel = document.getElementById('join-sponsor-panel');
  const honorBtn = document.getElementById('join-honor-btn');
  const inquiryBtn = document.getElementById('join-inquiry-btn');
  const sponsorBtn = document.getElementById('join-sponsor-btn');
  if (!honorPanel || !inquiryPanel || !sponsorPanel || !honorBtn || !inquiryBtn || !sponsorBtn) return;

  const target = String(panelName || 'honor').toLowerCase();
  const showHonor = target === 'honor';
  const showInquiry = target === 'inquiry';
  const showSponsor = target === 'sponsor';
  honorPanel.classList.toggle('d-none', !showHonor);
  inquiryPanel.classList.toggle('d-none', !showInquiry);
  sponsorPanel.classList.toggle('d-none', !showSponsor);

  honorBtn.classList.toggle('btn-light', showHonor);
  honorBtn.classList.toggle('btn-outline-light', !showHonor);
  inquiryBtn.classList.toggle('btn-light', showInquiry);
  inquiryBtn.classList.toggle('btn-outline-light', !showInquiry);
  sponsorBtn.classList.toggle('btn-light', showSponsor);
  sponsorBtn.classList.toggle('btn-outline-light', !showSponsor);
  if (showHonor && typeof renderJoinHonorHall === 'function') {
    renderJoinHonorHall();
  }
}

const JOIN_HONOR_KEY = 'weave_join_honor_hall';
const JOIN_HONOR_AUDIT_KEY = 'weave_join_honor_hall_audit';
const JOIN_HONOR_PAGE_SIZE = 24;
let joinHonorPage = 1;
let joinHonorQuery = '';

function canManageJoinHonor(user = getCurrentUser()) {
  return !!(
    user
    && user.status === 'active'
    && (isAdminUser(user) || isStaffUser(user))
  );
}

function getJoinHonorItems() {
  const parsed = safeJsonParse(safeStorageGet(JOIN_HONOR_KEY, '[]'), []);
  const rows = Array.isArray(parsed) ? parsed : [];
  return rows.filter((row) => row && typeof row === 'object').map((row) => ({
    id: Number(row.id || 0) || Date.now(),
    name: String(row.name || '').trim(),
    tier: ['gold', 'silver', 'bronze'].includes(String(row.tier || '').toLowerCase())
      ? String(row.tier || '').toLowerCase()
      : 'bronze',
    createdAt: String(row.createdAt || new Date().toISOString())
  }));
}

function saveJoinHonorItems(items) {
  const safe = Array.isArray(items) ? items.slice(0, 500) : [];
  safeStorageSet(JOIN_HONOR_KEY, JSON.stringify(safe));
}

function getJoinHonorAuditLogs() {
  const parsed = safeJsonParse(safeStorageGet(JOIN_HONOR_AUDIT_KEY, '[]'), []);
  return Array.isArray(parsed) ? parsed : [];
}

function saveJoinHonorAuditLogs(items) {
  const safe = Array.isArray(items) ? items.slice(0, 1000) : [];
  safeStorageSet(JOIN_HONOR_AUDIT_KEY, JSON.stringify(safe));
}

function addJoinHonorAuditLog(action, item, reason = '') {
  const user = getCurrentUser();
  const logs = getJoinHonorAuditLogs();
  logs.unshift({
    id: Date.now(),
    action: String(action || 'create'),
    name: String(item?.name || ''),
    tier: String(item?.tier || 'bronze'),
    reason: String(reason || '').trim().slice(0, 120),
    actor: String(user?.nickname || user?.username || user?.name || '관리자'),
    at: new Date().toISOString()
  });
  saveJoinHonorAuditLogs(logs);
}

function isValidHonorName(name) {
  const text = String(name || '').trim();
  if (!text || text.length < 2 || text.length > 20) return false;
  return /^[A-Za-z가-힣]+$/.test(text);
}

function getFilteredHonorItems() {
  const list = getJoinHonorItems();
  const q = String(joinHonorQuery || '').trim().toLowerCase();
  const filtered = !q ? list : list.filter((item) => String(item.name || '').toLowerCase().includes(q));
  return filtered.sort((a, b) => String(a.name || '').localeCompare(String(b.name || ''), 'ko-KR', { sensitivity: 'base' }));
}

function buildHonorTierSection(tier, items, canManage = false) {
  if (!Array.isArray(items) || !items.length) return '';
  const tierMeta = {
    gold: { label: '금', medal: 'fa-medal', color: '#f5c542', boxBg: '#fff7df' },
    silver: { label: '은', medal: 'fa-medal', color: '#9aa6b2', boxBg: '#eef2f7' },
    bronze: { label: '동', medal: 'fa-medal', color: '#b87942', boxBg: '#f8eee4' }
  }[tier] || { label: '동', medal: 'fa-medal', color: '#b87942', boxBg: '#f8eee4' };
  const cards = items.map((item) => `
    <div class="join-honor-card" style="background:#dff3ff;">
      <span class="join-honor-card-name">${escapeHtml(item.name || '')}</span>
      ${canManage ? `
      <div class="join-honor-card-actions">
        <button type="button" class="btn btn-sm btn-outline-secondary py-0 px-2" data-honor-edit-id="${Number(item.id || 0)}">수정</button>
        <button type="button" class="btn btn-sm btn-outline-danger py-0 px-2" data-honor-delete-id="${Number(item.id || 0)}">삭제</button>
      </div>` : ''}
    </div>
  `).join('');
  return `
    <section class="join-honor-tier">
      <div class="join-honor-tier-header" style="background:${tierMeta.color};">
        <i class="fas ${tierMeta.medal} me-2"></i>${tierMeta.label}
      </div>
      <div class="join-honor-tier-body" style="background:${tierMeta.boxBg};">
        <div class="join-honor-grid">${cards}</div>
      </div>
    </section>
  `;
}

function openJoinHonorDeleteConfirm(item, onDelete = null) {
  const targetName = escapeHtml(String(item?.name || ''));
  if (!window.bootstrap?.Modal) {
    const ok = window.confirm(`${String(item?.name || '')} 항목을 삭제할까요?`);
    if (ok && typeof onDelete === 'function') onDelete();
    return;
  }
  const modalId = 'join-honor-delete-confirm-modal';
  let modalEl = document.getElementById(modalId);
  if (!modalEl) {
    modalEl = document.createElement('div');
    modalEl.id = modalId;
    modalEl.className = 'modal fade';
    modalEl.tabIndex = -1;
    modalEl.innerHTML = `
      <div class="modal-dialog modal-dialog-centered">
        <div class="modal-content">
          <div class="modal-header border-0">
            <h5 class="modal-title">삭제 확인</h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="닫기"></button>
          </div>
          <div class="modal-body">
            <p class="mb-0" id="join-honor-delete-confirm-text"></p>
          </div>
          <div class="modal-footer border-0">
            <button type="button" class="btn btn-outline-secondary" id="join-honor-delete-cancel-btn" data-bs-dismiss="modal">아니오</button>
            <button type="button" class="btn btn-danger" id="join-honor-delete-confirm-btn">삭제</button>
          </div>
        </div>
      </div>
    `;
    document.body.appendChild(modalEl);
  }
  const textEl = document.getElementById('join-honor-delete-confirm-text');
  if (textEl) textEl.innerHTML = `<strong>${targetName}</strong> 항목을 삭제할까요?`;

  const deleteBtn = document.getElementById('join-honor-delete-confirm-btn');
  if (deleteBtn) {
    deleteBtn.onclick = () => {
      if (typeof onDelete === 'function') onDelete();
      const modal = bootstrap.Modal.getInstance(modalEl);
      if (modal) modal.hide();
    };
  }
  const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
  modal.show();
}

function renderJoinHonorPagination(totalPages) {
  const pager = document.getElementById('join-honor-pagination');
  if (!pager) return;
  pager.innerHTML = '';
  const appendPage = (label, disabled, page, active = false) => {
    const li = document.createElement('li');
    li.className = `page-item ${disabled ? 'disabled' : ''} ${active ? 'active' : ''}`.trim();
    li.innerHTML = `<a class="page-link" href="#">${label}</a>`;
    li.addEventListener('click', (e) => {
      e.preventDefault();
      if (disabled) return;
      joinHonorPage = page;
      renderJoinHonorHall();
    });
    pager.appendChild(li);
  };
  appendPage('이전', joinHonorPage <= 1, Math.max(1, joinHonorPage - 1), false);
  for (let page = 1; page <= totalPages; page += 1) {
    appendPage(String(page), false, page, page === joinHonorPage);
  }
  appendPage('다음', joinHonorPage >= totalPages, Math.min(totalPages, joinHonorPage + 1), false);
}

function updateJoinHonorAdminVisibility() {
  const wrap = document.getElementById('join-honor-admin-tools');
  if (!wrap) return;
  wrap.classList.toggle('d-none', !canManageJoinHonor(getCurrentUser()));
}

function renderJoinHonorHall() {
  const listEl = document.getElementById('join-honor-list');
  const emptyEl = document.getElementById('join-honor-empty');
  if (!listEl || !emptyEl) return;
  updateJoinHonorAdminVisibility();

  const filtered = getFilteredHonorItems();
  const user = getCurrentUser();
  const canManage = canManageJoinHonor(user);
  const totalPages = Math.max(1, Math.ceil(filtered.length / JOIN_HONOR_PAGE_SIZE));
  if (joinHonorPage > totalPages) joinHonorPage = totalPages;
  const start = (joinHonorPage - 1) * JOIN_HONOR_PAGE_SIZE;
  const pageItems = filtered.slice(start, start + JOIN_HONOR_PAGE_SIZE);
  const grouped = {
    gold: pageItems.filter((item) => item.tier === 'gold'),
    silver: pageItems.filter((item) => item.tier === 'silver'),
    bronze: pageItems.filter((item) => item.tier === 'bronze')
  };
  listEl.innerHTML = `${buildHonorTierSection('gold', grouped.gold, canManage)}${buildHonorTierSection('silver', grouped.silver, canManage)}${buildHonorTierSection('bronze', grouped.bronze, canManage)}`;
  emptyEl.classList.toggle('d-none', pageItems.length > 0);
  renderJoinHonorPagination(totalPages);
  renderJoinHonorAuditLogs();
  if (canManage) {
    listEl.querySelectorAll('[data-honor-edit-id]').forEach((btn) => {
      btn.addEventListener('click', () => {
        const id = Number(btn.getAttribute('data-honor-edit-id') || 0);
        const items = getJoinHonorItems();
        const target = items.find((row) => Number(row.id || 0) === id);
        const nameInput = document.getElementById('join-honor-name-input');
        const tierSelect = document.getElementById('join-honor-tier-select');
        if (!target || !(nameInput instanceof HTMLInputElement) || !(tierSelect instanceof HTMLSelectElement)) return;
        nameInput.value = target.name || '';
        tierSelect.value = target.tier || 'bronze';
        nameInput.dataset.editId = String(id);
        nameInput.focus();
      });
    });
    listEl.querySelectorAll('[data-honor-delete-id]').forEach((btn) => {
      btn.addEventListener('click', () => {
        const id = Number(btn.getAttribute('data-honor-delete-id') || 0);
        const items = getJoinHonorItems();
        const target = items.find((row) => Number(row.id || 0) === id);
        const reasonInput = document.getElementById('join-honor-reason-input');
        const reason = String(reasonInput?.value || '').trim() || '관리자 삭제';
        if (!target) return;
        openJoinHonorDeleteConfirm(target, () => {
          const next = items.filter((row) => Number(row.id || 0) !== id);
          saveJoinHonorItems(next);
          addJoinHonorAuditLog('delete', target, reason);
          renderJoinHonorHall();
          notifyMessage('명예의 전당 항목이 삭제되었습니다.');
        });
      });
    });
  }
}

function renderJoinHonorAuditLogs() {
  const listEl = document.getElementById('join-honor-audit-list');
  const wrap = document.getElementById('join-honor-audit-wrap');
  if (!listEl) return;
  const canManage = canManageJoinHonor(getCurrentUser());
  if (wrap) wrap.classList.toggle('d-none', !canManage);
  if (!canManage) {
    listEl.innerHTML = '';
    return;
  }
  const logs = getJoinHonorAuditLogs().slice(0, 20);
  if (!logs.length) {
    listEl.innerHTML = '<div class="small text-muted">아직 감사 로그가 없습니다.</div>';
    return;
  }
  const actionLabel = { create: '등록', update: '수정', delete: '삭제' };
  const tierLabel = { gold: '금', silver: '은', bronze: '동' };
  listEl.innerHTML = logs.map((log) => `
    <div class="border rounded p-2 small">
      <div><strong>${escapeHtml(actionLabel[String(log.action || 'create')] || '등록')}</strong> · ${escapeHtml(String(log.name || ''))} · ${escapeHtml(tierLabel[String(log.tier || 'bronze')] || '동')}</div>
      <div class="text-muted">${escapeHtml(String(log.actor || '관리자'))} · ${escapeHtml(formatDetailDateTime(log.at || ''))}</div>
      <div class="text-muted">사유: ${escapeHtml(String(log.reason || '-'))}</div>
    </div>
  `).join('');
}

function initJoinHonorBindings() {
  const searchInput = document.getElementById('join-honor-search');
  const searchBtn = document.getElementById('join-honor-search-btn');
  const addBtn = document.getElementById('join-honor-add-btn');
  const resetBtn = document.getElementById('join-honor-reset-btn');
  const nameInput = document.getElementById('join-honor-name-input');
  const tierSelect = document.getElementById('join-honor-tier-select');
  const reasonInput = document.getElementById('join-honor-reason-input');

  const applySearch = () => {
    joinHonorQuery = String(searchInput?.value || '').trim();
    joinHonorPage = 1;
    renderJoinHonorHall();
  };

  if (searchBtn) searchBtn.addEventListener('click', applySearch);
  if (searchInput) {
    searchInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        applySearch();
      }
    });
  }
  if (addBtn) {
    addBtn.addEventListener('click', () => {
      const user = getCurrentUser();
      if (!canManageJoinHonor(user)) {
        notifyMessage('관리자 또는 운영자 권한이 필요합니다.');
        return;
      }
      const name = String(nameInput?.value || '').trim();
      const tier = String(tierSelect?.value || 'bronze').toLowerCase();
      const reason = String(reasonInput?.value || '').trim();
      if (!isValidHonorName(name)) {
        notifyMessage('이름은 한글/영어만 입력 가능하며 2~20자여야 합니다.');
        return;
      }
      if (!reason) {
        notifyMessage('감사 사유를 입력해주세요.');
        return;
      }
      const next = getJoinHonorItems();
      const editId = Number(nameInput?.dataset?.editId || 0);
      if (editId > 0) {
        const target = next.find((row) => Number(row.id || 0) === editId);
        if (!target) {
          notifyMessage('수정 대상을 찾을 수 없습니다.');
          return;
        }
        target.name = name;
        target.tier = ['gold', 'silver', 'bronze'].includes(tier) ? tier : 'bronze';
        addJoinHonorAuditLog('update', target, reason);
        delete nameInput.dataset.editId;
      } else {
        const created = {
          id: Date.now(),
          name,
          tier: ['gold', 'silver', 'bronze'].includes(tier) ? tier : 'bronze',
          createdAt: new Date().toISOString()
        };
        next.unshift(created);
        addJoinHonorAuditLog('create', created, reason);
      }
      saveJoinHonorItems(next);
      if (nameInput) nameInput.value = '';
      if (reasonInput) reasonInput.value = '';
      joinHonorPage = 1;
      renderJoinHonorHall();
      notifyMessage('명예의 전당 항목이 저장되었습니다.');
    });
  }
  if (resetBtn) {
    resetBtn.addEventListener('click', () => {
      if (nameInput) nameInput.value = '';
      if (tierSelect) tierSelect.value = 'gold';
      if (reasonInput) reasonInput.value = '';
      if (nameInput?.dataset?.editId) delete nameInput.dataset.editId;
      if (searchInput) searchInput.value = '';
      joinHonorQuery = '';
      joinHonorPage = 1;
      renderJoinHonorHall();
    });
  }
}

document.addEventListener('DOMContentLoaded', () => {
  initJoinHonorBindings();
  renderJoinHonorHall();
});

document.addEventListener('weave:user-state-changed', () => {
  updateJoinHonorAdminVisibility();
  renderJoinHonorHall();
});

window.renderJoinHonorHall = renderJoinHonorHall;

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

