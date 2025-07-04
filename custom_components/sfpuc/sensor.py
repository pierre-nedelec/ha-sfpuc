"""Sensor platform for SFPUC Water Usage."""

from datetime import datetime
import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SFPUCCoordinator

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES = [
    SensorEntityDescription(
        key="latest_usage",
        name="Latest Water Usage",
        native_unit_of_measurement=UnitOfVolume.GALLONS,
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:water",
    ),
    SensorEntityDescription(
        key="total_usage",
        name="Total Water Usage",
        native_unit_of_measurement=UnitOfVolume.GALLONS,
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL,
        icon="mdi:water-pump",
    ),
    SensorEntityDescription(
        key="last_update",
        name="Last Update",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:clock-outline",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SFPUC sensors."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    entities = []
    for description in SENSOR_TYPES:
        entities.append(SFPUCSensor(coordinator, description))
    
    async_add_entities(entities)


class SFPUCSensor(CoordinatorEntity, SensorEntity):
    """Representation of a SFPUC sensor."""

    def __init__(
        self,
        coordinator: SFPUCCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{DOMAIN}_{description.key}"
        self._attr_name = description.name

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        if self.entity_description.key == "latest_usage":
            return round(self.coordinator.latest_usage, 2)
        elif self.entity_description.key == "total_usage":
            return round(self.coordinator.total_usage, 2)
        elif self.entity_description.key == "last_update":
            return self.coordinator.last_update_time
        return None

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.last_update_success

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        attrs = {}
        if self.entity_description.key == "latest_usage":
            attrs["last_update_success"] = self.coordinator.last_update_success
            attrs["last_update_time"] = self.coordinator.last_update_time
        elif self.entity_description.key == "total_usage":
            attrs["data_points"] = len(self.coordinator.data) if self.coordinator.data else 0
            attrs["last_update_success"] = self.coordinator.last_update_success
            attrs["last_update_time"] = self.coordinator.last_update_time
        elif self.entity_description.key == "last_update":
            attrs["last_update_success"] = self.coordinator.last_update_success
        return attrs 