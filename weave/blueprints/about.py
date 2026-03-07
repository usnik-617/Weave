from flask import Blueprint

from weave import about_routes as ar

bp = Blueprint("about", __name__)

bp.add_url_rule("/api/about/sections", view_func=ar.list_about_sections, methods=["GET"])
bp.add_url_rule("/api/about/sections", view_func=ar.update_about_section, methods=["PUT"])
bp.add_url_rule(
    "/api/about/sections/image",
    view_func=ar.upload_about_section_image,
    methods=["POST"],
)
bp.add_url_rule("/api/content/blocks", view_func=ar.list_content_blocks, methods=["GET"])
bp.add_url_rule("/api/content/blocks", view_func=ar.update_content_block, methods=["PUT"])
bp.add_url_rule("/api/content/site-editor", view_func=ar.get_site_editor_state, methods=["GET"])
bp.add_url_rule("/api/content/site-editor", view_func=ar.update_site_editor_state, methods=["PUT"])
bp.add_url_rule("/api/content/site-editor", view_func=ar.reset_site_editor_state, methods=["DELETE"])
bp.add_url_rule("/api/content/site-editor/history", view_func=ar.list_site_editor_history, methods=["GET"])
bp.add_url_rule("/api/content/site-editor/undo", view_func=ar.undo_site_editor_state, methods=["POST"])
bp.add_url_rule("/api/content/site-editor/restore", view_func=ar.restore_site_editor_state, methods=["POST"])
