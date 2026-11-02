# Free Render deployment with existing Neon database

1. Merge this change into `main`.
2. In https://dashboard.render.com choose **New → Blueprint**, connect
   `kazifire02/Dunes-TimeWise`, and select `main`.
3. Render reads `render.yaml`. Confirm the service uses the **Free** plan.
4. When prompted for `DATABASE_URL_POOLED`, paste your existing Neon pooled
   PostgreSQL connection string. Do not put it in GitHub.
5. Click **Deploy Blueprint**. Open the service's `onrender.com` URL when ready.

The Blueprint generates a strong `LATETRACK_SECRET_KEY` automatically. This is
for session cookies, not the admin password. Your existing Neon accounts and
attendance data remain available; no database migration or new database is needed.

Render runs native Python and Gunicorn, so password verification uses OpenSSL
instead of the Workers WebAssembly fallback. Hyperdrive and Wrangler are not used.
The web service sleeps after 15 idle minutes; waking it can take about one minute.
Local files are ephemeral, while application records remain in Neon.

For manual **New → Web Service** setup instead:

- Runtime: Python 3; branch: main; instance: Free
- Build: `pip install -r requirements.txt`
- Start: `gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 120 wsgi:app`
- Environment: `PYTHON_VERSION=3.13.5`, `DATABASE_URL_POOLED` with your Neon URL,
  and `LATETRACK_SECRET_KEY` with a long random secret.

Reference: https://render.com/docs/deploy-flask and https://render.com/docs/free
