# TowMagKit
**TowMagKit** is a Python-based processing suite for marine towed total-field magnetometer data, supporting both cesium and proton precession sensors. It provides an end-to-end workflow from raw sensor logs to geophysically corrected, publication-ready outputs, including:

### `run-raw2corrected.py` Full processing pipeline. raw logs → corrected .trk segments
- Conversion of raw logs to intermediate ASCII format  
- Moving-average smoothing  
- Cable-layback correction to align magnetometer and GPS positions  
- IGRF subtraction via IAGA-VMOD/ppigrf  
- Diurnal-variation correction using observatory data  
- Segmentation into straight survey legs and turning intervals  

Outputs from the segmentation step are formatted for compatibility with GMT/x2sys. While TowMagKit natively applies crossover correction via the Ishihara method, x2sys-based workflows are also supported through optional bundled bash scripts, allowing seamless integration into existing processing pipelines if desired.

### `run-crossover.py` 
- Crossover leveling based on the Ishihara method
---

## Installation in Ubuntu

Requires: Python >= 3.10
Optional but recommended: [uv](https://github.com/astral-sh/uv) for fast dependency syncing


1. **Download the package**
   Either clone from [GitHub](https://doi.org/xxxxxxx) or download the ZIP archive from our [Zenodo release](https://doi.org/xxxxxxx):

```bash
# Option 1: GitHub
git clone https://github.com/XXXXXX/towmagkit.git
cd towmagkit

# Option 2: Zenodo ZIP
unzip towmagkit‑vX.Y.Z.zip
cd towmagkit
```

2. **Install dependencies and the package**
   You can install using either `pip` or [uv](https://github.com/astral-sh/uv) (recommended).
   We strongly recommend using a **virtual environment** to avoid permission issues (especially on Linux/Mac).

```bash
# Option 1: Using pip
python3 -m venv .venv # Set up virtual environment
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .[full]

# Option 2: Or using uv (recommended)
uv sync
source .venv/bin/activate 
uv pip install -e .[full] # Install in editable mode (allows local source edits to take effect immediately)
```


3. **Build the Fortran codes**

```bash
cd src/ishihara-fortranwrappers
./compile.sh              # Requires gfortran or compatible Fortran compiler
```

**MISSION COMPLETE!!**

## (Optional) Errors on PyGMT and GMT on Ubuntu/WSL2 

run-crossover.py uses PyGMT, which sometimes requires the native GMT library (libgmt.so).
Usually things just work, but if you see errors related to libgmt.so, try the setup steps below—especially on WSL2.


#### 1. Install GMT

```bash
sudo apt update
sudo apt install gmt
```

#### 2. Check for installed GMT libraries

```bash
find /usr -name "libgmt.so*"
```

You should see something like:

```
/usr/lib/x86_64-linux-gnu/libgmt.so.6
/usr/lib/x86_64-linux-gnu/libgmt.so.6.5.0
```

#### 3. Create symbolic link to `libgmt.so`

If `libgmt.so` (without version suffix) is missing, create a symbolic link:

```bash
sudo ln -s /usr/lib/x86_64-linux-gnu/libgmt.so.6 /usr/lib/x86_64-linux-gnu/libgmt.so
```

#### 4. Add to `LD_LIBRARY_PATH`

Ensure the directory containing `libgmt.so` is in your dynamic library path:

```bash
export LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH
```

To make this permanent:

```bash
echo 'export LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH' >> ~/.bashrc
source ~/.bashrc
```

#### 5. Verify PyGMT works

```bash
python3 -c "import pygmt; print(pygmt.__version__)"
```

---

## Pipeline Scripts

| Script                 | Description                                                             |
| ---------------------- | ----------------------------------------------------------------------- |
| `run-raw2corrected.py` | Full processing pipeline: raw logs → corrected `.trk` segments          |
| `run-crossover.py`     | Apply Ishihara crossover leveling and export pre/post gridded anomalies |

---

## Directory Structure

```
project-root/
├── src/
│   ├── towmagkit/              # Core processing modules
│   ├── ishihara-fortranwrappers/  # Fortran binaries and source
│   └── ishiharautils/          # Python wrappers/utilities for crossover method
├── scripts/                    # Pipeline scripts
├── gmt_scripts/                # Optional: Bash tools for x2sys/GMT mapping
├── examples/                   # Sample cruise data (GS24 etc.)
├── paper/                      # Draft manuscript and figures
└── pyproject.toml              # Build metadata
```

---
## Raw-to-Corrected Workflow Overview

The run-raw2corrected.py script executes a complete preprocessing pipeline to convert raw magnetometer logs into corrected, line-segmented total-field anomaly datasets ready for analysis or crossover correction. The workflow applies sensor-specific raw file conversion, smoothing, layback correction, IGRF subtraction, and diurnal variation removal, before splitting the data into discrete straight-line tracks.

### Key Modules in "run-raw2corrected.py"
| Module                | Purpose                                                                                       |
| --------------------- | --------------------------------------------------------------------------------------------- |
| `protonraw2anmorg.py` | Convert proton magnetometer logs: `*.dat` → `*.dat.anmorg`                                    |
| `cesiumraw2anmorg.py` | Convert G-880/Cesium logs: `*.txt` → `*.txt.anmorg`                                           |
| `anmorg1min.py`       | Downsample `.anmorg` files to 1-minute resolution                                             |
| `cablecorr.py`        | Apply layback correction to compensate GPS-to-sensor offset                                   |
| `igrfcorrection.py`   | Subtract IGRF reference field using [ppigrf](https://github.com/IAGA-VMOD/ppigrf.git) by IAGA |
| `dv_min2obsc.py`      | Convert `.min` format to `.obsc` (1-min ASCII format used for removing diurnal variation)                  |
| `dvcorrection.py`     | Remove diurnal variation using observatory data                                               |
| `trksplitter.py`      | Track segmentation using Ramer–Douglas–Peucker algorithm                                      |

---

## Crossover Correction (Ishihara method)

The crossover correction module (Ishihara method) is implemented via Python + Fortran wrappers:

* Fortran binaries live in `src/ishihara-fortranwrappers/`
* Python interfaces and utilities live in `src/ishiharautils/`

Run `./compile.sh` in the Fortran directory to build required binaries.

### Key Modules in "run-crossover.py"
| Module                                 | Purpose                                                                     |
| -------------------------------------- | --------------------------------------------------------------------------- |
| `llaconverter.py`                      | Converts `.trk` segments to `.lla` (line-wise anomaly w/ coordinates)       |
| `lsdconverter.py`                      | Converts `.lla` > `.lsd`, appends cumulative distance                       |
| `lflcconvert.py`                       | Runs Fortran lflc on `.lsd`, `.stat`, `.lwt` > outputs corrected data nd visualized files (`.lncor`, `.csv`, `.nc`, `.tif`, `.html`)|
| `ishiharahoupipeline.py`               | Orchestrates all steps in the Ishihara crossover correction           |

### Note on parameter setting

```python
runner.run_fortran(
    dt0=6.0,      # crossover search radius [km]
    m2=3,         # window size for long-wavelength smoothing
    m1=6,         # window size for short-wavelength filtering
    f1=0.7,       # smoothing factor (long)
    f2=0.1,       # smoothing factor (short)
    sclmt=5.0     # shift limit [nT] – max correction allowed
)
```
Note: These values can be tuned to suit the noise level and track geometry of your survey.
```python
runner.plot(
    spacing="0.002",    # grid resolution (deg)
    tension=0.65,       # interpolation tension (0 = spline)
    maxradius="2k",     # max search radius for gridding
    netcdfexport=True   # export as NetCDF & GeoTIFF
)
```
Note: For full control over gridding options, refer to the PyGMT surface documentation.





### Diurnal Variation Correction (`dv/` folder)
This example uses shore-based 1-minute data from **Kakioka Magnetic Observatory** in `.min` format.
This example does **not** include `.min` data due to licensing restrictions

To prepare this:

1. Download `.min` files for the cruise dates from
   
   [Kakioka Magnetic Observatory, 2013, Kanoya geomagnetic field 1-minute digital data in IAGA-2002 format [dataset], Kakioka Magnetic Observatory Digital Data Service, doi:10.48682/186fd.3f000](https://www.kakioka-jma.go.jp/obsdata/metadata/en/orders/new/kny_geomag_1-min)
   
   
   Required files for this example:
   ```
   kny20240929dmin.min  
   kny20240930dmin.min  
   kny20241001dmin.min  
   kny20241002dmin.min
   ```
2. Place them in `dv/`


If .min files are not available, Step 5 will not run.
You should manually comment out Step 5 in the script, create a valid output.obsc file, and place it in the dv/ folder.

This file is required for Step 6 (Apply diurnal variation correction) to work correctly.

### `.obsc` File Format

The `output.obsc` file is a plain text file containing 1-minute diurnal variation values.

Each line must have the following six space-separated fields:

```
YYYY MM DD HH MM DV
```

Where:

* `YYYY MM DD HH MM` is the UTC timestamp (year, month, day, hour, minute)
* `DV` is the diurnal variation value in **nanoteslas (nT)**

The file must be sorted by time in ascending order.

**Example:**

```
2024 09 29 00 00   5.3
2024 09 29 00 01   5.1
2024 09 29 00 02   5.0
...
```

This allows Step 6 (diurnal variation correction) to be performed even without `.min` files.

---

## Example: GS24 (G-880 Cesium Magnetometer)

```bash
examples/GS24/
├── Export.G-880.gs24-day*.txt     # Raw log
├── dv/                            # Diurnal variation files (.min and .obsc)
├── splittedTRK_*/
│   ├── main_tracks/               # Long segments
│   ├── skipped_tracks/            # Too short
│   └── crossoverpreprocess/       # Intermediate files for Ishihara correction
```

---

## Outputs

### Core Processing

| Output                    | Description                                        |
| ------------------------- | -------------------------------------------------- |
| `*.anmorg`                | Unified ASCII with time, lat/lon, total field      |
| `*.1min.anmorg`           | 1-minute averaged total field (temporal smoothing) |
| `*.anmorg.anm_cc`         | After layback correction                           |
| `*.anmorg.anm_cc_igrf`    | After IGRF subtraction                             |
| `*.anmorg.anm_cc_igrf_dv` | After diurnal correction                           |
| `*.trk`                   | Final track segments (x2sys-compatible)            |

### Diurnal Correction

| Output             | Description                                    |
| ------------------ | ---------------------------------------------- |
| `*.min`            | Kakioka-style minute data input                |
| `*.obsc`           | Reformatted diurnal variation file             |
| `output_plot.html` | Interactive preview of ΔF at reference station |

### Crossover Correction (Ishihara method)

| Output                        | Description                                        |
| ----------------------------- | -------------------------------------------------- |
| `*.lla`                       | Cruise-wise raw anomaly, timestamp, lon/lat        |
| `*.lsd`                       | Distance-tagged lines derived from `.lla`          |
| `*.lfind`, `*.lfind2`         | Line-pair distance metadata                        |
| `*.lwt`                       | Line weights for leveling                          |
| `*.lncor`                     | Final corrected table with weights and corrections |
| `mag_before.nc/.tif`          | Pre-correction gridded anomaly                     |
| `mag_after.nc/.tif`           | Post-correction gridded anomaly                    |
| `mag_comparison_gridded.html` | Interactive comparison map                         |
| `pipeline_log_*.json`         | Traceable process log for reproducibility          |

---

## License

TowMagKit is released under the **MIT License**.
Please cite appropriately when using for academic or publication purposes.
