from __future__ import annotations

"""
ishiharautils.leveling_pipeline – LFLCconvert
================================================
Python helper to run Ishihara *lflc* (Fortran level‑off) and visualise results.
"""

import logging
import textwrap
import subprocess
import tempfile
import datetime as _dt
from pathlib import Path
from typing import Sequence

import pandas as pd
import numpy as np
import pygmt
import plotly.io as pio
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy.spatial import cKDTree

__all__ = ["LFLCconvert"]
LOGGER = logging.getLogger(__name__)


class LFLCconvert:  # noqa: D401
    """Run Ishihara *lflc* and generate stats / heatmap."""

    def __init__(
        self,
        work_dir: str | Path,
        basename: str = "merged",
        fortran_dir: str | Path | None = None,
        lflc_executable: str | Path | None = None,
    ) -> None:
        self.work_dir = Path(work_dir).expanduser().resolve()
        self.basename = basename

        self.fortran_dir = (
            Path(fortran_dir).expanduser().resolve()
            if fortran_dir is not None
            else (self.work_dir.parent / "ishihara-fortranwrappers").resolve()
        )
        self.lflc_executable = (
            Path(lflc_executable).expanduser().resolve()
            if lflc_executable is not None
            else self.fortran_dir / "lflc"
        )

        self._lsd = self.work_dir / f"{basename}.lsd"
        self._stat = self.work_dir / f"{basename}lsd.stat"
        self._lwt = self.work_dir / f"{basename}.lwt"
        self._lncor = self.work_dir / f"{basename}.lncor"

        for fp in (self._lsd, self._stat, self._lwt):
            if not fp.exists():
                raise FileNotFoundError(fp)

    def run_fortran(
        self,
        *,
        dt0: float = 6.0,
        m2: int = 3,
        m1: int = 6,
        f1: float = 0.7,
        f2: float = 0.1,
        sclmt: float = 5.0,
        extra_flags: Sequence[str] | None = None,
        keep_param_file: bool = False,
    ) -> Path:
        if not self.lflc_executable.exists():
            raise FileNotFoundError(self.lflc_executable)

        with self._stat.open("r+", encoding="utf-8") as fp:
            lines = fp.readlines()
            if len(lines) >= 1 and (len(lines) == 1 or lines[1].strip()):
                fp.seek(0)
                fp.write(lines[0])
                fp.write("\n")
                fp.writelines(lines[1:])
                LOGGER.warning(
                    "Inserted blank 2nd header line into %s", self._stat.name
                )

        param_text = (
            textwrap.dedent(
                f"""
            {dt0} {m2}
            {m1}
            {f1} {f2}
            {sclmt}
            {self._lsd.name}
            {self._stat.name}
            {self._lwt.name}
            {self._lncor.name}
            """
            ).strip()
            + "\n"
        )

        if keep_param_file:
            param_path = self.work_dir / "lflc_params.in"
            param_path.write_text(param_text)
            param_stdin = param_path.open("rb")
        else:
            param_stdin = tempfile.TemporaryFile()
            param_stdin.write(param_text.encode())
            param_stdin.seek(0)

        LOGGER.info("[lflc] launching Fortran …")
        start = _dt.datetime.now()
        try:
            result = subprocess.run(
                [str(self.lflc_executable)],
                stdin=param_stdin,
                cwd=self.work_dir,
                check=True,
                capture_output=True,
                text=True,
                *([] if extra_flags is None else extra_flags),
            )
            if result.stdout:
                LOGGER.info(result.stdout.rstrip())
            if result.stderr:
                LOGGER.warning(result.stderr.rstrip())
        except subprocess.CalledProcessError as e:
            LOGGER.error("lflc exited with code %s", e.returncode)
            if e.stdout:
                LOGGER.error("stdout:\n%s", e.stdout)
            if e.stderr:
                LOGGER.error("stderr:\n%s", e.stderr)
            raise
        finally:
            param_stdin.close()
        LOGGER.info(
            "[lflc] finished in %.1f s", (_dt.datetime.now() - start).total_seconds()
        )

        if not self._lncor.exists():
            raise RuntimeError("lflc completed but .lncor not found")
        return self._lncor

    def summary(self) -> pd.Series:
        lncor = self._load_lncor()
        stats = (lncor["corr_mag"] - lncor["mag"]).describe()
        print("\n=== Level-offset summary (corr_mag − mag) ===")
        print(stats.to_string(float_format="{:8.3f}".format))
        return stats

    def plot(
        self,
        *,
        spacing: str = "0.01",
        tension: float = 0.2,
        maxradius: str = "2k",
        netcdfexport: bool = False,
    ) -> Path:
        lsd_cols = ["cruise", "line", "year", "doy", "lon", "lat", "mag", "dist"]
        ln_cols = [
            "cruise",
            "datetime",
            "dummy",
            "lon",
            "lat",
            "mag",
            "corr_mag",
            "offset",
            "weight",
        ]
        lsd = pd.read_csv(self._lsd, sep=r"\s+", names=lsd_cols)
        lncor = pd.read_csv(self._lncor, sep=r"\s+", names=ln_cols)

        merged_csv = pd.DataFrame(
            {
                "lon": lncor["lon"],
                "lat": lncor["lat"],
                "mag": lsd["mag"],
                "corr_mag": lncor["corr_mag"],
            }
        )
        out_csv = self.work_dir / "mag_comparison_points.csv"
        merged_csv.to_csv(out_csv, index=False)
        LOGGER.info("Point CSV saved: %s", out_csv)

        fig = make_subplots(
            rows=1,
            cols=2,
            shared_yaxes=True,
            horizontal_spacing=0.10,
            subplot_titles=("Before", "After"),
        )
        for df, label, col in (
            (lsd, "before", "mag"),
            (lncor, "after", "corr_mag"),
        ):
            data = df[["lon", "lat", col]].dropna()
            data = data[np.isfinite(data[col])]
            region = [
                float(np.floor(data["lon"].min() * 10) / 10 - 0.3),
                float(np.ceil(data["lon"].max() * 10) / 10 + 0.3),
                float(np.floor(data["lat"].min() * 10) / 10 - 0.3),
                float(np.ceil(data["lat"].max() * 10) / 10 + 0.3),
            ]
            blk = pygmt.blockmedian(data=data, region=region, spacing=f"{spacing}+e")
            grid = pygmt.surface(
                data=blk,
                region=region,
                spacing=f"{spacing}+e",
                tension=tension,
                maxradius=maxradius,
            )

            xg, yg = np.meshgrid(
                grid.coords["x"].values, grid.coords["y"].values, indexing="xy"
            )
            xy = np.vstack([data["lon"], data["lat"]]).T
            tree = cKDTree(xy)
            dist, _ = tree.query(
                np.c_[xg.ravel(), yg.ravel()], distance_upper_bound=0.1
            )
            mask = dist.reshape(xg.shape)
            grid = grid.where(~np.isinf(mask))

            if netcdfexport:
                if not hasattr(grid, "rio"):
                    raise RuntimeError(
                        "rioxarray is not available or grid lacks .rio accessor"
                    )

                nc_path = self.work_dir / f"mag_{label}.nc"
                tif_path = self.work_dir / f"mag_{label}.tif"

                grid.rio.set_spatial_dims(x_dim="x", y_dim="y", inplace=True)
                grid.rio.write_crs("EPSG:4326", inplace=True)
                grid.to_netcdf(nc_path)
                LOGGER.info("NetCDF saved: %s", nc_path)
                grid.rio.to_raster(tif_path)
                LOGGER.info("GeoTIFF saved: %s", tif_path)

            fig.add_trace(
                go.Heatmap(
                    z=grid.values,
                    x=grid.coords["x"].values,
                    y=grid.coords["y"].values,
                    colorscale="RdBu_r",
                    colorbar=dict(title="nT", x=0.45 if label == "before" else 1.0),
                ),
                row=1,
                col=1 if label == "before" else 2,
            )

        fig.update_layout(
            width=1000,
            height=500,
            title_text="Magnetic Anomaly — Before / After (Fortran leveled)",
            showlegend=False,
        )
        out_html = self.work_dir / "mag_comparison_gridded.html"
        pio.write_html(fig, file=str(out_html), auto_open=False)
        LOGGER.info("Heatmap saved: %s", out_html)
        return out_html

    def _load_lncor(self) -> pd.DataFrame:
        cols = [
            "cruise",
            "datetime",
            "dummy",
            "lon",
            "lat",
            "mag",
            "corr_mag",
            "offset",
            "weight",
        ]
        return pd.read_csv(self._lncor, sep=r"\s+", names=cols)
