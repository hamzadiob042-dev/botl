from utils import load, total
rows = load("data.csv")
print("rows:", len(rows), "total:", total(rows))
