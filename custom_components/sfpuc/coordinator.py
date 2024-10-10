"""Coordinator to handle SFPUC connection."""

from collections.abc import Mapping
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.models import StatisticData, StatisticMetaData
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    get_last_statistics,
)
from homeassistant.const import UnitOfVolume
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util  # Import dt_util for timezone handling

from .const import DOMAIN, UPDATE_INTERVAL
from .download import download_usage_for_multiple_days
from .login import login

_LOGGER = logging.getLogger(__name__)


class SFPUCCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator to fetch SFPUC data and store it in statistics."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_data: Mapping[str, Any],
    ) -> None:
        """Initialize the SFPUC data handler."""
        super().__init__(
            hass,
            _LOGGER,
            name="SFPUC",
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )
        self.username = entry_data["username"]
        self.password = entry_data["password"]

        @callback
        def _dummy_listener() -> None:
            pass

        # Register a dummy listener to ensure periodic updates
        self.async_add_listener(_dummy_listener)

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch new data from the last recorded date and insert into statistics."""
        try:
            # Log in to SFPUC
            _LOGGER.info("Logging in to SFPUC")
            session = await self.hass.async_add_executor_job(
                login, self.username, self.password
            )
            if not session:
                raise UpdateFailed("Failed to log in to SFPUC")

            # Determine the last recorded time in the statistics system
            last_stats_time = await self._get_last_recorded_time()

            # Fetch data starting from the day after the last recorded time
            if last_stats_time:
                start_date = (last_stats_time + timedelta(days=0)).strftime("%m/%d/%Y")
            else:
                # If no previous data, fetch from an arbitrary recent past date
                # (e.g., 3 months ago) - will be adjusted to the earliest available date
                # by the download function
                start_date = (dt_util.now() - timedelta(days=120)).strftime("%m/%d/%Y")

            end_date = dt_util.now().strftime("%m/%d/%Y")

            # Download new usage data from the last recorded time to now
            _LOGGER.debug("Fetching data from %s to %s", start_date, end_date)
            parsed_data = await self.hass.async_add_executor_job(
                download_usage_for_multiple_days, session, start_date, end_date
            )
            if parsed_data:
                _LOGGER.debug("Parsed new data: %s", parsed_data)
                # Insert the new data into statistics
                await self._insert_statistics(parsed_data)
                _LOGGER.debug("Data inserted into statistics")

        except Exception as err:
            raise UpdateFailed(f"Error fetching data: {err}") from err
        else:
            return parsed_data

    async def _get_last_recorded_time(self) -> datetime | None:
        """Get the last recorded timestamp from Home Assistant statistics."""
        consumption_statistic_id = f"{DOMAIN}:sfpuc_water_usage"
        last_stat = await get_instance(self.hass).async_add_executor_job(
            get_last_statistics, self.hass, 1, consumption_statistic_id, True, set()
        )
        if last_stat:
            # Get the most recent timestamp
            last_stats_time = last_stat[consumption_statistic_id][0]["start"]
            # convert timestamp (just a long number) to readable date
            last_stats_time = dt_util.utc_from_timestamp(last_stats_time)
            _LOGGER.info("Last recorded time: %s", last_stats_time)
            return last_stats_time
        return None

    async def _insert_statistics(self, data: dict[str, Any]) -> None:
        """Insert SFPUC water usage statistics into Home Assistant's recorder."""
        consumption_statistic_id = f"{DOMAIN}:sfpuc_water_usage"
        _LOGGER.debug("Updating statistics for %s", consumption_statistic_id)

        # Get the last statistic time
        last_stat = await get_instance(self.hass).async_add_executor_job(
            get_last_statistics, self.hass, 1, consumption_statistic_id, True, set()
        )
        last_stats_time = None
        if last_stat:
            last_stats_time = last_stat[consumption_statistic_id][0]["start"]

        consumption_statistics = []
        consumption_sum = 0.0

        # Insert the data into Home Assistant's statistics system
        for timestamp, consumption in data.items():
            # Ensure the timestamp is timezone-aware, convert it to UTC if necessary
            if (
                timestamp.tzinfo is None
                or timestamp.tzinfo.utcoffset(timestamp) is None
            ):
                timestamp = dt_util.as_utc(timestamp)

            # Only insert data newer than the last statistics time
            if last_stats_time and timestamp.timestamp() <= last_stats_time:
                continue

            consumption_sum += consumption
            consumption_statistics.append(
                StatisticData(
                    start=timestamp,
                    state=consumption,
                    sum=consumption_sum,
                )
            )

        # Metadata for the statistic
        consumption_metadata = StatisticMetaData(
            has_mean=False,
            has_sum=True,
            name="SFPUC Water Usage",
            source=DOMAIN,
            statistic_id=consumption_statistic_id,
            unit_of_measurement=UnitOfVolume.GALLONS,
        )

        _LOGGER.debug(
            "Adding %s statistics for %s",
            len(consumption_statistics),
            consumption_statistic_id,
        )
        async_add_external_statistics(
            self.hass, consumption_metadata, consumption_statistics
        )
