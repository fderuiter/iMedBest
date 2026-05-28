#!/bin/bash
set -e

echo "[$(date)] Starting daily database backup..."
python src/manage.py backup_db
echo "[$(date)] Backup completed successfully."
