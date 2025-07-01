#!/usr/bin/env python3

import logging
from pathlib import Path
from ishiharautils import (
    LLAConverter,
    LSDConverter,
    IshiharaPipeline,
    LFLCconvert,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)

# ============================================
#  SETTINGS: Input directories and parameters
# ============================================

cruise_dirs = {
    241: "~/work/towmagkit/examples/GS24/corrected_towmag/splittedTRK_20250701_181839",
}
output_dir_str = (
    "~/work/towmagkit/examples/GS24/corrected_towmag/splittedTRK_20250701_181839"
)

# ==================================================
#  MAIN PIPELINE FUNCTION
# ==================================================


def main():
    input_dirs_str = []

    for cruise_num, base in cruise_dirs.items():
        base_path = Path(base).expanduser()

        # find directory=main_tracks
        subdirs = sorted(base_path.rglob("main_tracks"))

        if subdirs:
            for subdir in subdirs:
                if subdir.is_dir():
                    input_dirs_str.append((str(subdir), cruise_num))
        else:
            # if not found 'main_tracks', use base_path as main_tracks
            if base_path.is_dir():
                print(f"[INFO] No 'main_tracks' found under {base_path}, using it directly.")
                input_dirs_str.append((str(base_path), cruise_num))
            else:
                print(f"[WARNING] Skipping missing directory: {base_path}")

    print("\n[DEBUG] Input dirs to search:")
    for p, c in input_dirs_str:
        print(f"  Cruise {c}: {p}")

    multi_inputs = [(Path(p).expanduser(), n) for p, n in input_dirs_str]
    output_dir = Path(output_dir_str).expanduser()

    lla_dir = output_dir / "llaconverted"
    merged_lsd = output_dir / "merged.lsd"
    mapping_csv = output_dir / "line_index_map.csv"
    # lncor_file = output_dir / "merged.lncor"

    lla_converter = LLAConverter()
    lsd_converter = LSDConverter()

    for input_path, cruise_name in multi_inputs:
        print(f"\n=== Processing: {input_path} (Cruise {cruise_name}) ===")
        print(" - Step 1: Converting .trk → .lla (force re-run)")
        lla_converter.convert_directory(
            folder_path=str(input_path),
            track_number=cruise_name,
            output_dir=lla_dir,
            extension="*.trk",
        )

    print(f"[DEBUG] Checking .lla files in: {lla_dir}")
    print(list(lla_dir.glob("*.lla")))

    print(" - Step 2: Converting .lla → .lsd and merging")

    lsd_converter.convert_all_lla_to_lsd_and_merge(
        lla_dir=lla_dir, output_lsd_path=merged_lsd, mapping_csv_path=mapping_csv
    )

    print(" - Step 3: Running Fortran crossover detection")
    pipeline = IshiharaPipeline(input_file=merged_lsd)
    pipeline.run_from_lsd()

    print(" - Step 4: Running LFLC Fortran-leveling")
    runner = LFLCconvert(
        work_dir=output_dir,
        basename="merged",
        fortran_dir=Path("~/work/towmagkit/src/ishihara-fortranwrappers").expanduser(),
    )

    runner.run_fortran(dt0=6.0, m2=3, m1=6, f1=0.7, f2=0.1, sclmt=5.0)

    runner.summary()

    runner.plot(spacing="0.005", tension=0.65, maxradius="5k", netcdfexport=True)


# ============================================
#  Entry Point
# ============================================

if __name__ == "__main__":
    main()
