from pathlib import Path
import pandas as pd
from datetime import datetime

class LLA2TRKConverter:
    def __init__(self, output_ext=".trk"):
        self.output_ext = output_ext

    def convert_all(self, input_dir: str | Path) -> None:
        input_dir = Path(input_dir).expanduser().resolve()
        for fp in sorted(input_dir.glob("*.lla")):
            self.convert_file(fp)

    def convert_file(self, fp: Path) -> None:
        try:
            df = pd.read_csv(
                fp,
                sep=r"\s+",
                header=None,
                names=["track", "date", "time", "lon", "lat", "anomaly"],
            )
            if df.empty:
                print(f"[WARN] Skipped empty file: {fp.name}")
                return

            # datetime → UNIX時間（整数秒）に変換
            df["unixtime"] = [
                int(datetime.strptime(f"{d} {t:06}", "%Y%m%d %H%M%S").timestamp())
                for d, t in zip(df["date"], df["time"])
            ]

            df["anomaly"] = df["anomaly"].astype(float).round(1)

            output_path = fp.with_suffix(fp.suffix + self.output_ext)
            output_path.write_text(
                "\n".join(
                    f"{t} {lon:.7f} {lat:.7f} {mag:.1f}"
                    for t, lon, lat, mag in zip(
                        df["unixtime"], df["lon"], df["lat"], df["anomaly"]
                    )
                ),
                encoding="utf-8"
            )
            print(f"✅ Saved: {output_path.name}")
        except Exception as e:
            print(f"❌ Error processing {fp.name}: {e}")


# if __name__ == "__main__":
#     import sys
#     if len(sys.argv) < 2:
#         print("Usage: python lla2trk.py <input_dir>")
#     else:
#         convert_lla_to_trk(sys.argv[1])