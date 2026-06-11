"""F2 — render clean full-storey plans for the upper floors (2-5) the dataset deferred.

`data_curation/scripts/synth/3c_render_full_storeys.py` rendered only First Floor / Garage /
Level 1: Floors 2-5 have windows but their host walls are multi-storey walls contained in
"Level 1", so storey-containment alone yields wall-less plans (the "F2 future work" deferral).

Fix: for each upper floor, take its contained windows + pull their **host walls** via the
FILLS->VOIDS chain, and reuse the dataset's own `render_one` so the output (window=blue /
door=green / wall=dark + world_bbox json) byte-matches `floorplans_full/` — the M1b detector
(`slot_detector_cv.py`) consumes the new plans unchanged. Writes ADDITIVELY (new files; the 3
existing plans untouched). Needs the master_thesis renderer + ifcopenshell + the IFC model.

Run:  .venv/bin/python scripts/render_upper_storeys.py
"""
from __future__ import annotations
import importlib.util
import json
import sys
from pathlib import Path

SYNTH = Path("/home/hychi/projects/cmu/master_thesis/data_curation/scripts/synth")
sys.path.insert(0, str(SYNTH))
_spec = importlib.util.spec_from_file_location("render3c", SYNTH / "3c_render_full_storeys.py")
r3c = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(r3c)
from _floorplan_renderer import FloorplanRenderer  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
IFC = REPO / "data" / "ifc_models" / "AdvancedProject.ifc"
OUT = Path("/home/hychi/projects/cmu/master_thesis/data_curation/datasets/synth_v0.5_ap/floorplans_full")
UPPER = ["2 - Second Floor", "3 - Third Floor", "4 - Fourth Floor", "5 - Fifth Floor"]


def host_walls(ifc, window_guids):
    op2wall = {v.RelatedOpeningElement.GlobalId: v.RelatingBuildingElement
               for v in ifc.by_type("IfcRelVoidsElement")
               if v.RelatedOpeningElement and v.RelatingBuildingElement}
    win2op = {f.RelatedBuildingElement.GlobalId: f.RelatingOpeningElement
              for f in ifc.by_type("IfcRelFillsElement")
              if f.RelatedBuildingElement and f.RelatingOpeningElement}
    walls = {}
    for wg in window_guids:
        op = win2op.get(wg)
        w = op2wall.get(op.GlobalId) if op else None
        if w is not None:
            walls[w.GlobalId] = w
    return list(walls.values())


def main():
    renderer = FloorplanRenderer(str(IFC))
    ifc = renderer.file
    ff = json.load(open(OUT / "AP_storey_1_first_floor.json"))["world_bbox"]
    bbox = (ff["xmin"], ff["ymin"], ff["xmax"], ff["ymax"])

    orig = renderer._get_storey_elements
    for floor in UPPER:
        elems = orig(floor)                                   # contained (windows; no walls)
        wins = [(c, g, e) for (c, g, e) in elems if c == "IfcWindow"]
        wguids = [g for _, g, _ in wins]
        walls = host_walls(ifc, wguids)
        wall_elems = [(w.is_a(), w.GlobalId, renderer._get_2d_edges(w)) for w in walls]
        wall_elems = [(c, g, e) for (c, g, e) in wall_elems if e]
        augmented = wins + wall_elems
        if not wins or not wall_elems:
            print(f"  skip {floor}: windows={len(wins)} host_walls={len(wall_elems)}")
            continue
        renderer._get_storey_elements = lambda _n, _a=augmented: _a   # feed render_one
        cal = r3c.render_one(renderer, floor, OUT, "AP", bbox_override=bbox)
        print(f"  {floor}: {len(wins)} windows + {len(wall_elems)} host walls -> {cal and cal['png_path']}")
    renderer._get_storey_elements = orig
    print("done. new plans are additive in", OUT)


if __name__ == "__main__":
    main()
