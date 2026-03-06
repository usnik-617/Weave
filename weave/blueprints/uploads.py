from flask import Blueprint
from weave import post_files_routes as pfr

bp = Blueprint("uploads", __name__)

bp.add_url_rule(
    "/uploads/<path:filename>", view_func=pfr.serve_uploaded_file, methods=["GET"]
)
bp.add_url_rule(
    "/api/posts/<int:post_id>/files", view_func=pfr.upload_post_file, methods=["POST"]
)
bp.add_url_rule(
    "/api/posts/<int:post_id>/files", view_func=pfr.list_post_files, methods=["GET"]
)
bp.add_url_rule(
    "/api/post-files/<int:file_id>/download",
    view_func=pfr.download_post_file,
    methods=["GET"],
)
