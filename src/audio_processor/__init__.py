"""Audio Processor.

Audio file conversion and processing for RAG content pipelines
"""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version

try:
    __version__ = _pkg_version("audio-processor")
except PackageNotFoundError:
    __version__ = "unknown"
__author__ = "Byron Williams"
__email__ = "byron@williamshome.family"

__all__ = [
    "__author__",
    "__email__",
    "__version__",
]
