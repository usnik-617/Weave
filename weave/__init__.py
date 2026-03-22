import os

from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from weave import spa
from weave.blueprints import ALL_BLUEPRINTS
from weave.config import load_config
from weave.db import init_db
from weave.media_queue import ensure_background_workers_started
from weave.security import register_hooks


def create_app():
    app = Flask(__name__, static_folder=None)
    load_config(app)

    proxy_hops = int(os.environ.get("WEAVE_PROXY_HOPS", "1"))
    app.wsgi_app = ProxyFix(
        app.wsgi_app,
        x_for=proxy_hops,
        x_proto=proxy_hops,
        x_host=proxy_hops,
        x_port=proxy_hops,
    )

    register_hooks(app)

    for bp in ALL_BLUEPRINTS:
        app.register_blueprint(bp)

    app.add_url_rule("/", endpoint="spa_root", view_func=spa.root, methods=["GET"])
    app.add_url_rule(
        "/<path:path>",
        endpoint="spa_static_proxy",
        view_func=spa.static_proxy,
        methods=["GET"],
    )

    init_db()
    ensure_background_workers_started()
    return app
