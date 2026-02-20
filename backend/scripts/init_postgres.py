"""
Create PostgreSQL database for Code Clash.
Run once before starting the app: python scripts/init_postgres.py

Requires: PostgreSQL installed and running. Create user and database:

  sudo -u postgres psql
  CREATE USER codeclash WITH PASSWORD 'codeclash';
  CREATE DATABASE codeclash_db OWNER codeclash;
  GRANT ALL PRIVILEGES ON DATABASE codeclash_db TO codeclash;
  \q
"""

import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, text
from app.config import settings

def main():
    url = settings.DATABASE_URL
    if not url.startswith("postgresql"):
        print("DATABASE_URL is not PostgreSQL. Skipping.")
        return
    try:
        engine = create_engine(url)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("PostgreSQL connection OK. Database exists.")
    except Exception as e:
        print(f"Cannot connect to PostgreSQL: {e}")
        print("\nCreate database first:")
        print("  psql -U postgres -c \"CREATE USER codeclash WITH PASSWORD 'codeclash';\"")
        print("  psql -U postgres -c \"CREATE DATABASE codeclash_db OWNER codeclash;\"")
        print("  psql -U postgres -c \"GRANT ALL PRIVILEGES ON DATABASE codeclash_db TO codeclash;\"")
        sys.exit(1)

if __name__ == "__main__":
    main()
