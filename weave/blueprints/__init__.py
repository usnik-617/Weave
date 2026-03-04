from .auth import bp as auth_bp
from .users import bp as users_bp
from .posts import bp as posts_bp
from .events import bp as events_bp
from .uploads import bp as uploads_bp
from .admin import bp as admin_bp


ALL_BLUEPRINTS = [
    auth_bp,
    users_bp,
    posts_bp,
    events_bp,
    uploads_bp,
    admin_bp,
]
