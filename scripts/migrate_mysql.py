"""Copy the three app tables from local MySQL into an EMPTY Neon database.

Run locally: uv run --group migration python scripts/migrate_mysql.py
The source database is read-only. Target inserts are one transaction.
"""

from getpass import getpass
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import mysql.connector
from database import connect_url


TABLES = {
    "staff_users": ("staff_id", "username", "password_hash", "role"),
    "student_roster": ("student_no", "student_name", "grade", "section", "is_active"),
    "late_arrivals": (
        "arrival_id", "student_name", "grade", "section", "arrival_time", "recorded_by"
    ),
}


def main():
    url = os.environ.get("DATABASE_URL") or getpass("Neon direct DATABASE_URL: ")
    mysql_password = os.environ.get("MYSQL_PASSWORD")
    if mysql_password is None:
        mysql_password = getpass("Local MySQL password: ")
    source = mysql.connector.connect(
        host=os.environ.get("MYSQL_HOST", "localhost"),
        port=int(os.environ.get("MYSQL_PORT", "3306")),
        user=os.environ.get("MYSQL_USER", "root"),
        password=mysql_password,
        database=os.environ.get("MYSQL_DATABASE", "latetrack"),
    )
    target = None
    try:
        target = connect_url(url)
        out = target.cursor()
        # Check all target tables before writing anything, never overwrite data.
        for table in TABLES:
            out.execute(f"SELECT COUNT(*) FROM {table}")
            if out.fetchone()[0]:
                raise RuntimeError(f"{table} is not empty. Import aborted without changes.")
        source.start_transaction(consistent_snapshot=True, readonly=True)
        counts = {}
        for table, columns in TABLES.items():
            incoming = source.cursor()
            incoming.execute(f"SELECT {', '.join(columns)} FROM {table}")
            count = 0
            while rows := incoming.fetchmany(500):
                converted = []
                for row in rows:
                    values = list(row)
                    if table == "student_roster":
                        values[0] = str(values[0])
                        values[2] = str(values[2])
                        values[3] = str(values[3])
                        values[4] = bool(values[4])
                    elif table == "late_arrivals":
                        values[2] = str(values[2])
                        values[3] = str(values[3])
                    converted.append(tuple(values))
                out.executemany(
                    f"INSERT INTO {table} ({', '.join(columns)}) "
                    f"VALUES ({', '.join(['%s'] * len(columns))})", converted,
                )
                count += len(rows)
            incoming.close()
            counts[table] = count
        # IDs were preserved so reseed the identity sequences for future inserts.
        for table, column in (("staff_users", "staff_id"), ("late_arrivals", "arrival_id")):
            out.execute(
                f"SELECT setval(pg_get_serial_sequence('{table}', '{column}'), "
                f"COALESCE(MAX({column}), 1), COUNT(*) > 0) FROM {table}"
            )
        for table, expected in counts.items():
            out.execute(f"SELECT COUNT(*) FROM {table}")
            if out.fetchone()[0] != expected:
                raise RuntimeError("Row count verification failed; rolling back.")
        target.commit()
        out.close()
        for table, count in counts.items():
            print(f"Imported {count} rows into {table}.")
    except Exception:
        if target is not None:
            target.rollback()
        raise
    finally:
        source.rollback()
        source.close()
        if target is not None:
            target.close()


if __name__ == "__main__":
    main()
