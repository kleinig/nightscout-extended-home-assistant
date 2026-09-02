"""Constants for Nightscout AAPS."""
from datetime import timedelta

DOMAIN = "nightscout_aaps"
NAME = "Nightscout AAPS"

CONF_URL = "url"
CONF_CARTRIDGE_CAPACITY = "cartridge_capacity"
CONF_DAILY_USAGE = "daily_usage"
CONF_HISTORY_DAYS = "history_days"
CONF_RESERVOIR_WARNING = "reservoir_warning"
CONF_RESERVOIR_CRITICAL = "reservoir_critical"
CONF_PUMP_BATTERY_WARNING = "pump_battery_warning"
CONF_PHONE_BATTERY_WARNING = "phone_battery_warning"

DEFAULT_CARTRIDGE_CAPACITY = 300.0
DEFAULT_DAILY_USAGE = 40.0
DEFAULT_HISTORY_DAYS = 7
DEFAULT_RESERVOIR_WARNING = 80.0
DEFAULT_RESERVOIR_CRITICAL = 10.0
DEFAULT_PUMP_BATTERY_WARNING = 25.0
DEFAULT_PHONE_BATTERY_WARNING = 25.0

UPDATE_INTERVAL = timedelta(minutes=1)
API_TIMEOUT = 15

ATTRIBUTION = "Data provided by Nightscout"
