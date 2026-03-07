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
