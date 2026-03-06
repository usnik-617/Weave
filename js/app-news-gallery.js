// ============ NEWS SECTION ============
function getFilteredNewsItems() {
  const content = getContent();
  return content.news
    .filter(item => item.title.toLowerCase().includes(newsSearchKeyword.toLowerCase()))
    .sort((a, b) => b.id - a.id);
}

function getFilteredFaqItems() {
  const content = getContent();
  return (content.faq || [])
    .filter(item => item.title.toLowerCase().includes(faqSearchKeyword.toLowerCase()))
    .sort((a, b) => b.id - a.id);
}

function getFilteredQnaItems() {
  const content = getContent();
  return (content.qna || [])
    .filter(item => item.title.toLowerCase().includes(qnaSearchKeyword.toLowerCase()))
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

  pageItems.forEach(item => {
    const user = getCurrentUser();
    const canEdit = !!(user && (user.isAdmin || ADMIN_EMAILS.includes(user.email) || item.author === user.username || item.author === user.name));
    const recommendCount = getRecommendCount(getPostKey('news', item.id));
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${item.id}</td>
      <td><a href="#" onclick="openNotice(${item.id}); return false;">${item.title}</a></td>
      <td>${formatAuthorDisplay(item.author || '관리자', getCurrentUser())}</td>
      <td>${item.date}</td>
      <td>${item.views || 0}</td>
      <td>${recommendCount}</td>
      <td>${canEdit ? `<button class="btn btn-sm btn-outline-primary" onclick="startEditNews(${item.id})">수정</button>` : ''}</td>
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
  pageItems.forEach(item => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${item.id}</td>
      <td><a href="#" onclick="openFaqDetail(${item.id}); return false;">${item.title}</a></td>
      <td>${formatAuthorDisplay(item.author || '관리자', getCurrentUser())}</td>
      <td>${item.date || ''}</td>
      <td>${item.views || 0}</td>
      <td>${admin ? `<button class="btn btn-sm btn-outline-primary" onclick="startEditNews(${item.id}, 'faq')">수정</button>` : ''}</td>
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
  pageItems.forEach(item => {
    const canRead = !item.isSecret || admin;
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${item.id}</td>
      <td>${canRead ? `<a href="#" onclick="openQnaDetail(${item.id}); return false;">${item.title}${item.isSecret ? ' 🔒' : ''}</a>` : `비밀글 🔒`}</td>
      <td>${formatAuthorDisplay(item.author || '', getCurrentUser())}</td>
      <td>${item.date || ''}</td>
      <td>${item.answer ? '답변완료' : '대기'}</td>
      <td>${user && item.author === user.username ? `<button class="btn btn-sm btn-outline-primary" onclick="startEditNews(${item.id}, 'qna')">수정</button>` : ''}</td>
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
  const item = (data.faq || []).find(f => f.id === id);
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
  document.getElementById('news-detail-content').innerHTML = item.content || '';
  document.getElementById('news-detail-image').classList.add('d-none');
  document.getElementById('news-recommend-btn').parentElement.classList.add('d-none');
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
      next.faq = (next.faq || []).filter(entry => entry.id !== id);
      saveContent(next);
      renderFaq();
      movePanel('news');
      activateNewsTab('faq');
    }) : null;
  }
  document.getElementById('news-comments-section').innerHTML = '<div class="small text-muted">FAQ에는 댓글을 작성할 수 없습니다.</div>';

  document.querySelectorAll('[class*="panel"]').forEach(p => p.classList.remove('panel-active'));
  document.getElementById('news-detail').classList.add('panel-active');
}

function openQnaDetail(id) {
  const user = getCurrentUser();
  const operator = isStaffUser(user);
  const data = getContent();
  const item = (data.qna || []).find(q => q.id === id);
  if (!item) return;
  if (item.isSecret && !operator) {
    alert('비밀글은 운영자만 열람할 수 있습니다.');
    return;
  }

  document.getElementById('qna-detail-title').textContent = item.title;
  document.getElementById('qna-detail-meta').textContent = `${formatAuthorDisplay(item.author || '', getCurrentUser())} | ${item.date || ''}${item.isSecret ? ' | 비밀글' : ''}`;
  document.getElementById('qna-detail-question').innerHTML = item.content || '';
  document.getElementById('qna-detail-answer').innerHTML = item.answer || '아직 답변이 등록되지 않았습니다.';
  const answerBtn = document.getElementById('qna-answer-btn');
  answerBtn.classList.toggle('d-none', !operator);
  answerBtn.onclick = () => {
    openQnaAnswerEditor(id);
  };
  const qnaEditBtn = document.getElementById('qna-detail-edit-btn');
  const qnaDeleteBtn = document.getElementById('qna-detail-delete-btn');
  const canQnaEdit = !!(user && (operator || item.author === user.username || item.author === user.name));
  if (qnaEditBtn) {
    qnaEditBtn.classList.toggle('d-none', !canQnaEdit);
    qnaEditBtn.onclick = canQnaEdit ? (() => startEditNews(id, 'qna')) : null;
  }
  if (qnaDeleteBtn) {
    qnaDeleteBtn.classList.toggle('d-none', !canQnaEdit);
    qnaDeleteBtn.onclick = canQnaEdit ? (() => {
      if (!confirm('이 Q&A를 삭제하시겠습니까?')) return;
      const next = getContent();
      next.qna = (next.qna || []).filter(entry => entry.id !== id);
      saveContent(next);
      renderQna();
      movePanel('news');
      activateNewsTab('qna');
    }) : null;
  }

  document.querySelectorAll('[class*="panel"]').forEach(p => p.classList.remove('panel-active'));
  document.getElementById('qna-detail').classList.add('panel-active');
}

function openNotice(id) {
  const data = getContent();
  const notice = data.news.find(n => n.id === id);
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
  const itemKey = getPostKey('news', id);
  currentNewsDetailId = id;

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
      const fileUrl = file.file_url || file.url || '#';
      const downloadUrl = file.download_url || file.downloadUrl || fileUrl;
      const previewUrl = file.preview_url || file.inline_url || appendInlineQuery(fileUrl);
      const mimeType = String(file.mime_type || '').toLowerCase();
      const fileName = String(file.original_name || file.name || '첨부파일');
      const lowerName = fileName.toLowerCase();
      const isPdf = mimeType === 'application/pdf' || fileName.toLowerCase().endsWith('.pdf');
      const isImage = mimeType.startsWith('image/') || /\.(png|jpe?g|gif|webp|bmp|svg)$/i.test(lowerName);
      if (isPdf) {
        return `
          <a class="btn btn-sm btn-outline-secondary mt-2 me-2 mobile-attachment-btn" href="${previewUrl}" target="_blank" rel="noopener">PDF 미리보기</a>
          <a class="btn btn-sm btn-outline-primary mt-2 me-2 mobile-attachment-btn" href="${downloadUrl}" download target="_blank" rel="noopener">다운로드</a>
        `;
      }
      if (!isImage) {
        return `
          <a class="btn btn-sm btn-outline-primary mt-2 me-2 mobile-attachment-btn" href="${downloadUrl}" download target="_blank" rel="noopener">${escapeHtml(fileName)} 다운로드</a>
        `;
      }
      const imageThumb = file.thumbnail_url || file.thumb_url || file.preview_url || fileUrl;
      return `
        <a class="d-inline-block mt-2 me-2" href="${fileUrl}" target="_blank" rel="noopener">
          <img src="${imageThumb}" alt="${escapeHtml(fileName)}" loading="lazy" width="100" height="100" style="width:100px;height:100px;object-fit:cover;border-radius:8px;border:1px solid #dee2e6;">
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
  document.getElementById('news-recommend-btn').parentElement.classList.remove('d-none');
  const noticeImage = (Array.isArray(notice.images) && notice.images[0]) || notice.image_url || notice.image;
  if (noticeImage) {
    imageEl.src = noticeImage;
    imageEl.classList.remove('d-none');
  } else {
    imageEl.classList.add('d-none');
  }

  const canManage = !!(user && (isAdminUser(user) || notice.author === user.username || notice.author === user.name));
  if (editBtn) {
    editBtn.classList.toggle('d-none', !canManage);
    editBtn.onclick = canManage ? (() => startEditNews(id, 'notice')) : null;
  }
  if (canManage) {
    deleteBtn.classList.remove('d-none');
    deleteBtn.onclick = () => {
      if (!confirm('이 공지글을 삭제하시겠습니까?')) return;
      const next = getContent();
      next.news = next.news.filter(n => n.id !== id);
      saveContent(next);
      deleteBtn.classList.add('d-none');
      document.querySelectorAll('[class*="panel"]').forEach(p => p.classList.remove('panel-active'));
      document.getElementById('news').classList.add('panel-active');
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
  document.getElementById('news-detail').classList.add('panel-active');
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ============ GALLERY SECTION ============
function renderGallery() {
  const content = getContent();
  const grid = document.getElementById('gallery-grid');
  const pagination = document.getElementById('gallery-pagination');
  const totalCount = document.getElementById('gallery-total-count');
  if (!grid || !pagination || !totalCount) return;
  grid.innerHTML = makeSkeletonCards(6);

  try {
    const filtered = content.gallery.filter(item => {
      const byYear = galleryCurrentFilter === '*' || item.category === galleryCurrentFilter.replace('.', '');
      const byKeyword = !gallerySearchKeyword || item.title.toLowerCase().includes(gallerySearchKeyword.toLowerCase());
      return byYear && byKeyword;
    });
    totalCount.textContent = String(filtered.length);

    const totalPages = Math.max(1, Math.ceil(filtered.length / GALLERY_PAGE_SIZE));
    if (galleryCurrentPage > totalPages) galleryCurrentPage = totalPages;
    const start = (galleryCurrentPage - 1) * GALLERY_PAGE_SIZE;
    const pageItems = filtered.slice(start, start + GALLERY_PAGE_SIZE);

    grid.innerHTML = '';

  pageItems.forEach(item => {
    const user = getCurrentUser();
    const canEdit = !!(user && (user.isAdmin || ADMIN_EMAILS.includes(user.email) || item.author === user.username || item.author === user.name));
    const recommendCount = getRecommendCount(getPostKey('gallery', item.id));
    const firstBodyImage = getFirstImageFromHtml(item.content || '');
    const thumbImage = item.thumb_url
      || item.thumbnail_url
      || item.thumb
      || firstBodyImage
      || item.image_url
      || (Array.isArray(item.images) ? item.images[0] : '')
      || item.image
      || 'logo.png';
    const div = document.createElement('div');
    div.className = `col-md-6 col-lg-4 gallery-item ${item.category}`;
    div.innerHTML = `
      <div class="gallery-card position-relative overflow-hidden rounded-3" onclick="openGalleryDetail(${item.id})">
        <img src="${thumbImage}" alt="${item.title}" loading="lazy" decoding="async" width="640" height="480">
        <div class="gallery-caption p-3 bg-white border-top">
          <h6 class="mb-1">${item.title}</h6>
          <small class="text-muted">${item.date || ''} · ${item.year}</small>
          <div class="small text-muted">조회 ${(item.views || 0)} · 추천 ${recommendCount}</div>
          ${canEdit ? `<div class="mt-2"><button class="btn btn-sm btn-outline-primary" onclick="event.stopPropagation(); startEditGallery(${item.id});">수정</button></div>` : ''}
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
  const item = content.gallery.find(x => x.id === id);
  if (!item) return;

  item.views = (item.views || 0) + 1;
  saveContent(content);
  renderGallery();

  const user = getCurrentUser();
  const canEdit = !!(user && (user.isAdmin || ADMIN_EMAILS.includes(user.email) || item.author === user.username || item.author === user.name));
  const itemKey = getPostKey('gallery', id);
  currentGalleryDetailId = id;
  const detailImage = document.getElementById('gallery-detail-image');
  const detailContentHtml = String(item.content || '');
  if (detailImage) {
    detailImage.removeAttribute('src');
    detailImage.classList.add('d-none');
  }
  document.getElementById('gallery-detail-title').innerText = item.title;
  updateDetailMeta('gallery', {
    author: formatAuthorDisplay(item.author || '작성자 미상', getCurrentUser()),
    date: formatDetailDateTime(item.date),
    volunteer: item.year ? `${item.year}년 활동` : '',
    views: item.views || 0,
    recommends: getRecommendCount(itemKey),
    comments: getCommentCount(itemKey)
  });
  document.getElementById('gallery-detail-content').innerHTML = detailContentHtml || '내용이 없습니다.';
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
    editBtn.classList.remove('d-none');
    deleteBtn.classList.remove('d-none');
    editBtn.onclick = () => startEditGallery(id);
    deleteBtn.onclick = () => {
      if (!confirm('이 글을 삭제하시겠습니까?')) return;
      const data = getContent();
      data.gallery = data.gallery.filter(g => g.id !== id);
      saveContent(data);
      document.querySelectorAll('[class*="panel"]').forEach(p => p.classList.remove('panel-active'));
      document.getElementById('gallery').classList.add('panel-active');
      renderGallery();
    };
  } else {
    editBtn.classList.add('d-none');
    deleteBtn.classList.add('d-none');
    editBtn.onclick = null;
    deleteBtn.onclick = null;
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
  document.getElementById('gallery-detail').classList.add('panel-active');
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function startEditNews(id) {
  const user = getCurrentUser();
  if (!user) return alert('로그인이 필요합니다.');
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
  if (!user) return alert('로그인이 필요합니다.');
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
