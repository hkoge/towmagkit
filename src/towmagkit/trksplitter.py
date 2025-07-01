"""
trk_splitter.py — Split *.trk files into straight-line segments using RDP.

Created: 2025-06-10
"""

from __future__ import annotations
import datetime as _dt
import math
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
from rdp import rdp

__all__ = ["TRKSplitter", "splitter"]


class splitter:
    def __init__(self, *, epsilon: float = 0.001, min_distance_km: float = 2.0) -> None:
        self.epsilon = float(epsilon)
        self.min_distance_km = float(min_distance_km)

    def split(self, filepath: Path, output_root: Path) -> Path:
        fp = filepath.expanduser().resolve()
        print(f"\n >< Splitting {fp.name} ><")

        try:
            df = pd.read_csv(
                fp,
                delim_whitespace=True,
                names=["unixtime", "lon", "lat", "mag"],
                dtype=float,
                comment="#",
                engine="python",
            ).dropna()
        except Exception as exc:
            raise RuntimeError(f"Failed to read {fp}") from exc

        if df.empty:
            print("!!  input file is empty – nothing to do.")
            return fp.parent

        coords = df[["lon", "lat"]].to_numpy()

        mask = rdp(coords, epsilon=self.epsilon, return_mask=True)
        idx = np.flatnonzero(mask)
        if idx[0] != 0:
            idx = np.insert(idx, 0, 0)
        if idx[-1] != len(df) - 1:
            idx = np.append(idx, len(df) - 1)
        boundaries = np.append(idx, len(df))

        base_dir = output_root / fp.stem
        main_dir = base_dir / "main_tracks"
        skip_dir = base_dir / "skipped_tracks"
        main_dir.mkdir(parents=True, exist_ok=True)
        skip_dir.mkdir(exist_ok=True)

        track_id = 0
        track_vec = np.full(len(df), -1, dtype=int)
        category_vec = np.empty(len(df), dtype=object)

        for s, e in zip(boundaries[:-1], boundaries[1:]):
            seg = df.iloc[s:e]
            seg_len = _segment_length(seg[["lon", "lat"]].to_numpy())
            is_main = seg_len >= self.min_distance_km * 1_000.0
            outdir = main_dir if is_main else skip_dir
            category = "main" if is_main else "skipped"

            track_name = f"{fp.stem}_track{track_id:02d}.trk"
            (outdir / track_name).write_text(
                "\n".join(
                    f"{int(t):d} {lon:.7f} {lat:.7f} {mag:.1f}"
                    for t, lon, lat, mag in seg.to_numpy()
                ),
                encoding="utf-8",
            )

            track_vec[s:e] = track_id
            category_vec[s:e] = category
            print(f" > Saved {category}: {track_name} ({seg_len / 1000:.2f} km)")
            track_id += 1

        df_plot = df.assign(track=track_vec, category=category_vec)
        html_out = base_dir / f"{fp.stem}_rdp.html"
        _save_plot(df_plot, html_out)
        print(f"\n > HTML visualisation → {html_out}\n")

        return base_dir


def TRKSplitter(
    input_dir: str | Path,
    *,
    epsilon: float = 0.001,
    min_distance_km: float = 2.0,
) -> Path:
    splitter_core = splitter(epsilon=epsilon, min_distance_km=min_distance_km)
    input_dir = Path(input_dir).expanduser()

    trk_files = sorted(input_dir.glob("*.trk"))
    if not trk_files:
        raise RuntimeError("No .trk files were found for splitting.")

    # Create timestamped parent output folder
    tag = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_root = input_dir / f"splittedTRK_{tag}"
    output_root.mkdir(parents=True, exist_ok=True)

    for trk in trk_files:
        splitter_core.split(trk, output_root)

    return output_root


# -- helper functions --
def _haversine(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    R = 6_371_000.0
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    Δφ = math.radians(lat2 - lat1)
    Δλ = math.radians(lon2 - lon1)
    a = math.sin(Δφ / 2) ** 2 + math.cos(φ1) * math.cos(φ2) * math.sin(Δλ / 2) ** 2
    return 2.0 * R * math.asin(math.sqrt(a))


def _segment_length(coords: np.ndarray) -> float:
    if len(coords) < 2:
        return 0.0
    return sum(
        _haversine(lon1, lat1, lon2, lat2)
        for (lon1, lat1), (lon2, lat2) in zip(coords[:-1], coords[1:])
    )


def _save_plot(df: pd.DataFrame, html_path: Path) -> None:
    fig = px.scatter_geo(
        df,
        lat="lat",
        lon="lon",
        color=df["track"].astype(str),
        symbol="category",
        title="RDP-split Tracks",
        projection="natural earth",
    )
    fig.update_traces(marker=dict(size=4, opacity=0.8))
    fig.write_html(html_path, include_plotlyjs="cdn")
