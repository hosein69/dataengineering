"""Local SQLite warehouse. No network database and no silent logging fallback."""
from .store import Warehouse

# Historical V26.17/18 store is intentionally not imported here: logging_setup
# imports gsi.warehouse.log_sink during package initialization, so eager import
# would create a circular dependency. Use gsi.warehouse.historical_store directly.
