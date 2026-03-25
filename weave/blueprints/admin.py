from flask import Blueprint
from weave import admin_routes as ar
from weave import attendance_routes as atr
from weave import users_routes as ur
from weave.health import healthz, metrics

bp = Blueprint("admin", __name__)

bp.add_url_rule("/metrics", view_func=metrics, methods=["GET"])
bp.add_url_rule("/healthz", view_func=healthz, methods=["GET"])

bp.add_url_rule(
    "/api/admin/pending-users", view_func=ar.admin_pending_users, methods=["GET"]
)
bp.add_url_rule(
    "/api/admin/users/<int:user_id>/approve",
    view_func=ar.admin_approve_user,
    methods=["POST"],
)
bp.add_url_rule(
    "/api/admin/users/search",
    view_func=ar.admin_search_users_by_identity,
    methods=["GET"],
)
bp.add_url_rule(
    "/api/admin/users/<int:user_id>/role",
    view_func=ar.admin_update_user_role,
    methods=["PATCH"],
)
bp.add_url_rule(
    "/api/admin/users/<int:user_id>/reject",
    view_func=ar.admin_reject_user,
    methods=["POST"],
)
bp.add_url_rule(
    "/api/admin/users/<int:user_id>/suspend",
    view_func=ar.admin_suspend_user,
    methods=["POST"],
)
bp.add_url_rule(
    "/api/admin/users/<int:user_id>/activate",
    view_func=ar.admin_activate_user,
    methods=["POST"],
)
bp.add_url_rule(
    "/api/admin/users/<int:user_id>/nickname",
    view_func=ur.admin_update_user_nickname,
    methods=["PATCH"],
)

bp.add_url_rule(
    "/api/admin/dashboard", view_func=atr.admin_dashboard, methods=["GET"]
)
bp.add_url_rule(
    "/api/admin/export/participants.csv",
    view_func=atr.export_participants_csv,
    methods=["GET"],
)
bp.add_url_rule(
    "/api/admin/export/attendance.csv",
    view_func=atr.export_attendance_csv,
    methods=["GET"],
)
bp.add_url_rule(
    "/api/admin/export/hours.csv",
    view_func=atr.export_hours_csv,
    methods=["GET"],
)
bp.add_url_rule("/api/admin/stats", view_func=ar.admin_stats, methods=["GET"])
bp.add_url_rule("/api/admin/audit-logs", view_func=ar.get_audit_logs, methods=["GET"])
bp.add_url_rule(
    "/api/admin/maintenance/notice-calendar-integrity",
    view_func=ar.admin_run_notice_calendar_integrity,
    methods=["POST"],
)

bp.add_url_rule(
    "/api/admin/role-requests", view_func=ur.list_role_requests, methods=["GET"]
)
bp.add_url_rule(
    "/api/admin/role-requests/<int:request_id>/approve",
    view_func=ur.approve_role_request,
    methods=["POST"],
)
bp.add_url_rule(
    "/api/admin/role-requests/<int:request_id>/deny",
    view_func=ur.deny_role_request,
    methods=["POST"],
)
bp.add_url_rule(
    "/api/admin/role/requests", view_func=ur.list_role_requests_legacy, methods=["GET"]
)
bp.add_url_rule(
    "/api/admin/role/requests/<int:request_id>/approve",
    view_func=ur.approve_role_request_legacy,
    methods=["POST"],
)
bp.add_url_rule(
    "/api/admin/role/requests/<int:request_id>/reject",
    view_func=ur.reject_role_request_legacy,
    methods=["POST"],
)
