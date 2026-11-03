import csv


def load(path):
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def total(rows):
    return sum(int(row["n"]) for row in rows)
