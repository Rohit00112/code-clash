#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   ./scripts/restore_postgres.sh /path/to/backup.dump postgres user db

if [[ $# -lt 4 ]]; then
  echo "Usage: $0 <backup.dump> <host> <user> <db>"
  exit 1
fi

backup_file="$1"
db_host="$2"
db_user="$3"
db_name="$4"

if [[ ! -f "$backup_file" ]]; then
  echo "Backup file not found: $backup_file"
  exit 1
fi

echo "Restoring $backup_file into $db_name on $db_host ..."
pg_restore -h "$db_host" -U "$db_user" -d "$db_name" --clean --if-exists "$backup_file"
echo "Restore complete."
