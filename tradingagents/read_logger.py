import os
import json
import logging
import datetime

LOG = logging.getLogger("alpha.read_logger")

DOSSIER_DIR = r"C:\Trading\Alpha\logs"
READ_AUDIT_LOG_PATH = os.path.join(DOSSIER_DIR, "dossier_read_audit.log")

class DossierReadLogger:
    """
    Mandatory Audit Logger that records timestamped audit trails whenever
    the OpenCode Executive Trader or the System reads and evaluates the persistent dossier.
    """
    def __init__(self):
        os.makedirs(DOSSIER_DIR, exist_ok=True)

    def log_dossier_read(self, reader_name: str, action: str, details: str = "") -> str:
        """
        Records a mandatory audit log entry in dossier_read_audit.log.
        """
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = f"[{now_str}] MANDATORY READ AUDIT | Reader: {reader_name} | Action: {action} | Details: {details}\n"
        
        try:
            with open(READ_AUDIT_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(entry)
            LOG.info(f"MANDATORY READ LOGGED: {reader_name} -> {action}")
        except Exception as err:
            LOG.error(f"Failed to record dossier read audit log: {err}")

        return entry
