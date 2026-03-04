from flask import Blueprint
from weave import uploads_routes as ur

bp = Blueprint("uploads", __name__)

bp.add_url_rule("/uploads/<path:filename>", view_func=ur.serve_uploaded_file, methods=["GET"])
bp.add_url_rule("/api/posts/<int:post_id>/files", view_func=ur.upload_post_file, methods=["POST"])
bp.add_url_rule("/api/posts/<int:post_id>/files", view_func=ur.list_post_files, methods=["GET"])
bp.add_url_rule("/api/posts/files/<int:file_id>/download", view_func=ur.download_post_file, methods=["GET"])
