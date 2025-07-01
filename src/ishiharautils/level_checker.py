import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.stats import gaussian_kde
from pathlib import Path
import json

class LevelChecker:
    def __init__(self, cruise_dirs: dict[int, list[str]], output_dir: str, base_cruise: int = 1):

        self.cruise_dirs = cruise_dirs
        self.output_dir = Path(output_dir).expanduser()
        self.base_cruise = base_cruise
        self.cruise_peaks = {}
        self.level_offsets = {}
        self.anomaly_data = {}  # cruise_id → np.array

    def load_all_anomalies(self):
        self.anomaly_data = {}   # cruise_id → np.array of anomaly values
        self.source_paths = {}   # cruise_id → list of Path objects

        for cruise_id, path_list in self.cruise_dirs.items():
            all_values = []

            for path in path_list:
                cruise_path = Path(path).expanduser()
                track_dirs = sorted(cruise_path.rglob("main_tracks"))

                if not track_dirs:
                    print(f"⚠️ No 'main_tracks' found for cruise {cruise_id} in {cruise_path}")
                    continue

                for dir_path in track_dirs:
                    for trk_file in dir_path.glob("*.trk"):
                        values = self.load_anomaly_from_trk(trk_file)
                        all_values.extend(values)
                        self.source_paths.setdefault(cruise_id, []).append(trk_file.resolve())

            self.anomaly_data[cruise_id] = np.array(all_values)

    def detect_outliers(self):
        for cruise_id, anomalies in self.anomaly_data.items():
            median = np.median(anomalies)
            sigma = np.std(anomalies)
            lower, upper = median - 5 * sigma, median + 5 * sigma

            outliers = anomalies[(anomalies < lower) | (anomalies > upper)]
            filtered = anomalies[(anomalies >= lower) & (anomalies <= upper)]
            self.anomaly_data[cruise_id] = filtered  # 上書き

            if len(outliers) > 0:
                print(f"❌ [Outlier] Cruise {cruise_id:03d} → {len(outliers)} values outside Median ± 5σ")
                print(f"    Median = {median:.2f}, σ = {sigma:.2f}, Bounds = [{lower:.2f}, {upper:.2f}]")
                print(f"    Example outliers: {outliers[:5]}")
            else:
                print(f"✅ [OK] Cruise {cruise_id:03d} → No outliers found (Median = {median:.2f}, σ = {sigma:.2f})")


    def load_anomaly_from_trk(self, filepath: Path) -> np.ndarray:

        df = pd.read_csv(
            filepath,
            sep=r"\s+",
            header=None,
            names=["unixtime", "lon", "lat", "anomaly"],
            engine="python",  # 必須よ！
        )

        return df["anomaly"].values

    def estimate_kde_peaks(self):
        for cruise_id, anomalies in self.anomaly_data.items():
            kde = gaussian_kde(anomalies)
            x = np.linspace(anomalies.min(), anomalies.max(), 1000)
            y = kde(x)
            peak = x[np.argmax(y)]
            self.cruise_peaks[cruise_id] = peak
            print(f"Cruise {cruise_id:03d}: KDE peak = {peak:.2f}, Samples = {len(anomalies)}")

        base_peak = self.cruise_peaks[self.base_cruise]
        for cid, peak in self.cruise_peaks.items():
            self.level_offsets[cid] = round(base_peak - peak, 3)

    def save_json(self, filename="kde_level_offsets.json"):
        output_path = self.output_dir / filename
        self.output_dir.mkdir(parents=True, exist_ok=True)

        data = {
            "base_cruise": self.base_cruise,
            "kde_peaks": {str(k): round(v, 3) for k, v in self.cruise_peaks.items()},
            "level_offsets": {str(k): v for k, v in self.level_offsets.items()}
        }

        with open(output_path, "w") as f:
            json.dump(data, f, indent=4)

        print(f"✅ Saved JSON to: {output_path}")

    def plot_all(self):
        fig, ax = plt.subplots(figsize=(10, 5))
        cmap = plt.get_cmap("tab10")

        for i, (cruise_id, anomalies) in enumerate(self.anomaly_data.items()):
            kde = gaussian_kde(anomalies)
            x = np.linspace(anomalies.min(), anomalies.max(), 1000)
            y = kde(x)
            peak = self.cruise_peaks[cruise_id]
            mean = anomalies.mean()
            label = f"#{cruise_id:03d} | Peak={peak:.1f}, Mean={mean:.1f}"
            color = cmap(i % 10)

            ax.hist(anomalies, bins=50, density=True, alpha=0.3,
                    label=f"#{cruise_id:03d} Histogram", color=color)
            ax.plot(x, y, color=color, label=label)

        ax.set_title("KDE + Normalized Histograms (Outliers Removed)")
        ax.set_xlabel("Magnetic Anomaly [nT]")
        ax.set_ylabel("Normalized Frequency")
        ax.legend()
        fig.tight_layout()

        fig_path = self.output_dir / "kde_hist_combined_filtered.png"
        fig.savefig(fig_path, dpi=150)
        plt.close(fig)
        print(f"✅ Saved plot to: {fig_path}")
