import csv
from datetime import datetime
from collections import OrderedDict

rows = []
with open('loto_ci_raw.csv', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for r in reader:
        rows.append(r)

print("Total raw rows:", len(rows))

# Dedupe on Date+Jeu, keep first occurrence
seen = OrderedDict()
dups = 0
for r in rows:
    key = (r['Date'], r['Jeu'])
    if key in seen:
        dups += 1
    else:
        seen[key] = r

print("Duplicate rows found:", dups)
final_rows = list(seen.values())
print("Final row count:", len(final_rows))

# parse date for sorting
def parse_date(d):
    return datetime.strptime(d, '%d/%m/%Y')

final_rows.sort(key=lambda r: parse_date(r['Date']), reverse=True)

dates = [parse_date(r['Date']) for r in final_rows]
oldest = min(dates)
newest = max(dates)
print("Oldest date:", oldest.strftime('%d/%m/%Y'))
print("Newest date:", newest.strftime('%d/%m/%Y'))

games = set(r['Jeu'] for r in final_rows)
print("Distinct games:", len(games))
print(sorted(games))

# check for any weird jeu = "-"
bad = [r for r in final_rows if r['Jeu'].strip() == '-' or r['Jeu'].strip() == '']
print("Bad placeholder rows:", len(bad))

# Save deduped/sorted csv for xlsx build step
with open('loto_ci_final.csv', 'w', encoding='utf-8', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=['Date','Jour','Jeu','Numeros','Machine'])
    writer.writeheader()
    writer.writerows(final_rows)
