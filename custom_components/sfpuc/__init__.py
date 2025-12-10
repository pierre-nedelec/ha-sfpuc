"""The SFPUC Water Usage integration."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN, UPDATE_INTERVAL
from .coordinator import SFPUCCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

type SFPUCConfigEntry = ConfigEntry[SFPUCCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: SFPUCConfigEntry) -> bool:
    """Set up SFPUC Water Usage from a config entry."""
    # Set up the coordinator to fetch historical data
    coordinator = SFPUCCoordinator(hass, entry)

    # Do the initial refresh
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator in runtime_data
    entry.runtime_data = coordinator

    # Forward the setup to the sensor platform
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _LOGGER.info(
        "SFPUC integration setup complete, coordinator will update every %d hours",
        UPDATE_INTERVAL // 3600,
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: SFPUCConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
