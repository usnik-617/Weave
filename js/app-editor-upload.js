function setEditorHtml(editorId, html) {
  const editor = document.getElementById(editorId);
  if (editor) editor.innerHTML = html || '';
}

function ensureRepresentativeImageLabel(editorId) {
  const editor = document.getElementById(editorId);
  if (!editor) return [];
  editor.querySelectorAll('.representative-label').forEach(node => node.remove());
  const images = Array.from(editor.querySelectorAll('img')).filter(img => !!String(img.getAttribute('src') || '').trim());
  images.forEach((img) => img.removeAttribute('data-representative'));
  if (!images.length) return [];
  const first = images[0];
  first.setAttribute('data-representative', 'true');
  const label = document.createElement('div');
  label.className = 'representative-label text-primary fw-bold small mb-1';
  label.textContent = '[대표]';
  first.parentNode?.insertBefore(label, first);
  return images.map((img) => String(img.getAttribute('src') || '').trim()).filter(Boolean);
}

function getEditorImageSources(editorId) {
  const editor = document.getElementById(editorId);
  if (!editor) return [];
  return Array.from(editor.querySelectorAll('img'))
    .map(img => String(img.getAttribute('src') || '').trim())
    .filter(Boolean);
}

function syncEditorToInput(form, editorId, options = {}) {
  const editor = document.getElementById(editorId);
  if (!editor) return;
  if (options.markRepresentative) {
    ensureRepresentativeImageLabel(editorId);
  }
  form.content.value = editor.innerHTML.trim();
}

function setImagePreview(previewId, src) {
  const preview = document.getElementById(previewId);
  if (!preview) return;
  if (src) {
    preview.src = src;
    preview.classList.remove('d-none');
  } else {
    preview.removeAttribute('src');
    preview.classList.add('d-none');
  }
}

function parseDataUrlArray(rawValue) {
  try {
    const parsed = JSON.parse(String(rawValue || '[]'));
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((item) => typeof item === 'string' && item.startsWith('data:'));
  } catch (_) {
    return [];
  }
}

function setFormImageList(form, hiddenName, images) {
  if (!form || !hiddenName || !form.elements[hiddenName]) return;
  const safeImages = Array.isArray(images)
    ? images.filter((item) => typeof item === 'string' && item.startsWith('data:'))
    : [];
  form.elements[hiddenName].value = JSON.stringify(safeImages);
}

function getFormImageList(form, hiddenName) {
  if (!form || !hiddenName || !form.elements[hiddenName]) return [];
  return parseDataUrlArray(form.elements[hiddenName].value);
}

function syncCoverImageFromList(form, imagesHiddenName, coverHiddenName, previewId) {
  if (!form) return;
  const images = getFormImageList(form, imagesHiddenName);
  const cover = images[0] || '';
  if (coverHiddenName && form.elements[coverHiddenName]) {
    form.elements[coverHiddenName].value = cover;
  }
  if (previewId) {
    setImagePreview(previewId, cover);
  }
}

function insertImagesToEditor(editorId, imageDataUrls = []) {
  const editor = document.getElementById(editorId);
  if (!editor || !Array.isArray(imageDataUrls) || !imageDataUrls.length) return;
  editor.focus();

  const selection = window.getSelection();
  let range = null;
  if (selection && selection.rangeCount > 0 && editor.contains(selection.anchorNode)) {
    range = selection.getRangeAt(0).cloneRange();
  } else {
    range = document.createRange();
    range.selectNodeContents(editor);
    range.collapse(false);
  }

  imageDataUrls.forEach((dataUrl) => {
    const imageNode = document.createElement('img');
    imageNode.src = dataUrl;
    imageNode.alt = '업로드 이미지';
    imageNode.style.maxWidth = '100%';
    imageNode.style.height = 'auto';
    imageNode.style.display = 'block';
    imageNode.style.margin = '8px 0';

    const imageWrap = document.createElement('p');
    imageWrap.appendChild(imageNode);

    const spacer = document.createElement('p');
    spacer.innerHTML = '<br>';

    range.insertNode(spacer);
    range.insertNode(imageWrap);
    range.setStartAfter(spacer);
    range.setEndAfter(spacer);
    if (selection) {
      selection.removeAllRanges();
      selection.addRange(range);
    }
  });
}

