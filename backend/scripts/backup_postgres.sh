#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   DATABASE_URL=postgresql://user:pass@host:5432/db ./scripts/backup_postgres.sh
# or
#   ./scripts/backup_postgres.sh postgres user db /path/to/backups

timestamp="$(date +%Y%m%d_%H%M%S)"

if [[ $# -ge 4 ]]; then
  db_host="$1"
  db_user="$2"
  db_name="$3"
  backup_dir="$4"
  mkdir -p "$backup_dir"
  out_file="$backup_dir/${db_name}_${timestamp}.dump"
  pg_dump -h "$db_host" -U "$db_user" -Fc "$db_name" -f "$out_file"
  echo "Backup written: $out_file"
  exit 0
fi

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "Provide DATABASE_URL or args: <host> <user> <db> <backup_dir>"
  exit 1
fi

backup_dir="${BACKUP_DIR:-./backups}"
mkdir -p "$backup_dir"
out_file="$backup_dir/codeclash_${timestamp}.dump"

pg_dump "$DATABASE_URL" -Fc -f "$out_file"
echo "Backup written: $out_file"
