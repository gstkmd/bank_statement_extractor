from src.database import db

class AnonymizerMapping(db.Model):
    __tablename__ = 'anonymizer_mapping'
    original_text = db.Column(db.String(500), primary_key=True)
    fake_text = db.Column(db.String(500), nullable=False)

class TrialConfig(db.Model):
    __tablename__ = 'trial_config'
    id = db.Column(db.Integer, primary_key=True)
    machine_id = db.Column(db.String(100), nullable=False)
    first_run_date = db.Column(db.String(100), nullable=False)
    ocr_scan_count = db.Column(db.Integer, default=0)