const IMAGE_UPLOAD_DEFAULT_MAX_BYTES = 420 * 1024;
const IMAGE_UPLOAD_MIN_MAX_BYTES = 140 * 1024;
const IMAGE_UPLOAD_HARD_MAX_BYTES = 820 * 1024;
const IMAGE_UPLOAD_MAX_DIMENSION = 1600;
const IMAGE_UPLOAD_MIN_QUALITY = 0.45;

function getDataUrlByteSize(dataUrl) {
  const text = String(dataUrl || '');
  const base64 = text.includes(',') ? text.split(',')[1] : text;
  if (!base64) return 0;
  const padding = (base64.match(/=+$/) || [''])[0].length;
  return Math.max(0, Math.floor((base64.length * 3) / 4) - padding);
}

function estimateLocalStorageUsageBytes() {
  let total = 0;
  try {
    for (let index = 0; index < localStorage.length; index++) {
      const key = localStorage.key(index) || '';
      const value = localStorage.getItem(key) || '';
      total += (key.length + value.length) * 2;
    }
  } catch (_) {}
  return total;
}

function loadImageFromDataUrl(dataUrl) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error('이미지를 불러오지 못했습니다.'));
    img.src = dataUrl;
  });
}

async function resizeImageDataUrlToMaxBytes(dataUrl, maxBytes = IMAGE_UPLOAD_DEFAULT_MAX_BYTES) {
  const safeLimit = Math.max(IMAGE_UPLOAD_MIN_MAX_BYTES, Math.min(IMAGE_UPLOAD_HARD_MAX_BYTES, Number(maxBytes) || IMAGE_UPLOAD_DEFAULT_MAX_BYTES));
  if (getDataUrlByteSize(dataUrl) <= safeLimit) return String(dataUrl || '');

  const img = await loadImageFromDataUrl(dataUrl);
  let width = img.naturalWidth || img.width;
  let height = img.naturalHeight || img.height;
  const longest = Math.max(width, height);
  if (longest > IMAGE_UPLOAD_MAX_DIMENSION) {
    const ratio = IMAGE_UPLOAD_MAX_DIMENSION / longest;
    width = Math.max(1, Math.round(width * ratio));
    height = Math.max(1, Math.round(height * ratio));
  }

  const canvas = document.createElement('canvas');
  const context = canvas.getContext('2d');
  if (!context) return String(dataUrl || '');

  let scale = 1;
  let quality = 0.9;
  let best = String(dataUrl || '');

  for (let attempt = 0; attempt < 10; attempt++) {
    canvas.width = Math.max(1, Math.round(width * scale));
    canvas.height = Math.max(1, Math.round(height * scale));
    context.clearRect(0, 0, canvas.width, canvas.height);
    context.drawImage(img, 0, 0, canvas.width, canvas.height);

    const candidate = canvas.toDataURL('image/jpeg', quality);
    if (getDataUrlByteSize(candidate) < getDataUrlByteSize(best)) {
      best = candidate;
    }
    if (getDataUrlByteSize(candidate) <= safeLimit) {
      return candidate;
    }

    if (quality > IMAGE_UPLOAD_MIN_QUALITY) {
      quality = Math.max(IMAGE_UPLOAD_MIN_QUALITY, quality - 0.08);
    } else {
      scale *= 0.85;
    }
  }
  return best;
}

function getAdaptiveImageMaxBytes() {
  const storageLimit = 5 * 1024 * 1024;
  const used = estimateLocalStorageUsageBytes();
  const free = Math.max(0, storageLimit - used);
  const adaptive = Math.floor(free * 0.45);
  return Math.max(IMAGE_UPLOAD_MIN_MAX_BYTES, Math.min(IMAGE_UPLOAD_HARD_MAX_BYTES, adaptive || IMAGE_UPLOAD_DEFAULT_MAX_BYTES));
}

