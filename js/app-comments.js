function getPostKey(type, id) {
  return `${type}-${id}`;
}

const commentReplyDraftState = {};

function getComments(itemId) {
  const all = JSON.parse(localStorage.getItem(COMMENTS_KEY) || '{}');
  return all[itemId] || { comments: [], recommendUsers: [] };
}

function saveComments(itemId, comments) {
  const all = JSON.parse(localStorage.getItem(COMMENTS_KEY) || '{}');
  all[itemId] = comments;
  localStorage.setItem(COMMENTS_KEY, JSON.stringify(all));
}

function getRecommendCount(itemKey) {
  const info = getComments(itemKey);
  return (info.recommendUsers || []).length;
}

function hasRecommendation(itemKey, username) {
  const info = getComments(itemKey);
  const user = username || getCurrentUser()?.username;
  if (!user) return false;
  return Array.isArray(info.recommendUsers) && info.recommendUsers.includes(user);
}

function getCommentCount(itemKey) {
  const info = getComments(itemKey);
  return Array.isArray(info.comments) ? info.comments.length : 0;
}

function toggleRecommendation(itemKey) {
  const user = getCurrentUser();
  if (!user) {
    notifyMessage('추천하려면 로그인이 필요합니다.');
    return false;
  }
  const info = getComments(itemKey);
  if (!Array.isArray(info.recommendUsers)) info.recommendUsers = [];
  const existingIndex = info.recommendUsers.indexOf(user.username);
  if (existingIndex >= 0) {
    info.recommendUsers.splice(existingIndex, 1);
    saveComments(itemKey, info);
    return true;
  }
  info.recommendUsers.push(user.username);
  saveComments(itemKey, info);
  return true;
}

function togglePostCommentRecommendation(itemKey, commentId, containerId) {
  const user = getCurrentUser();
  if (!user) {
    notifyMessage('추천하려면 로그인이 필요합니다.');
    return;
  }
  const info = getComments(itemKey);
  if (!Array.isArray(info.comments)) info.comments = [];
  const target = info.comments.find(c => c.id === commentId);
  if (!target) return;
  if (!Array.isArray(target.recommendUsers)) target.recommendUsers = [];
  const existingIndex = target.recommendUsers.indexOf(user.username);
  if (existingIndex >= 0) {
    target.recommendUsers.splice(existingIndex, 1);
  } else {
    target.recommendUsers.push(user.username);
  }
  saveComments(itemKey, info);
  renderPostComments(containerId, itemKey);
}

function setRecommendButtonState(button, isActive) {
  if (!button) return;
  button.classList.toggle('btn-outline-primary', !isActive);
  button.classList.toggle('btn-primary', isActive);
}

function hasChildReplies(allComments, commentId) {
  return allComments.some(c => c.parentId === commentId);
}

