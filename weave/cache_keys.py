from __future__ import annotations

CACHE_NAMESPACE = "v1"

EVENTS_LIST_PREFIX = f"events:{CACHE_NAMESPACE}:list:"
POSTS_LIST_PREFIXES = (
    f"posts:{CACHE_NAMESPACE}:list:notice:",
    f"posts:{CACHE_NAMESPACE}:list:gallery:",
)


def events_list_key(user_id, page, page_size):
    return f"{EVENTS_LIST_PREFIX}{user_id}:{page}:{page_size}"


def event_detail_key(user_id, event_id):
    return f"events:{CACHE_NAMESPACE}:detail:{user_id}:{event_id}"


def event_participants_key(event_id):
    return f"events:{CACHE_NAMESPACE}:participants:{event_id}"


def post_list_key(category, page, page_size, can_include_scheduled):
    return (
        f"posts:{CACHE_NAMESPACE}:list:{category}:{page}:{page_size}:"
        f"{int(bool(can_include_scheduled))}"
    )