function readImageFileToDataUrl(file, onDone) {
  if (!file || !file.type.startsWith('image/')) {
    alert('이미지 파일만 업로드할 수 있습니다.');
    return;
  }
  const reader = new FileReader();
  reader.onload = async () => {
    let result = String(reader.result || '');
    try {
      result = await resizeImageDataUrlToMaxBytes(result, getAdaptiveImageMaxBytes());
    } catch (_) {}
    onDone(result);
  };
  reader.readAsDataURL(file);
}

function readAnyFileToDataUrl(file) {
  return new Promise((resolve, reject) => {
    if (!file) {
      reject(new Error('파일이 비어 있습니다.'));
      return;
    }
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ''));
    reader.onerror = () => reject(new Error('파일을 읽지 못했습니다.'));
    reader.readAsDataURL(file);
  });
}

function readImageFileToDataUrlAsync(file) {
  return new Promise((resolve, reject) => {
    if (!file || !file.type.startsWith('image/')) {
      reject(new Error('이미지 파일만 업로드할 수 있습니다.'));
      return;
    }
    readImageFileToDataUrl(file, (dataUrl) => resolve(String(dataUrl || '')));
  });
}

function bindImageUploader({ formId, inputName, dropzoneId, previewId, hiddenName, imagesHiddenName, editorId }) {
  const form = document.getElementById(formId);
  if (!form) return;
  const input = form.elements[inputName];
  const dropzone = document.getElementById(dropzoneId);
  const applyFiles = async (files) => {
    const imageFiles = Array.from(files || []).filter((file) => file && String(file.type || '').startsWith('image/'));
    if (!imageFiles.length) {
      alert('이미지 파일만 업로드할 수 있습니다.');
      return;
    }
    const uploadedImages = [];
    for (const file of imageFiles) {
      try {
        const dataUrl = await readImageFileToDataUrlAsync(file);
        uploadedImages.push(dataUrl);
      } catch (error) {
        alert(error.message || '이미지 업로드에 실패했습니다.');
        return;
      }
    }

    if (editorId) {
      insertImagesToEditor(editorId, uploadedImages);
      ensureRepresentativeImageLabel(editorId);
    }

    if (input) input.value = '';
  };

  if (input) {
    input.addEventListener('change', async (e) => {
      const files = e.target.files;
      if (files && files.length > 0) {
        await applyFiles(files);
      }
    });
  }
  if (!dropzone) return;
  dropzone.addEventListener('click', () => input && input.click());
  dropzone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropzone.classList.add('dragover');
  });
  dropzone.addEventListener('dragleave', () => dropzone.classList.remove('dragover'));
  dropzone.addEventListener('drop', async (e) => {
    e.preventDefault();
    dropzone.classList.remove('dragover');
    const files = e.dataTransfer?.files;
    if (files && files.length > 0) {
      await applyFiles(files);
    }
  });
}

function insertFileLinkToEditor(editorId, fileName, fileUrl) {
  const editor = document.getElementById(editorId);
  if (!editor) return;
  editor.focus();
  const selection = window.getSelection();
  let range = null;
  if (selection && selection.rangeCount > 0 && editor.contains(selection.anchorNode)) {
    range = selection.getRangeAt(0).cloneRange();
  } else {
    range = document.createRange();
    range.selectNodeContents(editor);
    range.collapse(false);
  }

  const wrapper = document.createElement('p');
  const link = document.createElement('a');
  link.href = fileUrl;
  link.textContent = fileName;
  link.target = '_blank';
  link.rel = 'noopener';
  wrapper.appendChild(link);
  range.insertNode(wrapper);
  range.setStartAfter(wrapper);
  range.setEndAfter(wrapper);
  if (selection) {
    selection.removeAllRanges();
    selection.addRange(range);
  }
}

