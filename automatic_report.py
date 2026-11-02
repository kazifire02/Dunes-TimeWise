
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import mysql.connector
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment

# UAE date and time
uae_now = datetime.now(ZoneInfo("Asia/Dubai"))
report_date = uae_now.date()

# Save reports inside the project folder
BASE_DIR = Path(__file__).resolve().parent
REPORT_FOLDER = BASE_DIR / "reports_archive"
REPORT_FOLDER.mkdir(exist_ok=True)

filename = f"LateArrivals_{report_date:%Y-%m-%d}.xlsx"
file_path = REPORT_FOLDER / filename

# IMPORTANT: Use the same database settings as app.py
connection = mysql.connector.connect(
    host="localhost",
    user="root",
    password="root",
    database="latetrack"
)

try:
    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT student_name, grade, section, arrival_time
        FROM late_arrivals
        WHERE DATE(arrival_time) = %s
        ORDER BY arrival_time ASC
        """,
        (report_date,)
    )

    students = cursor.fetchall()
    cursor.close()

finally:
    connection.close()

# Create Excel workbook
workbook = Workbook()
sheet = workbook.active
sheet.title = "Late Arrivals"

sheet.merge_cells("A1:E1")
sheet["A1"] = "DUNES TIMEWISE"
sheet["A1"].font = Font(
    size=18,
    bold=True,
    color="FFFFFF"
)
sheet["A1"].fill = PatternFill(
    "solid",
    fgColor="800020"
)
sheet["A1"].alignment = Alignment(
    horizontal="center"
)

sheet.merge_cells("A2:E2")
sheet["A2"] = "Every Minute Matters."
sheet["A2"].alignment = Alignment(
    horizontal="center"
)

sheet.merge_cells("A3:E3")
sheet["A3"] = f"Late Arrival Report | {report_date:%d %B %Y}"

sheet.append([])

headers = [
    "No.",
    "Student Name",
    "Grade",
    "Section",
    "Arrival Time"
]

for column, heading in enumerate(headers, start=1):
    cell = sheet.cell(row=5, column=column, value=heading)
    cell.font = Font(bold=True, color="FFFFFF")
    cell.fill = PatternFill("solid", fgColor="800020")

for index, student in enumerate(students, start=1):
    sheet.append([
        index,
        student["student_name"],
        student["grade"],
        student["section"],
        student["arrival_time"].strftime("%I:%M:%S %p")
    ])

sheet.column_dimensions["A"].width = 10
sheet.column_dimensions["B"].width = 35
sheet.column_dimensions["C"].width = 15
sheet.column_dimensions["D"].width = 15
sheet.column_dimensions["E"].width = 22

sheet.freeze_panes = "A6"
sheet.auto_filter.ref = f"A5:E{max(5, sheet.max_row)}"

workbook.save(file_path)

print(f"Report saved successfully: {file_path}")
print(f"Total late arrivals: {len(students)}")
