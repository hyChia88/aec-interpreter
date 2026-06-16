"""Build the assets for the interactive 3D-highlight demo (site/demo.html).

For a handful of held-out cases it (1) runs the M1b position-slot detector + temperature
calibration to get the predicted slot / confidence / ANSWER-DEFER decision, and (2) extracts
each case's storey geometry from the IFC to a glTF (GLB) whose every node is named by the
element GlobalId — so the Three.js viewer can highlight the grounded element by GUID. Emits
`site/assets/3d/<storey>.glb` (cached) + `site/assets/3d/cases.json` (the manifest the page reads).

Run:  .venv/bin/python eval/build_3d_demo.py
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

import numpy as np

EVAL = Path(__file__).resolve().parent
sys.path.insert(0, str(EVAL))
import slot_detector_cv as cv
from calibrate_rerank import apply_T, fit_temperature
from field_contract import collect_pairs
from rerank_prize import load_index, load_cases, pool_candidates, cand_feats, DEFAULT_INDEX, DEFAULT_TRACES
from reconstruct_position_index import load_position_index
from wall_fingerprint import load_wall_fingerprint
from spatial_address_ceiling import spatial_address, DEFAULT_POS, DEFAULT_WALL

REPO = EVAL.parent
IFC = REPO / "data" / "ifc_models" / "AdvancedProject.ifc"
OUT = REPO / "site" / "assets" / "3d"
DATASET = Path("/home/hychi/projects/cmu/master_thesis/data_curation/datasets/synth_v0.5_ap")
TAU = 0.40
MESH_CLASSES = ("IfcWallStandardCase", "IfcWall", "IfcWindow", "IfcDoor", "IfcSlab")
# showcase cases first; the rest auto-filled with covered fillers that ANSWER correctly
PINNED = ["AP_SK_102", "AP_SK_092"]


def slug(storey: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", storey.lower()).strip("_")


def extract_storey_glb(storey_name: str, out_path: Path) -> bool:
    if out_path.exists():
        print(f"  cached {out_path.name}")
        return True
    import ifcopenshell
    import ifcopenshell.geom as geom
    import ifcopenshell.util.element as eu
    import trimesh

    f = ifcopenshell.open(str(IFC))
    s = geom.settings(); s.set(s.USE_WORLD_COORDS, True)

    def storey_of(e):
        c = eu.get_container(e)
        while c and not c.is_a("IfcBuildingStorey"):
            c = eu.get_container(c)
        return c.Name if c else None

    t0 = time.time(); scene = trimesh.Scene(); n = 0
    for e in f.by_type("IfcProduct"):
        if e.is_a() not in MESH_CLASSES or storey_of(e) != storey_name:
            continue
        try:
            sh = geom.create_shape(s, e)
            v = np.array(sh.geometry.verts).reshape(-1, 3)
            fc = np.array(sh.geometry.faces).reshape(-1, 3)
            scene.add_geometry(trimesh.Trimesh(vertices=v, faces=fc),
                               node_name=e.GlobalId, geom_name=e.GlobalId)
            n += 1
        except Exception:
            pass
    if n == 0:
        print(f"  skip {storey_name}: no meshable elements")
        return False
    out_path.write_bytes(scene.export(file_type="glb"))
    print(f"  {storey_name}: {n} elements, {time.time()-t0:.0f}s, {out_path.stat().st_size/1024:.0f}KB")
    return True


IMG_MAXSIDE = 1000          # downscale long side for the web demo
IMG_QUALITY = 82


def img_rel(name: str) -> str | None:
    # page-relative (same convention as the GLB path) so it resolves on GitHub Pages
    # (page at /repo/demo.html) AND under local uvicorn (page at /). The web-sized JPEG
    # is written into site/assets/dataset/ by copy_site_images().
    p = DATASET / "imgs" / f"{name}_site.png"
    return f"assets/dataset/{name}_site.jpg" if p.exists() else None


def copy_site_images(case_ids) -> int:
    """Re-encode each case's site photo to a web-sized JPEG in site/assets/dataset/ so the
    static demo is self-contained and small enough to commit (≈8MB for 60 vs ≈120MB of PNGs)."""
    from PIL import Image
    dst = OUT.parent / "dataset"; dst.mkdir(parents=True, exist_ok=True)
    n = 0
    for cid in case_ids:
        src = DATASET / "imgs" / f"{cid}_site.png"
        if not src.exists():
            continue
        im = Image.open(src).convert("RGB")
        if max(im.size) > IMG_MAXSIDE:
            im.thumbnail((IMG_MAXSIDE, IMG_MAXSIDE), Image.LANCZOS)
        im.save(dst / f"{cid}_site.jpg", "JPEG", quality=IMG_QUALITY, optimize=True)
        n += 1
    print(f"re-encoded {n}/{len(case_ids)} site images -> {dst} (JPEG q{IMG_QUALITY}, ≤{IMG_MAXSIDE}px)")
    return n


def _vlm_constraints(c: dict) -> dict:
    """Extract the frozen VLM spatial address stored in the trace internals."""
    con = (c.get("internals") or {}).get("constraints") or {}
    return {
        "storey_name": con.get("storey_name"),
        "ifc_class": con.get("ifc_class"),
        "space_name": con.get("space_name"),
        "target_name_keyword": con.get("target_name_keyword"),
        "position_context": con.get("position_context"),
        "position_context_confidence": con.get("position_context_confidence"),
        "position_context_source": con.get("position_context_source"),
        "overall_confidence": round(float(con.get("confidence") or 0.0), 2),
        "source": con.get("source"),
        "spatial_relations": con.get("spatial_relations") or [],
    }


def _entry(sid, c, gt, idx, pos, wallfp, gslot, pred, T):
    """One manifest entry for a held-out case (filler -> realized slot; else DEFER).

    The result is computed from the FROZEN G8 trace (= what live VLM reproduces) + the
    OpenCV slot specialist, so the static page shows the *realized* neuro-symbolic
    grounding with no Modal/Neo4j. Fillers get a slot + calibrated ANSWER/DEFER; walls
    and 'other' carry no image-recoverable slot -> the system correctly DEFERs (the
    paper's negative result), but the case is still browsable in 3D (GT + look-alikes).
    """
    e = idx[gt]
    st = e.get("storey_name", "")
    is_filler = gt in gslot
    pi, pM, conf = pred(c) if is_filler else (None, None, 0.0)
    cal = apply_T(conf, T) if pi is not None else 0.0
    gi = gM = None
    match = False
    if is_filler:
        gi, gM = gslot[gt]["wall_position_index"], gslot[gt]["wall_child_total"]
        match = pi == gi and pM == gM
    pool = pool_candidates(c)
    constraints = _vlm_constraints(c)
    gf = cand_feats(gt, pool[gt], idx, pos)
    gaddr = spatial_address(gt, pos, wallfp)
    confusable = [g for g in pool
                  if cand_feats(g, pool[g], idx, pos).get("storey") == gf.get("storey")
                  and cand_feats(g, pool[g], idx, pos).get("ifc_class") == gf.get("ifc_class")]
    addr_match = [g for g in confusable if spatial_address(g, pos, wallfp) == gaddr]
    return {
        "id": sid,
        "type": "filler" if is_filler else ("wall" if e.get("ifc_class", "").startswith("IfcWall") else "other"),
        "storey": st,
        "glb": f"{slug(st)}.glb",
        "target_guid": gt,
        "ifc_class": e.get("ifc_class", "").replace("IfcWindow", "Window").replace("IfcDoor", "Door"),
        "constraints": constraints,
        "query": c["scenario"].get("query_text", ""),
        "site_img": img_rel(sid),
        "gt_slot": [gi, gM] if gi is not None else None,
        "pred_slot": [pi, pM] if pi is not None else None,
        "conf_raw": round(conf, 2),
        "conf_cal": round(cal, 2),
        "tau": TAU,
        "decision": "ANSWER" if cal >= TAU else "DEFER",
        "correct": bool(match),
        "waterfall": [
            {"stage": "retrieved pool", "n": len(pool)},
            {"stage": "+ storey + class", "n": len(confusable)},
            {"stage": "+ spatial address", "n": max(len(addr_match), 1)},
        ],
        "confusable_guids": [g for g in confusable if g != gt][:40],
    }


def build_all():
    """All-60-held-out manifest: extract every needed storey GLB (8 total, cached),
    emit a manifest entry per case. Static, offline — feeds the GitHub-Pages demo."""
    OUT.mkdir(parents=True, exist_ok=True)
    idx = load_index(DEFAULT_INDEX)
    cases = load_cases(DEFAULT_TRACES)
    pos = load_position_index(DEFAULT_POS)
    wallfp = load_wall_fingerprint(DEFAULT_WALL)
    gslot = cv.build_global_slot(idx, pos)
    pred = cv.make_predictor(idx)
    fillers = [c for c in cases if c["scenario"]["ground_truth"]["target_guid"] in gslot]
    T = fit_temperature(collect_pairs(pred, fillers, gslot))

    # every storey the 60 cases live on -> extract its GLB once (cached)
    storeys = {}
    for c in cases:
        st = idx[c["scenario"]["ground_truth"]["target_guid"]].get("storey_name", "")
        storeys.setdefault(st, slug(st))
    print(f"storeys across 60 cases: {len(storeys)} -> {sorted(storeys.values())}")
    ok = {st: extract_storey_glb(st, OUT / f"{sl}.glb") for st, sl in storeys.items()}

    manifest = []
    for c in cases:
        sid = c["scenario_id"]; gt = c["scenario"]["ground_truth"]["target_guid"]
        st = idx[gt].get("storey_name", "")
        if not ok.get(st):
            print(f"  skip {sid}: no GLB for storey {st!r}")
            continue
        manifest.append(_entry(sid, c, gt, idx, pos, wallfp, gslot, pred, T))
    copy_site_images([m["id"] for m in manifest])
    # showcase first: ANSWER+correct fillers, then the rest
    manifest.sort(key=lambda m: (m["decision"] != "ANSWER", not m["correct"], m["id"]))
    (OUT / "cases.json").write_text(json.dumps(manifest, indent=2))
    ans = sum(m["decision"] == "ANSWER" for m in manifest)
    cor = sum(m["correct"] for m in manifest)
    print(f"\nmanifest: {len(manifest)} cases -> {OUT/'cases.json'}  "
          f"(ANSWER {ans}, correct {cor})")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    idx = load_index(DEFAULT_INDEX)
    cases = load_cases(DEFAULT_TRACES)
    pos = load_position_index(DEFAULT_POS)
    wallfp = load_wall_fingerprint(DEFAULT_WALL)
    gslot = cv.build_global_slot(idx, pos)
    pred = cv.make_predictor(idx)
    fillers = [c for c in cases if c["scenario"]["ground_truth"]["target_guid"] in gslot]
    T = fit_temperature(collect_pairs(pred, fillers, gslot))
    by = {c["scenario_id"]: c for c in cases}

    # choose cases: pinned showcase + a few covered fillers that ANSWER correctly
    chosen = [s for s in PINNED if s in by]
    for c in fillers:
        sid = c["scenario_id"]
        if sid in chosen:
            continue
        gt = c["scenario"]["ground_truth"]["target_guid"]
        if gt not in pool_candidates(c):
            continue
        pi, pM, conf = pred(c)
        if pi is None:
            continue
        cal = apply_T(conf, T)
        gi, gM = gslot[gt]["wall_position_index"], gslot[gt]["wall_child_total"]
        if cal >= TAU and pi == gi and pM == gM:        # a clean ANSWER+correct case
            chosen.append(sid)
        if len(chosen) >= 6:
            break

    # extract the storeys those cases live on
    storeys = {}
    for sid in chosen:
        st = idx[by[sid]["scenario"]["ground_truth"]["target_guid"]].get("storey_name", "")
        storeys.setdefault(st, slug(st))
    print("extracting storeys:", list(storeys))
    ok = {}
    for st, sl in storeys.items():
        ok[st] = extract_storey_glb(st, OUT / f"{sl}.glb")

    # build the manifest
    manifest = []
    for sid in chosen:
        c = by[sid]; gt = c["scenario"]["ground_truth"]["target_guid"]; e = idx[gt]
        st = e.get("storey_name", "")
        if not ok.get(st):
            continue
        pi, pM, conf = pred(c)
        cal = apply_T(conf, T) if pi is not None else 0.0
        gi, gM = gslot[gt]["wall_position_index"], gslot[gt]["wall_child_total"]
        match = pi == gi and pM == gM
        # ── candidate-pool waterfall (what's happening at the backend) ──
        pool = pool_candidates(c)
        constraints = _vlm_constraints(c)
        gf = cand_feats(gt, pool[gt], idx, pos)
        gaddr = spatial_address(gt, pos, wallfp)
        confusable = [g for g in pool
                      if cand_feats(g, pool[g], idx, pos).get("storey") == gf.get("storey")
                      and cand_feats(g, pool[g], idx, pos).get("ifc_class") == gf.get("ifc_class")]
        addr_match = [g for g in confusable if spatial_address(g, pos, wallfp) == gaddr]
        manifest.append({
            "id": sid,
            "storey": st,
            "glb": f"{slug(st)}.glb",
            "target_guid": gt,
            "ifc_class": e.get("ifc_class", "").replace("IfcWindow", "Window").replace("IfcDoor", "Door"),
            "constraints": constraints,
            "query": c["scenario"].get("query_text", ""),
            "site_img": img_rel(sid),
            "gt_slot": [gi, gM],
            "pred_slot": [pi, pM] if pi is not None else None,
            "conf_raw": round(conf, 2),
            "conf_cal": round(cal, 2),
            "tau": TAU,
            "decision": "ANSWER" if cal >= TAU else "DEFER",
            "correct": bool(match),
            # backend pool waterfall: retrieved pool → +storey/class (look-alikes) → +address → target
            "waterfall": [
                {"stage": "retrieved pool", "n": len(pool)},
                {"stage": "+ storey + class", "n": len(confusable)},
                {"stage": "+ spatial address", "n": max(len(addr_match), 1)},
            ],
            # the confusable look-alikes (same storey+class) to highlight in 3D (cap for perf)
            "confusable_guids": [g for g in confusable if g != gt][:40],
        })
    (OUT / "cases.json").write_text(json.dumps(manifest, indent=2))
    print(f"\nmanifest: {len(manifest)} cases → {OUT/'cases.json'}")
    for m in manifest:
        print(f"  {m['id']:<12} {m['storey'][:16]:<16} {m['ifc_class']:<7} "
              f"pred {m['pred_slot']} gt {m['gt_slot']} {m['decision']} {'✓' if m['correct'] else '✗'}")


if __name__ == "__main__":
    if "--all" in sys.argv:
        build_all()
    else:
        main()
