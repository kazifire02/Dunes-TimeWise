# Dunes TimeWise — Neon PostgreSQL + Cloudflare Workers

This version replaces local MySQL with persistent Neon PostgreSQL. The Cloudflare
Worker connects to Neon through Hyperdrive. No tunnel or local database server is
needed after your existing data has been imported.

Your database password belongs in Neon/Cloudflare secrets, never in this repository.
Rotate the database password previously shared in chat before configuring deployment.

## 1. Create the tables in Neon

Open your Neon project → SQL Editor. Select your intended branch and `neondb`,
paste `schema.sql`, and run it. This creates the three tables used by the app and
their indexes. It can be run again without deleting rows.

Arrival times remain Dubai local timestamps, preserving the original app's reports.
Admission numbers and grades are stored as text, including leading zeroes and KG grades.

## 2. Import existing data OR create a new admin

### Keep your existing MySQL users, roster, and attendance

Back up your local MySQL database first. Pause writes in the old app while importing.
Do this before creating an admin in Neon: the importer requires all three target
tables to be empty and refuses to overwrite existing records.

On the computer that can reach MySQL, install uv (https://docs.astral.sh/uv/),
open a terminal in this project folder, and run:

```sh
uv sync --locked --group migration
uv run --group migration python scripts/migrate_mysql.py
```

The script privately prompts for your **new direct Neon connection URL** and local
MySQL password. Defaults are MySQL `localhost:3306`, user `root`, database `latetrack`.
Set `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, or `MYSQL_DATABASE` in your shell if needed.
It reads a consistent snapshot, preserves IDs and password hashes, copies the app's
columns in batches, checks target row counts, and commits all target rows together.
On failure, target inserts roll back. The source is read-only.

The repository does not include the source MySQL schema. The importer expects the
columns in `TABLES` inside `scripts/migrate_mysql.py`; any extra source-only columns
are not copied. Run an import on a separate Neon branch first if your local schema
has been customized. A raw MySQL SQL dump cannot be pasted into PostgreSQL unchanged.

After checking the imported roster and history in the new app, use Neon as the live
database. Keep the MySQL backup; switching back to the old app later would require
copying any new attendance records back first.

### Start with an empty database

Open `setup-admin.html` locally in a modern browser. Enter a username and a password.
Copy the generated INSERT statement into Neon's SQL Editor and run it once.
The utility works offline and sends no credentials anywhere. The SQL contains a
Werkzeug-compatible password hash, not the plaintext password.

Alternatively, `uv run python manage.py admin-sql` prints the same kind of SQL after
prompting for a password. Use the app's **New Student Admission** page to add students.

## 3. Connect Hyperdrive to Neon from the Cloudflare dashboard

1. In Neon, choose **Connect**, turn **Connection pooling off**, and copy the new
   connection details. Hyperdrive uses the **direct** hostname, without `-pooler`.
2. In Cloudflare, open **Storage & Databases → Hyperdrive → Create configuration**.
3. Choose a public PostgreSQL database and enter the direct Neon host, port `5432`,
   database `neondb`, your database username, and the rotated password. Require TLS.
4. Turn query caching **off** for this configuration so logins, attendance checks,
   and reports read current data.
5. Save and copy the Hyperdrive configuration ID.
6. In `wrangler.jsonc`, uncomment the `hyperdrive` line and replace
   `YOUR_HYPERDRIVE_ID` with that ID. It is a resource ID, not a secret.

This repository deliberately contains no account ID, database password, or personal
Hyperdrive ID. Dashboard-only bindings may be overwritten by a later code deployment;
keep the binding in `wrangler.jsonc` so it persists across Git builds.

## 4. Deploy or update your existing Worker

Upload this project's files into your GitHub repository, replacing `app.py` and
`automatic_report.py` and adding the new files. Keep `templates/` and `static/`.
There is no need to upload the old executable, Excel reports, or `__pycache__`.

In Cloudflare → **Workers & Pages → your Worker → Settings → Builds**, connect the
repository if necessary and set:

| Setting | Value |
| --- | --- |
| Production branch | `main` |
| Root directory | Repository root |
| Build command | `uv sync --locked` |
| Deploy command | `uv run pywrangler deploy` |

The name in `wrangler.jsonc` must match your existing Worker's name. The example
uses `dunes-timewise`; change it if your Worker has another name.

In the Worker's **Settings → Variables and Secrets**, add an encrypted runtime
secret named `LATETRACK_SECRET_KEY`. Use a stable random value, not your database
password. You can generate one locally with:

```sh
uv run python -c 'import secrets; print(secrets.token_hex(32))'
```

Save/deploy the secret and retry the Git build. Check the Worker has both `ASSETS`
and `HYPERDRIVE` bindings. The production Worker obtains database credentials from
Hyperdrive; it does not need your `DATABASE_URL` strings as additional runtime secrets.
If configuring non-production branch builds, use a separate Neon branch/Hyperdrive
configuration to keep preview writes out of the live database.

The build bundles the nine Jinja templates into Python source and copies only the
CSS/logo into public assets. Generated `src/`, `public/`, and dependency folders are
ignored by Git and rebuilt automatically. The offline admin utility and database
scripts are excluded from the deployed Worker.

Wrangler's configured build hook also runs `pywrangler sync --force` to install
the Python runtime packages into `python_modules/` and verifies those packages
before upload. This hook runs even when Cloudflare uses its default
`npx wrangler deploy` command. Installing packages only into the native `.venv`
does not make them available to the deployed Python Worker.

## 5. Check the deployment

Open the Worker URL, sign in with an imported account or the new admin, and check
the roster. Register a late arrival after 7:40 AM Dubai time on a weekday. Refresh
the dashboard, then download a daily report and an analytics report. Removal makes
a student inactive while keeping their arrival history.

If you get a database error, check the Hyperdrive connection test, selected Neon
branch/database, imported tables, and binding name. The Worker is configured for
Python compatibility date `2026-11-02`. The tested driver is `pg8000`; direct Neon
TLS from the Python Worker was unreliable in validation, so production should use
the Hyperdrive binding. Local Flask and import scripts can use verified direct TLS.

Strong password verification can exceed the Workers Free CPU allowance. If logs
show CPU limit error 1102, use Workers Paid with sufficient CPU allowance rather
than weakening existing password hashes.

## Local Flask and reports

For local Flask, set `DATABASE_URL_POOLED` and `LATETRACK_SECRET_KEY` in your shell,
then run `uv run python app.py`. `.env.example` documents the variable names;
it is not automatically loaded. The pooled URL is preferred for local app traffic,
while `DATABASE_URL` (direct) is used for administrative scripts and migration.

`uv run python automatic_report.py` uses PostgreSQL and writes a workbook into
`reports_archive/` locally. It is not automatically scheduled on Cloudflare, and a
Worker filesystem is not durable report storage. The web Excel exports stream
downloads directly and work without a persistent filesystem.

## Validation

Integration tests run against a disposable PostgreSQL database, named `timewise_test`:

```sh
TEST_DATABASE_URL='postgresql://postgres@127.0.0.1:55432/timewise_test?sslmode=disable' uv run python -m pytest -q
```

The integration fixture truncates these three tables in the test database.
Never point it at a database containing real records. Checks cover case-insensitive
login/search, roster changes, duplicate arrival detection, dashboard/history/analytics,
both Excel exports, idempotent schema creation, and Worker password-hashing fallbacks.
The same flows were also exercised through the actual local Cloudflare runtime.
The package was built with `uv run pywrangler deploy --dry-run` (about 2.1 MiB gzip).

Connection credentials are configured separately from source code. Initializing
this schema does not import your local MySQL data or create a default login.

References: [Python Workers + Hyperdrive](https://developers.cloudflare.com/hyperdrive/examples/python-workers/),
[Neon + Hyperdrive](https://developers.cloudflare.com/hyperdrive/examples/connect-to-postgres/postgres-database-providers/neon/),
[Workers Builds](https://developers.cloudflare.com/workers/ci-cd/builds/),
[Hyperdrive caching](https://developers.cloudflare.com/hyperdrive/concepts/query-caching/).
