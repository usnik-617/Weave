from weave.errors.auth import *
from weave.errors.common import *
from weave.errors.events import *
from weave.errors.files import *
from weave.errors.posts import *
from weave.errors.roles import *
from weave.errors.users import *

from weave.errors.auth import __all__ as _auth_all
from weave.errors.common import __all__ as _common_all
from weave.errors.events import __all__ as _events_all
from weave.errors.files import __all__ as _files_all
from weave.errors.posts import __all__ as _posts_all
from weave.errors.roles import __all__ as _roles_all
from weave.errors.users import __all__ as _users_all

__all__ = [
    *_auth_all,
    *_common_all,
    *_events_all,
    *_files_all,
    *_posts_all,
    *_roles_all,
    *_users_all,
]
