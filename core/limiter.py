from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Shared instance: created here (not in app_factory) so route modules can
# import and decorate endpoints without triggering circular imports.
limiter = Limiter(key_func=get_remote_address, default_limits=["200 per hour"])
