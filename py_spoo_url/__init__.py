import warnings

warnings.warn(
    "py-spoo-url is deprecated and no longer maintained. It targets the "
    "legacy spoo.me endpoints, which keep working but receive no new "
    "features. Install its successor instead: pip install spoo "
    "(https://github.com/spoo-me/spoo-py has a migration guide).",
    DeprecationWarning,
    stacklevel=2,
)

from .shortener import Shortener  # noqa: E402
from .statistics import Statistics  # noqa: E402

__all__ = ["Shortener", "Statistics"]
