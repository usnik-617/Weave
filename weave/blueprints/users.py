from flask import Blueprint
from weave import users_routes as ur

bp = Blueprint("users", __name__)

bp.add_url_rule("/api/user/profile", view_func=ur.user_profile, methods=["GET"])
bp.add_url_rule("/api/me/nickname", view_func=ur.update_my_nickname, methods=["PATCH"])
bp.add_url_rule("/api/me/activity", view_func=ur.list_my_activity, methods=["GET"])
bp.add_url_rule(
    "/api/me/notifications", view_func=ur.list_my_notifications, methods=["GET"]
)
bp.add_url_rule(
    "/api/me/notifications", view_func=ur.create_my_notification, methods=["POST"]
)
bp.add_url_rule(
    "/api/me/notifications/read-all",
    view_func=ur.mark_my_notifications_read_all,
    methods=["PATCH"],
)
bp.add_url_rule(
    "/api/me/notifications/<int:notification_id>/read",
    view_func=ur.mark_my_notification_read,
    methods=["PATCH"],
)
bp.add_url_rule(
    "/api/user/nickname", view_func=ur.update_user_nickname_legacy, methods=["POST"]
)
bp.add_url_rule(
    "/api/me/delete-account", view_func=ur.delete_my_account, methods=["POST"]
)
bp.add_url_rule("/api/me/history", view_func=ur.my_activity_history, methods=["GET"])
bp.add_url_rule(
    "/api/me/certificate.csv", view_func=ur.my_certificate_csv, methods=["GET"]
)
bp.add_url_rule("/api/role/request", view_func=ur.request_role_change, methods=["POST"])
bp.add_url_rule(
    "/api/role-requests/member", view_func=ur.request_member_role, methods=["POST"]
)
bp.add_url_rule(
    "/api/role-requests/executive",
    view_func=ur.request_executive_role,
    methods=["POST"],
)