function escapeHtml(value) {
  return String(value || '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function escapeHtmlAttr(value) {
  return escapeHtml(value).replaceAll('`', '&#96;');
}

function renderNetworkError(container, retryHandler) {
  if (!container) return;
  container.innerHTML = `
    <div class="network-error-box">
      <div class="small text-danger">네트워크 오류가 발생했습니다.</div>
      <button type="button" class="btn btn-sm btn-outline-primary mt-2">다시 시도</button>
    </div>
  `;
  const retryBtn = container.querySelector('button');
  if (retryBtn && typeof retryHandler === 'function') {
    retryBtn.addEventListener('click', retryHandler);
  }
}

function makeSkeletonRows(count = 5, cols = 6) {
  return Array.from({ length: count }).map(() => `
    <tr>
      ${Array.from({ length: cols }).map(() => '<td><span class="skeleton-line w-100"></span></td>').join('')}
    </tr>
  `).join('');
}

function makeSkeletonCards(count = 6) {
  return Array.from({ length: count }).map(() => `
    <div class="col-6 col-md-4">
      <div class="gallery-card skeleton-card">
        <div class="skeleton-block"></div>
        <div class="p-3">
          <span class="skeleton-line w-75 mb-2"></span>
          <span class="skeleton-line w-50"></span>
        </div>
      </div>
    </div>
  `).join('');
}

function renderPostComments(containerId, itemKey) {
  const wrap = document.getElementById(containerId);
  if (!wrap) return;
  const user = getCurrentUser();
  const isAdmin = !!(user && (user.isAdmin || ADMIN_EMAILS.includes(user.email)));
  const commentData = getComments(itemKey);
  const comments = Array.isArray(commentData.comments) ? commentData.comments : [];
  const roots = comments.filter(c => !c.parentId);
  const count = comments.length;

  const renderComment = (comment, isReply = false) => {
    const canDelete = !!(user && (isAdmin || comment.username === user.username));
    const canEdit = !!(user && comment.username === user.username && !hasChildReplies(comments, comment.id));
    const replies = comments.filter(c => c.parentId === comment.id);
    const recommendCount = Array.isArray(comment.recommendUsers) ? comment.recommendUsers.length : 0;
    const didRecommend = !!(user && Array.isArray(comment.recommendUsers) && comment.recommendUsers.includes(user.username));
    const activeReply = commentReplyDraftState[itemKey];
    const showReplyComposer = !!(user && activeReply && Number(activeReply.parentId) === Number(comment.id));
    const replyDraftText = showReplyComposer ? String(activeReply.text || '') : '';
    return `
      <div class="comment-item ${isReply ? 'comment-reply' : ''}" data-id="${comment.id}">
        <div class="comment-author">${escapeHtml(formatAuthorDisplay({ nickname: comment.nickname || comment.name || comment.username, role: comment.role || 'GENERAL' }))}</div>
        <div class="comment-text">${escapeHtml(comment.text)}</div>
        <div class="comment-time d-flex justify-content-between align-items-center gap-2 flex-wrap">
          <span>${new Date(comment.time).toLocaleString('ko-KR')}</span>
          <div class="d-flex gap-1">
            ${user ? `<button class="btn btn-sm ${didRecommend ? 'btn-primary' : 'btn-outline-primary'}" onclick="togglePostCommentRecommendation('${itemKey}', ${comment.id}, '${containerId}')">추천 ${recommendCount}</button>` : `<span class="small text-muted">추천 ${recommendCount}</span>`}
            ${user ? `<button class="btn btn-sm btn-outline-secondary" onclick="startReplyComment('${itemKey}', ${comment.id}, '${containerId}')">답글</button>` : ''}
            ${canEdit ? `<button class="btn btn-sm btn-outline-primary" onclick="startEditComment('${itemKey}', ${comment.id}, '${containerId}')">수정</button>` : ''}
            ${canDelete ? `<button class="btn btn-sm btn-outline-danger" onclick="deletePostComment('${itemKey}', ${comment.id}, '${containerId}')">삭제</button>` : ''}
          </div>
        </div>
        ${showReplyComposer ? `
          <form class="mt-2" onsubmit="submitInlineReply(event, '${itemKey}', ${comment.id}, '${containerId}')">
            <div class="input-group input-group-sm">
              <input
                type="text"
                class="form-control"
                name="replyText"
                value="${escapeHtmlAttr(replyDraftText)}"
                placeholder="답글을 입력하세요"
                required
                autocapitalize="off"
                autocomplete="off"
                inputmode="text"
                spellcheck="false"
                oninput="updateReplyDraft('${itemKey}', ${comment.id}, this.value)"
              >
              <button class="btn btn-primary" type="submit">등록</button>
              <button class="btn btn-outline-secondary" type="button" onclick="cancelReplyComment('${itemKey}', '${containerId}')">취소</button>
            </div>
          </form>
        ` : ''}
        ${replies.map(r => renderComment(r, true)).join('')}
      </div>
    `;
  };

  wrap.innerHTML = `
    <h6 class="fw-bold mb-3">댓글 (${count})</h6>
    <form class="comment-form mb-3" onsubmit="submitPostComment(event, '${itemKey}', '${containerId}')">
      <div class="input-group">
        <input type="text" class="form-control" name="comment" placeholder="댓글을 입력하세요" required autocapitalize="off" autocomplete="off" inputmode="text" spellcheck="false">
        <input type="hidden" name="parentId" value="">
        <input type="hidden" name="editId" value="">
        <button class="btn btn-primary" type="submit">등록</button>
      </div>
      <div class="invalid-feedback d-block d-none" data-comment-error>댓글을 입력해 주세요.</div>
    </form>
    <div class="comment-list">
      ${roots.map(c => renderComment(c)).join('') || '<div class="text-muted small">아직 댓글이 없습니다.</div>'}
    </div>
  `;

  const commentInput = wrap.querySelector('.comment-form [name="comment"]');
  const commentError = wrap.querySelector('[data-comment-error]');
  if (commentInput && commentError) {
    commentInput.addEventListener('input', () => {
      const hasText = !!String(commentInput.value || '').trim();
      commentInput.classList.toggle('is-invalid', !hasText);
      commentError.classList.toggle('d-none', hasText);
    });
  }

  const [postType, rawId] = String(itemKey || '').split('-');
  const postId = Number(rawId || 0);
  const data = getContent();
  if (postType === 'news' && postId) {
    const item = (data.news || []).find(n => n.id === postId);
    if (item) {
      const volunteerStart = item.volunteerStartDate || item.volunteerDate || '';
      const volunteerEnd = item.volunteerEndDate || item.volunteerDate || '';
      updateDetailMeta('news', {
        author: formatAuthorDisplay(item.author || '관리자', getCurrentUser()),
        date: formatDetailDateTime(item.date),
        volunteer: volunteerStart ? `봉사 일자 ${volunteerStart}${volunteerEnd && volunteerEnd !== volunteerStart ? ` ~ ${volunteerEnd}` : ''}` : '',
        views: item.views || 0,
        recommends: getRecommendCount(itemKey),
        comments: getCommentCount(itemKey)
      });
    }
  }
  if (postType === 'gallery' && postId) {
    const item = (data.gallery || []).find(g => g.id === postId);
    if (item) {
      updateDetailMeta('gallery', {
        author: formatAuthorDisplay(item.author || '작성자 미상', getCurrentUser()),
        date: formatDetailDateTime(item.date),
        volunteer: item.year ? `${item.year}년 활동` : '',
        views: item.views || 0,
        recommends: getRecommendCount(itemKey),
        comments: getCommentCount(itemKey)
      });
    }
  }
}

function submitPostComment(event, itemKey, containerId) {
  event.preventDefault();
  const user = getCurrentUser();
  if (!user) {
    notifyMessage('댓글을 작성하려면 로그인이 필요합니다.');
    return;
  }
  const form = event.target;
  const text = form.comment.value.trim();
  const errorEl = form.querySelector('[data-comment-error]');
  if (!text) {
    form.comment.classList.add('is-invalid');
    if (errorEl) errorEl.classList.remove('d-none');
    form.comment.focus();
    return;
  }
  form.comment.classList.remove('is-invalid');
  if (errorEl) errorEl.classList.add('d-none');
  const parentId = Number(form.parentId.value || 0);
  const editId = Number(form.editId.value || 0);
  const info = getComments(itemKey);
  if (!Array.isArray(info.comments)) info.comments = [];

  if (editId) {
    const target = info.comments.find(c => c.id === editId);
    if (target && target.username === user.username) {
      target.text = text;
      target.editedAt = new Date().toISOString();
    }
  } else {
    const newId = Math.max(0, ...info.comments.map(c => c.id || 0)) + 1;
    info.comments.push({
      id: newId,
      parentId: parentId || null,
      username: user.username,
      nickname: user.nickname || user.username,
      role: user.role || 'GENERAL',
      name: user.name,
      text,
      time: new Date().toISOString(),
      recommendUsers: []
    });
  }

  saveComments(itemKey, info);
  delete commentReplyDraftState[itemKey];
  renderPostComments(containerId, itemKey);
}

function startReplyComment(itemKey, parentId, containerId) {
  commentReplyDraftState[itemKey] = {
    parentId: Number(parentId),
    text: ''
  };
  renderPostComments(containerId, itemKey);
  const container = document.getElementById(containerId);
  const input = container?.querySelector(`.comment-item[data-id="${Number(parentId)}"] input[name="replyText"]`);
  if (input) input.focus();
}

function updateReplyDraft(itemKey, parentId, value) {
  const current = commentReplyDraftState[itemKey];
  if (!current || Number(current.parentId) !== Number(parentId)) return;
  current.text = String(value || '');
}

function cancelReplyComment(itemKey, containerId) {
  delete commentReplyDraftState[itemKey];
  renderPostComments(containerId, itemKey);
}

function submitInlineReply(event, itemKey, parentId, containerId) {
  event.preventDefault();
  const user = getCurrentUser();
  if (!user) {
    notifyMessage('댓글을 작성하려면 로그인이 필요합니다.');
    return;
  }
  const form = event.target;
  const text = String(form.replyText?.value || '').trim();
  if (!text) {
    if (form.replyText) form.replyText.focus();
    return;
  }

  const info = getComments(itemKey);
  if (!Array.isArray(info.comments)) info.comments = [];
  const newId = Math.max(0, ...info.comments.map(c => c.id || 0)) + 1;
  info.comments.push({
    id: newId,
    parentId: Number(parentId) || null,
    username: user.username,
    nickname: user.nickname || user.username,
    role: user.role || 'GENERAL',
    name: user.name,
    text,
    time: new Date().toISOString(),
    recommendUsers: []
  });

  saveComments(itemKey, info);
  delete commentReplyDraftState[itemKey];
  renderPostComments(containerId, itemKey);
}

function startEditComment(itemKey, commentId, containerId) {
  const info = getComments(itemKey);
  const target = (info.comments || []).find(c => c.id === commentId);
  if (!target) return;
  if (hasChildReplies(info.comments || [], commentId)) return;
  const container = document.getElementById(containerId);
  if (!container) return;
  const form = container.querySelector('.comment-form');
  if (!form) return;
  form.comment.value = target.text || '';
  form.parentId.value = '';
  form.editId.value = String(commentId);
  delete commentReplyDraftState[itemKey];
  form.comment.focus();
}

function deletePostComment(itemKey, commentId, containerId) {
  const user = getCurrentUser();
  if (!user) return;
  const isAdmin = !!(user.isAdmin || ADMIN_EMAILS.includes(user.email));
  const info = getComments(itemKey);
  const target = (info.comments || []).find(c => c.id === commentId);
  if (!target) return;
  if (!isAdmin && target.username !== user.username) {
    notifyMessage('본인 댓글 또는 관리자만 삭제할 수 있습니다.');
    return;
  }
  if (!confirm('댓글을 삭제하시겠습니까?')) return;

  const toDelete = new Set([commentId]);
  let changed = true;
  while (changed) {
    changed = false;
    (info.comments || []).forEach(c => {
      if (c.parentId && toDelete.has(c.parentId) && !toDelete.has(c.id)) {
        toDelete.add(c.id);
        changed = true;
      }
    });
  }
  info.comments = (info.comments || []).filter(c => !toDelete.has(c.id));
  saveComments(itemKey, info);
  renderPostComments(containerId, itemKey);
}
