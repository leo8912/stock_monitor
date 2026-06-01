import os

import mplfinance as mpf
import pandas as pd
import yfinance as yf

# Fetch data for Fuling Electric Power
df = yf.download("600452.SS", start="2023-10-01")

if isinstance(df.columns, pd.MultiIndex):
    df.columns = df.columns.get_level_values(0)

# Format index for mplfinance
df.index = pd.to_datetime(df.index)

# Target recent 60 days
df_plot = df.tail(60)

# Output directory within artifacts
out_dir = r"C:\Users\leo89\.gemini\antigravity-ide\brain\b834177c-eb63-4be2-97da-5bb29fbac8d9\scratch"
os.makedirs(out_dir, exist_ok=True)
out_file = os.path.join(out_dir, "chart_600452.png")

# Draw K-Line with Fibonacci Lines
# 14.08 (High), 13.80 (0.236), 13.63 (0.382), 13.35 (0.618), 12.90 (Low)
hlines = {
    "hlines": [14.08, 13.80, 13.63, 13.35, 12.90],
    "colors": ["red", "orange", "yellow", "green", "blue"],
    "linestyle": "--",
    "linewidths": 1,
}

mpf.plot(
    df_plot,
    type="candle",
    style="yahoo",
    title="Fuling Electric (600452) K-Line & Fibonacci Support",
    hlines=hlines,
    volume=True,
    savefig={"fname": out_file, "dpi": 150, "bbox_inches": "tight"},
)

print(f"Chart successfully saved to {out_file}")