async function insertActivityFilesToEditor(files = []) {
  const normalized = Array.from(files || []);
  if (!normalized.length) return;
  const imageDataUrls = [];
  for (const file of normalized) {
    const isImage = String(file.type || '').startsWith('image/');
    if (isImage) {
      const dataUrl = await readImageFileToDataUrlAsync(file);
      imageDataUrls.push(dataUrl);
      continue;
    }
    const isPdf = String(file.type || '').toLowerCase() === 'application/pdf' || /\.pdf$/i.test(String(file.name || ''));
    if (!isPdf) continue;
    const dataUrl = await readAnyFileToDataUrl(file);
    insertFileLinkToEditor('activity-editor', `[PDF] ${String(file.name || '첨부파일')}`, dataUrl);
  }
  if (imageDataUrls.length) {
    insertImagesToEditor('activity-editor', imageDataUrls);
  }
  ensureRepresentativeImageLabel('activity-editor');
}

async function buildNoticeAttachments(files = []) {
  const normalized = Array.from(files || []);
  if (!normalized.length) return null;
  if (normalized.length > 5) {
    throw new Error('첨부 파일은 최대 5개까지 업로드할 수 있습니다.');
  }

  const attachments = [];
  for (let index = 0; index < normalized.length; index++) {
    const file = normalized[index];
    const dataUrl = await readAnyFileToDataUrl(file);
    const fallbackName = `첨부파일_${index + 1}`;
    attachments.push({
      id: `att_${Date.now()}_${index}`,
      original_name: file.name || fallbackName,
      name: file.name || fallbackName,
      mime_type: String(file.type || 'application/octet-stream'),
      file_url: dataUrl,
      url: dataUrl,
      download_url: dataUrl,
    });
  }
  return attachments;
}

function bindAboutPhotoUploader() {
  const input = document.getElementById('about-photo-input');
  const button = document.getElementById('about-photo-btn');
  const dropzone = document.getElementById('about-photo-dropzone');
  if (!input) return;

  const hasPermission = () => {
    const user = getCurrentUser();
    return !!(user && user.status === 'active' && (String(user.role || '').toUpperCase() === 'ADMIN' || isAdminUser(user)));
  };

  const ensurePermission = () => {
    if (hasPermission()) return true;
    alert('운영자 권한이 필요합니다.');
    return false;
  };

  const applyFile = (file) => {
    if (!ensurePermission()) return;
    readImageFileToDataUrl(file, async (dataUrl) => {
      const img = document.getElementById('about-volunteer-image');
      if (img) img.src = dataUrl;
      try {
        localStorage.setItem(ABOUT_VOLUNTEER_PHOTO_KEY, dataUrl);
        alert('소개 사진이 변경되었습니다.');
      } catch (error) {
        const quotaExceeded = error && (error.name === 'QuotaExceededError' || error.code === 22);
        if (quotaExceeded) {
          try {
            const tightened = await resizeImageDataUrlToMaxBytes(dataUrl, IMAGE_UPLOAD_MIN_MAX_BYTES);
            localStorage.setItem(ABOUT_VOLUNTEER_PHOTO_KEY, tightened);
            if (img) img.src = tightened;
            alert('소개 사진이 자동으로 용량 조정되어 저장되었습니다.');
          } catch (_) {
            alert('사진 용량이 커서 저장소 한도를 초과했습니다. 이미지 용량을 줄이거나 기존 업로드 이미지를 정리한 뒤 다시 시도해주세요.');
          }
        } else {
          alert('사진 저장 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.');
        }
      }
      input.value = '';
    });
  };

  input.addEventListener('change', (e) => {
    const file = e.target.files && e.target.files[0];
    if (file) applyFile(file);
  });

  if (button) {
    button.addEventListener('click', () => {
      if (!ensurePermission()) return;
      input.click();
    });
  }

  if (!dropzone) return;
  dropzone.addEventListener('click', () => {
    if (!ensurePermission()) return;
    input.click();
  });
  dropzone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropzone.classList.add('dragover');
  });
  dropzone.addEventListener('dragleave', () => dropzone.classList.remove('dragover'));
  dropzone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropzone.classList.remove('dragover');
    const file = e.dataTransfer?.files?.[0];
    if (file) applyFile(file);
  });
}

