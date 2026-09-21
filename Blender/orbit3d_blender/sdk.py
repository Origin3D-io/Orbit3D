"""Use the packaged SDK, or an installed SDK during source development."""

from importlib import import_module
from importlib.util import find_spec

_bundled = f"{__package__}.orbit3d_hub"
hub = import_module(_bundled if find_spec(_bundled) is not None else "orbit3d_hub")

__all__ = ["hub"]
