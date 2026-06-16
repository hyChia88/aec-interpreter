"""Stage the (gitignored) live assets the Modal backend needs into one local dir,
mirroring the Volume layout, so it can be uploaded with a single `modal volume put`.

Only the assets actually used at runtime are staged (not the full 636M synth set):
  - the IFC model                                    -> ifc/AdvancedProject.ifc
  - each held-out case's site photo + floorplan patch -> data_curation/datasets/.../{imgs,floorplans}
  - the clean full-storey plans (OpenCV slot detector) -> data_curation/datasets/.../floorplans_full

Run:   python deploy/stage_assets.py
Then upload the staged top-level directories to the Volume root:
  modal volume put aec-assets deploy/_volume_stage/ifc /
  modal volume put aec-assets deploy/_volume_stage/data_curation /

The remote layout matches the AEC_* env vars set in deploy/modal_app.py:
  AEC_IFC_PATH=/assets/ifc/AdvancedProject.ifc
  AEC_DATA_ROOT=/assets/data_curation
  AEC_SYNTH_DATASET=/assets/data_curation/datasets/synth_v0.5_ap
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CASES = REPO / "data" / "test_sets" / "cases_ap_heldout_e2e.jsonl"
IFC_SRC = Path(os.getenv("AEC_IFC_PATH_LOCAL", str(REPO / "data" / "ifc_models" / "AdvancedProject.ifc")))
DATA_ROOT = Path(os.getenv("AEC_DATA_ROOT_LOCAL", "/home/hychi/projects/cmu/master_thesis/data_curation"))
SYNTH = DATA_ROOT / "datasets" / "synth_v0.5_ap"

STAGE = REPO / "deploy" / "_volume_stage"


def _copy(src: Path, dst: Path) -> bool:
    if not src.exists():
        print(f"  ⚠️  missing: {src}")
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return True


def main():
    if STAGE.exists():
        shutil.rmtree(STAGE)
    STAGE.mkdir(parents=True)

    # 1) IFC model
    ok_ifc = _copy(IFC_SRC, STAGE / "ifc" / "AdvancedProject.ifc")

    # 2) per-case site photo + floorplan patch (paths are relative to DATA_ROOT)
    cases = [json.loads(l) for l in CASES.read_text().splitlines() if l.strip()]
    rels: set[str] = set()
    for c in cases:
        inp = c.get("inputs", {})
        rels.update(inp.get("images") or [])
        if inp.get("floorplan_patch"):
            rels.add(inp["floorplan_patch"])
    n_img = sum(_copy(DATA_ROOT / r, STAGE / "data_curation" / r) for r in sorted(rels))

    # 3) clean full-storey plans (small; used by the OpenCV slot detector)
    full_src = SYNTH / "floorplans_full"
    n_full = 0
    if full_src.exists():
        for f in full_src.iterdir():
            if f.is_file() and _copy(f, STAGE / "data_curation" / "datasets" / "synth_v0.5_ap"
                                     / "floorplans_full" / f.name):
                n_full += 1
    else:
        print(f"  ⚠️  missing floorplans_full dir: {full_src}")

    size_mb = sum(p.stat().st_size for p in STAGE.rglob("*") if p.is_file()) / 1e6
    print(f"\nStaged into {STAGE}")
    print(f"  IFC: {'ok' if ok_ifc else 'MISSING'} · case images: {n_img}/{len(rels)} · "
          f"floorplans_full: {n_full} · total {size_mb:.0f} MB")
    print("\nUpload staged directories to the Volume root:")
    print(f"  modal volume put aec-assets {STAGE / 'ifc'} /")
    print(f"  modal volume put aec-assets {STAGE / 'data_curation'} /")
    if not ok_ifc:
        sys.exit("IFC model not found — set AEC_IFC_PATH_LOCAL or place it at data/ifc_models/.")


if __name__ == "__main__":
    main()
