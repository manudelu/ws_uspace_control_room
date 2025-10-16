import argparse
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def load_csv(file_path):
    df = pd.read_csv(file_path)
    required_cols = ["Timestamp", "gps.lat", "gps.lon", "altitudeRelative",
                     "localPosition.vx", "localPosition.vy", "localPosition.vz"]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    df["Timestamp"] = pd.to_datetime(df["Timestamp"])
    return df

def upsample(df, rate_hz=10):
    t0 = df["Timestamp"].iloc[0]
    df["t_sec"] = (df["Timestamp"] - t0).dt.total_seconds()
    t_new = np.arange(df["t_sec"].iloc[0], df["t_sec"].iloc[-1], 1/rate_hz)

    def interp(col):
        return np.interp(t_new, df["t_sec"], df[col])

    df_upsampled = pd.DataFrame({
        "timestamp": t_new + t0.timestamp(),
        "latitude": np.round(interp("gps.lat"), 6),
        "longitude": np.round(interp("gps.lon"), 6),
        "altitude": np.round(interp("altitudeRelative"), 2),
        "vx": np.round(interp("localPosition.vx"), 2),
        "vy": np.round(interp("localPosition.vy"), 2),
        "vz": np.round(interp("localPosition.vz"), 2),
    })
    return df_upsampled

def save_csv(df, out_file):
    df.to_csv(out_file, index=False)
    print(f"Upsampled CSV saved to {out_file}")

def main():
    parser = argparse.ArgumentParser(description="Upsample QGC CSV to higher frequency")
    parser.add_argument("input", help="Input QGC CSV file")
    parser.add_argument("output", help="Output CSV file")
    parser.add_argument("--rate", type=float, default=10.0, help="Upsample frequency (Hz)")
    args = parser.parse_args()

    df = load_csv(args.input)
    df_up = upsample(df, rate_hz=args.rate)
    save_csv(df_up, args.output)

if __name__ == "__main__":
    main()