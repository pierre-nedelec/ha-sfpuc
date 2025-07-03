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
                # Start from the day after the last recorded time to avoid duplicates
                start_date = (last_stats_time + timedelta(days=1)).strftime("%m/%d/%Y")
                _LOGGER.info(f"Fetching data from {start_date} (day after last recorded: {last_stats_time.strftime('%m/%d/%Y')})")
            else:
                # If no previous data, fetch from an arbitrary recent past date
                # (e.g., 90 days ago) - will be adjusted to the earliest available date
                # by the download function
                start_date = (dt_util.now() - timedelta(days=90)).strftime("%m/%d/%Y")
                _LOGGER.info(f"No previous data found, fetching from {start_date}")

            end_date = dt_util.now().strftime("%m/%d/%Y")

            # Download new usage data from the last recorded time to now
            _LOGGER.info("Fetching data from %s to %s", start_date, end_date)
            parsed_data = await self.hass.async_add_executor_job(
                download_usage_for_multiple_days, session, start_date, end_date
            )
            
            if parsed_data:
                _LOGGER.info("Successfully fetched %d new data points", len(parsed_data))
                # Insert the new data into statistics
                await self._insert_statistics(parsed_data)
                _LOGGER.info("Data inserted into statistics")
            else:
                _LOGGER.info("No new data available")

            return parsed_data

        except Exception as err:
            _LOGGER.exception("Error fetching data")
            raise UpdateFailed(f"Error fetching data: {err}") from err

    async def _get_last_recorded_time(self) -> datetime | None:
        """Get the last recorded timestamp from Home Assistant statistics."""
        consumption_statistic_id = f"{DOMAIN}:sfpuc_water_usage"
        last_stat = await get_instance(self.hass).async_add_executor_job(
            get_last_statistics, self.hass, 1, consumption_statistic_id, True, set()
        )
        if last_stat and consumption_statistic_id in last_stat:
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
        _LOGGER.info("Updating statistics for %s", consumption_statistic_id)

        # Get the last statistic sum to continue from where we left off
        last_stat = await get_instance(self.hass).async_add_executor_job(
            get_last_statistics, self.hass, 1, consumption_statistic_id, True, set()
        )
        
        # Start with the last known sum, or 0 if no previous data
        consumption_sum = 0.0
        if last_stat and consumption_statistic_id in last_stat:
            last_sum = last_stat[consumption_statistic_id][0].get("sum")
            if last_sum is not None:
                consumption_sum = last_sum
                _LOGGER.info("Continuing from last sum: %s", consumption_sum)

        consumption_statistics = []
        
        # Sort data by timestamp to ensure correct order
        sorted_data = sorted(data.items(), key=lambda x: x[0])
        
        # Insert the data into Home Assistant's statistics system
        for timestamp, consumption in sorted_data:
            # Ensure the timestamp is timezone-aware, convert it to UTC if necessary
            if (
                timestamp.tzinfo is None
                or timestamp.tzinfo.utcoffset(timestamp) is None
            ):
                timestamp = dt_util.as_utc(timestamp)

            # Skip if we already have this data point
            if last_stat and consumption_statistic_id in last_stat:
                last_stats_time = last_stat[consumption_statistic_id][0]["start"]
                if timestamp.timestamp() <= last_stats_time:
                    _LOGGER.debug("Skipping duplicate data point: %s", timestamp)
                    continue

            # Add to cumulative sum
            consumption_sum += consumption
            consumption_statistics.append(
                StatisticData(
                    start=timestamp,
                    state=consumption,
                    sum=consumption_sum,
                )
            )

        if not consumption_statistics:
            _LOGGER.info("No new statistics to add")
            return

        # Metadata for the statistic
        consumption_metadata = StatisticMetaData(
            has_mean=False,
            has_sum=True,
            name="SFPUC Water Usage",
            source=DOMAIN,
            statistic_id=consumption_statistic_id,
            unit_of_measurement=UnitOfVolume.GALLONS,
        )

        _LOGGER.info(
            "Adding %s new statistics for %s",
            len(consumption_statistics),
            consumption_statistic_id,
        )
        async_add_external_statistics(
            self.hass, consumption_metadata, consumption_statistics
        )
