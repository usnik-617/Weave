// ============ NEWS SECTION ============
function isFutureScheduled(item) {
  const publishAt = String(item?.publishAt || '').trim();
  if (!publishAt) return false;
  const publishDate = new Date(publishAt);
  if (Number.isNaN(publishDate.getTime())) return false;
  return publishDate.getTime() > Date.now();
}

function buildRouteStatePayload(panel = 'news') {
  const keys = (typeof ROUTE_STATE_KEYS === 'object' && ROUTE_STATE_KEYS) || {
    panel: 'panel', newsTab: 'newsTab', q: 'q', page: 'page', faqQ: 'faqQ', faqPage: 'faqPage',
    qnaQ: 'qnaQ', qnaPage: 'qnaPage', galleryQ: 'galleryQ', galleryPage: 'galleryPage', galleryFilter: 'galleryFilter'
  };
  return {
    [keys.panel]: panel,
    [keys.newsTab]: currentNewsTab || 'notice',
    [keys.q]: newsSearchKeyword || '',
    [keys.page]: String(newsCurrentPage || 1),
    [keys.faqQ]: faqSearchKeyword || '',
    [keys.faqPage]: String(faqCurrentPage || 1),
    [keys.qnaQ]: qnaSearchKeyword || '',
    [keys.qnaPage]: String(qnaCurrentPage || 1),
    [keys.galleryQ]: gallerySearchKeyword || '',
    [keys.galleryPage]: String(galleryCurrentPage || 1),
    [keys.galleryFilter]: String(galleryCurrentFilter || '*')
  };
}

function syncNewsRouteState() {
  if (typeof updateAppUrlState !== 'function') return;
  updateAppUrlState(buildRouteStatePayload('news'));
}

function syncGalleryRouteState() {
  if (typeof updateAppUrlState !== 'function') return;
  updateAppUrlState(buildRouteStatePayload('gallery'));
}

