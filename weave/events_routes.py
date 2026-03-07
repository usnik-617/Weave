from weave.authz import get_current_user_row
from weave import cache_keys, error_messages
from weave.core import (
    get_cache,
    get_db_connection,
    invalidate_cache,
    jsonify,
    request,
    serialize_activity_row,
    set_cache,
    write_app_log,
)
from weave import event_command_service, event_policy, event_query_service
from weave.event_exceptions import EventNotFoundError
from weave.responses import (
    error_response,
    success_response,
)
from weave.time_utils import parse_iso_datetime


def list_activities():
    date_value = str(request.args.get("date", "")).strip()
    include_all = str(request.args.get("all", "")).strip().lower() in {
        "1",
        "true",
        "yes",
    }
    view = str(request.args.get("view", "month")).strip().lower()
    view, start_date, end_date = event_policy.resolve_activity_calendar_window(
        date_value, view
    )
    items = event_query_service.list_activities_items(include_all, start_date, end_date)
    return success_response(
        {
            "ok": True,
            "view": view,
            "range": {"start": start_date.isoformat(), "end": end_date.isoformat()},
            "items": items,
        }
    )


def create_activity():
    payload = request.get_json(silent=True) or {}
    required = ["title", "startAt", "endAt"]
    for field in required:
        if not str(payload.get(field, "")).strip():
            return error_response(f"{field} 값이 필요합니다.", 400)

    title = str(payload.get("title", "")).strip()
    if len(title) > 120:
        return error_response("활동 제목은 120자 이하여야 합니다.", 400)

    start_at = str(payload.get("startAt", "")).strip()
    end_at = str(payload.get("endAt", "")).strip()
    start_dt = parse_iso_datetime(start_at)
    end_dt = parse_iso_datetime(end_at)
    if not start_dt or not end_dt:
        return error_response("시작/종료 시간 형식이 올바르지 않습니다.", 400)
    if end_dt <= start_dt:
        return error_response("종료 시간은 시작 시간보다 늦어야 합니다.", 400)

    recruitment_limit = int(payload.get("recruitmentLimit", 0) or 0)
    if recruitment_limit < 0 or recruitment_limit > 1000:
        return error_response("모집 인원은 0~1000 범위여야 합니다.", 400)

    recurrence_group_id = str(payload.get("recurrenceGroupId", "")).strip()
    if recurrence_group_id and not event_policy.is_valid_recurrence_group_id(
        recurrence_group_id
    ):
        return error_response("반복 그룹 ID 형식이 올바르지 않습니다.", 400)

    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response(error_messages.EVENT_LOGIN_REQUIRED, 401)
    if not event_policy.can_manage_activity(me):
        conn.close()
        return error_response(error_messages.EVENT_MANAGE_ACTIVITY_REQUIRED, 403)
    conn.close()
    row = event_command_service.create_activity_record(payload, me)
    return success_response(
        {"ok": True, "activity": serialize_activity_row(row)}
    )


def update_activity(activity_id):
    payload = request.get_json(silent=True) or {}
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response(error_messages.EVENT_LOGIN_REQUIRED, 401)
    if not event_policy.can_manage_activity(me):
        conn.close()
        return error_response(error_messages.EVENT_MANAGE_ACTIVITY_REQUIRED, 403)

    target = conn.execute(
        "SELECT * FROM activities WHERE id = ?", (activity_id,)
    ).fetchone()
    if not target:
        conn.close()
        return error_response(error_messages.EVENT_ACTIVITY_NOT_FOUND, 404)
    if target["is_cancelled"]:
        conn.close()
        return error_response("취소된 일정은 수정할 수 없습니다.", 409)

    title = str(payload.get("title", target["title"] or "")).strip()
    if not title:
        conn.close()
        return error_response("title 값이 필요합니다.", 400)
    if len(title) > 120:
        conn.close()
        return error_response("활동 제목은 120자 이하여야 합니다.", 400)

    start_at = str(payload.get("startAt", target["start_at"] or "")).strip()
    end_at = str(payload.get("endAt", target["end_at"] or "")).strip()
    start_dt = parse_iso_datetime(start_at)
    end_dt = parse_iso_datetime(end_at)
    if not start_dt or not end_dt:
        conn.close()
        return error_response("시작/종료 시간 형식이 올바르지 않습니다.", 400)
    if end_dt <= start_dt:
        conn.close()
        return error_response("종료 시간은 시작 시간보다 늦어야 합니다.", 400)

    raw_limit = payload.get("recruitmentLimit", target["recruitment_limit"])
    recruitment_limit = int(raw_limit or 0)
    if recruitment_limit < 0 or recruitment_limit > 1000:
        conn.close()
        return error_response("모집 인원은 0~1000 범위여야 합니다.", 400)

    conn.close()
    row = event_command_service.update_activity_record(activity_id, payload, target, me)
    return success_response(
        {"ok": True, "activity": serialize_activity_row(row)}
    )


def delete_activity(activity_id):
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response(error_messages.EVENT_LOGIN_REQUIRED, 401)
    if not event_policy.can_manage_activity(me):
        conn.close()
        return error_response(error_messages.EVENT_MANAGE_ACTIVITY_REQUIRED, 403)

    target = conn.execute(
        "SELECT * FROM activities WHERE id = ?", (activity_id,)
    ).fetchone()
    if not target:
        conn.close()
        return error_response(error_messages.EVENT_ACTIVITY_NOT_FOUND, 404)
    if target["is_cancelled"]:
        conn.close()
        return success_response(
            {"ok": True, "message": "이미 취소된 일정입니다."}
        )

    conn.close()
    event_command_service.cancel_activity_record(activity_id)
    return success_response(
        {"ok": True, "message": "일정이 취소(삭제)되었습니다."}
    )


