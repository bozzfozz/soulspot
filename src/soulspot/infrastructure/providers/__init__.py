"""Download Provider package.

Contains implementations of IDownloadProvider for various download backends.
"""

from soulspot.infrastructure.providers.registry import DownloadProviderRegistry
from soulspot.infrastructure.providers.slskd_provider import SlskdDownloadProvider

__all__ = [
    "DownloadProviderRegistry",
    "SlskdDownloadProvider",
]