function safeText(value) {
  const raw = String(value ?? '');
  if (typeof escapeHtml === 'function') return escapeHtml(raw);
  return raw
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function normalizeId(value) {
  const id = Number(value);
  return Number.isFinite(id) ? id : -1;
}

function safeLowerText(value) {
  return String(value ?? '').toLowerCase();
}

function safeCategoryClass(value) {
  return String(value || '').trim().replace(/[^a-zA-Z0-9_-]/g, '');
}

function safeUrl(value) {
  const raw = String(value || '').trim();
  if (!raw) return '';
  if (raw.startsWith('data:image/')) return raw;
  if (/^(https?:)?\/\//i.test(raw) || raw.startsWith('/')) return raw;
  return '';
}

function getFilteredNewsItems() {
  const content = getContent();
  return content.news
    .filter((item) => safeLowerText(item?.title).includes(safeLowerText(newsSearchKeyword)))
    .sort((a, b) => b.id - a.id);
}

function getFilteredFaqItems() {
  const content = getContent();
  return (content.faq || [])
    .filter((item) => safeLowerText(item?.title).includes(safeLowerText(faqSearchKeyword)))
    .sort((a, b) => b.id - a.id);
}

function getFilteredQnaItems() {
  const content = getContent();
  return (content.qna || [])
    .filter((item) => safeLowerText(item?.title).includes(safeLowerText(qnaSearchKeyword)))
    .sort((a, b) => b.id - a.id);
}

function enableContentImagePreview(containerId) {
  const container = document.getElementById(containerId);
  if (!container) return;
  container.querySelectorAll('img').forEach((img) => {
    const src = String(img.getAttribute('src') || '').trim();
    if (!src) return;
    img.loading = 'lazy';
    img.style.cursor = 'zoom-in';
    img.style.maxWidth = img.style.maxWidth || '100%';
    img.addEventListener('click', (event) => {
      event.preventDefault();
      window.open(src, '_blank', 'noopener');
    });
  });
}

function getFirstImageFromHtml(html) {
  const text = String(html || '');
  if (!text) return '';
  const matched = text.match(/<img[^>]+src=["']([^"']+)["']/i);
  return matched ? String(matched[1] || '').trim() : '';
}

function renderNews() {
  const tbody = document.getElementById('news-table-body');
  const pagination = document.getElementById('news-pagination');
  const totalCount = document.getElementById('news-total-count');
  if (!tbody || !pagination || !totalCount) return;

  tbody.innerHTML = makeSkeletonRows(5, 7);

  try {
    const filtered = getFilteredNewsItems();
    totalCount.textContent = filtered.length;

    const totalPages = Math.max(1, Math.ceil(filtered.length / NEWS_PAGE_SIZE));
    if (newsCurrentPage > totalPages) newsCurrentPage = totalPages;

    const start = (newsCurrentPage - 1) * NEWS_PAGE_SIZE;
    const pageItems = filtered.slice(start, start + NEWS_PAGE_SIZE);
    tbody.innerHTML = '';

  const user = getCurrentUser();
  const isAdmin = !!(user && (user.isAdmin || (typeof isAdminUser === 'function' && isAdminUser(user))));
  // 관리 헤더 토글
  const adminTh = document.getElementById('news-admin-th');
  if (adminTh) adminTh.style.display = isAdmin ? '' : 'none';

  pageItems.forEach((item) => {
    const newsId = normalizeId(item?.id);
    const recommendCount = getRecommendCount(getPostKey('news', newsId));
    const scheduledBadge = isFutureScheduled(item) ? '<span class="news-title-badge">예약</span>' : '';
    const safeTitle = safeText(item?.title || '제목 없음');
    const safeDate = safeText(item?.date || '');
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${newsId > -1 ? newsId : ''}</td>
      <td><a href="#" onclick="openNotice(${newsId}); return false;">${safeTitle}</a>${scheduledBadge}</td>
      <td>${formatAuthorDisplay(item?.author || '관리자', getCurrentUser())}</td>
      <td>${safeDate}</td>
      <td>${item.views || 0}</td>
      <td>${recommendCount}</td>
    `;
    tbody.appendChild(tr);
  });

    pagination.innerHTML = '';
  const prevLi = document.createElement('li');
  prevLi.className = `page-item ${newsCurrentPage === 1 ? 'disabled' : ''}`;
  prevLi.innerHTML = '<a class="page-link" href="#">이전</a>';
  prevLi.addEventListener('click', (e) => {
    e.preventDefault();
    if (newsCurrentPage > 1) {
      newsCurrentPage -= 1;
      syncNewsRouteState();
      renderNews();
    }
  });
  pagination.appendChild(prevLi);

  for (let page = 1; page <= totalPages; page++) {
    const li = document.createElement('li');
    li.className = `page-item ${page === newsCurrentPage ? 'active' : ''}`;
    li.innerHTML = `<a class="page-link" href="#">${page}</a>`;
    li.addEventListener('click', (e) => {
      e.preventDefault();
      newsCurrentPage = page;
      syncNewsRouteState();
      renderNews();
    });
    pagination.appendChild(li);
  }

    const nextLi = document.createElement('li');
    nextLi.className = `page-item ${newsCurrentPage === totalPages ? 'disabled' : ''}`;
    nextLi.innerHTML = '<a class="page-link" href="#">다음</a>';
    nextLi.addEventListener('click', (e) => {
      e.preventDefault();
      if (newsCurrentPage < totalPages) {
        newsCurrentPage += 1;
        syncNewsRouteState();
        renderNews();
      }
    });
    pagination.appendChild(nextLi);
  } catch (_) {
    renderNetworkError(tbody, renderNews);
  }
  renderHomeNoticeCarousel();
}

function renderFaq() {
  const tbody = document.getElementById('faq-table-body');
  const pagination = document.getElementById('faq-pagination');
  const totalCount = document.getElementById('faq-total-count');
  if (!tbody || !pagination || !totalCount) return;

  const items = getFilteredFaqItems();
  totalCount.textContent = items.length;
  const totalPages = Math.max(1, Math.ceil(items.length / FAQ_PAGE_SIZE));
  if (faqCurrentPage > totalPages) faqCurrentPage = totalPages;
  const start = (faqCurrentPage - 1) * FAQ_PAGE_SIZE;
  const pageItems = items.slice(start, start + FAQ_PAGE_SIZE);
  const user = getCurrentUser();
  const admin = isAdminUser(user);

  tbody.innerHTML = '';
  pageItems.forEach((item) => {
    const faqId = normalizeId(item?.id);
    const safeTitle = safeText(item?.title || '질문 없음');
    const safeDate = safeText(item?.date || '');
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${faqId > -1 ? faqId : ''}</td>
      <td><a href="#" onclick="openFaqDetail(${faqId}); return false;">${safeTitle}</a></td>
      <td>${formatAuthorDisplay(item?.author || '관리자', getCurrentUser())}</td>
      <td>${safeDate}</td>
      <td>${item.views || 0}</td>
    `;
    tbody.appendChild(tr);
  });

  pagination.innerHTML = '';
  const prevLi = document.createElement('li');
  prevLi.className = `page-item ${faqCurrentPage === 1 ? 'disabled' : ''}`;
  prevLi.innerHTML = '<a class="page-link" href="#">이전</a>';
  prevLi.addEventListener('click', (e) => {
    e.preventDefault();
    if (faqCurrentPage > 1) {
      faqCurrentPage -= 1;
      syncNewsRouteState();
      renderFaq();
    }
  });
  pagination.appendChild(prevLi);

  for (let page = 1; page <= totalPages; page++) {
    const li = document.createElement('li');
    li.className = `page-item ${page === faqCurrentPage ? 'active' : ''}`;
    li.innerHTML = `<a class="page-link" href="#">${page}</a>`;
    li.addEventListener('click', (e) => {
      e.preventDefault();
      faqCurrentPage = page;
      syncNewsRouteState();
      renderFaq();
    });
    pagination.appendChild(li);
  }

  const nextLi = document.createElement('li');
  nextLi.className = `page-item ${faqCurrentPage === totalPages ? 'disabled' : ''}`;
  nextLi.innerHTML = '<a class="page-link" href="#">다음</a>';
  nextLi.addEventListener('click', (e) => {
    e.preventDefault();
    if (faqCurrentPage < totalPages) {
      faqCurrentPage += 1;
      syncNewsRouteState();
      renderFaq();
    }
  });
  pagination.appendChild(nextLi);
}

function renderQna() {
  const tbody = document.getElementById('qna-table-body');
  const pagination = document.getElementById('qna-pagination');
  const totalCount = document.getElementById('qna-total-count');
  if (!tbody || !pagination || !totalCount) return;

  const items = getFilteredQnaItems();
  totalCount.textContent = items.length;
  const totalPages = Math.max(1, Math.ceil(items.length / QNA_PAGE_SIZE));
  if (qnaCurrentPage > totalPages) qnaCurrentPage = totalPages;
  const start = (qnaCurrentPage - 1) * QNA_PAGE_SIZE;
  const pageItems = items.slice(start, start + QNA_PAGE_SIZE);
  const user = getCurrentUser();
  const admin = isAdminUser(user);

  tbody.innerHTML = '';
  pageItems.forEach((item) => {
    const qnaId = normalizeId(item?.id);
    const canRead = !item?.isSecret || admin;
    const safeTitle = safeText(item?.title || '질문 없음');
    const safeDate = safeText(item?.date || '');
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${qnaId > -1 ? qnaId : ''}</td>
      <td>${canRead ? `<a href=\"#\" onclick=\"openQnaDetail(${qnaId}); return false;\">${safeTitle}${item?.isSecret ? ' 🔒' : ''}</a>` : '비밀글 🔒'}</td>
      <td>${formatAuthorDisplay(item?.author || '', getCurrentUser())}</td>
      <td>${safeDate}</td>
      <td>${item.answer ? '답변완료' : '대기'}</td>
    `;
    tbody.appendChild(tr);
  });

  pagination.innerHTML = '';
  const prevLi = document.createElement('li');
  prevLi.className = `page-item ${qnaCurrentPage === 1 ? 'disabled' : ''}`;
  prevLi.innerHTML = '<a class="page-link" href="#">이전</a>';
  prevLi.addEventListener('click', (e) => {
    e.preventDefault();
    if (qnaCurrentPage > 1) {
      qnaCurrentPage -= 1;
      syncNewsRouteState();
      renderQna();
    }
  });
  pagination.appendChild(prevLi);

  for (let page = 1; page <= totalPages; page++) {
    const li = document.createElement('li');
    li.className = `page-item ${page === qnaCurrentPage ? 'active' : ''}`;
    li.innerHTML = `<a class="page-link" href="#">${page}</a>`;
    li.addEventListener('click', (e) => {
      e.preventDefault();
      qnaCurrentPage = page;
      syncNewsRouteState();
      renderQna();
    });
    pagination.appendChild(li);
  }

  const nextLi = document.createElement('li');
  nextLi.className = `page-item ${qnaCurrentPage === totalPages ? 'disabled' : ''}`;
  nextLi.innerHTML = '<a class="page-link" href="#">다음</a>';
  nextLi.addEventListener('click', (e) => {
    e.preventDefault();
    if (qnaCurrentPage < totalPages) {
      qnaCurrentPage += 1;
      syncNewsRouteState();
      renderQna();
    }
  });
  pagination.appendChild(nextLi);
}

function setNewsWriteButtons() {
  const user = getCurrentUser();
  const activeMember = !!(user && user.status === 'active');
  const admin = activeMember && isAdminUser(user);
  const staff = activeMember && isStaffUser(user);
  const noticeBtn = document.getElementById('news-write-btn');
  const faqBtn = document.getElementById('faq-write-btn');
  const qnaBtn = document.getElementById('qna-write-btn');
  if (noticeBtn) noticeBtn.classList.toggle('d-none', !staff || currentNewsTab !== 'notice');
  if (faqBtn) faqBtn.classList.toggle('d-none', !admin || currentNewsTab !== 'faq');
  if (qnaBtn) qnaBtn.classList.toggle('d-none', !activeMember || currentNewsTab !== 'qna');
}

function openFaqDetail(id) {
  const data = getContent();
  const normalizedId = normalizeId(id);
  const item = (data.faq || []).find((f) => normalizeId(f.id) === normalizedId);
  if (!item) return;
  item.views = (item.views || 0) + 1;
  saveContent(data);
  renderFaq();

  document.getElementById('news-detail-title').textContent = item.title;
  updateDetailMeta('news', {
    author: formatAuthorDisplay(item.author || '관리자', getCurrentUser()),
    date: formatDetailDateTime(item.date),
    volunteer: '',
    views: item.views || 0,
    recommends: 0,
    comments: 0
  });
  const contentEl = document.getElementById('news-detail-content');
  const imageEl = document.getElementById('news-detail-image');
  const recommendBtn = document.getElementById('news-recommend-btn');
  if (contentEl) contentEl.innerHTML = item.content || '';
  if (imageEl) imageEl.classList.add('d-none');
  if (recommendBtn?.parentElement) recommendBtn.parentElement.classList.add('d-none');
  const editBtn = document.getElementById('news-detail-edit-btn');
  const deleteBtn = document.getElementById('news-detail-delete-btn');
  const user = getCurrentUser();
  const canManage = !!(user && isAdminUser(user));
  if (editBtn) {
    editBtn.classList.toggle('d-none', !canManage);
    editBtn.onclick = canManage ? (() => startEditNews(id, 'faq')) : null;
  }
  if (deleteBtn) {
    deleteBtn.classList.toggle('d-none', !canManage);
    deleteBtn.onclick = canManage ? (() => {
      if (!confirm('이 FAQ를 삭제하시겠습니까?')) return;
      const next = getContent();
      next.faq = (next.faq || []).filter((entry) => normalizeId(entry.id) !== normalizedId);
      saveContent(next);
      renderFaq();
      movePanel('news');
      activateNewsTab('faq');
    }) : null;
  }
  const commentsEl = document.getElementById('news-comments-section');
  if (commentsEl) commentsEl.innerHTML = '<div class="small text-muted">FAQ에는 댓글을 작성할 수 없습니다.</div>';

  document.querySelectorAll('[class*="panel"]').forEach(p => p.classList.remove('panel-active'));
  document.getElementById('news-detail')?.classList.add('panel-active');
}

function openQnaDetail(id) {
  const user = getCurrentUser();
  const operator = isStaffUser(user);
  const data = getContent();
  const normalizedId = normalizeId(id);
  const item = (data.qna || []).find((q) => normalizeId(q.id) === normalizedId);
  if (!item) return;
  if (item.isSecret && !operator) {
    notifyMessage('비밀글은 운영자만 열람할 수 있습니다.');
    return;
  }

  document.getElementById('qna-detail-title').textContent = item.title;
  document.getElementById('qna-detail-meta').textContent = `${formatAuthorDisplay(item.author || '', getCurrentUser())} | ${item.date || ''}${item.isSecret ? ' | 비밀글' : ''}`;
  const questionEl = document.getElementById('qna-detail-question');
  const answerEl = document.getElementById('qna-detail-answer');
  if (questionEl) questionEl.innerHTML = item.content || '';
  if (answerEl) answerEl.innerHTML = item.answer || '아직 답변이 등록되지 않았습니다.';
  const answerBtn = document.getElementById('qna-answer-btn');
  if (answerBtn) {
    answerBtn.classList.toggle('d-none', !operator);
    answerBtn.onclick = () => {
      openQnaAnswerEditor(normalizedId);
    };
  }
  const qnaEditBtn = document.getElementById('qna-detail-edit-btn');
  const qnaDeleteBtn = document.getElementById('qna-detail-delete-btn');
  const canQnaEdit = !!(user && (operator || item.author === user.username || item.author === user.name));
  if (qnaEditBtn) {
    qnaEditBtn.classList.toggle('d-none', !canQnaEdit);
    qnaEditBtn.onclick = canQnaEdit ? (() => startEditNews(normalizedId, 'qna')) : null;
  }
  if (qnaDeleteBtn) {
    qnaDeleteBtn.classList.toggle('d-none', !canQnaEdit);
    qnaDeleteBtn.onclick = canQnaEdit ? (() => {
      if (!confirm('이 Q&A를 삭제하시겠습니까?')) return;
      const next = getContent();
      next.qna = (next.qna || []).filter((entry) => normalizeId(entry.id) !== normalizedId);
      saveContent(next);
      renderQna();
      movePanel('news');
      activateNewsTab('qna');
    }) : null;
  }

  document.querySelectorAll('[class*="panel"]').forEach(p => p.classList.remove('panel-active'));
  document.getElementById('qna-detail')?.classList.add('panel-active');
}

function openNotice(id) {
  const data = getContent();
  const newsItems = Array.isArray(data.news) ? data.news : [];
  const normalizedId = normalizeId(id);
  const notice = newsItems.find((n) => normalizeId(n.id) === normalizedId);
  if (!notice) return;
  notice.views = (notice.views || 0) + 1;
  saveContent(data);
  renderNews();

  const user = getCurrentUser();
  const titleEl = document.getElementById('news-detail-title');
  const contentEl = document.getElementById('news-detail-content');
  const imageEl = document.getElementById('news-detail-image');
  const actionsEl = document.getElementById('news-detail-actions');
  const editBtn = document.getElementById('news-detail-edit-btn');
  const deleteBtn = document.getElementById('news-detail-delete-btn');
  const recommendBtn = document.getElementById('news-recommend-btn');
  const recommendCountEl = document.getElementById('news-recommend-count');
  const itemKey = getPostKey('news', normalizedId);
  currentNewsDetailId = normalizedId;

  if (!titleEl || !contentEl || !imageEl || !editBtn || !deleteBtn) return;

  titleEl.textContent = notice.title;
  const volunteerStart = notice.volunteerStartDate || notice.volunteerDate || '';
  const volunteerEnd = notice.volunteerEndDate || notice.volunteerDate || '';
  const volunteerMeta = volunteerStart
    ? `봉사 날짜 ${formatKoreanDate(volunteerStart)}${volunteerEnd && volunteerEnd !== volunteerStart ? ` ~ ${formatKoreanDate(volunteerEnd)}` : ''}`
    : '';
  updateDetailMeta('news', {
    author: formatAuthorDisplay(notice.author || '관리자', getCurrentUser()),
    date: formatDetailDateTime(notice.date),
    volunteer: volunteerMeta,
    views: notice.views || 0,
    recommends: getRecommendCount(itemKey),
    comments: getCommentCount(itemKey)
  });
  contentEl.innerHTML = notice.content || '';
  if (actionsEl) {
    const attachments = Array.isArray(notice.attachments)
      ? notice.attachments
      : (Array.isArray(notice.files) ? notice.files : []);
    const appendInlineQuery = (url) => {
      const raw = String(url || '').trim();
      if (!raw || raw === '#') return '#';
      if (raw.includes('inline=')) return raw;
      return `${raw}${raw.includes('?') ? '&' : '?'}inline=1`;
    };
    const attachmentHtml = attachments.map((file) => {
      const fileUrl = safeUrl(file.file_url || file.url) || '#';
      const downloadUrl = safeUrl(file.download_url || file.downloadUrl || fileUrl) || '#';
      const previewUrl = safeUrl(file.preview_url || file.inline_url || appendInlineQuery(fileUrl)) || '#';
      const mimeType = String(file.mime_type || '').toLowerCase();
      const fileName = String(file.original_name || file.name || '첨부파일');
      const fileSize = Number(file.size || 0);
      const sizeText = fileSize > 0 ? ` · ${(fileSize / 1024).toFixed(1)}KB` : '';
      const lowerName = fileName.toLowerCase();
      const isPdf = mimeType === 'application/pdf' || fileName.toLowerCase().endsWith('.pdf');
      const isImage = mimeType.startsWith('image/') || /\.(png|jpe?g|gif|webp|bmp|svg)$/i.test(lowerName);
      if (isPdf) {
        return `
          <span class="small text-muted d-block mt-2"><i class="fas fa-file-pdf me-1"></i>${escapeHtml(fileName)}${sizeText}</span>
          <a class="btn btn-sm btn-outline-secondary mt-2 me-2 mobile-attachment-btn" href="${previewUrl}" target="_blank" rel="noopener" aria-label="PDF 새 탭 열기: ${escapeHtml(fileName)}">새 탭에서 보기</a>
          <a class="btn btn-sm btn-outline-primary mt-2 me-2 mobile-attachment-btn" href="${downloadUrl}" download target="_blank" rel="noopener" aria-label="첨부파일 다운로드: ${escapeHtml(fileName)}">다운로드</a>
        `;
      }
      if (!isImage) {
        return `
          <span class="small text-muted d-block mt-2"><i class="fas fa-paperclip me-1"></i>${escapeHtml(fileName)}${sizeText}</span>
          <a class="btn btn-sm btn-outline-primary mt-2 me-2 mobile-attachment-btn" href="${downloadUrl}" download target="_blank" rel="noopener" aria-label="첨부파일 다운로드: ${escapeHtml(fileName)}">다운로드</a>
        `;
      }
      const imageThumb = safeUrl(file.thumbnail_url || file.thumb_url || file.preview_url || fileUrl) || fileUrl;
      return `
        <a class="d-inline-block mt-2 me-2" href="${fileUrl}" target="_blank" rel="noopener">
          <img src="${imageThumb}" alt="첨부 이미지 미리보기: ${escapeHtml(fileName)}" loading="lazy" width="100" height="100" style="width:100px;height:100px;object-fit:cover;border-radius:8px;border:1px solid #dee2e6;">
        </a>
      `;
    }).join('');

    const calendarButton = volunteerStart
      ? `<button class="btn btn-sm btn-outline-primary" id="notice-go-calendar-btn">캘린더로 이동</button>`
      : '';

    actionsEl.innerHTML = `${calendarButton}${attachmentHtml ? `<div class="mt-2 notice-attachment-actions">${attachmentHtml}</div>` : ''}`;
    const btn = document.getElementById('notice-go-calendar-btn');
    if (btn) {
      btn.onclick = async () => {
        await focusCalendarDate(volunteerStart);
      };
    }
  }
  if (recommendBtn?.parentElement) recommendBtn.parentElement.classList.remove('d-none');
  const noticeImage = safeUrl((Array.isArray(notice.images) && notice.images[0]) || notice.image_url || notice.image);
  if (noticeImage) {
    imageEl.src = noticeImage;
    imageEl.classList.remove('d-none');
  } else {
    imageEl.classList.add('d-none');
  }

  const canManage = !!(user && (isAdminUser(user) || notice.author === user.username || notice.author === user.name));
  if (editBtn) {
    editBtn.classList.toggle('d-none', !canManage);
    editBtn.onclick = canManage ? (() => startEditNews(normalizedId, 'notice')) : null;
  }
  if (canManage) {
    deleteBtn.classList.remove('d-none');
    deleteBtn.onclick = () => {
      if (!confirm('이 공지글을 삭제하시겠습니까?')) return;
      const next = getContent();
      next.news = (next.news || []).filter((n) => normalizeId(n.id) !== normalizedId);
      saveContent(next);
      deleteBtn.classList.add('d-none');
      document.querySelectorAll('[class*="panel"]').forEach(p => p.classList.remove('panel-active'));
      document.getElementById('news')?.classList.add('panel-active');
      renderNews();
    };
  } else {
    deleteBtn.classList.add('d-none');
    deleteBtn.onclick = null;
  }

  if (recommendBtn && recommendCountEl) {
    recommendCountEl.textContent = String(getRecommendCount(itemKey));
    setRecommendButtonState(recommendBtn, hasRecommendation(itemKey));
    recommendBtn.onclick = () => {
      if (toggleRecommendation(itemKey)) {
        recommendCountEl.textContent = String(getRecommendCount(itemKey));
        setRecommendButtonState(recommendBtn, hasRecommendation(itemKey));
        updateDetailMeta('news', {
          author: formatAuthorDisplay(notice.author || '관리자', getCurrentUser()),
          date: formatDetailDateTime(notice.date),
          volunteer: volunteerMeta,
          views: notice.views || 0,
          recommends: getRecommendCount(itemKey),
          comments: getCommentCount(itemKey)
        });
      }
    };
  }

  renderPostComments('news-comments-section', itemKey);

  document.querySelectorAll('[class*="panel"]').forEach(p => p.classList.remove('panel-active'));
  document.getElementById('news-detail')?.classList.add('panel-active');
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ============ GALLERY SECTION ============
function renderGallery() {
  const content = getContent();
  const grid = document.getElementById('gallery-grid');
  const pagination = document.getElementById('gallery-pagination');
  const totalCount = document.getElementById('gallery-total-count');
  if (!grid || !pagination || !totalCount) return;
  document.querySelectorAll('.gallery-filter button[data-filter]').forEach((btn) => {
    btn.classList.toggle('active', String(btn.dataset.filter || '*') === String(galleryCurrentFilter || '*'));
  });
  grid.innerHTML = makeSkeletonCards(6);

  try {
    const galleryItems = Array.isArray(content.gallery) ? content.gallery : [];
    const filtered = galleryItems.filter((item) => {
      const byYear = galleryCurrentFilter === '*' || String(item?.category || '') === String(galleryCurrentFilter || '').replace('.', '');
      const byKeyword = !gallerySearchKeyword || safeLowerText(item?.title).includes(safeLowerText(gallerySearchKeyword));
      return byYear && byKeyword;
    });
    totalCount.textContent = String(filtered.length);

    const totalPages = Math.max(1, Math.ceil(filtered.length / GALLERY_PAGE_SIZE));
    if (galleryCurrentPage > totalPages) galleryCurrentPage = totalPages;
    const start = (galleryCurrentPage - 1) * GALLERY_PAGE_SIZE;
    const pageItems = filtered.slice(start, start + GALLERY_PAGE_SIZE);

    grid.innerHTML = '';

  pageItems.forEach((item) => {
    const user = getCurrentUser();
    const galleryId = normalizeId(item?.id);
    const canEdit = !!(user && (user.isAdmin || ADMIN_EMAILS.includes(user.email) || item?.author === user.username || item?.author === user.name));
    const recommendCount = getRecommendCount(getPostKey('gallery', galleryId));
    const firstBodyImage = getFirstImageFromHtml(item.content || '');
    const thumbImage = item.thumb_url
      || item.thumbnail_url
      || item.thumb
      || firstBodyImage
      || item.image_url
      || (Array.isArray(item.images) ? item.images[0] : '')
      || item.image
      || 'logo.png';
    const safeThumb = safeUrl(thumbImage) || 'logo.png';
    const safeTitle = safeText(item?.title || '제목 없음');
    const safeDate = safeText(item?.date || '');
    const safeYear = safeText(item?.year || '');
    const categoryClass = safeCategoryClass(item?.category);
    const div = document.createElement('div');
    div.className = `col-md-6 col-lg-4 gallery-item ${categoryClass}`;
    div.innerHTML = `
      <div class="gallery-card position-relative overflow-hidden rounded-3" onclick="openGalleryDetail(${galleryId})">
        <img src="${safeThumb}" alt="${safeTitle}" loading="lazy" decoding="async" width="640" height="480">
        <div class="gallery-caption p-3 bg-white border-top">
          <h6 class="mb-1">${safeTitle}</h6>
          <small class="text-muted">${safeDate} · ${safeYear}</small>
          <div class="small text-muted">조회 ${(item.views || 0)} · 추천 ${recommendCount}</div>
          ${canEdit ? `<div class="mt-2"><button class="btn btn-sm btn-outline-primary" onclick="event.stopPropagation(); startEditGallery(${galleryId});">수정</button></div>` : ''}
        </div>
        <div class="gallery-overlay">
          <i class="fas fa-search-plus"></i>
        </div>
      </div>
    `;
    grid.appendChild(div);
  });

    if (pagination) {
      pagination.innerHTML = '';
    const prevLi = document.createElement('li');
    prevLi.className = `page-item ${galleryCurrentPage === 1 ? 'disabled' : ''}`;
    prevLi.innerHTML = '<a class="page-link" href="#">이전</a>';
    prevLi.addEventListener('click', (e) => {
      e.preventDefault();
      if (galleryCurrentPage > 1) {
        galleryCurrentPage -= 1;
        syncGalleryRouteState();
        renderGallery();
        window.scrollTo({ top: 0, behavior: 'smooth' });
      }
    });
    pagination.appendChild(prevLi);

    for (let page = 1; page <= totalPages; page++) {
      const li = document.createElement('li');
      li.className = `page-item ${page === galleryCurrentPage ? 'active' : ''}`;
      li.innerHTML = `<a class="page-link" href="#">${page}</a>`;
      li.addEventListener('click', (e) => {
        e.preventDefault();
        galleryCurrentPage = page;
        syncGalleryRouteState();
        renderGallery();
        window.scrollTo({ top: 0, behavior: 'smooth' });
      });
      pagination.appendChild(li);
    }

    const nextLi = document.createElement('li');
    nextLi.className = `page-item ${galleryCurrentPage === totalPages ? 'disabled' : ''}`;
    nextLi.innerHTML = '<a class="page-link" href="#">다음</a>';
    nextLi.addEventListener('click', (e) => {
      e.preventDefault();
      if (galleryCurrentPage < totalPages) {
        galleryCurrentPage += 1;
        syncGalleryRouteState();
        renderGallery();
        window.scrollTo({ top: 0, behavior: 'smooth' });
      }
    });
      pagination.appendChild(nextLi);
    }
  } catch (_) {
    renderNetworkError(grid, renderGallery);
  }
}

function openGalleryDetail(id) {
  const content = getContent();
  const galleryItems = Array.isArray(content.gallery) ? content.gallery : [];
  const normalizedId = normalizeId(id);
  const item = galleryItems.find((x) => normalizeId(x.id) === normalizedId);
  if (!item) return;

  item.views = (item.views || 0) + 1;
  saveContent(content);
  renderGallery();

  const user = getCurrentUser();
  const canEdit = !!(user && (user.isAdmin || ADMIN_EMAILS.includes(user.email) || item.author === user.username || item.author === user.name));
  const itemKey = getPostKey('gallery', normalizedId);
  currentGalleryDetailId = normalizedId;
  const detailImage = document.getElementById('gallery-detail-image');
  const detailContentHtml = String(item.content || '');
  const originalImage = item.image_url
    || item.image
    || (Array.isArray(item.images) ? item.images[0] : '')
    || '';
  const safeOriginalImage = safeUrl(originalImage);
  if (detailImage) {
    if (safeOriginalImage) {
      detailImage.src = safeOriginalImage;
      detailImage.classList.remove('d-none');
    } else {
      detailImage.removeAttribute('src');
      detailImage.classList.add('d-none');
    }
  }
  const titleEl = document.getElementById('gallery-detail-title');
  const contentEl = document.getElementById('gallery-detail-content');
  if (!titleEl || !contentEl) return;
  titleEl.innerText = item.title;
  updateDetailMeta('gallery', {
    author: formatAuthorDisplay(item.author || '작성자 미상', getCurrentUser()),
    date: formatDetailDateTime(item.date),
    volunteer: item.year ? `${item.year}년 활동` : '',
    views: item.views || 0,
    recommends: getRecommendCount(itemKey),
    comments: getCommentCount(itemKey)
  });
  contentEl.innerHTML = detailContentHtml || '내용이 없습니다.';
  enableContentImagePreview('gallery-detail-content');
  const actionsEl = document.getElementById('gallery-detail-actions');
  if (actionsEl) {
    const linkedActivityId = Number(item.activityId || item.activity_id || 0);
    const hasLinkedActivity = Number.isFinite(linkedActivityId) && linkedActivityId > 0;
    actionsEl.innerHTML = hasLinkedActivity
      ? '<button class="btn btn-sm btn-outline-primary" id="gallery-go-calendar-btn">캘린더로 이동</button>'
      : '';
    const goCalendarBtn = document.getElementById('gallery-go-calendar-btn');
    if (goCalendarBtn) {
      goCalendarBtn.onclick = async () => {
        if (typeof openCalendarActivityFromGallery === 'function') {
          await openCalendarActivityFromGallery(linkedActivityId, item.activityStartAt || item.date || '');
          return;
        }
        if (item.date) await focusCalendarDate(item.date);
      };
    }
  }

  const editBtn = document.getElementById('gallery-detail-edit-btn');
  const deleteBtn = document.getElementById('gallery-detail-delete-btn');
  if (canEdit) {
    if (editBtn) editBtn.classList.remove('d-none');
    if (deleteBtn) deleteBtn.classList.remove('d-none');
    if (editBtn) editBtn.onclick = () => startEditGallery(normalizedId);
    if (deleteBtn) deleteBtn.onclick = () => {
      if (!confirm('이 글을 삭제하시겠습니까?')) return;
      const data = getContent();
      data.gallery = (data.gallery || []).filter((g) => normalizeId(g.id) !== normalizedId);
      saveContent(data);
      document.querySelectorAll('[class*="panel"]').forEach(p => p.classList.remove('panel-active'));
      document.getElementById('gallery')?.classList.add('panel-active');
      renderGallery();
    };
  } else {
    if (editBtn) editBtn.classList.add('d-none');
    if (deleteBtn) deleteBtn.classList.add('d-none');
    if (editBtn) editBtn.onclick = null;
    if (deleteBtn) deleteBtn.onclick = null;
  }

  const recommendBtn = document.getElementById('gallery-recommend-btn');
  const recommendCountEl = document.getElementById('gallery-recommend-count');
  if (recommendBtn && recommendCountEl) {
    recommendCountEl.textContent = String(getRecommendCount(itemKey));
    setRecommendButtonState(recommendBtn, hasRecommendation(itemKey));
    recommendBtn.onclick = () => {
      if (toggleRecommendation(itemKey)) {
        recommendCountEl.textContent = String(getRecommendCount(itemKey));
        setRecommendButtonState(recommendBtn, hasRecommendation(itemKey));
        updateDetailMeta('gallery', {
          author: formatAuthorDisplay(item.author || '작성자 미상', getCurrentUser()),
          date: formatDetailDateTime(item.date),
          volunteer: item.year ? `${item.year}년 활동` : '',
          views: item.views || 0,
          recommends: getRecommendCount(itemKey),
          comments: getCommentCount(itemKey)
        });
      }
    };
  }

  renderPostComments('gallery-comments-section', itemKey);

  document.querySelectorAll('[class*="panel"]').forEach(p => p.classList.remove('panel-active'));
  document.getElementById('gallery-detail')?.classList.add('panel-active');
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function startEditNews(id) {
  const user = getCurrentUser();
  if (!user) return notifyMessage('로그인이 필요합니다.');
  const type = arguments[1] || 'notice';
  const data = getContent();
  const source = type === 'faq' ? (data.faq || []) : (type === 'qna' ? (data.qna || []) : data.news);
  const item = source.find(n => n.id === id);
  if (!item) return;
  const form = document.getElementById('add-news-form');
  form.editId.value = item.id;
  form.title.value = item.title || '';
  form.author.value = item.author || '';
  form.postTab.value = type;
  if (form.featuredOnHome) {
    form.featuredOnHome.checked = type === 'notice' && !!item.featuredOnHome;
  }
  updateVolunteerDateFieldVisibility(form);
  if (form.isScheduled) {
    const publishAt = item.publish_at || item.publishAt || '';
    form.isScheduled.checked = !!publishAt;
    if (form.publishAt) form.publishAt.value = publishAt ? String(publishAt).slice(0, 16) : '';
    const publishWrap = document.getElementById('news-publish-at-wrap');
    if (publishWrap) publishWrap.classList.toggle('d-none', !form.isScheduled.checked);
  }
  if (form.volunteerStartDate) {
    const rawStart = type === 'notice' ? (item.volunteerStartDate || item.volunteerDate || '') : '';
    form.volunteerStartDate.value = typeof toDatetimeLocalInput === 'function' ? toDatetimeLocalInput(rawStart, '09:00') : rawStart;
  }
  if (form.volunteerEndDate) {
    const rawEnd = type === 'notice' ? (item.volunteerEndDate || item.volunteerDate || '') : '';
    form.volunteerEndDate.value = typeof toDatetimeLocalInput === 'function' ? toDatetimeLocalInput(rawEnd, '18:00') : rawEnd;
  }
  form.isSecret.checked = !!item.isSecret;
  form.content.value = item.content || '';
  setEditorHtml('news-editor', item.content || '');
  if (form.imagesData) form.imagesData.value = '[]';
  if (form.imageData) form.imageData.value = '';
  setImagePreview('news-image-preview', '');
  openWritePanel('news-admin');
}

function startEditGallery(id) {
  const user = getCurrentUser();
  if (!user) return notifyMessage('로그인이 필요합니다.');
  const data = getContent();
  const item = data.gallery.find(g => g.id === id);
  if (!item) return;
  const form = document.getElementById('add-gallery-form');
  form.editId.value = item.id;
  form.title.value = item.title || '';
  if (form.isScheduled) {
    const publishAt = item.publish_at || item.publishAt || '';
    form.isScheduled.checked = !!publishAt;
    if (form.publishAt) form.publishAt.value = publishAt ? String(publishAt).slice(0, 16) : '';
    const publishWrap = document.getElementById('gallery-publish-at-wrap');
    if (publishWrap) publishWrap.classList.toggle('d-none', !form.isScheduled.checked);
  }
  form.year.value = String(item.year || 2026);
  ensureGalleryYearOptions(String(item.year || 2026));
  if (form.activityId) {
    const linkedActivityId = String(item.activityId || item.activity_id || '');
    form.activityId.value = linkedActivityId;
    if (typeof loadGalleryActivityOptions === 'function') {
      loadGalleryActivityOptions(linkedActivityId);
    }
  }
  if (form.imagesData) form.imagesData.value = '[]';
  if (form.imageData) form.imageData.value = '';
  setImagePreview('gallery-image-preview', '');
  form.content.value = item.content || '';
  setEditorHtml('gallery-editor', item.content || '');
  openWritePanel('gallery-admin');
}
