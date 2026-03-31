import os

SECRET_KEY = os.environ.get("BANK_SECRET_KEY", "dev-secret-key-change-in-prod")

DB_CONFIG = {
    "host":     os.environ.get("DB_HOST", "localhost"),
    "user":     os.environ.get("DB_USER", "root"),
    "password": os.environ.get("DB_PASSWORD", ""),
    "database": os.environ.get("DB_NAME", "banking_db"),
    "autocommit": False,
}
