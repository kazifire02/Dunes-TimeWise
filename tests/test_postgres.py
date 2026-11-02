"""Integration tests against a disposable PostgreSQL database, never Neon."""

from datetime import datetime
from io import BytesIO
import os
from pathlib import Path

from openpyxl import load_workbook
import pytest
from werkzeug.security import generate_password_hash

import app as application
from database import connect_url, dict_cursor


@pytest.fixture()
def client(monkeypatch):
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to a disposable local PostgreSQL database.")
    assert "timewise_test" in url, "Use the disposable timewise_test database."
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.delenv("DATABASE_URL_POOLED", raising=False)
    connection = connect_url(url)
    connection.autocommit = True
    cursor = connection.cursor()
    cursor.execute(Path("schema.sql").read_text())
    cursor.execute("TRUNCATE late_arrivals, student_roster, staff_users RESTART IDENTITY")
    cursor.execute(
        "INSERT INTO staff_users (username, password_hash, role) VALUES (%s, %s, 'admin')",
        ("Admin", generate_password_hash("test-password-123", method="pbkdf2:sha256:1000")),
    )
    cursor.close()
    connection.close()
    application.app.config.update(TESTING=True, SECRET_KEY="integration-test-key")

    class SchoolMorning(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 11, 2, 8, 30, tzinfo=tz)

    monkeypatch.setattr(application, "datetime", SchoolMorning)
    with application.app.test_client() as client:
        yield client


def login(client):
    response = client.post("/login", data={"username": "admin", "password": "test-password-123"})
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/dashboard")


def admit(client, number="001", name="Alice Example"):
    response = client.post("/new-admission", data={
        "student_no": number, "student_name": name, "grade": "5", "section": "A",
    })
    assert response.status_code == 302


def test_login_and_case_insensitive_student_search(client):
    assert client.get("/dashboard").status_code == 302
    login(client)
    admit(client)
    result = client.get("/api/student-search?q=ALICE").get_json()
    assert result[0]["student_no"] == "001"
    assert result[0]["student_name"] == "Alice Example"
    assert client.get("/api/student-search?q=%27%20OR%201%3D1--").get_json() == []
    assert client.get("/api/roster?grade=5&section=A").get_json()[0]["student_no"] == "001"


def test_registration_reports_exports_and_removal(client):
    login(client)
    admit(client)
    assert client.post("/", data={"student_no": "001"}).status_code == 302
    assert client.post("/", data={"student_no": "001"}).status_code == 302
    connection = application.get_connection()
    cursor = dict_cursor(connection)
    cursor.execute("SELECT COUNT(*) AS total FROM late_arrivals")
    assert cursor.fetchone() == {"total": 1}
    cursor.execute("SELECT arrival_time FROM late_arrivals")
    assert cursor.fetchone()["arrival_time"].hour == 8
    cursor.close()
    connection.close()
    for path in (
        "/", "/dashboard", "/reports?date=2026-11-02", "/notifications",
        "/student-history?grade=5&section=A&student_no=001", "/analytics",
        "/new-admission", "/remove-student?student_no=001",
    ):
        assert client.get(path).status_code == 200, path
    for path in ("/export?date=2026-11-02", "/analytics/export"):
        response = client.get(path)
        assert response.status_code == 200, path
        workbook = load_workbook(BytesIO(response.data))
        assert any("Alice Example" == cell.value for sheet in workbook for row in sheet for cell in row)
    assert client.post("/remove-student", data={"student_no": "001"}).status_code == 302
    assert client.get("/api/student-search?q=Alice").get_json() == []
    assert b"Alice Example" in client.get("/student-history").data


def test_failed_login_cannot_write(client):
    response = client.post("/login", data={"username": "admin", "password": "wrong"})
    assert response.status_code == 200
    assert client.post("/new-admission", data={}).status_code == 302


def test_schema_is_idempotent(client):
    connection = application.get_connection()
    connection.autocommit = True
    cursor = connection.cursor()
    cursor.execute(Path("schema.sql").read_text())
    cursor.execute("SELECT COUNT(*) FROM staff_users")
    assert cursor.fetchone()[0] == 1
    cursor.close()
    connection.close()
