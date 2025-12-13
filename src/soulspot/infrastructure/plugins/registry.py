"""
Plugin Registry for SoulSpot Music Service Plugins.

Hey future me – das ist die ZENTRALE STELLE für alle Music Service Plugins!
Hier werden Plugins registriert und können über ServiceType abgerufen werden.

Verwendung:
    registry = PluginRegistry()
    registry.register(SpotifyPlugin(client, token))

    # Später...
    spotify = registry.get(ServiceType.SPOTIFY)
    artist = await spotify.get_artist("...")

    # Oder alle verfügbaren Plugins
    for plugin in registry.all():
        status = await plugin.get_auth_status()

Thread-Safety:
    Die Registry ist NICHT thread-safe! Bei Multi-Threading sync selbst.
    Für async ist sie safe (GIL in CPython).
"""

from collections.abc import Iterator

from soulspot.domain.ports.plugin import (
    IMetadataPlugin,
    IMusicServicePlugin,
    ServiceType,
)


class PluginRegistry:
    """
    Central registry for music service plugins.

    Hey future me – das ist ein einfacher Singleton-Pattern!
    Jeder ServiceType kann nur EIN Plugin haben (keine Duplikate).
    """

    def __init__(self) -> None:
        """Initialize empty registry."""
        self._plugins: dict[ServiceType, IMusicServicePlugin] = {}
        self._metadata_plugins: dict[ServiceType, IMetadataPlugin] = {}

    def register(self, plugin: IMusicServicePlugin) -> None:
        """
        Register a music service plugin.

        Hey future me – überschreibt existierendes Plugin für gleichen ServiceType!
        Das ist Absicht für Hot-Reloading bei Token-Refresh.

        Args:
            plugin: Plugin instance to register
        """
        self._plugins[plugin.service_type] = plugin

    def register_metadata(self, plugin: IMetadataPlugin) -> None:
        """
        Register a metadata-only plugin (MusicBrainz, etc).

        Args:
            plugin: Metadata plugin instance
        """
        self._metadata_plugins[plugin.service_type] = plugin

    def get(self, service_type: ServiceType) -> IMusicServicePlugin | None:
        """
        Get a plugin by service type.

        Args:
            service_type: The service type to look up

        Returns:
            Plugin instance or None if not registered
        """
        return self._plugins.get(service_type)

    def get_metadata(self, service_type: ServiceType) -> IMetadataPlugin | None:
        """
        Get a metadata plugin by service type.

        Args:
            service_type: The service type to look up

        Returns:
            Metadata plugin instance or None
        """
        return self._metadata_plugins.get(service_type)

    def require(self, service_type: ServiceType) -> IMusicServicePlugin:
        """
        Get a plugin, raising if not found.

        Hey future me – nutze das wenn Plugin MUSS existieren!
        Besser als get() + None-Check überall.

        Args:
            service_type: The service type to look up

        Returns:
            Plugin instance

        Raises:
            KeyError: If plugin not registered
        """
        plugin = self._plugins.get(service_type)
        if plugin is None:
            raise KeyError(f"No plugin registered for {service_type.value}")
        return plugin

    def unregister(self, service_type: ServiceType) -> None:
        """
        Unregister a plugin.

        Args:
            service_type: The service type to remove
        """
        self._plugins.pop(service_type, None)

    def all(self) -> Iterator[IMusicServicePlugin]:
        """
        Iterate over all registered plugins.

        Yields:
            Each registered plugin
        """
        yield from self._plugins.values()

    def all_metadata(self) -> Iterator[IMetadataPlugin]:
        """
        Iterate over all metadata plugins.

        Yields:
            Each metadata plugin
        """
        yield from self._metadata_plugins.values()

    @property
    def available_services(self) -> list[ServiceType]:
        """
        Get list of all registered service types.

        Returns:
            List of ServiceType enums
        """
        return list(self._plugins.keys())

    def is_registered(self, service_type: ServiceType) -> bool:
        """
        Check if a service is registered.

        Args:
            service_type: The service type to check

        Returns:
            True if registered
        """
        return service_type in self._plugins

    def clear(self) -> None:
        """
        Clear all registered plugins.

        Hey future me – nur für Tests verwenden!
        """
        self._plugins.clear()
        self._metadata_plugins.clear()


# Global singleton instance
# Hey future me – das ist der DEFAULT Registry!
# Für DI/Testing kannst du eigene Instanzen erstellen.
_default_registry: PluginRegistry | None = None


def get_plugin_registry() -> PluginRegistry:
    """
    Get the global plugin registry singleton.

    Returns:
        The global PluginRegistry instance
    """
    global _default_registry
    if _default_registry is None:
        _default_registry = PluginRegistry()
    return _default_registry


# Export
__all__ = [
    "PluginRegistry",
    "get_plugin_registry",
]
