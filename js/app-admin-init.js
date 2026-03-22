  // ============ ADMIN FORMS ============
  document.addEventListener('DOMContentLoaded', function() {
    const toDateOnly = (value) => {
      const raw = String(value || '').trim();
      if (!raw) return '';
      if (/^\d{4}-\d{2}-\d{2}$/.test(raw)) return raw;
      const parsed = new Date(raw);
      if (Number.isNaN(parsed.getTime())) return '';
      const y = parsed.getFullYear();
      const m = String(parsed.getMonth() + 1).padStart(2, '0');
      const d = String(parsed.getDate()).padStart(2, '0');
      return `${y}-${m}-${d}`;
    };
    const addDays = (dateOnly, days) => {
      const parsed = new Date(`${dateOnly}T00:00:00`);
      if (Number.isNaN(parsed.getTime())) return '';
      parsed.setDate(parsed.getDate() + Number(days || 0));
      return toDateOnly(parsed);
    };
    const compressHtmlInlineImages = async (html, maxBytes = 180 * 1024) => {
      const raw = String(html || '');
      if (!raw || typeof DOMParser === 'undefined' || typeof resizeImageDataUrlToMaxBytes !== 'function') return raw;
      const parser = new DOMParser();
      const doc = parser.parseFromString(`<div id="__weave_inline_root">${raw}</div>`, 'text/html');
      const root = doc.getElementById('__weave_inline_root');
      if (!root) return raw;
      const images = Array.from(root.querySelectorAll('img[src^="data:image/"]'));
      if (!images.length) return raw;
      for (const img of images) {
        const src = String(img.getAttribute('src') || '').trim();
        if (!src) continue;
        try {
          const compressed = await resizeImageDataUrlToMaxBytes(src, maxBytes);
          if (compressed) img.setAttribute('src', compressed);
        } catch (_) {}
      }
      return root.innerHTML;
    };
    const compactPostItemForQuota = async (item, options = {}) => {
      if (!item || typeof item !== 'object') return;
      const contentLimit = Math.max(60 * 1024, Number(options.contentBytes || 120 * 1024));
      const imageLimit = Math.max(60 * 1024, Number(options.imageBytes || 120 * 1024));
      const thumbLimit = Math.max(50 * 1024, Number(options.thumbBytes || 70 * 1024));
      if (typeof item.content === 'string' && item.content.includes('data:image/')) {
        item.content = await compressHtmlInlineImages(item.content, contentLimit);
      }
      if (Array.isArray(item.images) && typeof resizeImageDataUrlToMaxBytes === 'function') {
        const compacted = [];
        for (const src of item.images) {
          if (typeof src !== 'string' || !src.startsWith('data:image/')) {
            compacted.push(src);
            continue;
          }
          try {
            compacted.push(await resizeImageDataUrlToMaxBytes(src, imageLimit));
          } catch (_) {
            compacted.push(src);
          }
        }
        item.images = compacted;
      }
      const cover = String(item.image || '');
      if (cover.startsWith('data:image/') && typeof resizeImageDataUrlToMaxBytes === 'function') {
        try {
          item.image = await resizeImageDataUrlToMaxBytes(cover, imageLimit);
        } catch (_) {}
      }
      const thumb1 = String(item.thumb_url || '');
      const thumb2 = String(item.thumbnail_url || '');
      if (thumb1.startsWith('data:image/') && typeof resizeImageDataUrlToMaxBytes === 'function') {
        try {
          item.thumb_url = await resizeImageDataUrlToMaxBytes(thumb1, thumbLimit);
        } catch (_) {}
      }
      if (thumb2.startsWith('data:image/') && typeof resizeImageDataUrlToMaxBytes === 'function') {
        try {
          item.thumbnail_url = await resizeImageDataUrlToMaxBytes(thumb2, thumbLimit);
        } catch (_) {}
      }
    };
    const compactAllCachedPostsForQuota = async (payload) => {
      const safePayload = payload && typeof payload === 'object' ? payload : {};
      const sections = ['news', 'gallery', 'faq', 'qna'];
      for (const section of sections) {
        const list = Array.isArray(safePayload[section]) ? safePayload[section] : [];
        for (const item of list) {
          await compactPostItemForQuota(item, { contentBytes: 90 * 1024, imageBytes: 90 * 1024, thumbBytes: 60 * 1024 });
        }
      }
    };
    const getNextNumericId = (items = []) => {
      const safeItems = Array.isArray(items) ? items : [];
      const maxId = safeItems.reduce((maxValue, item) => {
        const id = Number(item?.id || 0);
        return Number.isFinite(id) ? Math.max(maxValue, id) : maxValue;
      }, 0);
      return maxId + 1;
    };
    const dataUrlToBlob = async (dataUrl) => {
      try {
        const res = await fetch(String(dataUrl || ''));
        return await res.blob();
      } catch (_) {
        return null;
      }
    };
    const extractInlineImageTokens = (html) => {
      const raw = String(html || '');
      const tokenItems = [];
      let nextHtml = raw;
      let sequence = 0;
      const tokenFor = () => `__WEAVE_IMG_TOKEN_${Date.now()}_${sequence++}__`;
      const parser = typeof DOMParser !== 'undefined' ? new DOMParser() : null;
      if (parser) {
        const doc = parser.parseFromString(`<div id="__weave_inline_root">${raw}</div>`, 'text/html');
        const root = doc.getElementById('__weave_inline_root');
        if (root) {
          root.querySelectorAll('img').forEach((img) => {
            const src = String(img.getAttribute('src') || '').trim();
            if (!src.startsWith('data:image/')) return;
            const token = tokenFor();
            tokenItems.push({ token, src });
            img.setAttribute('src', token);
          });
          nextHtml = root.innerHTML;
        }
      } else {
        nextHtml = raw.replace(/<img([^>]*?)src=["'](data:image\/[^"']+)["']([^>]*)>/gi, (_, pre, src, post) => {
          const token = tokenFor();
          tokenItems.push({ token, src: String(src || '') });
          return `<img${pre}src="${token}"${post}>`;
        });
      }
      return { htmlWithTokens: nextHtml, tokenItems };
    };
    const replaceInlineImageTokens = (html, tokenMap = {}) => {
      let next = String(html || '');
      Object.entries(tokenMap).forEach(([token, url]) => {
        const safeToken = String(token || '');
        const safeUrl = String(url || '');
        if (!safeToken || !safeUrl) return;
        next = next.split(safeToken).join(safeUrl);
      });
      return next;
    };
    const getImageSourcesFromHtml = (html) => {
      const raw = String(html || '');
      if (!raw) return [];
      const matched = raw.match(/<img[^>]+src=["']([^"']+)["']/gi) || [];
      return matched.map((tag) => {
        const srcMatch = tag.match(/src=["']([^"']+)["']/i);
        return String(srcMatch?.[1] || '').trim();
      }).filter(Boolean);
    };
    const getRepresentativeImageFromHtml = (html) => {
      const raw = String(html || '').trim();
      if (!raw || typeof DOMParser === 'undefined') return '';
      const parser = new DOMParser();
      const doc = parser.parseFromString(`<div id="__weave_inline_root">${raw}</div>`, 'text/html');
      const root = doc.getElementById('__weave_inline_root');
      if (!root) return '';
      const pinned = root.querySelector('img[data-representative="true"]');
      const pinnedSrc = String(pinned?.getAttribute('src') || '').trim();
      if (pinnedSrc) return pinnedSrc;
      const first = root.querySelector('img');
      return String(first?.getAttribute('src') || '').trim();
    };
    const parseCreatedPostId = (payload) => {
      return Number(
        payload?.post_id
        || payload?.postId
        || payload?.id
        || payload?.data?.post_id
        || payload?.data?.postId
        || payload?.data?.id
        || 0
      ) || 0;
    };
    const uploadInlineImagesToServer = async (postId, tokenItems = [], representativeSrc = '') => {
      const items = Array.isArray(tokenItems) ? tokenItems : [];
      if (!items.length) return { tokenToUrl: {}, representativeUrl: '' };
      const BATCH_SIZE = 8;
      const MAX_RETRY_BATCH = 1;
      const rep = String(representativeSrc || '').trim();
      const sortable = items.slice().sort((a, b) => {
        const aRep = String(a?.src || '') === rep;
        const bRep = String(b?.src || '') === rep;
        if (aRep === bRep) return 0;
        return aRep ? 1 : -1; // 대표 이미지를 마지막 업로드로 보냄(cover 반영)
      });
      const tokenToUrl = {};
      const failedTokens = [];
      let representativeUrl = '';

      const uploadSingleFallback = async (item, index, setCover = false) => {
        const blob = await dataUrlToBlob(item.src);
        if (!blob) return null;
        const ext = String(blob.type || '').includes('webp') ? 'webp' : (String(blob.type || '').includes('png') ? 'png' : 'jpg');
        const formData = new FormData();
        formData.append('file', blob, `gallery_${postId}_${index + 1}.${ext}`);
        if (setCover) formData.append('set_cover', '1');
        const uploaded = await apiRequest(`/posts/${postId}/files`, { method: 'POST', body: formData });
        const fileId = Number(uploaded?.file_id || uploaded?.fileId || 0);
        if (!(fileId > 0)) return null;
        const files = await apiRequest(`/posts/${postId}/files`, { method: 'GET', suppressSessionModal: true });
        const match = (Array.isArray(files?.items) ? files.items : []).find((entry) => Number(entry?.id || 0) === fileId);
        return String(match?.file_url || '').trim();
      };

      for (let start = 0; start < sortable.length; start += BATCH_SIZE) {
        const chunk = sortable.slice(start, start + BATCH_SIZE);
        let uploadedBatch = null;
        let batchError = null;
        for (let attempt = 0; attempt <= MAX_RETRY_BATCH; attempt += 1) {
          try {
            const formData = new FormData();
            let representativeIndex = -1;
            for (let i = 0; i < chunk.length; i += 1) {
              const item = chunk[i];
              const blob = await dataUrlToBlob(item.src);
              if (!blob) continue;
              const ext = String(blob.type || '').includes('webp') ? 'webp' : (String(blob.type || '').includes('png') ? 'png' : 'jpg');
              formData.append('files', blob, `gallery_${postId}_${start + i + 1}.${ext}`);
              formData.append('tokens', String(item.token || ''));
              if (String(item?.src || '') === rep) representativeIndex = i;
            }
            if (representativeIndex >= 0) {
              formData.append('representative_index', String(representativeIndex));
            }
            uploadedBatch = await apiRequest(`/posts/${postId}/files/batch`, {
              method: 'POST',
              body: formData
            });
            batchError = null;
            break;
          } catch (error) {
            batchError = error;
          }
        }

        if (!uploadedBatch || batchError) {
          for (let i = 0; i < chunk.length; i += 1) {
            const item = chunk[i];
            const isRep = String(item?.src || '') === rep;
            try {
              const fileUrl = await uploadSingleFallback(item, start + i, isRep);
              if (fileUrl) {
                tokenToUrl[item.token] = fileUrl;
                if (isRep) representativeUrl = fileUrl;
              } else {
                failedTokens.push({ token: item.token, reason: '업로드 실패' });
              }
            } catch (error) {
              failedTokens.push({
                token: item.token,
                reason: String(error?.message || '업로드 실패')
              });
            }
          }
          continue;
        }

        const successItems = Array.isArray(uploadedBatch?.items) ? uploadedBatch.items : [];
        successItems.forEach((entry) => {
          const token = String(entry?.token || '').trim();
          const fileUrl = String(entry?.file_url || '').trim();
          if (token && fileUrl) tokenToUrl[token] = fileUrl;
          if (entry?.is_cover_updated && fileUrl) representativeUrl = fileUrl;
        });
        const failedItems = Array.isArray(uploadedBatch?.failed) ? uploadedBatch.failed : [];
        for (const entry of failedItems) {
          const token = String(entry?.token || '').trim();
          const reason = String(entry?.error || '업로드 실패').trim();
          const original = chunk.find((item) => String(item?.token || '').trim() === token);
          if (!original) {
            failedTokens.push({ token, reason });
            continue;
          }
          const isRep = String(original?.src || '') === rep;
          try {
            const fileUrl = await uploadSingleFallback(original, start + Number(entry?.index || 0), isRep);
            if (fileUrl) {
              tokenToUrl[original.token] = fileUrl;
              if (isRep) representativeUrl = fileUrl;
              continue;
            }
          } catch (_) {}
          failedTokens.push({ token, reason });
        }
      }

      if (!representativeUrl) {
        const repItem = sortable.find((item) => String(item?.src || '') === rep);
        if (repItem) representativeUrl = String(tokenToUrl[repItem.token] || '').trim();
      }
      if (failedTokens.length) {
        const reasons = failedTokens.map((entry) => `${entry.token}: ${entry.reason}`).join(', ');
        throw new Error(`일부 이미지 업로드 실패(${failedTokens.length}개) - ${reasons}`);
      }
      return { tokenToUrl, representativeUrl };
    };
    const uploadGalleryInlineImagesToServer = async (postId, tokenItems = [], representativeSrc = '') => {
      return uploadInlineImagesToServer(postId, tokenItems, representativeSrc);
    };

    initRichEditorToolbars();
    bindImageUploader({
      formId: 'add-news-form',
      inputName: 'imageFile',
      dropzoneId: 'news-image-dropzone',
      previewId: 'news-image-preview',
      hiddenName: 'imageData',
      imagesHiddenName: 'imagesData',
      editorId: 'news-editor',
      stripExifToggleId: 'news-strip-exif',
      progressWrapId: 'news-upload-progress-wrap',
      progressBarId: 'news-upload-progress-bar',
      progressTextId: 'news-upload-progress-text',
      progressPercentId: 'news-upload-progress-percent',
      queueListId: 'news-upload-queue-list',
      queueSummaryId: 'news-upload-queue-summary',
      queueRetryBtnId: 'news-upload-retry-btn',
      totalGaugeBarId: 'news-upload-total-bar',
      totalGaugeTextId: 'news-upload-total-text',
      compressionSelectId: 'news-compression-level',
      limitHintId: 'news-image-limit-hint',
      limitHintPrefix: '본문 이미지',
      maxImageBytes: (typeof GALLERY_IMAGE_MAX_BYTES === 'number' ? GALLERY_IMAGE_MAX_BYTES : 360 * 1024)
    });
    bindImageUploader({
      formId: 'add-gallery-form',
      inputName: 'imageFile',
      dropzoneId: 'gallery-image-dropzone',
      previewId: 'gallery-image-preview',
      hiddenName: 'imageData',
      imagesHiddenName: 'imagesData',
      editorId: 'gallery-editor',
      stripExifToggleId: 'gallery-strip-exif',
      progressWrapId: 'gallery-upload-progress-wrap',
      progressBarId: 'gallery-upload-progress-bar',
      progressTextId: 'gallery-upload-progress-text',
      progressPercentId: 'gallery-upload-progress-percent',
      queueListId: 'gallery-upload-queue-list',
      queueSummaryId: 'gallery-upload-queue-summary',
      queueRetryBtnId: 'gallery-upload-retry-btn',
      totalGaugeBarId: 'gallery-upload-total-bar',
      totalGaugeTextId: 'gallery-upload-total-text',
      compressionSelectId: 'gallery-compression-level',
      maxImageBytes: (typeof GALLERY_IMAGE_MAX_BYTES === 'number' ? GALLERY_IMAGE_MAX_BYTES : 360 * 1024)
    });
    ensureGalleryYearOptions();
    if (typeof applyWriteRoleVisibility === 'function') {
      applyWriteRoleVisibility();
    }

    // News Form
    const newsForm = document.getElementById('add-news-form');
    if (newsForm) {
      const showNewsSubmitError = (reason, detail = '') => {
        const message = String(reason || '소식 저장 중 오류가 발생했습니다.');
        notifyMessage(message, { level: 'error', durationMs: 4200 });
        if (typeof showErrorPopup === 'function') {
          showErrorPopup('소식 작성 실패', message, detail);
        }
      };
      let newsSubmitInFlight = false;
      if (newsForm.postTab) {
        newsForm.postTab.addEventListener('change', () => updateVolunteerDateFieldVisibility(newsForm));
      }
      if (newsForm.isScheduled) {
        newsForm.isScheduled.addEventListener('change', () => {
          const publishWrap = document.getElementById('news-publish-at-wrap');
          if (publishWrap) publishWrap.classList.toggle('d-none', !newsForm.isScheduled.checked);
          if (!newsForm.isScheduled.checked && newsForm.publishAt) newsForm.publishAt.value = '';
        });
      }
      updateVolunteerDateFieldVisibility(newsForm);
      newsForm.onsubmit = async (e) => {
        e.preventDefault();
        if (newsSubmitInFlight) return;
        newsSubmitInFlight = true;
        const submitBtn = newsForm.querySelector('button[type="submit"]');
        const originalSubmitText = submitBtn ? submitBtn.textContent : '';
        if (submitBtn) {
          submitBtn.setAttribute('disabled', 'disabled');
          submitBtn.textContent = '저장 중...';
        }
        try {
          const user = getCurrentUser();
          if (!user) {
            notifyMessage('로그인이 필요합니다.');
            return;
          }

          syncEditorToInput(e.target, 'news-editor', { markRepresentative: true });
          const newsImageCount = (String(e.target.content.value || '').match(/<img[\s>]/gi) || []).length;
          if (newsImageCount > 30) {
            notifyMessage('이미지는 게시글당 최대 30장까지 등록할 수 있습니다.');
            return;
          }
          const data = getContent();
          const editId = Number(e.target.editId.value || 0);
          const newDate = getTodayString();
          const editorImages = getEditorImageSources('news-editor');
          const hadRepresentativeBeforeSync = /data-representative=["']true["']/i.test(String(document.getElementById('news-editor')?.innerHTML || ''));
          const tabType = e.target.postTab.value;
          const isSecret = !!e.target.isSecret.checked;
          if (!isStaffUser(user) && tabType !== 'qna') {
            notifyMessage('일반/단원 계정은 Q&A만 작성할 수 있습니다.');
            return;
          }
          const volunteerStartDate = (e.target.volunteerStartDate?.value || '').trim();
          const volunteerEndDateRaw = (e.target.volunteerEndDate?.value || '').trim();
          const volunteerEndDate = volunteerEndDateRaw || volunteerStartDate;
          const featuredOnHome = tabType === 'notice' ? !!e.target.featuredOnHome?.checked : false;
          const publishAt = e.target.isScheduled?.checked ? (e.target.publishAt?.value || '').trim() : '';
          const normalizedNewsContent = await compressHtmlInlineImages(e.target.content.value || '', 180 * 1024);
          const normalizedCover = getRepresentativeImageFromHtml(normalizedNewsContent);
          const coverImage = normalizedCover
            || (typeof getRepresentativeEditorImageSource === 'function'
              ? getRepresentativeEditorImageSource('news-editor')
              : '')
            || editorImages[0]
            || '';
          const generatedThumb = coverImage && typeof createThumbnailDataUrl === 'function'
            ? await createThumbnailDataUrl(coverImage, { width: 360, height: 220, quality: 0.78 }).catch(() => '')
            : '';
          if (editorImages.length > 0 && !hadRepresentativeBeforeSync) {
            notifyMessage('대표 이미지가 설정되지 않아 첫 번째 이미지를 대표로 자동 지정했습니다.');
          }
          const preferServerUpload = !editId
            && (tabType === 'notice' || tabType === 'qna')
            && typeof apiRequest === 'function';
          let serverCreatedPostId = 0;
          let serverResolvedContent = normalizedNewsContent;
          let serverResolvedCover = coverImage;
          let serverResolvedThumb = generatedThumb || coverImage || '';
          if (preferServerUpload) {
            if (navigator.onLine === false) {
              throw new Error('오프라인 상태에서는 소식 이미지를 업로드할 수 없습니다. 네트워크 연결 후 다시 시도해 주세요.');
            }
            const { htmlWithTokens, tokenItems } = extractInlineImageTokens(normalizedNewsContent);
            try {
              const created = await apiRequest('/posts', {
                method: 'POST',
                body: {
                  category: tabType,
                  title: e.target.title.value,
                  content: htmlWithTokens,
                  publish_at: publishAt || ''
                }
              });
              serverCreatedPostId = parseCreatedPostId(created);
              if (serverCreatedPostId <= 0) {
                throw new Error('소식 게시글 생성에 실패했습니다.');
              }
              if (tokenItems.length) {
                const uploaded = await uploadInlineImagesToServer(serverCreatedPostId, tokenItems, coverImage);
                serverResolvedContent = replaceInlineImageTokens(htmlWithTokens, uploaded.tokenToUrl);
                serverResolvedCover = String(uploaded.representativeUrl || serverResolvedCover || '').trim();
                serverResolvedThumb = serverResolvedCover || serverResolvedThumb;
                await apiRequest(`/posts/${serverCreatedPostId}`, {
                  method: 'PUT',
                  body: {
                    category: tabType,
                    title: e.target.title.value,
                    content: serverResolvedContent,
                    publish_at: publishAt || ''
                  }
                });
              } else {
                serverResolvedContent = htmlWithTokens;
              }
            } catch (serverError) {
              throw new Error(`서버 업로드를 완료하지 못했습니다. ${serverError?.message || '잠시 후 다시 시도해 주세요.'}`);
            }
          }
          let noticeAttachments = null;

          if (tabType === 'notice') {
            try {
              noticeAttachments = await buildNoticeAttachments(e.target.noticeAttachmentFiles?.files || []);
            } catch (error) {
              notifyMessage(error.message || '첨부 파일 처리 중 오류가 발생했습니다.');
              return;
            }
          }

          if (tabType === 'notice' && volunteerStartDate && volunteerEndDate && volunteerEndDate < volunteerStartDate) {
            notifyMessage('봉사 종료일시는 시작일시보다 빠를 수 없습니다.');
            return;
          }

          if (tabType === 'faq' && !isAdminUser(user)) {
            notifyMessage('FAQ 작성은 관리자만 가능합니다.');
            return;
          }

          const source = tabType === 'faq'
            ? (data.faq ||= [])
            : (tabType === 'qna' ? (data.qna ||= []) : (data.news ||= []));
          let newsItem = null;
          if (editId) {
            const target = source.find(n => n.id === editId);
            if (target) {
              target.title = e.target.title.value;
              target.author = e.target.author.value || user.nickname || user.username || user.name;
              target.date = target.date || newDate;
              const existingImages = Array.isArray(target.images)
                ? target.images
                : (target.image ? [target.image] : []);
              const nextImages = editorImages.length ? editorImages : existingImages;
              target.images = nextImages;
              target.image = coverImage || nextImages[0] || target.image || '';
              if (generatedThumb) {
                target.thumb_url = generatedThumb;
                target.thumbnail_url = generatedThumb;
              }
              target.content = normalizedNewsContent;
              target.publishAt = publishAt || '';
              if (tabType === 'qna') target.isSecret = isSecret;
              if (tabType === 'qna') {
                target.authorUserId = Number(target.authorUserId || user.id || 0) || 0;
                target.authorUsername = target.authorUsername || user.username || '';
                target.authorNickname = target.authorNickname || user.nickname || '';
                target.authorEmail = target.authorEmail || user.email || '';
              }
              if (tabType === 'notice') {
                target.featuredOnHome = featuredOnHome;
                if (Array.isArray(noticeAttachments)) {
                  target.attachments = noticeAttachments;
                  target.files = noticeAttachments;
                }
                target.volunteerStartDate = volunteerStartDate || '';
                target.volunteerEndDate = volunteerStartDate ? volunteerEndDate : '';
                if (!target.volunteerStartDate) {
                  delete target.volunteerStartDate;
                  delete target.volunteerEndDate;
                }
                delete target.volunteerDate;
              } else {
                delete target.featuredOnHome;
                delete target.volunteerDate;
                delete target.volunteerStartDate;
                delete target.volunteerEndDate;
              }
              newsItem = target;
            }
          } else {
            const newId = getNextNumericId(source);
            const resolvedImages = getImageSourcesFromHtml(serverResolvedContent);
            const nextImages = serverCreatedPostId > 0
              ? (resolvedImages.length ? resolvedImages : [])
              : (editorImages.length ? editorImages : []);
            const newItem = {
              id: serverCreatedPostId > 0 ? serverCreatedPostId : newId,
              title: e.target.title.value,
              author: e.target.author.value || user.nickname || user.username || user.name,
              date: newDate,
              image: serverResolvedCover || coverImage || nextImages[0] || '',
              thumb_url: serverResolvedThumb || generatedThumb || coverImage || '',
              thumbnail_url: serverResolvedThumb || generatedThumb || coverImage || '',
              images: nextImages,
              content: serverResolvedContent || normalizedNewsContent || '',
              publishAt: publishAt || '',
              views: 0,
              isSecret: tabType === 'qna' ? isSecret : false,
              answer: ''
            };
            if (tabType === 'qna') {
              newItem.authorUserId = Number(user.id || 0) || 0;
              newItem.authorUsername = user.username || '';
              newItem.authorNickname = user.nickname || '';
              newItem.authorEmail = user.email || '';
            }
            if (tabType === 'notice') {
              newItem.featuredOnHome = featuredOnHome;
              if (Array.isArray(noticeAttachments)) {
                newItem.attachments = noticeAttachments;
                newItem.files = noticeAttachments;
              }
              if (volunteerStartDate) {
                newItem.volunteerStartDate = volunteerStartDate;
                newItem.volunteerEndDate = volunteerEndDate;
              }
            }
            source.unshift(newItem);
            newsItem = newItem;
          }
          try {
            saveContent(data);
          } catch (saveError) {
            const quotaLike = /quota|storage|space/i.test(String(saveError?.message || ''))
              || String(saveError?.name || '').toLowerCase().includes('quota');
            if (!quotaLike) throw saveError;
            if (serverCreatedPostId > 0) {
              try {
                localStorage.removeItem(DATA_KEY);
                if (typeof hydrateContentFromServer === 'function') {
                  await hydrateContentFromServer({ force: true });
                } else if (typeof hydrateContentFromServerIfEmpty === 'function') {
                  await hydrateContentFromServerIfEmpty({ force: true });
                }
              } catch (_) {}
              renderNews();
              renderFaq();
              renderQna();
              resetWriteForms();
              activateNewsTab(tabType);
              if (tabType === 'notice' && typeof loadActivitiesCalendar === 'function') {
                loadActivitiesCalendar().catch(() => {});
              }
              movePanel('news');
              notifyMessage('로컬 저장소를 정리하고 서버 기준으로 저장을 완료했습니다.');
              return;
            }
            await compactPostItemForQuota(newsItem, { contentBytes: 120 * 1024, imageBytes: 120 * 1024, thumbBytes: 70 * 1024 });
            try {
              saveContent(data);
              notifyMessage('이미지 용량이 커서 자동 압축 후 저장했습니다.');
            } catch (secondError) {
              const secondQuotaLike = /quota|storage|space/i.test(String(secondError?.message || ''))
                || String(secondError?.name || '').toLowerCase().includes('quota');
              if (!secondQuotaLike) throw secondError;
              await compactAllCachedPostsForQuota(data);
              try {
                saveContent(data);
                notifyMessage('캐시 용량을 최적화해 저장을 완료했습니다.');
              } catch (_) {
                throw new Error('브라우저 저장소 용량을 초과했습니다. 압축 수준을 "고압축"으로 변경하거나 이미지 수를 줄인 뒤 다시 시도해 주세요.');
              }
            }
          }
          renderNews();
          renderFaq();
          renderQna();
          resetWriteForms();
          activateNewsTab(tabType);
          if (tabType === 'notice' && typeof loadActivitiesCalendar === 'function') {
            loadActivitiesCalendar().catch(() => {});
          }
          movePanel('news');
          notifyMessage('글이 저장되었습니다!');
        } catch (error) {
          const errorText = String(error?.message || '글 저장 중 오류가 발생했습니다.').trim();
          const detailParts = [];
          if (/quota|storage|space|용량/.test(errorText.toLowerCase())) {
            detailParts.push('원인: 브라우저 저장소 용량 부족 또는 이미지 데이터 과다입니다.');
            detailParts.push('해결: 압축 수준을 표준/고압축으로 변경 후 다시 시도해 주세요.');
          } else if (/heic|heif/.test(errorText.toLowerCase())) {
            detailParts.push('원인: HEIC/HEIF 변환 실패입니다.');
            detailParts.push('해결: iPhone 카메라 포맷을 "높은 호환성"으로 변경하거나 JPG/PNG로 변환 후 업로드해 주세요.');
          } else {
            detailParts.push('원인: 저장 처리 중 예외가 발생했습니다.');
            detailParts.push('해결: 동일 입력으로 다시 시도해 주세요.');
          }
          showNewsSubmitError(errorText, detailParts.join('\n'));
        } finally {
          newsSubmitInFlight = false;
          if (submitBtn) {
            submitBtn.removeAttribute('disabled');
            submitBtn.textContent = originalSubmitText || '소식 추가';
          }
        }
      };
    }

    // Gallery Form
    const galleryForm = document.getElementById('add-gallery-form');
    if (galleryForm) {
      const showGallerySubmitError = (reason, detail = '') => {
        const message = String(reason || '갤러리 저장 중 오류가 발생했습니다.');
        notifyMessage(message, { level: 'error', durationMs: 4200 });
        if (typeof showErrorPopup === 'function') {
          showErrorPopup('갤러리 작성 실패', message, detail);
        }
      };
      let gallerySubmitInFlight = false;
      const gallerySubmitBtn = galleryForm.querySelector('button[type="submit"]');
      if (gallerySubmitBtn && !gallerySubmitBtn.dataset.boundSubmitProxy) {
        gallerySubmitBtn.dataset.boundSubmitProxy = '1';
        gallerySubmitBtn.addEventListener('click', (event) => {
          if (gallerySubmitInFlight) {
            event.preventDefault();
            return;
          }
          // 일부 브라우저/탭 전환 상태에서 기본 submit 누락 케이스 방지
          if (typeof galleryForm.requestSubmit === 'function') {
            event.preventDefault();
            galleryForm.requestSubmit(gallerySubmitBtn);
          }
        });
      }
      const galleryDurationEl = document.getElementById('gallery-activity-duration');
      const galleryStartDateEl = document.getElementById('gallery-activity-start-date');
      const galleryEndDateEl = document.getElementById('gallery-activity-end-date');
      const galleryEndWrapEl = document.getElementById('gallery-activity-end-wrap');
      const syncGalleryActivityRange = () => {
        const mode = String(galleryDurationEl?.value || 'same_day');
        const startDate = toDateOnly(galleryStartDateEl?.value || '');
        const showCustomEnd = mode === 'custom';
        if (galleryEndWrapEl) galleryEndWrapEl.classList.toggle('d-none', !showCustomEnd);
        if (galleryEndDateEl) {
          if (showCustomEnd) {
            galleryEndDateEl.removeAttribute('readonly');
          } else {
            galleryEndDateEl.setAttribute('readonly', 'readonly');
            if (startDate) {
              galleryEndDateEl.value = mode === 'overnight' ? addDays(startDate, 1) : startDate;
            } else {
              galleryEndDateEl.value = '';
            }
          }
        }
      };
      if (galleryDurationEl) galleryDurationEl.addEventListener('change', syncGalleryActivityRange);
      if (galleryStartDateEl) galleryStartDateEl.addEventListener('change', syncGalleryActivityRange);
      if (galleryStartDateEl && !String(galleryStartDateEl.value || '').trim()) {
        galleryStartDateEl.value = toDateOnly(getTodayString());
      }
      syncGalleryActivityRange();
      if (galleryForm.isScheduled) {
        galleryForm.isScheduled.addEventListener('change', () => {
          const publishWrap = document.getElementById('gallery-publish-at-wrap');
          if (publishWrap) publishWrap.classList.toggle('d-none', !galleryForm.isScheduled.checked);
          if (!galleryForm.isScheduled.checked && galleryForm.publishAt) galleryForm.publishAt.value = '';
        });
      }
      galleryForm.onsubmit = async (e) => {
        e.preventDefault();
        if (gallerySubmitInFlight) return;
        gallerySubmitInFlight = true;
        const submitBtn = galleryForm.querySelector('button[type="submit"]');
        const originalSubmitText = submitBtn ? submitBtn.textContent : '';
        if (submitBtn) {
          submitBtn.setAttribute('disabled', 'disabled');
          submitBtn.textContent = '저장 중...';
        }
        try {
          ensureGalleryYearOptions(e.target.year?.value || '2026');
          const user = getCurrentUser();
          if (!user) {
            throw new Error('로그인이 필요합니다. 로그인 후 다시 시도해 주세요.');
          }
          if (!isStaffUser(user)) {
            throw new Error('일반/단원 계정은 갤러리 글을 작성할 수 없습니다.');
          }

          syncEditorToInput(e.target, 'gallery-editor', { markRepresentative: true, representativeLabel: false });
          const galleryImageCount = (String(e.target.content.value || '').match(/<img[\s>]/gi) || []).length;
          if (galleryImageCount > 30) {
            throw new Error('이미지는 게시글당 최대 30장까지 등록할 수 있습니다.');
          }
          const data = getContent();
          if (!Array.isArray(data.gallery)) data.gallery = [];
          const year = Number(e.target.year.value || 2026);
          const editId = Number(e.target.editId.value || 0);
          const newDate = getTodayString();
          const activityDuration = String(e.target.activityDuration?.value || 'same_day');
          const activityStartDate = toDateOnly(e.target.activityStartDate?.value || toDateOnly(getTodayString()));
          const rawActivityEndDate = toDateOnly(e.target.activityEndDate?.value || '');
          let activityEndDate = activityStartDate;
          if (!activityStartDate) {
            throw new Error('봉사 활동 시작 날짜를 선택해 주세요.');
          }
          if (activityDuration === 'overnight') {
            activityEndDate = addDays(activityStartDate, 1);
          } else if (activityDuration === 'custom') {
            activityEndDate = rawActivityEndDate || activityStartDate;
          }
          if (activityEndDate < activityStartDate) {
            throw new Error('봉사 활동 종료일은 시작일보다 빠를 수 없습니다.');
          }
          const editorImages = getEditorImageSources('gallery-editor');
          const hadRepresentativeBeforeSync = /data-representative=["']true["']/i.test(String(document.getElementById('gallery-editor')?.innerHTML || ''));
          const publishAt = e.target.isScheduled?.checked ? (e.target.publishAt?.value || '').trim() : '';
          const normalizedGalleryContent = await compressHtmlInlineImages(e.target.content.value || '', 180 * 1024);
          const normalizedCover = getRepresentativeImageFromHtml(normalizedGalleryContent);
          const coverImage = normalizedCover
            || (typeof getRepresentativeEditorImageSource === 'function'
              ? getRepresentativeEditorImageSource('gallery-editor')
              : '')
            || editorImages[0]
            || '';
          const generatedThumb = coverImage && typeof createThumbnailDataUrl === 'function'
            ? await createThumbnailDataUrl(coverImage, { width: 360, height: 220, quality: 0.78 }).catch(() => '')
            : '';
          if (editorImages.length > 0 && !hadRepresentativeBeforeSync) {
            notifyMessage('대표 이미지가 설정되지 않아 첫 번째 이미지를 대표로 자동 지정했습니다.');
          }
          const preferServerUpload = !editId && typeof apiRequest === 'function';
          let serverResolvedContent = normalizedGalleryContent;
          let serverResolvedCover = coverImage;
          let serverResolvedThumb = generatedThumb || coverImage || '';
          let serverPostId = 0;
          if (preferServerUpload) {
            if (navigator.onLine === false) {
              throw new Error('오프라인 상태에서는 갤러리 이미지를 업로드할 수 없습니다. 네트워크 연결 후 다시 시도해 주세요.');
            }
            const { htmlWithTokens, tokenItems } = extractInlineImageTokens(normalizedGalleryContent);
            try {
              const created = await apiRequest('/posts', {
                method: 'POST',
                body: {
                  category: 'gallery',
                  title: e.target.title.value,
                  content: htmlWithTokens,
                  publish_at: publishAt || ''
                }
              });
              serverPostId = Number(created?.post_id || created?.postId || 0);
              if (serverPostId <= 0) {
                throw new Error('갤러리 게시글 생성에 실패했습니다.');
              }
              if (serverPostId > 0 && tokenItems.length) {
                const uploaded = await uploadGalleryInlineImagesToServer(serverPostId, tokenItems, coverImage);
                serverResolvedContent = replaceInlineImageTokens(htmlWithTokens, uploaded.tokenToUrl);
                serverResolvedCover = String(uploaded.representativeUrl || serverResolvedCover || '').trim();
                serverResolvedThumb = serverResolvedCover || serverResolvedThumb;
                await apiRequest(`/posts/${serverPostId}`, {
                  method: 'PUT',
                  body: {
                    category: 'gallery',
                    title: e.target.title.value,
                    content: serverResolvedContent,
                    publish_at: publishAt || ''
                  }
                });
              }
            } catch (serverError) {
              throw new Error(`서버 업로드를 완료하지 못했습니다. ${serverError?.message || '잠시 후 다시 시도해 주세요.'}`);
            }
          }
          let galleryItem = null;
          if (editId) {
            const target = data.gallery.find(g => g.id === editId);
            if (target) {
              target.title = e.target.title.value;
              target.date = target.date || newDate;
              target.year = year;
              target.category = `y${year}`;
              const existingImages = Array.isArray(target.images)
                ? target.images
                : (target.image ? [target.image] : []);
              const nextImages = editorImages.length ? editorImages : existingImages;
              target.images = nextImages;
              target.image = coverImage || nextImages[0] || target.image || 'logo.png';
              if (generatedThumb) {
                target.thumb_url = generatedThumb;
                target.thumbnail_url = generatedThumb;
              } else {
                target.thumb_url = coverImage || '';
                target.thumbnail_url = coverImage || '';
              }
              target.content = normalizedGalleryContent || '';
              target.publishAt = publishAt || '';
              target.activityDuration = activityDuration;
              target.activityStartDate = activityStartDate;
              target.activityEndDate = activityEndDate;
              delete target.activityId;
              delete target.activityStartAt;
              galleryItem = target;
            }
          } else {
            const newId = getNextNumericId(data.gallery);
            const resolvedImages = getImageSourcesFromHtml(serverResolvedContent);
            const nextImages = serverPostId > 0
              ? (resolvedImages.length ? resolvedImages : [])
              : (editorImages.length ? editorImages : []);
            galleryItem = {
              id: serverPostId > 0 ? serverPostId : newId,
              title: e.target.title.value,
              date: newDate,
              year,
              category: `y${year}`,
              image: serverResolvedCover || coverImage || nextImages[0] || 'logo.png',
              thumb_url: serverResolvedThumb || generatedThumb || coverImage || '',
              thumbnail_url: serverResolvedThumb || generatedThumb || coverImage || '',
              images: nextImages,
              content: serverResolvedContent || normalizedGalleryContent || '',
              publishAt: publishAt || '',
              author: user.nickname || user.username || user.name,
              views: 0,
              activityDuration,
              activityStartDate,
              activityEndDate
            };
            data.gallery.unshift(galleryItem);
          }
          const compactGalleryItemForQuota = async (targetItem) => {
            if (!targetItem || typeof targetItem !== 'object') return;
            if (typeof targetItem.content === 'string') {
              targetItem.content = await compressHtmlInlineImages(targetItem.content, 120 * 1024);
            }
            if (Array.isArray(targetItem.images) && typeof resizeImageDataUrlToMaxBytes === 'function') {
              const compressedImages = [];
              for (const src of targetItem.images) {
                if (typeof src !== 'string' || !src.startsWith('data:image/')) {
                  compressedImages.push(src);
                  continue;
                }
                try {
                  compressedImages.push(await resizeImageDataUrlToMaxBytes(src, 120 * 1024));
                } catch (_) {
                  compressedImages.push(src);
                }
              }
              targetItem.images = compressedImages;
            }
            const safeImage = typeof targetItem.image === 'string' ? targetItem.image : '';
            if (safeImage.startsWith('data:image/') && typeof resizeImageDataUrlToMaxBytes === 'function') {
              try {
                targetItem.image = await resizeImageDataUrlToMaxBytes(safeImage, 140 * 1024);
              } catch (_) {}
            }
            const safeThumb = typeof targetItem.thumb_url === 'string' ? targetItem.thumb_url : '';
            const safeThumb2 = typeof targetItem.thumbnail_url === 'string' ? targetItem.thumbnail_url : '';
            if (safeThumb.startsWith('data:image/') && typeof resizeImageDataUrlToMaxBytes === 'function') {
              try {
                targetItem.thumb_url = await resizeImageDataUrlToMaxBytes(safeThumb, 70 * 1024);
              } catch (_) {}
            }
            if (safeThumb2.startsWith('data:image/') && typeof resizeImageDataUrlToMaxBytes === 'function') {
              try {
                targetItem.thumbnail_url = await resizeImageDataUrlToMaxBytes(safeThumb2, 70 * 1024);
              } catch (_) {}
            }
          };
          try {
            saveContent(data);
          } catch (saveError) {
            const quotaLike = /quota|storage|space/i.test(String(saveError?.message || ''))
              || String(saveError?.name || '').toLowerCase().includes('quota');
            if (!quotaLike) throw saveError;
            if (serverPostId > 0) {
              // 서버 저장이 완료된 경우에는 로컬 캐시만 정리하고 진행한다.
              try {
                localStorage.removeItem(DATA_KEY);
                if (typeof hydrateContentFromServerIfEmpty === 'function') {
                  await hydrateContentFromServerIfEmpty();
                }
                notifyMessage('로컬 저장소 용량이 가득 차 서버 데이터로 자동 재동기화했습니다.');
                galleryCurrentFilter = `y${year}`;
                galleryCurrentPage = 1;
                if (typeof syncGalleryRouteState === 'function') syncGalleryRouteState();
                renderGallery();
                resetWriteForms();
                ensureGalleryYearOptions();
                movePanel('gallery');
                notifyMessage(editId ? '갤러리가 수정되었습니다!' : '갤러리가 추가되었습니다!');
                return;
              } catch (_) {
                // 재동기화 실패 시 아래 압축 fallback으로 한 번 더 시도
              }
            }
            await compactGalleryItemForQuota(galleryItem);
            try {
              saveContent(data);
              notifyMessage('이미지 용량이 커서 자동 압축 후 저장했습니다.');
            } catch (secondError) {
              const secondQuotaLike = /quota|storage|space/i.test(String(secondError?.message || ''))
                || String(secondError?.name || '').toLowerCase().includes('quota');
              if (!secondQuotaLike) throw secondError;
              await compactAllCachedPostsForQuota(data);
              try {
                saveContent(data);
                notifyMessage('기존 게시글 이미지 캐시를 정리해 저장을 완료했습니다.');
              } catch (thirdError) {
                if (serverPostId > 0) {
                  try {
                    localStorage.removeItem(DATA_KEY);
                    if (typeof hydrateContentFromServer === 'function') {
                      await hydrateContentFromServer({ force: true });
                    } else if (typeof hydrateContentFromServerIfEmpty === 'function') {
                      await hydrateContentFromServerIfEmpty({ force: true });
                    }
                    notifyMessage('로컬 캐시 용량을 초과해 서버 기준으로 재동기화했습니다.');
                  } catch (_) {}
                  galleryCurrentFilter = `y${year}`;
                  galleryCurrentPage = 1;
                  if (typeof syncGalleryRouteState === 'function') syncGalleryRouteState();
                  renderGallery();
                  resetWriteForms();
                  ensureGalleryYearOptions();
                  movePanel('gallery');
                  notifyMessage(editId ? '갤러리가 수정되었습니다!' : '갤러리가 추가되었습니다!');
                  return;
                }
                throw new Error('이미지 용량이 커서 저장할 수 없습니다. 이미지 개수를 줄이거나 더 작은 파일로 다시 시도해주세요.');
              }
            }
          }
          galleryCurrentFilter = `y${year}`;
          galleryCurrentPage = 1;
          if (typeof syncGalleryRouteState === 'function') syncGalleryRouteState();
          renderGallery();
          resetWriteForms();
          ensureGalleryYearOptions();
          movePanel('gallery');
          notifyMessage(editId ? '갤러리가 수정되었습니다!' : '갤러리가 추가되었습니다!');
        } catch (error) {
          const errorText = String(error?.message || '갤러리 저장 중 오류가 발생했습니다.').trim();
          const detailParts = [];
          if (/quota|storage|space|용량/.test(errorText.toLowerCase())) {
            if (/총 업로드 용량|300mb|게시글당/.test(errorText.toLowerCase())) {
              detailParts.push('원인: 글당 업로드 총량(300MB)을 초과했습니다.');
              detailParts.push('해결: 일부 이미지를 줄이거나 압축 수준을 "표준/고압축"으로 변경 후 다시 시도해 주세요.');
            } else {
              detailParts.push('원인: 브라우저 저장소 용량 초과 가능성이 있습니다.');
              detailParts.push('해결: 이미지 개수를 줄이거나 JPG/WebP로 변환 후 다시 시도해 주세요.');
            }
          } else if (/heic|heif/.test(errorText.toLowerCase())) {
            detailParts.push('원인: HEIC/HEIF 변환 실패입니다.');
            detailParts.push('해결: iPhone 카메라 포맷을 "높은 호환성"으로 변경하거나 JPG/PNG로 변환 후 업로드해 주세요.');
          } else if (/network|fetch|오프라인|연결/.test(errorText.toLowerCase())) {
            detailParts.push('원인: 네트워크 연결 또는 서버 응답 오류입니다.');
            detailParts.push('해결: 네트워크 확인 후 다시 시도해 주세요.');
          } else {
            detailParts.push('원인: 저장 처리 중 예외가 발생했습니다.');
            detailParts.push('해결: 동일 입력으로 재시도 후 계속 실패하면 문의해 주세요.');
          }
          showGallerySubmitError(errorText, detailParts.join('\n'));
        } finally {
          gallerySubmitInFlight = false;
          if (submitBtn) {
            submitBtn.removeAttribute('disabled');
            submitBtn.textContent = originalSubmitText || '갤러리 추가';
          }
        }
      };
    }

    const qnaAnswerBackBtn = document.getElementById('qna-answer-back-btn');
    if (qnaAnswerBackBtn) {
      qnaAnswerBackBtn.addEventListener('click', () => {
        if (currentQnaAnswerId) {
          openQnaDetail(currentQnaAnswerId);
          return;
        }
        movePanel('news');
      });
    }

    const qnaAnswerForm = document.getElementById('qna-answer-form');
    if (qnaAnswerForm) {
      qnaAnswerForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const user = getCurrentUser();
        if (!isStaffUser(user)) {
          notifyMessage('Q&A 답변은 운영자만 작성할 수 있습니다.');
          return;
        }
        const editId = Number(document.getElementById('qna-answer-edit-id')?.value || 0);
        if (!editId) return;
        const editor = document.getElementById('qna-answer-editor');
        const answerHtml = (editor?.innerHTML || '').trim();

        const next = getContent();
        const target = (next.qna || []).find(q => q.id === editId);
        if (!target) {
          notifyMessage('대상 글을 찾을 수 없습니다.');
          return;
        }
        target.answer = answerHtml;
        target.answerDate = getTodayString();
        target.answerAuthor = user.nickname || user.username || user.name || '운영자';
        saveContent(next);
        if (typeof pushInAppNotification === 'function') {
          pushInAppNotification({
            title: 'Q&A 답변이 등록되었습니다.',
            message: `질문 "${target.title || '제목 없음'}"에 운영진 답변이 등록되었습니다.`,
            panel: 'qna',
            qnaId: editId,
            userId: Number(target.authorUserId || 0) || 0,
            toUser: target.author || '',
            toUsername: target.authorUsername || target.author || '',
            toNickname: target.authorNickname || target.author || '',
            toName: target.author || ''
            ,
            toEmail: target.authorEmail || '',
            anchorId: 'qna-answer-anchor',
            kind: 'qna_answer',
            targetId: editId,
            meta: {
              qnaId: editId,
              anchorId: 'qna-answer-anchor'
            }
          });
        }
        if (typeof renderMyNotifications === 'function') renderMyNotifications();
        renderQna();
        openQnaDetail(editId);
      });
    }

    const myinfoEditBtn = document.getElementById('myinfo-edit-btn');
    if (myinfoEditBtn) {
      myinfoEditBtn.addEventListener('click', () => {
        const user = getCurrentUser();
        if (!user) {
          notifyMessage('로그인이 필요합니다.');
          return;
        }
        const usernameEl = document.getElementById('myinfo-auth-username');
        const passwordEl = document.getElementById('myinfo-auth-password');
        if (usernameEl) usernameEl.value = user.username || '';
        if (passwordEl) passwordEl.value = '';
        movePanel('myinfo-auth');
      });
    }

    const myinfoAuthCancel = document.getElementById('myinfo-auth-cancel');
    if (myinfoAuthCancel) {
      myinfoAuthCancel.addEventListener('click', () => {
        movePanel('myinfo');
      });
    }

    const myinfoAuthForm = document.getElementById('myinfo-auth-form');
    if (myinfoAuthForm) {
      myinfoAuthForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const user = getCurrentUser();
        if (!user) {
          notifyMessage('로그인이 필요합니다.');
          return;
        }
        const password = document.getElementById('myinfo-auth-password')?.value || '';
        try {
          const auth = await apiRequest('/auth/login', {
            method: 'POST',
            body: JSON.stringify({ username: user.username, password })
          });
          if (!auth?.ok || !auth?.user) {
            notifyMessage('비밀번호 확인에 실패했습니다.');
            return;
          }
          const form = document.getElementById('myinfo-edit-form');
          if (!form) return;
          form.name.value = auth.user.name || '';
          form.username.value = auth.user.username || '';
          form.email.value = auth.user.email || '';
          form.phone.value = auth.user.phone || '';
          form.birthDate.value = auth.user.birthDate || '';
          form.generation.value = auth.user.generation || '';
          form.interests.value = auth.user.interests || '';
          form.certificates.value = auth.user.certificates || '';
          form.availability.value = auth.user.availability || '';
          setCurrentUser(auth.user);
          movePanel('myinfo-edit');
        } catch (error) {
          notifyMessage(error.message || '비밀번호 확인에 실패했습니다.');
        }
      });
    }

    const myinfoEditCancel = document.getElementById('myinfo-edit-cancel');
    if (myinfoEditCancel) {
      myinfoEditCancel.addEventListener('click', () => {
        movePanel('myinfo');
      });
    }

    const myinfoEditForm = document.getElementById('myinfo-edit-form');
    if (myinfoEditForm) {
      myinfoEditForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const currentUser = getCurrentUser();
        if (!currentUser) {
          notifyMessage('로그인이 필요합니다.');
          return;
        }

        const updated = {
          ...currentUser,
          name: e.target.name.value.trim(),
          email: e.target.email.value.trim(),
          phone: e.target.phone.value.trim(),
          birthDate: e.target.birthDate.value.trim(),
          generation: e.target.generation.value.trim(),
          interests: e.target.interests.value.trim(),
          certificates: e.target.certificates.value.trim(),
          availability: e.target.availability.value.trim(),
        };

        if (!isValidBirthDate(updated.birthDate)) {
          notifyMessage('생년월일은 yyyy.mm.dd 형식으로 입력해주세요.');
          return;
        }
        if (!/^01[0-9]-?\d{3,4}-?\d{4}$/.test(updated.phone)) {
          notifyMessage('연락처 형식이 올바르지 않습니다. (예: 010-1234-5678)');
          return;
        }

        setCurrentUser(updated);
        notifyMessage('내 정보가 수정되었습니다.');
        movePanel('myinfo');
      });
    }

    if (typeof initWriteEntryBindingsFromGlobals === 'function') {
      initWriteEntryBindingsFromGlobals();
    }

    const newsSearchInput = document.getElementById('news-search');
    const newsSearchBtn = document.getElementById('news-search-btn');
    const faqSearchInput = document.getElementById('faq-search');
    const faqSearchBtn = document.getElementById('faq-search-btn');
    const qnaSearchInput = document.getElementById('qna-search');
    const qnaSearchBtn = document.getElementById('qna-search-btn');
    const gallerySearchInput = document.getElementById('gallery-search');
    const gallerySearchBtn = document.getElementById('gallery-search-btn');
    const newsSortSelect = document.getElementById('news-sort');
    const gallerySortSelect = document.getElementById('gallery-sort');
    const galleryViewOneBtn = document.getElementById('gallery-view-1col');
    const galleryViewTwoBtn = document.getElementById('gallery-view-2col');
    const eventsRefreshBtn = document.getElementById('events-refresh-btn');
    const eventDetailBackBtn = document.getElementById('event-detail-back-btn');
    const joinHonorBtn = document.getElementById('join-honor-btn');
    const joinInquiryBtn = document.getElementById('join-inquiry-btn');
    const joinSponsorBtn = document.getElementById('join-sponsor-btn');
    const copyDonationAccountBtn = document.getElementById('copy-donation-account-btn');
    const noticeTabBtn = document.getElementById('notice-tab-btn');
    const faqTabBtn = document.getElementById('faq-tab-btn');
    const qnaTabBtn = document.getElementById('qna-tab-btn');
    const noticeTab = document.getElementById('notice-tab');
    const faqTab = document.getElementById('faq-tab');
    const qnaTab = document.getElementById('qna-tab');
    if (newsSearchInput) {
      newsSearchInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          newsSearchKeyword = newsSearchInput.value.trim();
          newsCurrentPage = 1;
          renderNews();
        }
      });
    }

    const newsBackBtn = document.getElementById('news-back-btn');
    if (newsBackBtn) {
      newsBackBtn.addEventListener('click', () => {
        document.querySelectorAll('[class*="panel"]').forEach(p => p.classList.remove('panel-active'));
        document.getElementById('news').classList.add('panel-active');
        window.scrollTo({ top: 0, behavior: 'smooth' });
      });
    }
    if (newsSearchBtn) {
      newsSearchBtn.addEventListener('click', () => {
        newsSearchKeyword = newsSearchInput.value.trim();
        newsCurrentPage = 1;
        renderNews();
      });
    }

    if (faqSearchBtn && faqSearchInput) {
      faqSearchBtn.addEventListener('click', () => {
        faqSearchKeyword = faqSearchInput.value.trim();
        faqCurrentPage = 1;
        renderFaq();
      });
      faqSearchInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          faqSearchKeyword = faqSearchInput.value.trim();
          faqCurrentPage = 1;
          renderFaq();
        }
      });
    }

    if (qnaSearchBtn && qnaSearchInput) {
      qnaSearchBtn.addEventListener('click', () => {
        qnaSearchKeyword = qnaSearchInput.value.trim();
        qnaCurrentPage = 1;
        renderQna();
      });
      qnaSearchInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          qnaSearchKeyword = qnaSearchInput.value.trim();
          qnaCurrentPage = 1;
          renderQna();
        }
      });
    }

    if (gallerySearchBtn && gallerySearchInput) {
      gallerySearchBtn.addEventListener('click', () => {
        gallerySearchKeyword = gallerySearchInput.value.trim();
        galleryCurrentPage = 1;
        renderGallery();
      });
      gallerySearchInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          gallerySearchKeyword = gallerySearchInput.value.trim();
          galleryCurrentPage = 1;
          renderGallery();
        }
      });
    }

    if (eventsRefreshBtn) {
      eventsRefreshBtn.addEventListener('click', async () => {
        await loadVolunteerEvents();
      });
    }

    if (eventDetailBackBtn) {
      eventDetailBackBtn.addEventListener('click', () => {
        movePanel('news');
        activateNewsTab('notice');
      });
    }

    if (joinHonorBtn) {
      joinHonorBtn.addEventListener('click', () => {
        setJoinActionPanel('honor');
      });
    }
    if (newsSortSelect) {
      newsSortSelect.addEventListener('change', () => {
        newsSortMode = String(newsSortSelect.value || 'latest');
        newsCurrentPage = 1;
        renderNews();
      });
    }
    if (gallerySortSelect) {
      gallerySortSelect.addEventListener('change', () => {
        gallerySortMode = String(gallerySortSelect.value || 'latest');
        galleryCurrentPage = 1;
        renderGallery();
      });
    }
    const applyGalleryMobileViewMode = (mode) => {
      const normalized = mode === '1' ? '1' : '2';
      const galleryGrid = document.getElementById('gallery-grid');
      if (!galleryGrid) return;
      galleryGrid.classList.toggle('mobile-cols-1', normalized === '1');
      galleryGrid.classList.toggle('mobile-cols-2', normalized !== '1');
      if (galleryViewOneBtn) galleryViewOneBtn.classList.toggle('active', normalized === '1');
      if (galleryViewTwoBtn) galleryViewTwoBtn.classList.toggle('active', normalized !== '1');
      try {
        localStorage.setItem('weave_gallery_mobile_cols', normalized);
      } catch (_) {}
    };
    if (galleryViewOneBtn && galleryViewTwoBtn) {
      const storedViewMode = String(localStorage.getItem('weave_gallery_mobile_cols') || '2');
      applyGalleryMobileViewMode(storedViewMode);
      galleryViewOneBtn.addEventListener('click', () => applyGalleryMobileViewMode('1'));
      galleryViewTwoBtn.addEventListener('click', () => applyGalleryMobileViewMode('2'));
      window.addEventListener('resize', () => {
        const mode = String(localStorage.getItem('weave_gallery_mobile_cols') || '2');
        applyGalleryMobileViewMode(mode);
      });
    }
    if (joinInquiryBtn) {
      joinInquiryBtn.addEventListener('click', () => {
        setJoinActionPanel('inquiry');
      });
    }
    if (joinSponsorBtn) {
      joinSponsorBtn.addEventListener('click', () => {
        setJoinActionPanel('sponsor');
      });
    }
    if (copyDonationAccountBtn) {
      copyDonationAccountBtn.addEventListener('click', async () => {
        await copyDonationAccount();
      });
    }

    if (noticeTabBtn && faqTabBtn && qnaTabBtn && noticeTab && faqTab && qnaTab) {
      noticeTabBtn.addEventListener('click', () => {
        currentNewsTab = 'notice';
        noticeTabBtn.classList.add('active');
        faqTabBtn.classList.remove('active');
        qnaTabBtn.classList.remove('active');
        noticeTab.classList.remove('d-none');
        faqTab.classList.add('d-none');
        qnaTab.classList.add('d-none');
        loadVolunteerEvents().catch(() => {});
        setNewsWriteButtons();
        setActiveNavStates('news');
      });
      faqTabBtn.addEventListener('click', () => {
        currentNewsTab = 'faq';
        faqTabBtn.classList.add('active');
        noticeTabBtn.classList.remove('active');
        qnaTabBtn.classList.remove('active');
        faqTab.classList.remove('d-none');
        noticeTab.classList.add('d-none');
        qnaTab.classList.add('d-none');
        renderFaq();
        setNewsWriteButtons();
        setActiveNavStates('news');
      });
      qnaTabBtn.addEventListener('click', () => {
        currentNewsTab = 'qna';
        qnaTabBtn.classList.add('active');
        noticeTabBtn.classList.remove('active');
        faqTabBtn.classList.remove('active');
        qnaTab.classList.remove('d-none');
        noticeTab.classList.add('d-none');
        faqTab.classList.add('d-none');
        renderQna();
        setNewsWriteButtons();
        setActiveNavStates('news');
      });
    }

    const qnaBackBtn = document.getElementById('qna-back-btn');
    if (qnaBackBtn) {
      qnaBackBtn.addEventListener('click', () => {
        document.querySelectorAll('[class*="panel"]').forEach(p => p.classList.remove('panel-active'));
        document.getElementById('news').classList.add('panel-active');
      });
    }

    const statsForm = document.getElementById('update-stats-form');
    const homeHeroForm = document.getElementById('update-home-hero-form');
    const homeHeroBgImageInput = document.getElementById('home-hero-bg-image-input');
    const homeHeroBgImageDropzone = document.getElementById('home-hero-bg-image-dropzone');
    const homeHeroBgImageInputHome = document.getElementById('home-hero-bg-image-input-home');
    const homeHeroBgImageDropzoneHome = document.getElementById('home-hero-bg-image-dropzone-home');
    const homeHeroBgImageOpenHome = document.getElementById('home-hero-bg-image-open-home');
    const homeHeroBgResetHome = document.getElementById('home-hero-bg-reset-home');
    const homeHeroBgPreviewHome = document.getElementById('home-hero-bg-preview-home');
    const homeHeroPosX = document.getElementById('home-hero-position-x');
    const homeHeroPosY = document.getElementById('home-hero-position-y');
    const homeHeroPosXNumber = document.getElementById('home-hero-position-x-number');
    const homeHeroPosYNumber = document.getElementById('home-hero-position-y-number');
    const homeHeroPosXMinus = document.getElementById('home-hero-position-x-minus');
    const homeHeroPosXPlus = document.getElementById('home-hero-position-x-plus');
    const homeHeroPosYMinus = document.getElementById('home-hero-position-y-minus');
    const homeHeroPosYPlus = document.getElementById('home-hero-position-y-plus');
    const homeHeroBgPosX = document.getElementById('home-hero-bg-position-x');
    const homeHeroBgPosY = document.getElementById('home-hero-bg-position-y');
    const homeHeroBgPosXNumber = document.getElementById('home-hero-bg-position-x-number');
    const homeHeroBgPosYNumber = document.getElementById('home-hero-bg-position-y-number');
    const homeHeroBgPosXMinus = document.getElementById('home-hero-bg-position-x-minus');
    const homeHeroBgPosXPlus = document.getElementById('home-hero-bg-position-x-plus');
    const homeHeroBgPosYMinus = document.getElementById('home-hero-bg-position-y-minus');
    const homeHeroBgPosYPlus = document.getElementById('home-hero-bg-position-y-plus');
    const homeHeroResetBtn = document.getElementById('home-hero-reset-btn');
    const syncHomeQuickBgPreview = () => {
      if (!homeHeroBgPreviewHome) return;
      const hero = getHomeHeroConfig();
      const bgImage = String(hero.backgroundImage || DEFAULT_HOME_HERO.backgroundImage).replace(/'/g, "\\'");
      const bgPosX = Math.max(0, Math.min(100, Number(hero.backgroundPosX || 50)));
      const bgPosY = Math.max(0, Math.min(100, Number(hero.backgroundPosY || 45)));
      homeHeroBgPreviewHome.style.backgroundImage = `url('${bgImage}')`;
      homeHeroBgPreviewHome.style.backgroundPosition = `${bgPosX}% ${bgPosY}%`;
    };
    syncHomeQuickBgPreview();
    if (homeHeroForm) {
      const hero = getHomeHeroConfig();
      homeHeroForm.leadText.value = hero.leadText;
      homeHeroForm.subText.value = hero.subText;
      if (homeHeroPosX) homeHeroPosX.value = String(hero.imageOffsetX || 0);
      if (homeHeroPosY) homeHeroPosY.value = String(hero.imageOffsetY || 0);
      if (homeHeroPosXNumber) homeHeroPosXNumber.value = String(hero.imageOffsetX || 0);
      if (homeHeroPosYNumber) homeHeroPosYNumber.value = String(hero.imageOffsetY || 0);
      if (homeHeroBgPosX) homeHeroBgPosX.value = String(hero.backgroundPosX || 50);
      if (homeHeroBgPosY) homeHeroBgPosY.value = String(hero.backgroundPosY || 45);
      if (homeHeroBgPosXNumber) homeHeroBgPosXNumber.value = String(hero.backgroundPosX || 50);
      if (homeHeroBgPosYNumber) homeHeroBgPosYNumber.value = String(hero.backgroundPosY || 45);
      homeHeroForm.onsubmit = (e) => {
        e.preventDefault();
        const user = getCurrentUser();
        if (!canManageHomeHero(user)) {
          notifyMessage('권한이 없습니다.');
          return;
        }
        saveHomeHeroConfig({
          leadText: String(e.target.leadText.value || '').trim() || DEFAULT_HOME_HERO.leadText,
          subText: String(e.target.subText.value || '').trim() || DEFAULT_HOME_HERO.subText,
          imageOffsetX: Number(homeHeroPosX?.value || 0),
          imageOffsetY: Number(homeHeroPosY?.value || 0),
          backgroundPosX: Number(homeHeroBgPosX?.value || 50),
          backgroundPosY: Number(homeHeroBgPosY?.value || 45)
        });
        renderHomeHeroConfig();
        notifyMessage('홈 문구가 저장되었습니다.');
      };
    }
    const clampNumber = (value, min, max) => Math.max(min, Math.min(max, Number(value || 0)));
    const syncAxisValue = ({
      rangeEl,
      numberEl,
      min,
      max,
      key,
    }) => {
      const next = clampNumber(rangeEl?.value ?? numberEl?.value, min, max);
      if (rangeEl) rangeEl.value = String(next);
      if (numberEl) numberEl.value = String(next);
      const payload = {
        imageOffsetX: Number(homeHeroPosX?.value || 0),
        imageOffsetY: Number(homeHeroPosY?.value || 0),
        backgroundPosX: Number(homeHeroBgPosX?.value || 50),
        backgroundPosY: Number(homeHeroBgPosY?.value || 45),
      };
      payload[key] = next;
      saveHomeHeroConfig(payload);
      renderHomeHeroConfig();
    };
    const bindAxisGroup = ({
      rangeEl,
      numberEl,
      minusEl,
      plusEl,
      min,
      max,
      key,
      step,
    }) => {
      if (rangeEl) {
        rangeEl.addEventListener('input', () => {
          const user = getCurrentUser();
          if (!canManageHomeHero(user)) return;
          syncAxisValue({ rangeEl, numberEl, min, max, key });
        });
      }
      if (numberEl) {
        numberEl.addEventListener('change', () => {
          const user = getCurrentUser();
          if (!canManageHomeHero(user)) return;
          syncAxisValue({ rangeEl, numberEl, min, max, key });
        });
      }
      if (minusEl) {
        minusEl.addEventListener('click', () => {
          const user = getCurrentUser();
          if (!canManageHomeHero(user)) return;
          const current = Number(rangeEl?.value || numberEl?.value || 0);
          const next = clampNumber(current - step, min, max);
          if (rangeEl) rangeEl.value = String(next);
          if (numberEl) numberEl.value = String(next);
          syncAxisValue({ rangeEl, numberEl, min, max, key });
        });
      }
      if (plusEl) {
        plusEl.addEventListener('click', () => {
          const user = getCurrentUser();
          if (!canManageHomeHero(user)) return;
          const current = Number(rangeEl?.value || numberEl?.value || 0);
          const next = clampNumber(current + step, min, max);
          if (rangeEl) rangeEl.value = String(next);
          if (numberEl) numberEl.value = String(next);
          syncAxisValue({ rangeEl, numberEl, min, max, key });
        });
      }
    };
    bindAxisGroup({
      rangeEl: homeHeroPosX,
      numberEl: homeHeroPosXNumber,
      minusEl: homeHeroPosXMinus,
      plusEl: homeHeroPosXPlus,
      min: -120,
      max: 120,
      key: 'imageOffsetX',
      step: 1,
    });
    bindAxisGroup({
      rangeEl: homeHeroPosY,
      numberEl: homeHeroPosYNumber,
      minusEl: homeHeroPosYMinus,
      plusEl: homeHeroPosYPlus,
      min: -120,
      max: 120,
      key: 'imageOffsetY',
      step: 1,
    });
    bindAxisGroup({
      rangeEl: homeHeroBgPosX,
      numberEl: homeHeroBgPosXNumber,
      minusEl: homeHeroBgPosXMinus,
      plusEl: homeHeroBgPosXPlus,
      min: 0,
      max: 100,
      key: 'backgroundPosX',
      step: 1,
    });
    bindAxisGroup({
      rangeEl: homeHeroBgPosY,
      numberEl: homeHeroBgPosYNumber,
      minusEl: homeHeroBgPosYMinus,
      plusEl: homeHeroBgPosYPlus,
      min: 0,
      max: 100,
      key: 'backgroundPosY',
      step: 1,
    });

    const applyBgPositionFromPointer = (clientX, clientY) => {
      const user = getCurrentUser();
      if (!canManageHomeHero(user)) return;
      const preview = document.getElementById('home-hero-bg-preview');
      if (!preview) return;
      const rect = preview.getBoundingClientRect();
      if (!rect.width || !rect.height) return;
      const xPct = Math.max(0, Math.min(100, Math.round(((clientX - rect.left) / rect.width) * 100)));
      const yPct = Math.max(0, Math.min(100, Math.round(((clientY - rect.top) / rect.height) * 100)));
      if (homeHeroBgPosX) homeHeroBgPosX.value = String(xPct);
      if (homeHeroBgPosY) homeHeroBgPosY.value = String(yPct);
      if (homeHeroBgPosXNumber) homeHeroBgPosXNumber.value = String(xPct);
      if (homeHeroBgPosYNumber) homeHeroBgPosYNumber.value = String(yPct);
      saveHomeHeroConfig({
        backgroundPosX: xPct,
        backgroundPosY: yPct,
      });
      renderHomeHeroConfig();
    };

    const homeHeroBgPreview = document.getElementById('home-hero-bg-preview');
    if (homeHeroBgPreview) {
      let dragging = false;
      let pointerId = null;
      homeHeroBgPreview.addEventListener('pointerdown', (event) => {
        dragging = true;
        pointerId = event.pointerId;
        homeHeroBgPreview.classList.add('dragging');
        homeHeroBgPreview.setPointerCapture?.(pointerId);
        applyBgPositionFromPointer(event.clientX, event.clientY);
      });
      homeHeroBgPreview.addEventListener('pointermove', (event) => {
        if (!dragging) return;
        if (pointerId !== null && event.pointerId !== pointerId) return;
        applyBgPositionFromPointer(event.clientX, event.clientY);
      });
      const finishPointerDrag = (event) => {
        if (!dragging) return;
        if (pointerId !== null && event && event.pointerId !== pointerId) return;
        dragging = false;
        if (pointerId !== null) {
          homeHeroBgPreview.releasePointerCapture?.(pointerId);
        }
        pointerId = null;
        homeHeroBgPreview.classList.remove('dragging');
      };
      homeHeroBgPreview.addEventListener('pointerup', finishPointerDrag);
      homeHeroBgPreview.addEventListener('pointercancel', finishPointerDrag);
    }

    if (homeHeroBgImageInput) {
      homeHeroBgImageInput.addEventListener('change', (e) => {
        const file = e.target.files?.[0];
        if (file) applyHomeHeroBackgroundFile(file);
        e.target.value = '';
      });
    }
    if (homeHeroBgImageInputHome) {
      homeHeroBgImageInputHome.addEventListener('change', (e) => {
        const file = e.target.files?.[0];
        if (file) applyHomeHeroBackgroundFile(file);
        e.target.value = '';
      });
    }
    if (homeHeroBgImageDropzone) {
      homeHeroBgImageDropzone.addEventListener('click', () => {
        const user = getCurrentUser();
        if (!canManageHomeHero(user)) {
          notifyMessage('권한이 없습니다.');
          return;
        }
        if (homeHeroBgImageInput) homeHeroBgImageInput.click();
      });
      homeHeroBgImageDropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        homeHeroBgImageDropzone.classList.add('dragover');
      });
      homeHeroBgImageDropzone.addEventListener('dragleave', () => {
        homeHeroBgImageDropzone.classList.remove('dragover');
      });
      homeHeroBgImageDropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        homeHeroBgImageDropzone.classList.remove('dragover');
        const file = e.dataTransfer?.files?.[0];
        if (file) applyHomeHeroBackgroundFile(file);
      });
    }
    if (homeHeroBgImageOpenHome) {
      homeHeroBgImageOpenHome.addEventListener('click', () => {
        const user = getCurrentUser();
        if (!canManageHomeHero(user)) {
          notifyMessage('권한이 없습니다.');
          return;
        }
        if (homeHeroBgImageInputHome) homeHeroBgImageInputHome.click();
      });
    }
    if (homeHeroBgImageDropzoneHome) {
      homeHeroBgImageDropzoneHome.addEventListener('click', () => {
        const user = getCurrentUser();
        if (!canManageHomeHero(user)) {
          notifyMessage('권한이 없습니다.');
          return;
        }
        if (homeHeroBgImageInputHome) homeHeroBgImageInputHome.click();
      });
      homeHeroBgImageDropzoneHome.addEventListener('dragover', (e) => {
        e.preventDefault();
        homeHeroBgImageDropzoneHome.classList.add('dragover');
      });
      homeHeroBgImageDropzoneHome.addEventListener('dragleave', () => {
        homeHeroBgImageDropzoneHome.classList.remove('dragover');
      });
      homeHeroBgImageDropzoneHome.addEventListener('drop', (e) => {
        e.preventDefault();
        homeHeroBgImageDropzoneHome.classList.remove('dragover');
        const file = e.dataTransfer?.files?.[0];
        if (file) applyHomeHeroBackgroundFile(file);
      });
    }
    if (homeHeroBgResetHome) {
      homeHeroBgResetHome.addEventListener('click', () => {
        const user = getCurrentUser();
        if (!canManageHomeHero(user)) {
          notifyMessage('권한이 없습니다.');
          return;
        }
        localStorage.removeItem(HOME_HERO_KEY);
        renderHomeHeroConfig();
        syncHomeQuickBgPreview();
        notifyMessage('홈 배경을 기본값으로 복원했습니다.');
      });
    }
    if (homeHeroBgPreviewHome) {
      let dragging = false;
      let pointerId = null;
      const applyQuickPreviewPointer = (clientX, clientY) => {
        const user = getCurrentUser();
        if (!canManageHomeHero(user)) return;
        const rect = homeHeroBgPreviewHome.getBoundingClientRect();
        if (!rect.width || !rect.height) return;
        const xPct = Math.max(0, Math.min(100, Math.round(((clientX - rect.left) / rect.width) * 100)));
        const yPct = Math.max(0, Math.min(100, Math.round(((clientY - rect.top) / rect.height) * 100)));
        saveHomeHeroConfig({ backgroundPosX: xPct, backgroundPosY: yPct });
        renderHomeHeroConfig();
        syncHomeQuickBgPreview();
      };
      homeHeroBgPreviewHome.addEventListener('pointerdown', (event) => {
        dragging = true;
        pointerId = event.pointerId;
        homeHeroBgPreviewHome.classList.add('dragging');
        homeHeroBgPreviewHome.setPointerCapture?.(pointerId);
        applyQuickPreviewPointer(event.clientX, event.clientY);
      });
      homeHeroBgPreviewHome.addEventListener('pointermove', (event) => {
        if (!dragging) return;
        if (pointerId !== null && event.pointerId !== pointerId) return;
        applyQuickPreviewPointer(event.clientX, event.clientY);
      });
      const finishQuickPreviewPointer = (event) => {
        if (!dragging) return;
        if (pointerId !== null && event && event.pointerId !== pointerId) return;
        dragging = false;
        if (pointerId !== null) homeHeroBgPreviewHome.releasePointerCapture?.(pointerId);
        pointerId = null;
        homeHeroBgPreviewHome.classList.remove('dragging');
      };
      homeHeroBgPreviewHome.addEventListener('pointerup', finishQuickPreviewPointer);
      homeHeroBgPreviewHome.addEventListener('pointercancel', finishQuickPreviewPointer);
    }
    if (homeHeroResetBtn) {
      homeHeroResetBtn.addEventListener('click', () => {
        const user = getCurrentUser();
        if (!canManageHomeHero(user)) {
          notifyMessage('권한이 없습니다.');
          return;
        }
        localStorage.removeItem(HOME_HERO_KEY);
        if (homeHeroForm) {
          homeHeroForm.leadText.value = DEFAULT_HOME_HERO.leadText;
          homeHeroForm.subText.value = DEFAULT_HOME_HERO.subText;
        }
        if (homeHeroPosX) homeHeroPosX.value = String(DEFAULT_HOME_HERO.imageOffsetX);
        if (homeHeroPosY) homeHeroPosY.value = String(DEFAULT_HOME_HERO.imageOffsetY);
        if (homeHeroPosXNumber) homeHeroPosXNumber.value = String(DEFAULT_HOME_HERO.imageOffsetX);
        if (homeHeroPosYNumber) homeHeroPosYNumber.value = String(DEFAULT_HOME_HERO.imageOffsetY);
        if (homeHeroBgPosX) homeHeroBgPosX.value = String(DEFAULT_HOME_HERO.backgroundPosX);
        if (homeHeroBgPosY) homeHeroBgPosY.value = String(DEFAULT_HOME_HERO.backgroundPosY);
        if (homeHeroBgPosXNumber) homeHeroBgPosXNumber.value = String(DEFAULT_HOME_HERO.backgroundPosX);
        if (homeHeroBgPosYNumber) homeHeroBgPosYNumber.value = String(DEFAULT_HOME_HERO.backgroundPosY);
        renderHomeHeroConfig();
        notifyMessage('홈 대표 이미지/문구를 기본값으로 복원했습니다.');
      });
    }

    if (statsForm) {
      const stats = getStats();
      statsForm.generation.value = stats.generation;
      statsForm.members.value = stats.members;
      statsForm.activities.value = stats.activities;
      statsForm.impact.value = stats.impact;
      statsForm.onsubmit = (e) => {
        e.preventDefault();
        const user = getCurrentUser();
        if (!user || (!user.isAdmin && !ADMIN_EMAILS.includes(user.email))) {
          notifyMessage('권한이 없습니다.');
          return;
        }
        saveStats({
          generation: e.target.generation.value,
          members: e.target.members.value,
          activities: e.target.activities.value,
          impact: e.target.impact.value
        });
        renderStats();
        notifyMessage('홈 통계가 저장되었습니다.');
      };
    }

    // Initial render
    (async () => {
      if (typeof hydrateContentFromServerIfEmpty === 'function') {
        await hydrateContentFromServerIfEmpty();
      }
      renderNews();
      renderFaq();
      renderQna();
      renderGallery();
    })();
    renderHomeHeroConfig();
    renderStats();
    initSiteContentEditor();
    setNewsWriteButtons();
    setJoinActionPanel('honor');
    loadVolunteerEvents().catch(() => {});

    const activitiesOverviewTabBtn = document.getElementById('activities-overview-tab-btn');
    const activitiesCalendarTabBtn = document.getElementById('activities-calendar-tab-btn');
    if (activitiesOverviewTabBtn) {
      activitiesOverviewTabBtn.addEventListener('click', () => {
        openActivitiesOverviewTab();
      });
    }
    if (activitiesCalendarTabBtn) {
      activitiesCalendarTabBtn.addEventListener('click', async () => {
        openActivitiesCalendarTab();
        await loadActivitiesCalendar();
      });
    }

    const prevBtn = document.getElementById('calendar-prev-btn');
    const nextBtn = document.getElementById('calendar-next-btn');
    if (prevBtn) {
      prevBtn.addEventListener('click', async () => {
        calendarBaseDate = new Date(calendarBaseDate.getFullYear(), calendarBaseDate.getMonth() - 1, 1);
        await loadActivitiesCalendar();
      });
    }
    if (nextBtn) {
      nextBtn.addEventListener('click', async () => {
        calendarBaseDate = new Date(calendarBaseDate.getFullYear(), calendarBaseDate.getMonth() + 1, 1);
        await loadActivitiesCalendar();
      });
    }

    const homeCalendarGoBtn = document.getElementById('home-calendar-go-btn');
    const homeCalendarPrevBtn = document.getElementById('home-calendar-prev-btn');
    const homeCalendarNextBtn = document.getElementById('home-calendar-next-btn');
    const homeNoticeToggleBtn = document.getElementById('home-notice-toggle-btn');
    if (homeCalendarPrevBtn) {
      homeCalendarPrevBtn.addEventListener('click', async () => {
        calendarBaseDate = new Date(calendarBaseDate.getFullYear(), calendarBaseDate.getMonth() - 1, 1);
        await loadActivitiesCalendar();
      });
    }
    if (homeCalendarNextBtn) {
      homeCalendarNextBtn.addEventListener('click', async () => {
        calendarBaseDate = new Date(calendarBaseDate.getFullYear(), calendarBaseDate.getMonth() + 1, 1);
        await loadActivitiesCalendar();
      });
    }
    if (homeCalendarGoBtn) {
      homeCalendarGoBtn.addEventListener('click', async (e) => {
        e.preventDefault();
        movePanel('activities');
        openActivitiesCalendarTab();
        await loadActivitiesCalendar();
      });
    }
    if (homeNoticeToggleBtn) {
      homeNoticeToggleBtn.addEventListener('click', () => {
        homeNoticePaused = !homeNoticePaused;
        if (homeNoticePaused) {
          stopHomeNoticeAutoRotate();
        } else {
          startHomeNoticeAutoRotate();
        }
        renderHomeNoticeCarousel();
      });
    }

    if (typeof initOpsDashboardBindingsFromGlobals === 'function') {
      initOpsDashboardBindingsFromGlobals();
    }

    const calendarCreateForm = document.getElementById('calendar-create-form');
    if (calendarCreateForm) {
      calendarCreateForm.addEventListener('submit', createActivityFromCalendar);
      if (calendarCreateForm.activityAttachmentFiles) {
        calendarCreateForm.activityAttachmentFiles.addEventListener('change', async (event) => {
          const files = event.target.files;
          if (!files || !files.length) return;
          try {
            await insertActivityFilesToEditor(files);
          } catch (error) {
            notifyMessage(error.message || '첨부 삽입 중 오류가 발생했습니다.');
          } finally {
            event.target.value = '';
          }
        });
      }
      const activityEditor = document.getElementById('activity-editor');
      if (activityEditor) {
        activityEditor.addEventListener('dragover', (event) => {
          event.preventDefault();
        });
        activityEditor.addEventListener('drop', async (event) => {
          event.preventDefault();
          const files = event.dataTransfer?.files;
          if (!files || !files.length) return;
          try {
            await insertActivityFilesToEditor(files);
          } catch (error) {
            notifyMessage(error.message || '첨부 삽입 중 오류가 발생했습니다.');
          }
        });
      }
    }

    const recurrenceConfirmBtn = document.getElementById('recurrence-cancel-confirm-btn');
    if (recurrenceConfirmBtn) {
      recurrenceConfirmBtn.addEventListener('click', executeRecurrenceCancel);
    }

    loadActivitiesCalendar().catch(() => {});
  });




