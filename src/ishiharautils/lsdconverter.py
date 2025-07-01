from pathlib import Path
import pandas as pd
import math
import csv


class LSDConverter:
    # Converts one or more .lla files to a unified .lsd format with distance calculation.
    def __init__(self):
        pass

    def haversine(self, lon1, lat1, lon2, lat2):
        # Calculate the great-circle distance (in km) between two points using the Haversine formula.
        R = 6371.0
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = (
            math.sin(dphi / 2) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
        )
        return 2 * R * math.asin(math.sqrt(a))

    def convert_lla_to_lsd(
        self,
        lla_path: Path,
        line_number: int,
        *,
        global_mean: float | None = None,
        global_std: float | None = None,
        z_thresh: float = 3.5,
    ) -> list[str]:
        """
        One .lla → list[str].
        set z score
        """
        try:
            df = pd.read_csv(
                lla_path,
                sep=r"\s+",
                header=None,
                names=["track", "yyyymmdd", "hhmmss", "lon", "lat", "anomaly"],
                dtype=str,
            )
        except Exception as e:
            print(f"X. Failed to read {lla_path.name}: {e}")
            return []

        df = df.dropna(subset=["yyyymmdd", "hhmmss", "lon", "lat", "anomaly"])
        df = df[df["yyyymmdd"].str.len() == 8]
        df = df[df["hhmmss"].str.len() >= 4]
        if len(df) < 2:
            print(f"! Skipping {lla_path.name}: not enough valid rows ({len(df)})")
            return []

        df["anomaly"] = pd.to_numeric(df["anomaly"], errors="coerce")
        df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
        df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
        df["track"] = pd.to_numeric(df["track"], errors="coerce").astype("Int64")

        # remove noise data
        if global_mean is not None and pd.notna(global_std) and global_std > 0:
            z = (df["anomaly"] - global_mean) / global_std
            before = len(df)
            df = df[z.abs() < z_thresh]
            if len(df) < 2:
                print(
                    f"! Skipping {lla_path.name}: only {len(df)}/{before} rows remain after "
                    f"outlier removal (z>{z_thresh})"
                )
                return []

        df["year"] = df["yyyymmdd"].str[:4].astype(int)
        df["month"] = df["yyyymmdd"].str[4:6].astype(int)
        df["day"] = df["yyyymmdd"].str[6:8].astype(int)

        hhmmss_str = df["hhmmss"].str.zfill(6)
        df["hour"] = hhmmss_str.str[:2].astype(int)
        df["minute"] = hhmmss_str.str[2:4].astype(int)
        df["second"] = hhmmss_str.str[4:6].astype(int)

        df["datetime"] = pd.to_datetime(
            df[["year", "month", "day", "hour", "minute", "second"]]
        )
        df["doy"] = df["datetime"].dt.dayofyear
        df["dec_time"] = df["hour"] + df["minute"] / 60 + df["second"] / 3600
        df["doy_time"] = df["doy"] + df["dec_time"] / 24

        df["distance_km"] = 0.0
        for i in range(1, len(df)):
            dist = self.haversine(
                df.iloc[i - 1]["lon"],
                df.iloc[i - 1]["lat"],
                df.iloc[i]["lon"],
                df.iloc[i]["lat"],
            )
            df.at[df.index[i], "distance_km"] = (
                df.at[df.index[i - 1], "distance_km"] + dist
            )

        df["lon_west"] = df["lon"].apply(lambda x: x - 360 if x > 180 else x)

        lsd_lines: list[str] = []
        for _, row in df.iterrows():
            line = (
                f"{row['track']:4d} {line_number:5d} {row['year']:4d} "
                f"{row['doy_time']:12.7f} {row['lon_west']:10.5f} "
                f"{row['lat']:9.5f} {row['anomaly']:8.2f} {row['distance_km']:10.2f}"
            )
            lsd_lines.append(line)

        return lsd_lines

    def convert_all_lla_to_lsd_and_merge(
        self, lla_dir, output_lsd_path, mapping_csv_path, z_thresh: float = 3.5
    ):
        lla_files = sorted(Path(lla_dir).glob("*.lla"))
        if not lla_files:
            print("No .lla files found.")
            return

        # remove anomaly noise
        all_anom = []
        for f in lla_files:
            try:
                s = pd.read_csv(
                    f,
                    sep=r"\s+",
                    header=None,
                    usecols=[5],
                    names=["anomaly"],
                    dtype=str,
                )["anomaly"]
                all_anom.append(pd.to_numeric(s, errors="coerce"))
            except Exception as e:
                print(f"X. preload {f.name}: {e}")

        anom_series = pd.concat(all_anom, ignore_index=True).dropna()
        global_mean = anom_series.mean()
        global_std = anom_series.std()
        print(f"   global_mean={global_mean:.3f}, global_std={global_std:.3f}")

        # coonvert LSD
        all_lines, mapping = [], []
        for i, file in enumerate(lla_files, start=1):
            print(f"> {file.name} → line {i}")
            lines = self.convert_lla_to_lsd(
                file,
                line_number=i,
                global_mean=global_mean,
                global_std=global_std,
                z_thresh=z_thresh,
            )
            all_lines.extend(lines)
            mapping.append({"line_number": i, "filename": file.name})

        # Export
        with open(output_lsd_path, "w") as f:
            f.write("\n".join(all_lines) + "\n")

        with open(mapping_csv_path, "w", newline="") as f:
            csv.DictWriter(f, fieldnames=["line_number", "filename"]).writerows(mapping)

        print(f" - Merged LSD: {output_lsd_path}")
        print(f" - Mapping CSV: {mapping_csv_path}")