function initRichEditorToolbars() {
  document.querySelectorAll('.editor-toolbar').forEach(toolbar => {
    const targetId = toolbar.dataset.editorTarget;
    const editor = document.getElementById(targetId);
    if (!editor) return;
    toolbar.querySelectorAll('[data-cmd]').forEach(control => {
      control.addEventListener('click', (e) => {
        e.preventDefault();
        editor.focus();
        const cmd = control.dataset.cmd;
        const value = control.type === 'color' ? control.value : null;
        document.execCommand(cmd, false, value);
      });
    });
  });
}

function ensureGalleryYearOptions(selectedYear) {
  const select = document.getElementById('gallery-year-select');
  if (!select) return;
  const years = [...new Set(getContent().gallery.map(g => Number(g.year)).filter(Boolean))].sort((a, b) => b - a);
  select.innerHTML = years.map(y => `<option value="${y}">${y}</option>`).join('');
  if (selectedYear && years.includes(Number(selectedYear))) {
    select.value = String(selectedYear);
  }
}

function showWriteTab(tabId) {
  const trigger = document.querySelector(`[data-bs-target="#${tabId}"]`);
  if (trigger) {
    const tab = new bootstrap.Tab(trigger);
    tab.show();
  }
}

function openWritePanel(tabId = 'news-admin') {
  document.querySelectorAll('[class*="panel"]').forEach(p => p.classList.remove('panel-active'));
  const writePanel = document.getElementById('write');
  if (writePanel) writePanel.classList.add('panel-active');
  const statsSection = document.getElementById('home-stats');
  if (statsSection) statsSection.style.display = 'none';
  showWriteTab(tabId);
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function resetWriteForms() {
  const newsForm = document.getElementById('add-news-form');
  const galleryForm = document.getElementById('add-gallery-form');
  if (newsForm) {
    newsForm.reset();
    newsForm.editId.value = '';
    newsForm.imageData.value = '';
    if (newsForm.imagesData) newsForm.imagesData.value = '[]';
    if (newsForm.noticeAttachmentFiles) newsForm.noticeAttachmentFiles.value = '';
    if (newsForm.volunteerStartDate) newsForm.volunteerStartDate.value = '';
    if (newsForm.volunteerEndDate) newsForm.volunteerEndDate.value = '';
    if (newsForm.featuredOnHome) newsForm.featuredOnHome.checked = false;
    setEditorHtml('news-editor', '');
    setImagePreview('news-image-preview', '');
    updateVolunteerDateFieldVisibility(newsForm);
  }
  if (galleryForm) {
    galleryForm.reset();
    galleryForm.editId.value = '';
    galleryForm.imageData.value = '';
    if (galleryForm.imagesData) galleryForm.imagesData.value = '[]';
    setEditorHtml('gallery-editor', '');
    setImagePreview('gallery-image-preview', '');
    ensureGalleryYearOptions();
  }
  const activityForm = document.getElementById('calendar-create-form');
  if (activityForm) {
    if (activityForm.content) activityForm.content.value = '';
    if (activityForm.activityAttachmentFiles) activityForm.activityAttachmentFiles.value = '';
    setEditorHtml('activity-editor', '');
  }
}

function updateVolunteerDateFieldVisibility(form) {
  if (!form || !form.postTab) return;
  const wrap = document.getElementById('news-volunteer-date-wrap');
  const attachmentWrap = document.getElementById('news-attachments-wrap');
  const featuredWrap = document.getElementById('news-home-featured-wrap');
  if (!wrap) return;
  const isNotice = form.postTab.value === 'notice';
  wrap.classList.toggle('d-none', !isNotice);
  if (attachmentWrap) attachmentWrap.classList.toggle('d-none', !isNotice);
  if (featuredWrap) featuredWrap.classList.toggle('d-none', !isNotice);
  if (!isNotice) {
    if (form.volunteerStartDate) form.volunteerStartDate.value = '';
    if (form.volunteerEndDate) form.volunteerEndDate.value = '';
    if (form.noticeAttachmentFiles) form.noticeAttachmentFiles.value = '';
    if (form.featuredOnHome) form.featuredOnHome.checked = false;
  }
}
