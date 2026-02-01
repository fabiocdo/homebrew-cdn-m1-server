import os
from .log_utils import Logger
from .pkg_utils import PkgUtils

# Default Logger instance for compatibility
_log_level = os.getenv("LOG_LEVEL", "info")
_default_logger = Logger(log_level=_log_level)
log = _default_logger.log

# Default PkgUtils instance
pkg_utils = PkgUtils()
