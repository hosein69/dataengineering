import logging
import traceback
from .store import Warehouse
class WarehouseHandler(logging.Handler):
    def emit(self,record):
        # Failure must propagate: never pretend an unaudited operation succeeded.
        Warehouse().audit('runtime_log',{'level':record.levelname,'message':record.getMessage(),'exception':''.join(traceback.format_exception(*record.exc_info)) if record.exc_info else None},actor=record.name)
