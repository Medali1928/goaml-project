import pandas as pd
from datetime import datetime
from pathlib import Path
 

 
 
def load_defaults():

    defaults = {}
    
    file_path = Path(__file__).resolve().parents[2] / "param_file" / "default.txt"

    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
 
            if not line or line.startswith("#"):
                continue
 
            key, value = line.split("=", 1)
            defaults[key.strip()] = value.strip()
 
    return defaults
 
 
def handle_missing_extra(df1):
 
    df = df1.copy()
 
    # Load defaults internally
    defaults = load_defaults()
 
    # --- AMOUNT_LOCAL = ABS(transaction_amount_lcy)
    df["AMOUNT_LOCAL"] = df["TRANSACTION_AMOUNT_LCY"].astype(float)
 
    # --- currency codes
    df["CURRENCY_CODE_1"] = df["TRANSACTION_CURRENCY"]
    df["CURRENCY_CODE_2"] = df["TRANSACTION_CURRENCY"]
 
    # --- foreign amounts
    df["FOREIGN_AMOUNT_1"] = df["TRANSACTION_AMOUNT"]
    df["FOREIGN_AMOUNT_2"] = df["TRANSACTION_AMOUNT"]
 
    # --- date formatter
    def parse_date(ts):
        if pd.isna(ts):
            return None
 
        ts = str(ts).strip()
 
        if "." in ts:
            ts = ts.replace(".", ":")
 
        dt = datetime.strptime(ts, "%Y-%m-%d %H:%M")
 
        return dt.strftime("%Y-%m-%dT%H:%M:00")
 
    # --- DATE_TRANSACTION
    df["DATE_TRANSACTION"] = df["TRANSACTION_DATE_TS"].apply(parse_date)
 
    # --- TRANSACTION_NUMBER
    df["TRANSACTION_NUMBER"] = (
        "30/"
        + df["TRANSACTION_REF"].astype(str)
        + "/"
        + df["DATE_TRANSACTION"].astype(str)
    )
 
    # --- apply defaults for missing columns
    for col, default_value in defaults.items():
        if col not in df.columns:
            df[col] = default_value
 
    return df