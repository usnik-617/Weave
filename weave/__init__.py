import os
from pathlib import Path

from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from weave import system_routes
from weave.blueprints import ALL_BLUEPRINTS
from weave.config import load_config
from weave.db import init_db
from weave.security import register_hooks


def create_app():
    project_root = Path(__file__).resolve().parent.parent
    static_dir = project_root / "static"

    app = Flask(__name__, static_folder=str(static_dir), static_url_path="")
    load_config(app)

    proxy_hops = int(os.environ.get("WEAVE_PROXY_HOPS", "1"))
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=proxy_hops, x_proto=proxy_hops, x_host=proxy_hops, x_port=proxy_hops)

    register_hooks(app)

    for bp in ALL_BLUEPRINTS:
        app.register_blueprint(bp)

    app.add_url_rule("/", view_func=system_routes.root, methods=["GET"])
    app.add_url_rule("/<path:path>", view_func=system_routes.static_proxy, methods=["GET"])

    init_db()
    return app
