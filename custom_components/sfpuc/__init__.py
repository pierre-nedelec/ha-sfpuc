"""The SFPUC Water Usage integration."""

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, UPDATE_INTERVAL
from .coordinator import SFPUCCoordinator
from .login import login

_LOGGER = logging.getLogger(__name__)
PLATFORMS = []  # No sensor platform for live updates


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SFPUC Water Usage from a config entry."""

    username = entry.data["username"]
    password = entry.data["password"]

    # Set up the coordinator to fetch historical data
    coordinator = SFPUCCoordinator(hass, entry.data)
    
    # Store the coordinator in hass.data first
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    
    # Now do the initial refresh
    await coordinator.async_config_entry_first_refresh()

    # The coordinator will automatically continue updating based on UPDATE_INTERVAL
    _LOGGER.info("SFPUC integration setup complete, coordinator will update every %d seconds", UPDATE_INTERVAL)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = True  # No platforms to unload
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
