import os

bind = os.environ.get("WEAVE_BIND", "0.0.0.0:8000")
workers = int(os.environ.get("WEAVE_WORKERS", "4"))
threads = int(os.environ.get("WEAVE_THREADS", "8"))
worker_class = "gthread"
timeout = int(os.environ.get("WEAVE_TIMEOUT", "60"))
keepalive = int(os.environ.get("WEAVE_KEEPALIVE", "5"))
max_requests = int(os.environ.get("WEAVE_MAX_REQUESTS", "2000"))
max_requests_jitter = int(os.environ.get("WEAVE_MAX_REQUESTS_JITTER", "200"))
accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("WEAVE_LOG_LEVEL", "info")
