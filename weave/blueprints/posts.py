from flask import Blueprint
from weave import posts_routes as pr

bp = Blueprint("posts", __name__)

bp.add_url_rule("/api/posts", view_func=pr.list_posts, methods=["GET"])
bp.add_url_rule("/api/posts", view_func=pr.create_post, methods=["POST"])
bp.add_url_rule("/api/posts/<int:post_id>", view_func=pr.get_post, methods=["GET"])
bp.add_url_rule("/api/posts/<int:post_id>", view_func=pr.update_post, methods=["PUT"])
bp.add_url_rule(
    "/api/posts/<int:post_id>", view_func=pr.delete_post, methods=["DELETE"]
)
bp.add_url_rule(
    "/api/posts/<int:post_id>/comments",
    view_func=pr.create_post_comment,
    methods=["POST"],
)
bp.add_url_rule(
    "/api/posts/<int:post_id>/recommend", view_func=pr.recommend_post, methods=["POST"]
)
bp.add_url_rule(
    "/api/home/important-notices", view_func=pr.important_notices, methods=["GET"]
)
bp.add_url_rule(
    "/api/gallery/albums", view_func=pr.list_gallery_albums, methods=["GET"]
)
bp.add_url_rule(
    "/api/gallery/albums", view_func=pr.create_gallery_album, methods=["POST"]
)
bp.add_url_rule(
    "/api/gallery/albums/<int:album_id>/photos",
    view_func=pr.add_gallery_photos,
    methods=["POST"],
)
bp.add_url_rule(
    "/api/gallery/photos/<int:photo_id>",
    view_func=pr.delete_gallery_photo,
    methods=["DELETE"],
)
bp.add_url_rule("/api/press-kit", view_func=pr.get_press_kit, methods=["GET"])
bp.add_url_rule(
    "/api/rules/versions", view_func=pr.list_rules_versions, methods=["GET"]
)
bp.add_url_rule(
    "/api/rules/versions", view_func=pr.create_rules_version, methods=["POST"]
)
bp.add_url_rule(
    "/api/reports/annual/<int:year>", view_func=pr.get_annual_report, methods=["GET"]
)
bp.add_url_rule("/api/templates", view_func=pr.get_templates, methods=["GET"])
bp.add_url_rule(
    "/api/templates/generate", view_func=pr.generate_template, methods=["POST"]
)
bp.add_url_rule("/api/about/sections", view_func=pr.list_about_sections, methods=["GET"])
bp.add_url_rule(
    "/api/about/sections", view_func=pr.update_about_section, methods=["PUT"]
)
bp.add_url_rule(
    "/api/about/sections/image",
    view_func=pr.upload_about_section_image,
    methods=["POST"],
)
bp.add_url_rule("/api/content/blocks", view_func=pr.list_content_blocks, methods=["GET"])
bp.add_url_rule("/api/content/blocks", view_func=pr.update_content_block, methods=["PUT"])
