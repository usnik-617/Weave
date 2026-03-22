from __future__ import annotations

from weave.authz import can_create_gallery, can_create_notice, role_at_least
from weave import cache_keys

# Categories accepted by POST /api/posts create.
CREATE_ALLOWED_CATEGORIES = ("notice", "review", "recruit", "qna", "gallery")

# Categories accepted by GET /api/posts?type=... filter.
LIST_ALLOWED_CATEGORIES = ("notice", "faq", "qna", "gallery", "review", "recruit")

# Keep cache invalidation targets explicit and centralized.
CACHE_INVALIDATION_PREFIXES = cache_keys.POSTS_LIST_PREFIXES

# Category aliases used by list filtering.
LIST_CATEGORY_ALIASES = {
    "faq": "review",
}


def normalize_create_category(raw_category):
    return str(raw_category or "").strip().lower()


def is_creatable_category(category):
    return category in CREATE_ALLOWED_CATEGORIES


def normalize_list_category(raw_category):
    category = str(raw_category or "").strip().lower()
    if category in LIST_ALLOWED_CATEGORIES:
        return LIST_CATEGORY_ALIASES.get(category, category)
    return ""


def can_include_scheduled_posts(user, include_scheduled_flag):
    return bool(
        user and include_scheduled_flag and role_at_least(user["role"], "VICE_LEADER")
    )


def can_view_scheduled_post_detail(user):
    return bool(user and role_at_least(user["role"], "VICE_LEADER"))


def create_permission_error(category, user):
    if category == "notice" and not can_create_notice(user):
        return "공지/갤러리 작성은 운영진 이상만 가능합니다."
    if category == "gallery" and not can_create_gallery(user):
        return "공지/갤러리 작성은 운영진 이상만 가능합니다."
    if category in ("review", "recruit") and not role_at_least(user["role"], "EXECUTIVE"):
        return "해당 글 유형은 운영진 이상만 작성할 수 있습니다."
    if category == "qna" and not role_at_least(user["role"], "GENERAL"):
        return "Q&A 작성 권한이 없습니다."
    return ""


def update_permission_error(category, user):
    if category == "notice" and not can_create_notice(user):
        return "공지 수정은 운영진 이상만 가능합니다."
    if category == "gallery" and not can_create_gallery(user):
        return "갤러리 수정은 운영진 이상만 가능합니다."
    if category in ("review", "recruit") and not role_at_least(user["role"], "EXECUTIVE"):
        return "해당 글 유형은 운영진 이상만 수정할 수 있습니다."
    return ""


def is_special_category(category):
    return category in ("notice", "gallery", "qna")


def should_cache_post_list(category, keyword):
    return category in ("notice", "gallery") and not keyword


def post_list_cache_key(category, page, page_size, can_include_scheduled):
    return cache_keys.post_list_key(category, page, page_size, can_include_scheduled)
