"""One-time database setup; credentials are read from the environment or prompts."""

import argparse
from getpass import getpass
import os
from pathlib import Path

from werkzeug.security import generate_password_hash

from database import connect_url


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["init-db", "create-admin", "admin-sql"])
    parser.add_argument("--username", default="admin")
    args = parser.parse_args()

    if args.command in {"create-admin", "admin-sql"}:
        password = getpass("New admin password: ")
        if len(password) < 12:
            parser.error("Choose a password with at least 12 characters.")
        if password != getpass("Confirm password: "):
            parser.error("Passwords did not match.")
        hashed = generate_password_hash(password, method="pbkdf2:sha256:1000000")
        if args.command == "admin-sql":
            username_sql = args.username.replace("'", "''")
            print("INSERT INTO staff_users (username, password_hash, role) VALUES "
                  f"('{username_sql}', '{hashed}', 'admin');")
            return

    url = os.environ.get("DATABASE_URL") or getpass("Neon direct DATABASE_URL: ")
    connection = connect_url(url)
    try:
        cursor = connection.cursor()
        if args.command == "init-db":
            # schema.sql contains its own atomic transaction.
            connection.autocommit = True
            cursor.execute(Path(__file__).with_name("schema.sql").read_text())
        else:
            cursor.execute(
                "INSERT INTO staff_users (username, password_hash, role) "
                "VALUES (%s, %s, 'admin')", (args.username, hashed),
            )
            connection.commit()
        cursor.close()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    print("Schema ready." if args.command == "init-db" else "Admin account created.")


if __name__ == "__main__":
    main()
