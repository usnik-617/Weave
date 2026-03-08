import os

from weave import create_app


app = create_app()


if __name__ == "__main__":
    host = os.environ.get("WEAVE_HOST", "127.0.0.1")
    port = int(os.environ.get("WEAVE_PORT", os.environ.get("PORT", "5000")))
    app.run(host=host, port=port, debug=False, threaded=True)
