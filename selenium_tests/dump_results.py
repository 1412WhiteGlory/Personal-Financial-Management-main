import openpyxl, glob, os

f = max(glob.glob('reports/selenium_test_report_*.xlsx'), key=os.path.getctime)
print(f"Reading: {f}")
wb = openpyxl.load_workbook(f)
ws = wb['Detailed Results']

with open('results_dump.txt', 'w', encoding='utf-8') as out:
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row[1]:
            actual = str(row[6])[:120] if row[6] else ""
            err = str(row[7])[:120] if row[7] else ""
            out.write(f"{row[1]} | {row[5]} | {actual} | {err}\n")

print("Done. See results_dump.txt")
