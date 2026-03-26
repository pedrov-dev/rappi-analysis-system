import pandas as pd

metrics = pd.read_csv("data/METRICS.csv")
orders = pd.read_csv("data/ORDERS.csv")
summary = pd.read_csv("data/SUMMARY.csv")

if metrics is not None and orders is not None and summary is not None:
    print("Successfully loaded data: METRICS, ORDERS, SUMMARY")
else:
    print("Error loading data. Please check the file paths and formats.")