from flask import Blueprint
from weave import auth_routes as ar

bp = Blueprint("auth", __name__)

bp.add_url_rule("/api/auth/me", view_func=ar.auth_me, methods=["GET"])
bp.add_url_rule("/api/auth/csrf", view_func=ar.auth_csrf_token, methods=["GET"])
bp.add_url_rule("/api/auth/signup", view_func=ar.auth_signup, methods=["POST"])
bp.add_url_rule("/api/auth/login", view_func=ar.auth_login, methods=["POST"])
bp.add_url_rule("/api/auth/logout", view_func=ar.auth_logout, methods=["POST"])
bp.add_url_rule("/api/auth/find-username", view_func=ar.auth_find_username, methods=["POST"])
bp.add_url_rule("/api/auth/reset-password", view_func=ar.auth_reset_password, methods=["POST"])
bp.add_url_rule("/api/auth/unlock-account", view_func=ar.auth_unlock_account, methods=["POST"])
bp.add_url_rule("/api/auth/withdraw", view_func=ar.auth_withdraw, methods=["POST"])
