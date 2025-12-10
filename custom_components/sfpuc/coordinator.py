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
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DOMAIN, UPDATE_INTERVAL
from .download import download_usage_for_multiple_days, get_available_date_range
from .login import login

_LOGGER = logging.getLogger(__name__)


class SFPUCCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator to fetch SFPUC data and store it in statistics."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the SFPUC data handler."""
        super().__init__(
            hass,
            _LOGGER,
            name="SFPUC",
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
            config_entry=config_entry,  # Pass config_entry for proper lifecycle
        )
        self.username = config_entry.data["username"]
        self.password = config_entry.data["password"]
        self.latest_usage: float = 0.0
        self.total_usage: float = 0.0
        self.last_update_time: datetime | None = None
        self._last_successful_fetch: bool = False

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch new data from the last recorded date and insert into statistics."""
        try:
            # Log in to SFPUC
            _LOGGER.debug("Logging in to SFPUC")
            session = await self.hass.async_add_executor_job(
                login, self.username, self.password
            )
            if not session:
                raise UpdateFailed("Failed to log in to SFPUC")

            # Get the available date range from SFPUC first
            _LOGGER.debug("Getting available date range from SFPUC")
            available_start, available_end = await self.hass.async_add_executor_job(
                get_available_date_range, session
            )

            if not available_start or not available_end:
                raise UpdateFailed("Could not determine available date range from SFPUC")

            _LOGGER.info(
                "SFPUC available range: %s to %s",
                available_start.strftime("%m/%d/%Y"),
                available_end.strftime("%m/%d/%Y"),
            )

            # Get the last recorded time and sum in one call to avoid race conditions
            last_stats_time, last_sum = await self._get_last_statistics()

            # Determine start date for fetching
            if last_stats_time:
                # If last recorded time is outside available range, start from available start
                if last_stats_time.date() < available_start.date():
                    start_date = available_start
                    _LOGGER.info(
                        "Last recorded time %s is outside available range. Starting from %s",
                        last_stats_time.strftime("%m/%d/%Y"),
                        start_date.strftime("%m/%d/%Y"),
                    )
                else:
                    # Start from the day after the last recorded time
                    start_date = last_stats_time + timedelta(days=1)
                    _LOGGER.debug(
                        "Fetching data from %s (day after last recorded: %s)",
                        start_date.strftime("%m/%d/%Y"),
                        last_stats_time.strftime("%m/%d/%Y"),
                    )
            else:
                # If no previous data, start from available start date
                start_date = available_start
                _LOGGER.info(
                    "No previous data found, starting from available start date: %s",
                    start_date.strftime("%m/%d/%Y"),
                )

            # Use available end date, but don't go beyond today
            today = dt_util.now().replace(hour=0, minute=0, second=0, microsecond=0)

            # Ensure both datetimes are timezone-aware for comparison
            if available_end.tzinfo is None:
                available_end = dt_util.as_utc(available_end)
            if today.tzinfo is None:
                today = dt_util.as_utc(today)

            end_date = min(available_end, today)

            # Check if we have any new data to fetch
            # Convert start_date to UTC for comparison if needed
            start_date_utc = start_date
            if start_date.tzinfo is None:
                start_date_utc = dt_util.as_utc(start_date)

            if start_date_utc.date() > end_date.date():
                _LOGGER.info(
                    "No new data to fetch (start %s > end %s). Data is up to date.",
                    start_date.strftime("%m/%d/%Y"),
                    end_date.strftime("%m/%d/%Y"),
                )
                self._last_successful_fetch = True
                self.last_update_time = dt_util.now()
                # Don't reset latest_usage/total_usage - keep previous values
                return self.data or {}

            # Download new usage data
            _LOGGER.info(
                "Fetching data from %s to %s",
                start_date.strftime("%m/%d/%Y"),
                end_date.strftime("%m/%d/%Y"),
            )
            parsed_data = await self.hass.async_add_executor_job(
                download_usage_for_multiple_days,
                session,
                start_date.strftime("%m/%d/%Y"),
                end_date.strftime("%m/%d/%Y"),
            )

            if parsed_data:
                _LOGGER.info("Successfully fetched %d new data points", len(parsed_data))

                # Update coordinator data for sensor entities
                self.latest_usage = max(parsed_data.values()) if parsed_data else 0.0
                self.total_usage = sum(parsed_data.values()) if parsed_data else 0.0

                # Insert the new data into statistics
                await self._insert_statistics(parsed_data, last_stats_time, last_sum)
                _LOGGER.info("Data inserted into statistics")
            else:
                _LOGGER.info("No new data available from SFPUC")
                # Don't reset values when no new data

            self._last_successful_fetch = True
            self.last_update_time = dt_util.now()
            return parsed_data or {}

        except Exception as err:
            _LOGGER.exception("Error fetching data from SFPUC")
            self._last_successful_fetch = False
            self.last_update_time = dt_util.now()
            raise UpdateFailed(f"Error fetching data: {err}") from err

    async def _get_last_statistics(self) -> tuple[datetime | None, float]:
        """Get the last recorded timestamp and sum from Home Assistant statistics.

        Returns:
            Tuple of (last_timestamp, last_sum) or (None, 0.0) if no data exists.
        """
        consumption_statistic_id = f"{DOMAIN}:sfpuc_water_usage"
        last_stat = await get_instance(self.hass).async_add_executor_job(
            get_last_statistics, self.hass, 1, consumption_statistic_id, True, set()
        )

        if last_stat and consumption_statistic_id in last_stat:
            stat_data = last_stat[consumption_statistic_id][0]
            last_stats_time = dt_util.utc_from_timestamp(stat_data["start"])
            last_sum = stat_data.get("sum", 0.0)

            # Validate sum is not negative
            if last_sum is None or last_sum < 0:
                _LOGGER.warning(
                    "Last sum was negative or invalid (%s), will start from 0",
                    last_sum,
                )
                last_sum = 0.0

            _LOGGER.debug("Last recorded: time=%s, sum=%s", last_stats_time, last_sum)
            return last_stats_time, last_sum

        return None, 0.0

    async def _insert_statistics(
        self,
        data: dict[datetime, float],
        last_stats_time: datetime | None,
        last_sum: float,
    ) -> None:
        """Insert SFPUC water usage statistics into Home Assistant's recorder.

        Args:
            data: Dictionary mapping timestamps to consumption values.
            last_stats_time: The timestamp of the last recorded statistic.
            last_sum: The cumulative sum from the last recorded statistic.
        """
        consumption_statistic_id = f"{DOMAIN}:sfpuc_water_usage"
        _LOGGER.debug("Updating statistics for %s", consumption_statistic_id)

        consumption_sum = last_sum
        consumption_statistics = []

        # Sort data by timestamp to ensure correct order
        sorted_data = sorted(data.items(), key=lambda x: x[0])

        for timestamp, consumption in sorted_data:
            # Ensure the timestamp is timezone-aware, convert it to UTC if necessary
            if timestamp.tzinfo is None or timestamp.tzinfo.utcoffset(timestamp) is None:
                timestamp = dt_util.as_utc(timestamp)

            # Skip if we already have this data point (prevent duplicates)
            if last_stats_time and timestamp <= last_stats_time:
                _LOGGER.debug("Skipping duplicate data point: %s", timestamp)
                continue

            # Validate consumption is non-negative
            if consumption < 0:
                _LOGGER.warning(
                    "Skipping negative consumption value: %s at %s",
                    consumption,
                    timestamp,
                )
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
            _LOGGER.debug("No new statistics to add")
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
            "Adding %d new statistics for %s (sum: %.2f)",
            len(consumption_statistics),
            consumption_statistic_id,
            consumption_sum,
        )
        async_add_external_statistics(
            self.hass, consumption_metadata, consumption_statistics
        )
