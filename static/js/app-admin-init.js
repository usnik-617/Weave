  // ============ ADMIN FORMS ============
  document.addEventListener('DOMContentLoaded', function() {
    initRichEditorToolbars();
    bindImageUploader({
      formId: 'add-news-form',
      inputName: 'imageFile',
      dropzoneId: 'news-image-dropzone',
      previewId: 'news-image-preview',
      hiddenName: 'imageData',
      imagesHiddenName: 'imagesData',
      editorId: 'news-editor',
      stripExifToggleId: 'news-strip-exif'
    });
    bindImageUploader({
      formId: 'add-gallery-form',
      inputName: 'imageFile',
      dropzoneId: 'gallery-image-dropzone',
      previewId: 'gallery-image-preview',
      hiddenName: 'imageData',
      imagesHiddenName: 'imagesData',
      editorId: 'gallery-editor',
      stripExifToggleId: 'gallery-strip-exif'
    });
    ensureGalleryYearOptions();
    const galleryTabTrigger = document.getElementById('gallery-tab');
    if (galleryTabTrigger) {
      galleryTabTrigger.addEventListener('shown.bs.tab', () => {
        const selected = document.getElementById('gallery-activity-select')?.value || '';
        loadGalleryActivityOptions(selected);
      });
    }

    // News Form
    const newsForm = document.getElementById('add-news-form');
    if (newsForm) {
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
        const user = getCurrentUser();
        if (!user) {
          notifyMessage('로그인이 필요합니다.');
          return;
        }

        syncEditorToInput(e.target, 'news-editor', { markRepresentative: true });
        const data = getContent();
        const editId = Number(e.target.editId.value || 0);
        const newDate = getTodayString();
        const editorImages = getEditorImageSources('news-editor');
        const coverImage = editorImages[0] || '';
        const generatedThumb = coverImage && typeof createThumbnailDataUrl === 'function'
          ? await createThumbnailDataUrl(coverImage, { width: 360, height: 220, quality: 0.78 }).catch(() => '')
          : '';
        const tabType = e.target.postTab.value;
        const isSecret = !!e.target.isSecret.checked;
        const volunteerStartDate = (e.target.volunteerStartDate?.value || '').trim();
        const volunteerEndDateRaw = (e.target.volunteerEndDate?.value || '').trim();
        const volunteerEndDate = volunteerEndDateRaw || volunteerStartDate;
        const featuredOnHome = tabType === 'notice' ? !!e.target.featuredOnHome?.checked : false;
        const publishAt = e.target.isScheduled?.checked ? (e.target.publishAt?.value || '').trim() : '';
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

        const source = tabType === 'faq' ? (data.faq ||= []) : (tabType === 'qna' ? (data.qna ||= []) : data.news);
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
            target.images = [];
            target.image = coverImage || nextImages[0] || target.image || '';
            if (generatedThumb) {
              target.thumb_url = generatedThumb;
              target.thumbnail_url = generatedThumb;
            }
            target.content = e.target.content.value;
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
          }
        } else {
          const newId = Math.max(...source.map(x => x.id), 0) + 1;
          const nextImages = editorImages.length ? editorImages : [];
          const newItem = {
            id: newId,
            title: e.target.title.value,
            author: e.target.author.value || user.nickname || user.username || user.name,
            date: newDate,
            image: coverImage || nextImages[0] || '',
            thumb_url: generatedThumb || '',
            thumbnail_url: generatedThumb || '',
            images: [],
            content: e.target.content.value,
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
        }
        saveContent(data);
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
      };
    }

    // Gallery Form
    const galleryForm = document.getElementById('add-gallery-form');
    if (galleryForm) {
      if (galleryForm.isScheduled) {
        galleryForm.isScheduled.addEventListener('change', () => {
          const publishWrap = document.getElementById('gallery-publish-at-wrap');
          if (publishWrap) publishWrap.classList.toggle('d-none', !galleryForm.isScheduled.checked);
          if (!galleryForm.isScheduled.checked && galleryForm.publishAt) galleryForm.publishAt.value = '';
        });
      }
      galleryForm.onsubmit = async (e) => {
        e.preventDefault();
        const user = getCurrentUser();
        if (!user) {
          notifyMessage('로그인이 필요합니다.');
          return;
        }

        syncEditorToInput(e.target, 'gallery-editor', { markRepresentative: true, representativeLabel: false });
        const data = getContent();
        if (!Array.isArray(data.gallery)) data.gallery = [];
        const year = Number(e.target.year.value || 2026);
        const activityId = Number(e.target.activityId?.value || 0);
        const selectedActivityOption = e.target.activityId?.selectedOptions?.[0] || null;
        const activityStartAt = activityId > 0 ? String(selectedActivityOption?.dataset?.startAt || '') : '';
        const editId = Number(e.target.editId.value || 0);
        const newDate = getTodayString();
        const editorImages = getEditorImageSources('gallery-editor');
        const coverImage = editorImages[0] || '';
        const generatedThumb = coverImage && typeof createThumbnailDataUrl === 'function'
          ? await createThumbnailDataUrl(coverImage, { width: 360, height: 220, quality: 0.78 }).catch(() => '')
          : '';
        const publishAt = e.target.isScheduled?.checked ? (e.target.publishAt?.value || '').trim() : '';
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
            target.images = [];
            target.image = coverImage || nextImages[0] || target.image || 'logo.png';
            if (generatedThumb) {
              target.thumb_url = generatedThumb;
              target.thumbnail_url = generatedThumb;
            }
            target.content = e.target.content.value || '';
            target.publishAt = publishAt || '';
            if (activityId > 0) {
              target.activityId = activityId;
              target.activityStartAt = activityStartAt;
            } else {
              delete target.activityId;
              delete target.activityStartAt;
            }
            galleryItem = target;
          }
        } else {
          const newId = Math.max(...data.gallery.map(x => Number(x.id) || 0), 0) + 1;
          const nextImages = editorImages.length ? editorImages : [];
          galleryItem = {
            id: newId,
            title: e.target.title.value,
            date: newDate,
            year,
            category: `y${year}`,
            image: coverImage || nextImages[0] || 'logo.png',
            thumb_url: generatedThumb || '',
            thumbnail_url: generatedThumb || '',
            images: [],
            content: e.target.content.value || '',
            publishAt: publishAt || '',
            author: user.nickname || user.username || user.name,
            views: 0,
            activityId: activityId > 0 ? activityId : undefined,
            activityStartAt: activityId > 0 ? activityStartAt : undefined
          };
          data.gallery.unshift(galleryItem);
        }
        // 봉사 기간(활동) 선택 시 캘린더 일정 추가
        if (activityId > 0 && activityStartAt) {
          // 일정 추가 API 호출 (예시, 실제 API 엔드포인트에 맞게 수정 필요)
          fetch('/activities', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              title: galleryItem.title,
              startAt: activityStartAt,
              endAt: activityStartAt,
              place: '-',
              manager: user.nickname || user.username || user.name,
              sourceType: 'gallery',
              sourceGalleryId: galleryItem.id
            })
          }).then(() => {
            // 일정 추가 후 캘린더 새로고침
            if (typeof loadActivitiesCalendar === 'function') {
              loadActivitiesCalendar();
            }
          });
        }
        saveContent(data);
        renderGallery();
        resetWriteForms();
        ensureGalleryYearOptions();
        movePanel('gallery');
        notifyMessage(editId ? '갤러리가 수정되었습니다!' : '갤러리가 추가되었습니다!');
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
    const eventsRefreshBtn = document.getElementById('events-refresh-btn');
    const eventDetailBackBtn = document.getElementById('event-detail-back-btn');
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
    renderNews();
    renderFaq();
    renderQna();
    renderGallery();
    renderHomeHeroConfig();
    renderStats();
    initSiteContentEditor();
    setNewsWriteButtons();
    setJoinActionPanel('inquiry');
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

