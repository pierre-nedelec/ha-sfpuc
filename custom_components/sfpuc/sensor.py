"""Sensor platform for SFPUC Water Usage."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import SFPUCConfigEntry
from .const import DOMAIN
from .coordinator import SFPUCCoordinator

_LOGGER = logging.getLogger(__name__)

# Coordinator handles updates, no parallel update limit needed
PARALLEL_UPDATES = 0

SENSOR_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="latest_usage",
        translation_key="latest_usage",
        native_unit_of_measurement=UnitOfVolume.GALLONS,
        # Note: device_class=WATER requires state_class total/total_increasing
        # This is a point-in-time measurement, so we omit device_class
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="total_usage",
        translation_key="total_usage",
        native_unit_of_measurement=UnitOfVolume.GALLONS,
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL,
    ),
    SensorEntityDescription(
        key="last_update",
        translation_key="last_update",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SFPUCConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SFPUC sensors."""
    coordinator = entry.runtime_data

    async_add_entities(
        SFPUCSensor(coordinator, description, entry)
        for description in SENSOR_DESCRIPTIONS
    )


class SFPUCSensor(CoordinatorEntity[SFPUCCoordinator], SensorEntity):
    """Representation of a SFPUC sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SFPUCCoordinator,
        description: SensorEntityDescription,
        entry: SFPUCConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="SFPUC Water",
            manufacturer="San Francisco Public Utilities Commission",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        key = self.entity_description.key
        if key == "latest_usage":
            return round(self.coordinator.latest_usage, 2)
        if key == "total_usage":
            return round(self.coordinator.total_usage, 2)
        if key == "last_update":
            return self.coordinator.last_update_time
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        attrs: dict[str, Any] = {}
        key = self.entity_description.key

        if key in ("latest_usage", "total_usage"):
            attrs["last_update_time"] = self.coordinator.last_update_time
            if key == "total_usage" and self.coordinator.data:
                attrs["data_points"] = len(self.coordinator.data)

        return attrs
