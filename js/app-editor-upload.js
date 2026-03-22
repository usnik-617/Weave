function setEditorHtml(editorId, html) {
  const editor = document.getElementById(editorId);
  if (!editor) return;
  editor.innerHTML = html || '';
  if (editorId === 'gallery-editor') {
    ensureGalleryEditorGrid(editorId);
  } else if (editorId === 'news-editor') {
    ensureInlineEditorImageDeleteUi(editorId);
  }
  syncRepresentativePreview(editorId);
}

function ensureRepresentativeImageLabel(editorId, options = {}) {
  const editor = document.getElementById(editorId);
  if (!editor) return [];
  const showLabel = options.showLabel !== false;
  editor.querySelectorAll('.representative-label').forEach(node => node.remove());
  const images = Array.from(editor.querySelectorAll('img')).filter(img => !!String(img.getAttribute('src') || '').trim());
  const pinned = images.find((img) => String(img.getAttribute('data-representative') || '').toLowerCase() === 'true');
  images.forEach((img) => img.removeAttribute('data-representative'));
  if (!images.length) return [];
  const first = pinned || images[0];
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

function getRepresentativeEditorImageSource(editorId) {
  const editor = document.getElementById(editorId);
  if (!editor) return '';
  const pinned = editor.querySelector('img[data-representative="true"]');
  const fromPinned = String(pinned?.getAttribute('src') || '').trim();
  if (fromPinned) return fromPinned;
  const first = editor.querySelector('img');
  return String(first?.getAttribute('src') || '').trim();
}

function syncRepresentativePreview(editorId) {
  const src = getRepresentativeEditorImageSource(editorId);
  if (editorId === 'gallery-editor') {
    setImagePreview('gallery-image-preview', src);
  } else if (editorId === 'news-editor') {
    setImagePreview('news-image-preview', src);
  }
}

function syncEditorToInput(form, editorId, options = {}) {
  const editor = document.getElementById(editorId);
  if (!editor) return;
  if (options.markRepresentative) {
    ensureRepresentativeImageLabel(editorId, {
      showLabel: options.representativeLabel !== false
    });
    syncRepresentativePreview(editorId);
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

function makeTodayDateInputValue() {
  const now = new Date();
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, '0');
  const d = String(now.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

function bindGalleryGridDnD(grid) {
  if (!grid) return;
  let draggingItem = null;
  grid.querySelectorAll('.gallery-image-grid-item').forEach((item) => {
    item.draggable = true;
    item.addEventListener('dragstart', () => {
      draggingItem = item;
      item.classList.add('is-dragging');
    });
    item.addEventListener('dragend', () => {
      item.classList.remove('is-dragging');
      draggingItem = null;
    });
    item.addEventListener('dragover', (event) => {
      event.preventDefault();
    });
    item.addEventListener('drop', (event) => {
      event.preventDefault();
      if (!draggingItem || draggingItem === item) return;
      const rect = item.getBoundingClientRect();
      const before = (event.clientX - rect.left) < (rect.width / 2);
      if (before) {
        item.parentNode?.insertBefore(draggingItem, item);
      } else {
        item.parentNode?.insertBefore(draggingItem, item.nextSibling);
      }
    });
  });
}

function ensureEditorImageDeleteConfirmModal() {
  const modalId = 'editor-image-delete-confirm-modal';
  let modalEl = document.getElementById(modalId);
  if (!modalEl) {
    const wrapper = document.createElement('div');
    wrapper.innerHTML = `
      <div class="modal fade" id="${modalId}" tabindex="-1" aria-hidden="true">
        <div class="modal-dialog modal-dialog-centered">
          <div class="modal-content">
            <div class="modal-header">
              <h5 class="modal-title">이미지 삭제</h5>
              <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="닫기"></button>
            </div>
            <div class="modal-body">
              <div class="d-flex flex-column gap-2">
                <img id="editor-image-delete-confirm-thumb" class="editor-delete-confirm-thumb d-none" alt="삭제할 이미지 미리보기">
                <p class="mb-0" id="editor-image-delete-confirm-text"></p>
              </div>
            </div>
            <div class="modal-footer">
              <button type="button" class="btn btn-outline-secondary" id="editor-image-delete-cancel-btn" data-bs-dismiss="modal">아니오</button>
              <button type="button" class="btn btn-danger" id="editor-image-delete-confirm-btn">삭제</button>
            </div>
          </div>
        </div>
      </div>`;
    document.body.appendChild(wrapper.firstElementChild);
    modalEl = document.getElementById(modalId);
  }
  return {
    modalEl,
    textEl: document.getElementById('editor-image-delete-confirm-text'),
    thumbEl: document.getElementById('editor-image-delete-confirm-thumb'),
    confirmBtn: document.getElementById('editor-image-delete-confirm-btn')
  };
}

function askEditorImageDeleteConfirm(message = '선택한 이미지를 삭제할까요?', imageSrc = '') {
  const safeMessage = String(message || '선택한 이미지를 삭제할까요?').trim();
  if (!window.bootstrap?.Modal) {
    return Promise.resolve(window.confirm(safeMessage));
  }
  const { modalEl, textEl, thumbEl, confirmBtn } = ensureEditorImageDeleteConfirmModal();
  if (!modalEl || !confirmBtn) return Promise.resolve(false);
  if (textEl) textEl.textContent = safeMessage;
  if (thumbEl) {
    const safeSrc = String(imageSrc || '').trim();
    if (safeSrc) {
      thumbEl.src = safeSrc;
      thumbEl.classList.remove('d-none');
    } else {
      thumbEl.removeAttribute('src');
      thumbEl.classList.add('d-none');
    }
  }
  const modal = bootstrap.Modal.getOrCreateInstance(modalEl, { backdrop: 'static' });
  return new Promise((resolve) => {
    let finished = false;
    const complete = (result) => {
      if (finished) return;
      finished = true;
      resolve(!!result);
    };
    const handleHidden = () => {
      modalEl.removeEventListener('hidden.bs.modal', handleHidden);
      confirmBtn.removeEventListener('click', handleConfirm);
      complete(false);
    };
    const handleConfirm = () => {
      modalEl.removeEventListener('hidden.bs.modal', handleHidden);
      confirmBtn.removeEventListener('click', handleConfirm);
      complete(true);
      modal.hide();
    };
    modalEl.addEventListener('hidden.bs.modal', handleHidden);
    confirmBtn.addEventListener('click', handleConfirm);
    modal.show();
  });
}

function ensureInlineEditorImageDeleteUi(editorId = 'news-editor') {
  const editor = document.getElementById(editorId);
  if (!editor) return;
  const images = Array.from(editor.querySelectorAll('img')).filter((img) => !img.closest('.gallery-image-grid-item'));
  images.forEach((img) => {
    let wrap = img.closest('.editor-inline-image-wrap');
    if (!wrap) {
      wrap = document.createElement('div');
      wrap.className = 'editor-inline-image-wrap';
      const parent = img.parentNode;
      if (parent) {
        parent.insertBefore(wrap, img);
        wrap.appendChild(img);
      }
    }
    let deleteBtn = wrap.querySelector('.editor-image-delete-btn');
    if (!deleteBtn) {
      deleteBtn = document.createElement('button');
      deleteBtn.type = 'button';
      deleteBtn.className = 'editor-image-delete-btn';
      deleteBtn.textContent = '삭제';
      deleteBtn.addEventListener('click', async (event) => {
        event.preventDefault();
        event.stopPropagation();
        const ok = await askEditorImageDeleteConfirm('이 이미지를 삭제할까요?', String(img.getAttribute('src') || ''));
        if (!ok) return;
        wrap.remove();
        ensureRepresentativeImageLabel(editorId, { showLabel: true });
        syncRepresentativePreview(editorId);
      });
      wrap.appendChild(deleteBtn);
    }
  });
}

function refreshGalleryGridPinUi(grid) {
  if (!grid) return;
  const items = Array.from(grid.querySelectorAll('.gallery-image-grid-item'));
  items.forEach((item) => {
    let pinBtn = item.querySelector('.gallery-image-pin-btn');
    let deleteBtn = item.querySelector('.gallery-image-delete-btn');
    const img = item.querySelector('img');
    if (!img) return;
    if (!pinBtn) {
      pinBtn = document.createElement('button');
      pinBtn.type = 'button';
      pinBtn.className = 'gallery-image-pin-btn';
      pinBtn.title = '대표 이미지로 고정';
      pinBtn.innerHTML = '<i class="fas fa-thumbtack"></i>';
      item.appendChild(pinBtn);
      pinBtn.addEventListener('click', (event) => {
        event.preventDefault();
        event.stopPropagation();
        const allImages = Array.from(grid.querySelectorAll('.gallery-image-grid-item img'));
        allImages.forEach((target) => target.removeAttribute('data-representative'));
        img.setAttribute('data-representative', 'true');
        refreshGalleryGridPinUi(grid);
      });
    }
    if (!deleteBtn) {
      deleteBtn = document.createElement('button');
      deleteBtn.type = 'button';
      deleteBtn.className = 'gallery-image-delete-btn';
      deleteBtn.title = '이미지 삭제';
      deleteBtn.textContent = '삭제';
      item.appendChild(deleteBtn);
      deleteBtn.addEventListener('click', async (event) => {
        event.preventDefault();
        event.stopPropagation();
        const ok = await askEditorImageDeleteConfirm('이 이미지를 삭제할까요?', String(img.getAttribute('src') || ''));
        if (!ok) return;
        const wasPinned = String(img.getAttribute('data-representative') || '').toLowerCase() === 'true';
        item.remove();
        if (wasPinned) {
          const first = grid.querySelector('.gallery-image-grid-item img');
          if (first) first.setAttribute('data-representative', 'true');
        }
        refreshGalleryGridPinUi(grid);
        syncRepresentativePreview('gallery-editor');
      });
    }
    const pinned = String(img.getAttribute('data-representative') || '').toLowerCase() === 'true';
    item.classList.toggle('is-pinned', pinned);
    pinBtn.classList.toggle('active', pinned);
  });
  syncRepresentativePreview('gallery-editor');
}

function ensureGalleryEditorGrid(editorId = 'gallery-editor') {
  const editor = document.getElementById(editorId);
  if (!editor) return null;
  let grid = editor.querySelector('.gallery-image-grid');
  if (!grid) {
    grid = document.createElement('div');
    grid.className = 'gallery-image-grid';
    editor.appendChild(grid);
  }
  const candidates = Array.from(editor.querySelectorAll('img'));
  candidates.forEach((img) => {
    if (img.closest('.gallery-image-grid-item')) return;
    const src = String(img.getAttribute('src') || '').trim();
    if (!src) return;
    const item = document.createElement('div');
    item.className = 'gallery-image-grid-item';
    const movedImg = img.cloneNode(true);
    movedImg.style.maxWidth = '';
    movedImg.style.height = '';
    movedImg.style.display = '';
    movedImg.style.margin = '';
    item.appendChild(movedImg);
    grid.appendChild(item);
    const parent = img.parentElement;
    if (parent && parent !== editor) {
      parent.remove();
    } else {
      img.remove();
    }
  });
  bindGalleryGridDnD(grid);
  if (!grid.querySelector('img[data-representative="true"]')) {
    const first = grid.querySelector('img');
    if (first) first.setAttribute('data-representative', 'true');
  }
  refreshGalleryGridPinUi(grid);
  syncRepresentativePreview(editorId);
  return grid;
}

function insertImagesToEditor(editorId, imageDataUrls = []) {
  const editor = document.getElementById(editorId);
  if (!editor || !Array.isArray(imageDataUrls) || !imageDataUrls.length) return 0;
  if (editorId === 'gallery-editor') {
    const grid = ensureGalleryEditorGrid(editorId);
    if (!grid) return 0;
    let inserted = 0;
    imageDataUrls.forEach((dataUrl) => {
      const item = document.createElement('div');
      item.className = 'gallery-image-grid-item';
      const imageNode = document.createElement('img');
      imageNode.src = dataUrl;
      imageNode.alt = '업로드 이미지';
      imageNode.loading = 'lazy';
      imageNode.decoding = 'async';
      item.appendChild(imageNode);
      grid.appendChild(item);
      inserted += 1;
    });
    bindGalleryGridDnD(grid);
    return inserted;
  }
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
  if (editorId === 'news-editor') {
    ensureInlineEditorImageDeleteUi(editorId);
  }
  syncRepresentativePreview(editorId);
  return imageDataUrls.length;
}

const IMAGE_UPLOAD_DEFAULT_MAX_BYTES = 420 * 1024;
const IMAGE_UPLOAD_MIN_MAX_BYTES = 140 * 1024;
const IMAGE_UPLOAD_HARD_MAX_BYTES = 820 * 1024;
const IMAGE_UPLOAD_MAX_DIMENSION = 1600;
const IMAGE_UPLOAD_MIN_QUALITY = 0.45;
const IMAGE_UPLOAD_MAX_FILE_BYTES = 25 * 1024 * 1024;
const POST_IMAGE_MAX_COUNT = 30;
const POST_IMAGE_TOTAL_MAX_BYTES = 300 * 1024 * 1024;
const IMAGE_UPLOAD_MAX_PARALLEL = 4;
const GALLERY_IMAGE_MAX_BYTES = 360 * 1024;
const WRITE_DRAFT_NEWS_KEY = 'weave_draft_news';
const WRITE_DRAFT_GALLERY_KEY = 'weave_draft_gallery';
const IMAGE_UPLOAD_STRIP_EXIF_KEY = 'weave_image_strip_exif';
const IMAGE_COMPRESSION_LEVEL_KEY = 'weave_image_compression_level';
const IMAGE_COMPRESSION_PROFILES = {
  original: { label: '원본', maxBytes: 0 },
  high: { label: '고화질', maxBytes: 560 * 1024 },
  standard: { label: '표준', maxBytes: 360 * 1024 },
  compact: { label: '고압축', maxBytes: 220 * 1024 },
};

function formatBytes(bytes) {
  const safe = Math.max(0, Number(bytes || 0));
  if (safe < 1024) return `${safe} B`;
  const kb = safe / 1024;
  if (kb < 1024) return `${kb.toFixed(kb >= 100 ? 0 : 1)} KB`;
  const mb = kb / 1024;
  if (mb < 1024) return `${mb.toFixed(mb >= 100 ? 0 : 1)} MB`;
  const gb = mb / 1024;
  return `${gb.toFixed(1)} GB`;
}

function getCompressionLevelFromSelect(selectId = '') {
  const select = selectId ? document.getElementById(selectId) : null;
  if (!(select instanceof HTMLSelectElement)) return 'standard';
  const value = String(select.value || '').trim().toLowerCase();
  if (IMAGE_COMPRESSION_PROFILES[value]) return value;
  return 'standard';
}

function getCompressionMaxBytes(level = 'standard', fallbackBytes = 0) {
  const normalized = String(level || '').trim().toLowerCase();
  if (IMAGE_COMPRESSION_PROFILES[normalized]) {
    const profileBytes = Number(IMAGE_COMPRESSION_PROFILES[normalized].maxBytes || 0);
    if (profileBytes > 0) return profileBytes;
    return Number(fallbackBytes || 0) || 0;
  }
  return Number(fallbackBytes || 0) || 0;
}

function isSupportedImageUploadFile(file) {
  const mime = String(file?.type || '').toLowerCase();
  const name = String(file?.name || '').toLowerCase();
  const byMime = mime.startsWith('image/');
  const byExt = /\.(jpg|jpeg|png|webp|gif|heic|heif)$/i.test(name);
  return byMime || byExt;
}

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
  const sourceText = String(dataUrl || '');
  const mimeMatch = sourceText.match(/^data:(image\/[a-zA-Z0-9+.-]+);/i);
  const sourceMime = String(mimeMatch?.[1] || '').toLowerCase();
  const preferredType = getPreferredImageMimeType();
  const shouldPreferWebp = preferredType === 'image/webp' && sourceMime && sourceMime !== 'image/webp' && sourceMime !== 'image/gif';
  if (getDataUrlByteSize(dataUrl) <= safeLimit && !shouldPreferWebp) return sourceText;

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

function readImageFileToDataUrl(file, onDone, options = {}, onError = null) {
  if (!file || !isSupportedImageUploadFile(file)) {
    const error = new Error('이미지 파일만 업로드할 수 있습니다.');
    notifyMessage(error.message);
    if (typeof onError === 'function') onError(error);
    return;
  }
  const reader = new FileReader();
  reader.onload = async () => {
    let result = String(reader.result || '');
    try {
      const rawType = String(file.type || '').toLowerCase();
      const rawName = String(file.name || '').toLowerCase();
      const isHeicLike = /image\/hei[cf]/.test(rawType) || /\.(heic|heif)$/.test(rawName);
      if (isHeicLike) {
        const converted = await readImageFileWithOrientation(file);
        if (!converted || !String(converted).startsWith('data:image/')) {
          throw new Error('HEIC/HEIF 변환에 실패했습니다. iPhone 설정에서 카메라 포맷을 "높은 호환성(JPG)"으로 변경하거나 JPG/PNG/WebP로 변환 후 다시 업로드해 주세요.');
        }
        result = converted;
      }
      const stripExif = typeof options.stripExif === 'boolean'
        ? options.stripExif
        : shouldStripExifMetadata();
      if (stripExif && !isHeicLike) {
        const oriented = await readImageFileWithOrientation(file);
        if (oriented) result = oriented;
      }
      const configuredMaxBytes = Number(options.maxBytes || 0);
      const perImageLimit = configuredMaxBytes > 0
        ? Math.max(70 * 1024, configuredMaxBytes)
        : 0;
      if (perImageLimit > 0) {
        result = await resizeImageDataUrlToMaxBytes(result, perImageLimit);
      }
      if (!String(result || '').startsWith('data:image/')) {
        throw new Error('이미지 변환 결과가 올바르지 않습니다.');
      }
    } catch (error) {
      const safeError = error instanceof Error ? error : new Error('이미지 처리 중 오류가 발생했습니다.');
      notifyMessage(safeError.message || '이미지 처리 중 오류가 발생했습니다.');
      if (typeof onError === 'function') onError(safeError);
      return;
    }
    onDone(result);
  };
  reader.onerror = () => {
    const error = new Error('이미지 파일을 읽을 수 없습니다.');
    notifyMessage(error.message);
    if (typeof onError === 'function') onError(error);
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
    fields: ['title', 'year', 'publishAt', 'activityDuration', 'activityStartDate', 'activityEndDate']
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
    if (!file || !isSupportedImageUploadFile(file)) {
      reject(new Error('이미지 파일만 업로드할 수 있습니다.'));
      return;
    }
    readImageFileToDataUrl(
      file,
      (dataUrl) => resolve(String(dataUrl || '')),
      options,
      (error) => reject(error instanceof Error ? error : new Error('이미지 처리 중 오류가 발생했습니다.'))
    );
  });
}

function bindImageUploader({
  formId,
  inputName,
  dropzoneId,
  previewId,
  hiddenName,
  imagesHiddenName,
  editorId,
  stripExifToggleId = '',
  progressWrapId = '',
  progressBarId = '',
  progressTextId = '',
  progressPercentId = '',
  queueListId = '',
  queueSummaryId = '',
  queueRetryBtnId = '',
  totalGaugeBarId = '',
  totalGaugeTextId = '',
  compressionSelectId = '',
  limitHintId = '',
  limitHintPrefix = '본문 이미지',
  maxImageBytes = 0
}) {
  const form = document.getElementById(formId);
  if (!form) return;
  const input = form.elements[inputName];
  const dropzone = document.getElementById(dropzoneId);
  const progressWrap = progressWrapId ? document.getElementById(progressWrapId) : null;
  const progressBar = progressBarId ? document.getElementById(progressBarId) : null;
  const progressText = progressTextId ? document.getElementById(progressTextId) : null;
  const progressPercent = progressPercentId ? document.getElementById(progressPercentId) : null;
  const queueList = queueListId ? document.getElementById(queueListId) : null;
  const queueSummary = queueSummaryId ? document.getElementById(queueSummaryId) : null;
  const queueRetryBtn = queueRetryBtnId ? document.getElementById(queueRetryBtnId) : null;
  const totalGaugeBar = totalGaugeBarId ? document.getElementById(totalGaugeBarId) : null;
  const totalGaugeText = totalGaugeTextId ? document.getElementById(totalGaugeTextId) : null;
  const compressionSelect = compressionSelectId ? document.getElementById(compressionSelectId) : null;
  let queueItems = [];

  const updateCompressionPreference = () => {
    const level = getCompressionLevelFromSelect(compressionSelectId);
    try {
      localStorage.setItem(IMAGE_COMPRESSION_LEVEL_KEY, level);
    } catch (_) {}
  };
  if (compressionSelect instanceof HTMLSelectElement) {
    const storedLevel = String(localStorage.getItem(IMAGE_COMPRESSION_LEVEL_KEY) || '').trim().toLowerCase();
    if (IMAGE_COMPRESSION_PROFILES[storedLevel]) {
      compressionSelect.value = storedLevel;
    } else if (!String(compressionSelect.value || '').trim()) {
      compressionSelect.value = 'standard';
    }
    compressionSelect.addEventListener('change', updateCompressionPreference);
  }

  const setQueueStatus = (itemId, status, reason = '') => {
    queueItems = queueItems.map((item) => {
      if (item.id !== itemId) return item;
      return { ...item, status, reason: reason || item.reason || '' };
    });
  };
  const renderQueue = () => {
    if (!queueList && !queueSummary && !queueRetryBtn) return;
    if (queueList) {
      queueList.innerHTML = queueItems.map((item) => {
        const cls = `is-${item.status || 'waiting'}`;
        const safeName = String(item.name || '이름없음');
        const safeReason = String(item.reason || '').trim();
        const reasonHtml = safeReason ? `<span class="upload-queue-reason">${safeReason}</span>` : '';
        return `<li class="upload-queue-item ${cls}" data-queue-id="${item.id}">
          <span class="upload-queue-name">${safeName}</span>
          <span class="upload-queue-status">${item.status === 'success' ? '성공' : item.status === 'failed' ? '실패' : item.status === 'processing' ? '처리중' : '대기'}</span>
          ${reasonHtml}
        </li>`;
      }).join('');
    }
    const successCount = queueItems.filter((item) => item.status === 'success').length;
    const failCount = queueItems.filter((item) => item.status === 'failed').length;
    const waitCount = queueItems.filter((item) => item.status === 'waiting' || item.status === 'processing').length;
    if (queueSummary) {
      queueSummary.textContent = `대기 ${waitCount} / 성공 ${successCount} / 실패 ${failCount}`;
    }
    if (queueRetryBtn) {
      queueRetryBtn.classList.toggle('d-none', failCount <= 0);
    }
  };

  const updateTotalGauge = (selectedBytes = 0) => {
    if (!totalGaugeBar && !totalGaugeText) return;
    let existingBytes = 0;
    if (editorId) {
      existingBytes = getEditorImageSources(editorId).reduce((sum, src) => sum + getDataUrlByteSize(src), 0);
    }
    const total = Math.max(0, Number(existingBytes + selectedBytes));
    const ratio = Math.min(100, Math.round((total / POST_IMAGE_TOTAL_MAX_BYTES) * 100));
    if (totalGaugeBar) {
      totalGaugeBar.style.width = `${ratio}%`;
      totalGaugeBar.setAttribute('aria-valuenow', String(ratio));
    }
    if (totalGaugeText) {
      totalGaugeText.textContent = `${formatBytes(total)} / ${formatBytes(POST_IMAGE_TOTAL_MAX_BYTES)}`;
    }
  };

  const setProgress = (value, label = '') => {
    const safe = Math.max(0, Math.min(100, Number(value || 0)));
    if (progressWrap) progressWrap.classList.remove('d-none');
    if (progressBar) {
      progressBar.style.width = `${safe}%`;
      progressBar.setAttribute('aria-valuenow', String(safe));
    }
    if (progressPercent) progressPercent.textContent = String(safe);
    if (progressText && label) progressText.textContent = label;
  };
  const finishProgress = () => {
    if (!progressWrap) return;
    window.setTimeout(() => {
      if (progressWrap) progressWrap.classList.add('d-none');
      if (progressBar) progressBar.style.width = '0%';
      if (progressPercent) progressPercent.textContent = '0';
      if (progressText) progressText.textContent = '업로드 준비중...';
    }, 420);
  };
  const resolveStripExif = () => {
    const toggle = stripExifToggleId ? document.getElementById(stripExifToggleId) : null;
    if (toggle instanceof HTMLInputElement) return !!toggle.checked;
    return shouldStripExifMetadata();
  };
  const updateImageLimitHint = () => {
    const hint = limitHintId ? document.getElementById(limitHintId) : null;
    if (!hint) return;
    const count = editorId ? getEditorImageSources(editorId).length : 0;
    hint.textContent = `${limitHintPrefix} ${count}/${POST_IMAGE_MAX_COUNT}장 · 파일당 최대 25MB · 글당 최대 300MB`;
  };

  const convertOneFile = async (file, options = {}) => {
    const filename = String(file?.name || '파일');
    const mime = String(file.type || '').toLowerCase();
    if (!isSupportedImageUploadFile(file)) {
      throw new Error('지원되지 않는 형식입니다. 이미지 파일만 업로드 가능합니다.');
    }
    if (Number(file.size || 0) > IMAGE_UPLOAD_MAX_FILE_BYTES) {
      throw new Error('파일 용량이 너무 큽니다. 파일당 25MB 이하 이미지만 업로드 가능합니다.');
    }
    if (!mime.startsWith('image/') && !/\.(heic|heif)$/i.test(filename)) {
      throw new Error('지원되지 않는 이미지 형식입니다.');
    }
    const dataUrl = await readImageFileToDataUrlAsync(file, options);
    if (!String(dataUrl || '').startsWith('data:image/')) {
      throw new Error('이미지 변환에 실패했습니다. 파일 형식을 확인해주세요.');
    }
    return dataUrl;
  };

  const processFileBatch = async (batchItems, imageOptions, onItemDone) => {
    const queue = Array.from(batchItems || []);
    const successes = [];
    const failures = [];
    let cursor = 0;
    const total = queue.length;
    const worker = async () => {
      while (cursor < total) {
        const current = cursor;
        cursor += 1;
        const item = queue[current];
        if (!item) continue;
        const itemId = item.id;
        setQueueStatus(itemId, 'processing', '');
        renderQueue();
        try {
          const dataUrl = await convertOneFile(item.file, imageOptions);
          successes.push({ ...item, dataUrl });
          setQueueStatus(itemId, 'success', '');
        } catch (error) {
          const reason = String(error?.message || '이미지 처리 중 오류가 발생했습니다.');
          failures.push({ ...item, reason });
          setQueueStatus(itemId, 'failed', reason);
        } finally {
          if (typeof onItemDone === 'function') onItemDone();
          renderQueue();
        }
      }
    };
    const workerCount = Math.max(1, Math.min(IMAGE_UPLOAD_MAX_PARALLEL, total));
    await Promise.all(Array.from({ length: workerCount }, () => worker()));
    return { successes, failures };
  };

  const applyFiles = async (files, { retryOnly = false } = {}) => {
    const normalized = Array.from(files || []);
    const imageFiles = normalized.filter((file) => file && isSupportedImageUploadFile(file));
    if (!imageFiles.length) {
      notifyMessage('이미지 파일만 업로드할 수 있습니다.');
      return;
    }
    const existingCount = editorId ? getEditorImageSources(editorId).length : 0;
    const remain = Math.max(0, POST_IMAGE_MAX_COUNT - existingCount);
    if (remain <= 0) {
      notifyMessage(`이미지는 게시글당 최대 ${POST_IMAGE_MAX_COUNT}장까지 등록할 수 있습니다.`);
      return;
    }
    const cappedFiles = imageFiles.slice(0, remain);
    if (imageFiles.length > cappedFiles.length) {
      notifyMessage(`이미지는 최대 ${POST_IMAGE_MAX_COUNT}장까지 등록 가능합니다. 초과 ${imageFiles.length - cappedFiles.length}장은 제외됩니다.`);
    }
    const selectedBytes = cappedFiles.reduce((sum, file) => sum + Number(file?.size || 0), 0);
    updateTotalGauge(selectedBytes);
    const selectedLevel = getCompressionLevelFromSelect(compressionSelectId);
    const selectedMaxBytes = getCompressionMaxBytes(selectedLevel, maxImageBytes || 0);
    const imageOptions = {
      stripExif: resolveStripExif(),
      maxBytes: selectedMaxBytes
    };
    const queueBase = retryOnly
      ? queueItems.filter((item) => item.status === 'failed' && item.file)
      : cappedFiles.map((file, index) => ({
          id: `${Date.now()}_${index}_${Math.random().toString(16).slice(2, 8)}`,
          file,
          name: String(file?.name || `파일 ${index + 1}`),
          status: 'waiting',
          reason: ''
        }));
    if (!retryOnly) {
      queueItems = queueBase.slice();
    } else {
      queueBase.forEach((item) => setQueueStatus(item.id, 'waiting', ''));
    }
    renderQueue();

    const total = cappedFiles.length;
    setProgress(0, `이미지 ${total}개 업로드 준비중...`);
    let processedCount = 0;
    const targetItems = retryOnly ? queueBase : queueItems;
    const result = await processFileBatch(targetItems, imageOptions, () => {
      processedCount += 1;
      const progress = total > 0 ? Math.round((processedCount / total) * 100) : 100;
      setProgress(progress, `${processedCount}/${total} 처리됨`);
    });
    const uploadedImages = result.successes.map((item) => item.dataUrl);
    const failedFiles = result.failures.map((item) => item.name);

    finishProgress();
    if (!uploadedImages.length) return;
    if (editorId) {
      const insertedCount = Number(insertImagesToEditor(editorId, uploadedImages) || 0);
      if (editorId === 'gallery-editor' && insertedCount < uploadedImages.length) {
        // 예외 fallback: 삽입 실패분은 DOM API로 안전 삽입 후 즉시 그리드 재정렬
        const editor = document.getElementById(editorId);
        if (editor) {
          const missing = uploadedImages.slice(insertedCount);
          const fragment = document.createDocumentFragment();
          missing.forEach((src) => {
            const p = document.createElement('p');
            const img = document.createElement('img');
            img.src = String(src || '');
            img.alt = '업로드 이미지';
            p.appendChild(img);
            fragment.appendChild(p);
          });
          editor.appendChild(fragment);
        }
        ensureGalleryEditorGrid(editorId);
      }
      ensureRepresentativeImageLabel(editorId, { showLabel: editorId !== 'gallery-editor' });
      if (editorId === 'gallery-editor') {
        const grid = ensureGalleryEditorGrid(editorId);
        if (grid) refreshGalleryGridPinUi(grid);
        const finalCount = getEditorImageSources(editorId).length;
        notifyMessage(`본문 이미지 ${finalCount}/${POST_IMAGE_MAX_COUNT}장`);
        updateImageLimitHint();
        updateTotalGauge(0);
      }
    }
    if (uploadedImages.length > 1) {
      notifyMessage(`${uploadedImages.length}개 이미지가 본문에 추가되었습니다.${failedFiles.length ? ` (실패 ${failedFiles.length}개)` : ''}`);
    } else if (failedFiles.length) {
      notifyMessage(`이미지 일부 업로드 실패 (${failedFiles.length}개)`);
    }

    if (input) input.value = '';
  };

  if (input) {
      input.addEventListener('change', async (e) => {
        const files = e.target.files;
        if (files && files.length > 0) {
          const selectedBytes = Array.from(files).reduce((sum, file) => sum + Number(file?.size || 0), 0);
          updateTotalGauge(selectedBytes);
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
      const selectedBytes = Array.from(files).reduce((sum, file) => sum + Number(file?.size || 0), 0);
      updateTotalGauge(selectedBytes);
      await applyFiles(files);
    }
  });
  if (queueRetryBtn) {
    queueRetryBtn.addEventListener('click', async () => {
      const failedItems = queueItems.filter((item) => item.status === 'failed' && item.file);
      if (!failedItems.length) {
        notifyMessage('재시도할 실패 항목이 없습니다.');
        return;
      }
      await applyFiles(failedItems.map((item) => item.file), { retryOnly: true });
    });
  }
  updateImageLimitHint();
  updateTotalGauge(0);
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
  const fixedYears = [2026, 2025, 2024, 2023, 2022];
  const source = (typeof getContent === 'function') ? getContent() : {};
  const galleryItems = Array.isArray(source?.gallery) ? source.gallery : [];
  const dataYears = [...new Set(galleryItems.map(g => Number(g?.year)).filter(Boolean))];
  const years = [...new Set([...fixedYears, ...dataYears])].sort((a, b) => b - a);
  select.innerHTML = years.map(y => `<option value="${y}">${y}</option>`).join('');
  if (selectedYear && years.includes(Number(selectedYear))) {
    select.value = String(selectedYear);
  } else if (years.length) {
    select.value = String(years[0]);
  }
}

function showWriteTab(tabId) {
  const trigger = document.querySelector(`[data-bs-target="#${tabId}"]`);
  if (trigger) {
    if (window.bootstrap?.Tab) {
      const tab = new bootstrap.Tab(trigger);
      tab.show();
    } else {
      const pane = document.querySelector(`#${tabId}`);
      const navLinks = document.querySelectorAll('#write .nav-link[data-bs-toggle="tab"]');
      const panes = document.querySelectorAll('#write .tab-pane');
      navLinks.forEach((link) => link.classList.remove('active'));
      panes.forEach((el) => {
        el.classList.remove('show', 'active');
        el.classList.add('fade');
      });
      trigger.classList.add('active');
      if (pane) {
        pane.classList.add('show', 'active');
        pane.classList.remove('fade');
      }
    }
  }
}

function getAllowedNewsPostTabs(user) {
  const activeMember = !!(user && user.status === 'active');
  if (!activeMember) return [];
  if (isAdminUser(user)) return ['notice', 'faq', 'qna'];
  if (isStaffUser(user)) return ['notice', 'qna'];
  return ['qna'];
}

function applyWriteRoleVisibility() {
  const user = getCurrentUser();
  const allowedNewsTabs = getAllowedNewsPostTabs(user);
  const canUseGalleryManage = !!(user && user.status === 'active' && isStaffUser(user));
  const canUseStatsManage = !!(user && user.status === 'active' && isStaffUser(user));

  const newsTabBtn = document.getElementById('news-tab');
  const galleryTabBtn = document.getElementById('gallery-tab');
  const statsTabBtn = document.getElementById('stats-tab');
  const galleryPane = document.getElementById('gallery-admin');
  const statsPane = document.getElementById('stats-admin');
  const newsPane = document.getElementById('news-admin');
  const newsForm = document.getElementById('add-news-form');
  const postTabSelect = newsForm?.postTab || null;

  if (newsTabBtn) {
    const canUseNews = allowedNewsTabs.length > 0;
    newsTabBtn.classList.toggle('d-none', !canUseNews);
    newsTabBtn.setAttribute('aria-hidden', canUseNews ? 'false' : 'true');
  }
  if (galleryTabBtn) {
    galleryTabBtn.classList.toggle('d-none', !canUseGalleryManage);
    galleryTabBtn.setAttribute('aria-hidden', canUseGalleryManage ? 'false' : 'true');
  }
  if (statsTabBtn) {
    statsTabBtn.classList.toggle('d-none', !canUseStatsManage);
    statsTabBtn.setAttribute('aria-hidden', canUseStatsManage ? 'false' : 'true');
  }
  if (galleryPane) galleryPane.classList.toggle('d-none', !canUseGalleryManage);
  if (statsPane) statsPane.classList.toggle('d-none', !canUseStatsManage);
  if (newsPane) newsPane.classList.toggle('d-none', allowedNewsTabs.length === 0);

  if (postTabSelect) {
    Array.from(postTabSelect.options || []).forEach((opt) => {
      const value = String(opt.value || '').toLowerCase();
      const allowed = allowedNewsTabs.includes(value);
      opt.hidden = !allowed;
      opt.disabled = !allowed;
    });
    const current = String(postTabSelect.value || '').toLowerCase();
    if (!allowedNewsTabs.includes(current)) {
      postTabSelect.value = allowedNewsTabs[0] || '';
    }
    if (typeof updateVolunteerDateFieldVisibility === 'function') {
      updateVolunteerDateFieldVisibility(newsForm);
    }
  }

  const activeTabBtn = document.querySelector('#write .nav-tabs .nav-link.active');
  const activeTarget = String(activeTabBtn?.getAttribute('data-bs-target') || '').replace('#', '');
  if (
    activeTarget === 'gallery-admin' && !canUseGalleryManage
    || activeTarget === 'stats-admin' && !canUseStatsManage
    || activeTarget === 'news-admin' && allowedNewsTabs.length === 0
  ) {
    const fallback = allowedNewsTabs.length > 0 ? 'news-admin' : (canUseGalleryManage ? 'gallery-admin' : (canUseStatsManage ? 'stats-admin' : 'news-admin'));
    showWriteTab(fallback);
  }
}

function resolveWriteTabByRole(requestedTabId = 'news-admin') {
  const user = getCurrentUser();
  const allowedNewsTabs = getAllowedNewsPostTabs(user);
  const canUseGalleryManage = !!(user && user.status === 'active' && isStaffUser(user));
  const canUseStatsManage = !!(user && user.status === 'active' && isStaffUser(user));
  const requested = String(requestedTabId || 'news-admin');
  if (requested === 'gallery-admin' && !canUseGalleryManage) return allowedNewsTabs.length > 0 ? 'news-admin' : (canUseStatsManage ? 'stats-admin' : 'news-admin');
  if (requested === 'stats-admin' && !canUseStatsManage) return allowedNewsTabs.length > 0 ? 'news-admin' : (canUseGalleryManage ? 'gallery-admin' : 'news-admin');
  if (requested === 'news-admin' && allowedNewsTabs.length === 0) return canUseGalleryManage ? 'gallery-admin' : (canUseStatsManage ? 'stats-admin' : 'news-admin');
  return requested;
}

function openWritePanel(tabId = 'news-admin') {
  applyWriteRoleVisibility();
  const safeTabId = resolveWriteTabByRole(tabId);
  document.querySelectorAll('[class*="panel"]').forEach(p => p.classList.remove('panel-active'));
  const writePanel = document.getElementById('write');
  if (writePanel) writePanel.classList.add('panel-active');
  const statsSection = document.getElementById('home-stats');
  if (statsSection) statsSection.style.display = 'none';
  showWriteTab(safeTabId);
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
      if (galleryForm.activityDuration) galleryForm.activityDuration.value = 'same_day';
      if (galleryForm.activityStartDate) galleryForm.activityStartDate.value = makeTodayDateInputValue();
      if (galleryForm.activityEndDate) galleryForm.activityEndDate.value = '';
    setEditorHtml('gallery-editor', '');
    ensureGalleryEditorGrid('gallery-editor');
    const galleryHint = document.getElementById('gallery-image-limit-hint');
    if (galleryHint) galleryHint.textContent = `본문 이미지 0/${POST_IMAGE_MAX_COUNT}장`;
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

window.ensureGalleryEditorGrid = ensureGalleryEditorGrid;
window.getRepresentativeEditorImageSource = getRepresentativeEditorImageSource;
window.GALLERY_IMAGE_MAX_BYTES = GALLERY_IMAGE_MAX_BYTES;
window.applyWriteRoleVisibility = applyWriteRoleVisibility;

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
