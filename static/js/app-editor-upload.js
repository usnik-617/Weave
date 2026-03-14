function setEditorHtml(editorId, html) {
  const editor = document.getElementById(editorId);
  if (editor) editor.innerHTML = html || '';
}

function ensureRepresentativeImageLabel(editorId, options = {}) {
  const editor = document.getElementById(editorId);
  if (!editor) return [];
  const showLabel = options.showLabel !== false;
  editor.querySelectorAll('.representative-label').forEach(node => node.remove());
  const images = Array.from(editor.querySelectorAll('img')).filter(img => !!String(img.getAttribute('src') || '').trim());
  images.forEach((img) => img.removeAttribute('data-representative'));
  if (!images.length) return [];
  const first = images[0];
  first.setAttribute('data-representative', 'true');
  if (showLabel) {
    const label = document.createElement('div');
    label.className = 'representative-label text-primary fw-bold small mb-1';
    label.textContent = '[대표]';
    first.parentNode?.insertBefore(label, first);
  }
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
    ensureRepresentativeImageLabel(editorId, {
      showLabel: options.representativeLabel !== false
    });
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
const WRITE_DRAFT_NEWS_KEY = 'weave_draft_news';
const WRITE_DRAFT_GALLERY_KEY = 'weave_draft_gallery';
const IMAGE_UPLOAD_STRIP_EXIF_KEY = 'weave_image_strip_exif';

function getDataUrlByteSize(dataUrl) {
  const text = String(dataUrl || '');
  const base64 = text.includes(',') ? text.split(',')[1] : text;
  if (!base64) return 0;
  const padding = (base64.match(/=+$/) || [''])[0].length;
  return Math.max(0, Math.floor((base64.length * 3) / 4) - padding);
}

function getPreferredImageMimeType() {
  try {
    const canvas = document.createElement('canvas');
    canvas.width = 2;
    canvas.height = 2;
    const sample = canvas.toDataURL('image/webp', 0.8);
    if (typeof sample === 'string' && sample.startsWith('data:image/webp')) {
      return 'image/webp';
    }
  } catch (_) {}
  return 'image/jpeg';
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

async function readImageFileWithOrientation(file) {
  if (!file || !window.createImageBitmap) return '';
  try {
    const bitmap = await createImageBitmap(file, { imageOrientation: 'from-image' });
    let width = bitmap.width;
    let height = bitmap.height;
    const longest = Math.max(width, height);
    if (longest > IMAGE_UPLOAD_MAX_DIMENSION) {
      const ratio = IMAGE_UPLOAD_MAX_DIMENSION / longest;
      width = Math.max(1, Math.round(width * ratio));
      height = Math.max(1, Math.round(height * ratio));
    }
    const canvas = document.createElement('canvas');
    const context = canvas.getContext('2d');
    if (!context) {
      if (typeof bitmap.close === 'function') bitmap.close();
      return '';
    }
    canvas.width = width;
    canvas.height = height;
    context.drawImage(bitmap, 0, 0, width, height);
    if (typeof bitmap.close === 'function') bitmap.close();
    const preferredType = getPreferredImageMimeType();
    return canvas.toDataURL(preferredType, 0.9);
  } catch (_) {
    return '';
  }
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
  const preferredType = getPreferredImageMimeType();

  for (let attempt = 0; attempt < 10; attempt++) {
    canvas.width = Math.max(1, Math.round(width * scale));
    canvas.height = Math.max(1, Math.round(height * scale));
    context.clearRect(0, 0, canvas.width, canvas.height);
    context.drawImage(img, 0, 0, canvas.width, canvas.height);

    const candidate = canvas.toDataURL(preferredType, quality);
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

async function createThumbnailDataUrl(dataUrl, options = {}) {
  const source = String(dataUrl || '').trim();
  if (!source || !source.startsWith('data:image/')) return '';
  const widthLimit = Math.max(80, Number(options.width || 360));
  const heightLimit = Math.max(80, Number(options.height || 220));
  const quality = Math.max(0.4, Math.min(0.92, Number(options.quality || 0.78)));
  const image = await loadImageFromDataUrl(source);
  const sourceWidth = Number(image.naturalWidth || image.width || 0);
  const sourceHeight = Number(image.naturalHeight || image.height || 0);
  if (!sourceWidth || !sourceHeight) return '';
  const ratio = Math.min(widthLimit / sourceWidth, heightLimit / sourceHeight, 1);
  const targetWidth = Math.max(1, Math.round(sourceWidth * ratio));
  const targetHeight = Math.max(1, Math.round(sourceHeight * ratio));
  const canvas = document.createElement('canvas');
  const context = canvas.getContext('2d');
  if (!context) return '';
  canvas.width = targetWidth;
  canvas.height = targetHeight;
  context.clearRect(0, 0, targetWidth, targetHeight);
  context.drawImage(image, 0, 0, targetWidth, targetHeight);
  const preferredType = getPreferredImageMimeType();
  return canvas.toDataURL(preferredType, quality);
}

async function buildEditorThumbnail(editorId, options = {}) {
  const firstImage = (getEditorImageSources(editorId) || [])[0] || '';
  if (!firstImage) return '';
  try {
    return await createThumbnailDataUrl(firstImage, options);
  } catch (_) {
    return '';
  }
}

function getAdaptiveImageMaxBytes() {
  const storageLimit = 5 * 1024 * 1024;
  const used = estimateLocalStorageUsageBytes();
  const free = Math.max(0, storageLimit - used);
  const adaptive = Math.floor(free * 0.45);
  return Math.max(IMAGE_UPLOAD_MIN_MAX_BYTES, Math.min(IMAGE_UPLOAD_HARD_MAX_BYTES, adaptive || IMAGE_UPLOAD_DEFAULT_MAX_BYTES));
}

function shouldStripExifMetadata() {
  const newsToggle = document.getElementById('news-strip-exif');
  const galleryToggle = document.getElementById('gallery-strip-exif');
  if (newsToggle instanceof HTMLInputElement && newsToggle.checked === false) return false;
  if (galleryToggle instanceof HTMLInputElement && galleryToggle.checked === false) return false;
  const stored = String(localStorage.getItem(IMAGE_UPLOAD_STRIP_EXIF_KEY) || '').trim().toLowerCase();
  if (stored === '0' || stored === 'false') return false;
  return true;
}

function persistStripExifPreference() {
  const enabled = shouldStripExifMetadata();
  try {
    localStorage.setItem(IMAGE_UPLOAD_STRIP_EXIF_KEY, enabled ? '1' : '0');
  } catch (_) {}
}

function readImageFileToDataUrl(file, onDone, options = {}) {
  if (!file || !file.type.startsWith('image/')) {
    notifyMessage('이미지 파일만 업로드할 수 있습니다.');
    return;
  }
  const reader = new FileReader();
  reader.onload = async () => {
    let result = String(reader.result || '');
    try {
      const stripExif = typeof options.stripExif === 'boolean'
        ? options.stripExif
        : shouldStripExifMetadata();
      if (stripExif) {
        const oriented = await readImageFileWithOrientation(file);
        if (oriented) result = oriented;
        result = await resizeImageDataUrlToMaxBytes(result, getAdaptiveImageMaxBytes());
      }
    } catch (_) {}
    onDone(result);
  };
  reader.readAsDataURL(file);
}

function bindWriteDraftAutosave({ formId, editorId, storageKey, fields = [] }) {
  const form = document.getElementById(formId);
  const editor = document.getElementById(editorId);
  if (!form || !editor || !storageKey) return;

  const saveDraft = () => {
    const snapshot = {
      content: String(editor.innerHTML || ''),
      updatedAt: new Date().toISOString()
    };
    fields.forEach((fieldName) => {
      const field = form.elements[fieldName];
      if (!field) return;
      snapshot[fieldName] = field.type === 'checkbox' ? !!field.checked : String(field.value || '');
    });
    localStorage.setItem(storageKey, JSON.stringify(snapshot));
  };

  const restoreDraft = () => {
    let parsed = null;
    try {
      parsed = JSON.parse(localStorage.getItem(storageKey) || '{}');
    } catch (_) {
      parsed = null;
    }
    if (!parsed || typeof parsed !== 'object') return;
    const hasMeaningfulDraft = String(parsed.content || '').trim() || fields.some((name) => String(parsed[name] || '').trim());
    if (!hasMeaningfulDraft) return;
    editor.innerHTML = String(parsed.content || '');
    fields.forEach((fieldName) => {
      const field = form.elements[fieldName];
      if (!field) return;
      if (field.type === 'checkbox') {
        field.checked = !!parsed[fieldName];
      } else {
        field.value = String(parsed[fieldName] || '');
      }
    });
  };

  restoreDraft();
  editor.addEventListener('input', saveDraft);
  fields.forEach((fieldName) => {
    const field = form.elements[fieldName];
    if (!field) return;
    field.addEventListener('input', saveDraft);
    field.addEventListener('change', saveDraft);
  });
}

function initWriteDraftAutosave() {
  bindWriteDraftAutosave({
    formId: 'add-news-form',
    editorId: 'news-editor',
    storageKey: WRITE_DRAFT_NEWS_KEY,
    fields: ['title', 'author', 'postTab', 'volunteerStartDate', 'volunteerEndDate', 'publishAt']
  });
  bindWriteDraftAutosave({
    formId: 'add-gallery-form',
    editorId: 'gallery-editor',
    storageKey: WRITE_DRAFT_GALLERY_KEY,
    fields: ['title', 'year', 'publishAt']
  });
}

document.addEventListener('DOMContentLoaded', () => {
  const stored = String(localStorage.getItem(IMAGE_UPLOAD_STRIP_EXIF_KEY) || '1');
  const enabled = !(stored === '0' || stored.toLowerCase() === 'false');
  ['news-strip-exif', 'gallery-strip-exif'].forEach((id) => {
    const el = document.getElementById(id);
    if (!(el instanceof HTMLInputElement)) return;
    el.checked = enabled;
    el.addEventListener('change', persistStripExifPreference);
  });
});

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

function readImageFileToDataUrlAsync(file, options = {}) {
  return new Promise((resolve, reject) => {
    if (!file || !file.type.startsWith('image/')) {
      reject(new Error('이미지 파일만 업로드할 수 있습니다.'));
      return;
    }
    readImageFileToDataUrl(file, (dataUrl) => resolve(String(dataUrl || '')), options);
  });
}

function bindImageUploader({ formId, inputName, dropzoneId, previewId, hiddenName, imagesHiddenName, editorId, stripExifToggleId = '' }) {
  const form = document.getElementById(formId);
  if (!form) return;
  const input = form.elements[inputName];
  const dropzone = document.getElementById(dropzoneId);
  const resolveStripExif = () => {
    const toggle = stripExifToggleId ? document.getElementById(stripExifToggleId) : null;
    if (toggle instanceof HTMLInputElement) return !!toggle.checked;
    return shouldStripExifMetadata();
  };

  const applyFiles = async (files) => {
    const imageFiles = Array.from(files || []).filter((file) => file && String(file.type || '').startsWith('image/'));
    if (!imageFiles.length) {
      notifyMessage('이미지 파일만 업로드할 수 있습니다.');
      return;
    }
    const uploadedImages = [];
    for (const file of imageFiles) {
      try {
        const dataUrl = await readImageFileToDataUrlAsync(file, { stripExif: resolveStripExif() });
        uploadedImages.push(dataUrl);
      } catch (error) {
        notifyMessage(error.message || '이미지 업로드에 실패했습니다.');
        return;
      }
    }

    if (editorId) {
      insertImagesToEditor(editorId, uploadedImages);
      ensureRepresentativeImageLabel(editorId, { showLabel: editorId !== 'gallery-editor' });
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
    return !!(user && user.status === 'active' && isStaffUser(user));
  };

  const ensurePermission = () => {
    if (hasPermission()) return true;
    notifyMessage('운영진 권한이 필요합니다.');
    return false;
  };

  const applyFile = (file) => {
    if (!ensurePermission()) return;
    readImageFileToDataUrl(file, async (dataUrl) => {
      const img = document.getElementById('about-volunteer-image');
      if (img) img.src = dataUrl;
      try {
        localStorage.setItem(ABOUT_VOLUNTEER_PHOTO_KEY, dataUrl);
        if (typeof renderAboutVolunteerPhoto === 'function') renderAboutVolunteerPhoto();
        notifyMessage('소개 사진이 변경되었습니다.');
      } catch (error) {
        const quotaExceeded = error && (error.name === 'QuotaExceededError' || error.code === 22);
        if (quotaExceeded) {
          try {
            const tightened = await resizeImageDataUrlToMaxBytes(dataUrl, IMAGE_UPLOAD_MIN_MAX_BYTES);
            localStorage.setItem(ABOUT_VOLUNTEER_PHOTO_KEY, tightened);
            if (img) img.src = tightened;
            if (typeof renderAboutVolunteerPhoto === 'function') renderAboutVolunteerPhoto();
            notifyMessage('소개 사진이 자동으로 용량 조정되어 저장되었습니다.');
          } catch (_) {
            notifyMessage('사진 용량이 커서 저장 시도를 초과했습니다. 이미지 용량을 줄이거나 기존 업로드 이미지를 정리한 뒤 다시 시도해 주세요.');
          }
        } else {
          notifyMessage('사진 저장 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.');
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
    localStorage.removeItem(WRITE_DRAFT_NEWS_KEY);
  }
  if (galleryForm) {
    galleryForm.reset();
    galleryForm.editId.value = '';
    galleryForm.imageData.value = '';
    if (galleryForm.imagesData) galleryForm.imagesData.value = '[]';
    setEditorHtml('gallery-editor', '');
    setImagePreview('gallery-image-preview', '');
    ensureGalleryYearOptions();
    localStorage.removeItem(WRITE_DRAFT_GALLERY_KEY);
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
