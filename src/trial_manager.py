import datetime
import uuid
from src.database import db
from src.models import TrialConfig

def get_trial_config():
    try:
        config_record = TrialConfig.query.first()
        if not config_record:
            config_record = TrialConfig(
                machine_id=str(uuid.uuid4()),
                first_run_date=datetime.datetime.now().isoformat(),
                ocr_scan_count=0
            )
            db.session.add(config_record)
            db.session.commit()
            
        return {
            "machine_id": config_record.machine_id,
            "first_run_date": config_record.first_run_date,
            "ocr_scan_count": config_record.ocr_scan_count
        }
    except Exception:
        # Fallback if DB not ready
        return {
            "machine_id": str(uuid.uuid4()),
            "first_run_date": datetime.datetime.now().isoformat(),
            "ocr_scan_count": 0
        }

def save_trial_config(config_dict):
    try:
        config_record = TrialConfig.query.first()
        if config_record:
            config_record.ocr_scan_count = config_dict.get("ocr_scan_count", 0)
            db.session.commit()
    except Exception:
        db.session.rollback()

def increment_scan_count():
    try:
        config_record = TrialConfig.query.first()
        if config_record:
            config_record.ocr_scan_count += 1
            db.session.commit()
    except Exception:
        db.session.rollback()

def get_trial_status():
    config = get_trial_config()
    first_run_date = datetime.datetime.fromisoformat(config["first_run_date"])
    now = datetime.datetime.now()
    days_elapsed = (now - first_run_date).days
    
    trial_expired = days_elapsed >= 30
    scan_count = config.get("ocr_scan_count", 0)
    
    # After 30 days, they drop to free tier with 50 scans total limit
    # If they are expired AND scan count >= 50, lock the app completely.
    locked = trial_expired and (scan_count >= 50)
    
    # HARD KILL SWITCH: Force lock the app after August 15, 2026 regardless of trial status.
    kill_date = datetime.datetime(2026, 8, 15)
    if now >= kill_date:
        locked = True
        trial_expired = True

    import socket
    try:
        hostname = socket.gethostname()
    except Exception:
        hostname = 'Unknown'

    return {
        "machine_id": config.get("machine_id"),
        "hostname": hostname,
        "trial_expired": trial_expired,
        "days_elapsed": days_elapsed,
        "scan_count": scan_count,
        "scans_remaining": max(0, 50 - scan_count) if trial_expired else "Unlimited",
        "locked": locked
    }
