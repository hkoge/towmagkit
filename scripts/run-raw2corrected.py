#!/usr/bin/env python3

from towmagkit import (
    CESIUMRAW2ANMORG,
    PROTONRAW2ANMORG,
    ANMORG1MIN,
    CABLECORRECTION,
    IGRFCORRECTION,
    DVCONVERT,
    DVCORRECTION,
    TRKSplitter,
)
from pathlib import Path

# ==================================================
#  SETTINGS: Define input/output folders and params
# ==================================================

# Base input directories
input_dir_str = "~/work/towmagkit/examples/GS24"
input_dv_dir_str = "~/work/towmagkit/examples/GS24/dv"

# Instrument
instrument = 'cesium' # cesium or proton

# --- Cable length correction ---
wire_len = 329.95  # [m] Cable length from ship's GPS to magnetometer
steps = 3  # Steps ahead to estimate heading

# Notes on `steps`:
#   1 = raw direction, sensitive to noise
#   3 = moderate smoothing (recommended)
#   5+ = stronger smoothing for fast/sparse data

# --- RDP Track Simplification ---
epsilon = 0.01  # Tolerance [deg] for RDP simplification
min_distance_km = 3  # Minimum segment length to keep [km]


# ==================================================
#  MAIN PIPELINE FUNCTION
# ==================================================
def main():
    input_dir = Path(input_dir_str).expanduser()
    input_dv_dir = Path(input_dv_dir_str).expanduser()
    corrected_dir = input_dir / "corrected_towmag"
    corrected_dir.mkdir(exist_ok=True)

    # Step 1: Convert raw TXT → ANMORG format
    if instrument == 'cesium':
        converter = CESIUMRAW2ANMORG(input_dir=input_dir, output_dir=corrected_dir)
    elif instrument == 'proton':
        converter = PROTONRAW2ANMORG(input_dir=input_dir, output_dir=corrected_dir)
    else:
        raise ValueError(f"Unknown instrument type: {instrument}")
    converter.convert_all(start_number=1)

    # Step 2: Resample .anmorg to 1-minute interval
    processor = ANMORG1MIN(input_dir=corrected_dir)
    processor.process_directory()

    # Step 3: Apply cable length correction
    corrector = CABLECORRECTION(input_dir=corrected_dir, wire_len=wire_len, steps=steps)
    corrector.process_directory()

    # Step 4: Subtract IGRF model
    igrf_corrector = IGRFCORRECTION(input_dir=corrected_dir, wire_height=0.0)
    igrf_corrector.process_directory()

    # Step 5: Convert diurnal-variation (.min → .obsc)
    dv_converter = DVCONVERT(input_dir=input_dv_dir)
    dv_converter.convert()

    # Step 6: Apply diurnal-variation correction
    dv_corrector = DVCORRECTION(anm_folder=corrected_dir, obsc_folder=input_dv_dir)
    dv_corrector.run()

    # Step 7: Split tracks using RDP algorithm
    TRKSplitter(
        input_dir=corrected_dir, epsilon=epsilon, min_distance_km=min_distance_km
    )

    print(f" - Cesium data written to: {corrected_dir}")


# ==================================================
#  Entry point
# ==================================================

if __name__ == "__main__":
    main()
