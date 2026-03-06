from flask import Blueprint
from weave import attendance_routes as ar
from weave import event_participation_routes as epr
from weave import events_routes as er

bp = Blueprint("events", __name__)

bp.add_url_rule("/api/events", view_func=er.list_events, methods=["GET"])
bp.add_url_rule("/api/events", view_func=er.create_event, methods=["POST"])
bp.add_url_rule(
    "/api/events/<int:event_id>", view_func=er.update_event, methods=["PUT"]
)
bp.add_url_rule(
    "/api/events/<int:event_id>", view_func=er.get_event_detail, methods=["GET"]
)
bp.add_url_rule(
    "/api/events/<int:event_id>/participants",
    view_func=epr.list_event_participants,
    methods=["GET"],
)
bp.add_url_rule(
    "/api/events/<int:event_id>/join", view_func=epr.join_event, methods=["POST"]
)
bp.add_url_rule(
    "/api/events/<int:event_id>/cancel",
    view_func=epr.cancel_event_participation,
    methods=["POST"],
)
bp.add_url_rule(
    "/api/events/<int:event_id>/vote", view_func=er.vote_event, methods=["POST"]
)
bp.add_url_rule(
    "/api/events/<int:event_id>/attendance",
    view_func=ar.mark_event_attendance,
    methods=["POST"],
)

bp.add_url_rule("/api/activities", view_func=er.list_activities, methods=["GET"])
bp.add_url_rule("/api/activities", view_func=er.create_activity, methods=["POST"])
bp.add_url_rule(
    "/api/activities/<int:activity_id>", view_func=er.update_activity, methods=["PUT"]
)
bp.add_url_rule(
    "/api/activities/<int:activity_id>",
    view_func=er.delete_activity,
    methods=["DELETE"],
)
bp.add_url_rule(
    "/api/activities/<int:activity_id>/apply",
    view_func=epr.apply_activity,
    methods=["POST"],
)
bp.add_url_rule(
    "/api/activities/recurrence/<group_id>/cancel",
    view_func=er.cancel_recurrence_group,
    methods=["POST"],
)
bp.add_url_rule(
    "/api/activities/recurrence/<group_id>/impact",
    view_func=er.recurrence_group_impact,
    methods=["GET"],
)
bp.add_url_rule(
    "/api/activities/<int:activity_id>/cancel",
    view_func=epr.cancel_activity,
    methods=["POST"],
)
bp.add_url_rule(
    "/api/activities/<int:activity_id>/attendance/qr-token",
    view_func=ar.create_attendance_qr_token,
    methods=["POST"],
)
bp.add_url_rule(
    "/api/activities/<int:activity_id>/attendance/qr-check",
    view_func=ar.qr_check_attendance,
    methods=["POST"],
)
bp.add_url_rule(
    "/api/activities/<int:activity_id>/attendance/bulk",
    view_func=ar.bulk_attendance,
    methods=["POST"],
)
