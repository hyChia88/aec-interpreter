"""Guard the Idea-3c spatial-address ceiling: type-conditional address (filler slot + wall
fingerprint) nearly solves oracle grounding, and the wall fingerprint closes the wall subgroup."""
from pathlib import Path

import spatial_address_ceiling as sac
import rerank_prize as rp
from reconstruct_position_index import load_position_index
from wall_fingerprint import load_wall_fingerprint

REPO_ROOT = Path(__file__).resolve().parent.parent


def _run():
    idx = rp.load_index(REPO_ROOT / "data" / "references" / "element_index.jsonl")
    cases = rp.load_cases(REPO_ROOT / "eval" / "fixtures" / "traces" / "g8_posctx_dim.jsonl")
    pos = load_position_index(REPO_ROOT / "data" / "references" / "position_index.jsonl")
    wallfp = load_wall_fingerprint(REPO_ROOT / "data" / "references" / "wall_fingerprint.jsonl")
    return sac.run(idx, cases, pos, wallfp), sac.wall_ceiling(idx, cases, pos, wallfp)


def test_subgroups_cover_the_held_out():
    res, _ = _run()
    sc = res["subgroup_counts"]
    assert sc["filler"] == 35 and sc["wall"] == 22 and sc["other"] == 3  # = 60


def test_wall_fingerprint_beats_object_type():
    """The open piece: walls have no position-slot; the connection/opening/length/external
    fingerprint is their spatial address — crushes |C| where object_type can't."""
    _, wc = _run()
    assert wc["n_wall_targets"] == 22
    assert wc["coarse_median"] == 110.0
    assert wc["plus_wall_fp_median"] <= 3          # 110 -> ~2
    assert wc["plus_wall_fp_median"] < wc["plus_object_type_median"]  # beats object_type (26)
    assert wc["uniquely_id_by_wall_fp"] >= 8       # ~10/22 unique; object_type 0/22
    assert wc["uniquely_id_by_object_type"] == 0


def test_type_conditional_address_nearly_solves_oracle():
    res, _ = _run()
    m = res["metrics_overall"]
    # type-conditional spatial address is the headline: oracle Top-1 ~78, Top-10 ~98
    assert m["plus_spatial_address"]["top1"] >= 70
    assert m["plus_spatial_address"]["top10"] >= 95
    # both subgroups are now addressable
    f = res["metrics_by_subgroup"]["filler"]["plus_spatial_address"]
    w = res["metrics_by_subgroup"]["wall"]["plus_spatial_address"]
    assert f["top1"] >= 85          # fillers via position-slot
    assert w["top1"] >= 55          # walls via wall fingerprint
    assert w["top1"] > res["metrics_by_subgroup"]["wall"]["plus_object_type"]["top1"]