def cancel_recurrence_group(group_id):
    group_id = str(group_id or "").strip()
    if not event_policy.is_valid_recurrence_group_id(group_id):
        return error_response("유효하지 않은 반복 그룹 ID입니다.", 400)

    activity_ids = event_query_service.get_active_activity_ids_by_group(group_id)
    if not activity_ids:
        return error_response("취소할 반복 그룹이 없습니다.", 404)
    event_command_service.cancel_recurrence_group_records(activity_ids)
    return success_response(
        {
            "ok": True,
            "message": "반복 그룹 일정이 일괄 취소되었습니다.",
            "count": len(activity_ids),
        }
    )


def recurrence_group_impact(group_id):
    group_id = str(group_id or "").strip()
    if not event_policy.is_valid_recurrence_group_id(group_id):
        return error_response("유효하지 않은 반복 그룹 ID입니다.", 400)
    impact = event_query_service.recurrence_group_impact_data(group_id)

    return success_response(
        {
            "ok": True,
            "groupId": group_id,
            "impact": impact,
        }
    )


def list_events():
    page = max(1, int(request.args.get("page", "1") or 1))
    page_size = min(100, max(1, int(request.args.get("pageSize", "10") or 10)))
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response(error_messages.UNAUTHORIZED, 401)
    if not event_policy.can_view_event(me):
        conn.close()
        return error_response(error_messages.EVENT_VIEW_FORBIDDEN, 403)
    conn.close()
    cache_key = cache_keys.events_list_key(me["id"], page, page_size)
    cached = get_cache(cache_key)
    if cached is not None:
        return success_response(cached)
    data = event_query_service.events_page_data(me["id"], page, page_size)
    set_cache(cache_key, data)
    return success_response(data)


def create_event():
    payload = request.get_json(silent=True) or {}
    title = str(payload.get("title", "")).strip()
    start_datetime = str(
        payload.get("start_datetime", payload.get("event_date", ""))
    ).strip()
    end_datetime = str(payload.get("end_datetime", start_datetime)).strip()
    if not title or not start_datetime:
        return error_response("title/start_datetime은 필수입니다.", 400)
    if not parse_iso_datetime(start_datetime) or not parse_iso_datetime(end_datetime):
        return error_response(
            "start_datetime/end_datetime은 ISO 형식이어야 합니다.", 400
        )

    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response(error_messages.UNAUTHORIZED, 401)
    if not event_policy.can_manage_event(me):
        conn.close()
        return error_response(error_messages.EVENT_MANAGE_FORBIDDEN, 403)
    conn.close()
    event_id = event_command_service.create_event_record(payload, me)
    invalidate_cache(cache_keys.EVENTS_LIST_PREFIX)
    write_app_log(
        "info", "create_event", user_id=me["id"], extra={"event_id": event_id}
    )
    return success_response({"event_id": event_id}, 201)


def update_event(event_id):
    payload = request.get_json(silent=True) or {}
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response(error_messages.UNAUTHORIZED, 401)
    if not event_policy.can_manage_event(me):
        conn.close()
        return error_response(error_messages.EVENT_UPDATE_FORBIDDEN, 403)
    target = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    if not target:
        conn.close()
        return error_response(error_messages.EVENT_NOT_FOUND, 404)

    start_datetime = str(
        payload.get(
            "start_datetime",
            payload.get("event_date", target["start_datetime"] or target["event_date"]),
        )
    ).strip()
    end_datetime = str(
        payload.get("end_datetime", target["end_datetime"] or start_datetime)
    ).strip()
    if not parse_iso_datetime(start_datetime) or not parse_iso_datetime(end_datetime):
        conn.close()
        return error_response(
            "start_datetime/end_datetime은 ISO 형식이어야 합니다.", 400
        )
    conn.close()
    try:
        notified = event_command_service.update_event_record(
            event_id,
            payload,
            target,
            me,
        )
    except EventNotFoundError:
        return error_response(error_messages.EVENT_NOT_FOUND, 404)
    invalidate_cache(cache_keys.EVENTS_LIST_PREFIX)
    write_app_log(
        "info",
        "update_event",
        user_id=me["id"],
        extra={"event_id": event_id, "notified": notified},
    )
    return success_response({"event_id": event_id, "notified": notified})


def get_event_detail(event_id):
    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response(error_messages.UNAUTHORIZED, 401)
    if not event_policy.can_view_event(me):
        conn.close()
        return error_response(error_messages.EVENT_VIEW_FORBIDDEN, 403)
    conn.close()
    data = event_query_service.event_detail_data(event_id, me["id"])
    if not data:
        return error_response(error_messages.EVENT_NOT_FOUND, 404)
    return success_response(data)


def event_detail(event_id):
    return get_event_detail(event_id)


def vote_event(event_id):
    payload = request.get_json(silent=True) or {}
    status = event_policy.normalize_vote_status(payload.get("status", ""))
    if not status:
        return error_response(
            "투표 상태는 ATTEND/ABSENT/WAITING 중 하나여야 합니다.", 400
        )

    conn = get_db_connection()
    me = get_current_user_row(conn)
    if not me:
        conn.close()
        return error_response(error_messages.UNAUTHORIZED, 401)
    if not event_policy.can_vote_event(me):
        conn.close()
        return error_response(error_messages.EVENT_VOTE_FORBIDDEN, 403)

    event = conn.execute("SELECT id FROM events WHERE id = ?", (event_id,)).fetchone()
    if not event:
        conn.close()
        return error_response(error_messages.EVENT_NOT_FOUND, 404)

    conn.close()
    event_command_service.upsert_event_vote(event_id, me, status)
    return success_response({"event_id": event_id, "status": status})



