"""Step B (diagnostic) — is M1b's raw confidence calibrated? Gate before any routing.

Per the enhanced module L180 ("先 gate on ECE/reliability diagram") + L188 (ECE-failure
contingency), routing is only legitimate if the detector confidence tracks correctness.
This script runs the ECE gate on the raw M1b slot confidence over the 35 held-out fillers:
reliability diagram + ECE (Guo et al. 2017, arXiv:1706.04599) + a discrimination check
(AUROC = P[conf(correct) > conf(wrong)]). AUROC < 0.5 ⇒ confidence is *anti*-correlated and
no monotonic recalibration (temperature scaling) can make it useful for soft-rerank — which
is exactly the L188 contingency, reported as a finding rather than discovered late.

Run:  .venv/bin/python eval/calibration_diag.py
Out:  output/calibration_diag.{png,json}  +  a results_ledger row (printed).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "eval"))

import slot_detector_cv as cv
from field_contract import CalibrationPair, collect_pairs
from rerank_prize import load_index, load_cases, DEFAULT_INDEX, DEFAULT_TRACES
from reconstruct_position_index import load_position_index
from spatial_address_ceiling import DEFAULT_POS

OUT = REPO / "output"


def ece(pairs: list[CalibrationPair], n_bins: int = 5) -> dict:
    """Expected Calibration Error with equal-width bins (Guo et al. 2017)."""
    N = len(pairs)
    edges = [i / n_bins for i in range(n_bins + 1)]
    bins = []
    e = 0.0
    for b in range(n_bins):
        lo, hi = edges[b], edges[b + 1]
        members = [p for p in pairs
                   if (p.confidence >= lo and (p.confidence < hi or (b == n_bins - 1 and p.confidence <= hi)))]
        if not members:
            bins.append({"lo": lo, "hi": hi, "n": 0, "conf": None, "acc": None})
            continue
        conf = sum(p.confidence for p in members) / len(members)
        acc = sum(p.correct for p in members) / len(members)
        e += (len(members) / N) * abs(acc - conf)
        bins.append({"lo": lo, "hi": hi, "n": len(members), "conf": conf, "acc": acc})
    return {"ece": e, "bins": bins, "n": N}


def auroc(pairs: list[CalibrationPair]) -> float:
    """P[conf(correct) > conf(wrong)] with ties=0.5 — discrimination of conf for correctness.
    0.5 = no signal; <0.5 = anti-correlated (higher conf predicts WRONG)."""
    pos = [p.confidence for p in pairs if p.correct]
    neg = [p.confidence for p in pairs if not p.correct]
    if not pos or not neg:
        return float("nan")
    wins = sum((c > w) + 0.5 * (c == w) for c in pos for w in neg)
    return wins / (len(pos) * len(neg))


def bootstrap_ci(pairs, fn, n_boot: int = 10000, seed: int = 0, alpha: float = 0.05):
    """Percentile bootstrap CI for a scalar statistic fn(pairs) over the n fillers.
    Returns (point, lo, hi). Honest about the small-n (35) uncertainty."""
    import numpy as np
    rng = np.random.default_rng(seed)
    n = len(pairs)
    point = fn(pairs)
    boots = []
    for _ in range(n_boot):
        sample = [pairs[i] for i in rng.integers(0, n, size=n)]
        v = fn(sample)
        if v == v:  # skip nan (degenerate resample with all-correct / all-wrong)
            boots.append(v)
    lo, hi = np.percentile(boots, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return float(point), float(lo), float(hi)


def make_figure(pairs, stats, out_path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, (axr, axs) = plt.subplots(1, 2, figsize=(12, 5))

    # (a) reliability diagram: bin confidence vs empirical accuracy
    bins = [b for b in stats["bins"] if b["n"]]
    xs = [(b["lo"] + b["hi"]) / 2 for b in bins]
    accs = [b["acc"] for b in bins]
    confs = [b["conf"] for b in bins]
    ns = [b["n"] for b in bins]
    axr.plot([0, 1], [0, 1], ls="--", c="#999", lw=1, label="perfect calibration")
    axr.bar(xs, accs, width=1 / stats["n_bins"] * 0.9, color="#1f77b4", alpha=0.7,
            edgecolor="#10456a", label="empirical accuracy")
    axr.plot(xs, confs, "o-", c="#ff7f0e", lw=2, label="mean confidence")
    for x, a, k in zip(xs, accs, ns):
        axr.text(x, a + 0.02, f"n={k}", ha="center", fontsize=8, color="#333")
    axr.set_xlim(0, 1); axr.set_ylim(0, 1)
    axr.set_xlabel("confidence bin"); axr.set_ylabel("accuracy / confidence")
    axr.set_title(f"Reliability diagram (raw M1b conf)\nECE = {stats['ece']:.3f}", fontsize=11)
    axr.legend(fontsize=8, loc="upper left")

    # (b) the anti-correlation: conf distribution for correct vs wrong
    cc = [p.confidence for p in pairs if p.correct]
    ww = [p.confidence for p in pairs if not p.correct]
    import statistics as st
    axs.hist([cc, ww], bins=8, range=(0, 1), color=["#2ca02c", "#d62728"],
             label=[f"correct (n={len(cc)}, μ={st.mean(cc):.2f})",
                    f"wrong (n={len(ww)}, μ={st.mean(ww):.2f})"])
    axs.axvline(st.mean(cc), c="#2ca02c", ls="--", lw=1.5)
    axs.axvline(st.mean(ww), c="#d62728", ls="--", lw=1.5)
    axs.set_xlabel("raw confidence"); axs.set_ylabel("# fillers")
    if stats["auroc"] < 0.5:
        verdict, sub = "ANTI-correlated", "higher conf predicts a WRONG slot — not usable"
    elif stats["auroc"] < 0.7:
        verdict, sub = "weakly +correlated", "some signal; calibration may help"
    else:
        verdict, sub = "+correlated", "higher conf predicts a correct slot — usable signal"
    axs.set_title(f"Confidence vs correctness — AUROC = {stats['auroc']:.2f} ({verdict})\n{sub}",
                  fontsize=11)
    axs.legend(fontsize=8)

    gate = "PASS — recalibrate (temperature) then soft-rerank" if stats["auroc"] >= 0.7 \
        else ("WEAK — try a geometry-margin signal" if stats["auroc"] >= 0.5
              else "FAIL — L188 contingency (anti-correlated)")
    fig.suptitle(f"Step B — ECE gate on raw M1b confidence (L180): {gate}",
                 fontsize=12, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(out_path, dpi=130)
    print(f"figure → {out_path}")


def main():
    idx = load_index(DEFAULT_INDEX)
    cases = load_cases(DEFAULT_TRACES)
    pos = load_position_index(DEFAULT_POS)
    fill = [c for c in cases if c["scenario"]["ground_truth"]["target_guid"] in pos]
    gslot = cv.build_global_slot(idx, pos)   # convention-consistent GT (detector + GT agree)
    pairs = collect_pairs(cv.make_predictor(idx), fill, gslot)

    n_bins = 5
    stats = ece(pairs, n_bins)
    stats["n_bins"] = n_bins
    stats["auroc"] = auroc(pairs)
    stats["joint_acc"] = sum(p.correct for p in pairs) / len(pairs)

    # bootstrap 95% CIs (n=35 is small — report the uncertainty, do not hide it)
    a_pt, a_lo, a_hi = bootstrap_ci(pairs, auroc)
    e_pt, e_lo, e_hi = bootstrap_ci(pairs, lambda ps: ece(ps, n_bins)["ece"])
    j_pt, j_lo, j_hi = bootstrap_ci(pairs, lambda ps: sum(p.correct for p in ps) / len(ps))
    stats["auroc_ci95"] = [round(a_lo, 3), round(a_hi, 3)]
    stats["ece_ci95"] = [round(e_lo, 3), round(e_hi, 3)]
    stats["joint_acc_ci95"] = [round(j_lo, 3), round(j_hi, 3)]

    OUT.mkdir(exist_ok=True)
    make_figure(pairs, stats, OUT / "calibration_diag.png")
    json.dump({k: v for k, v in stats.items() if k != "bins"} | {"bins": stats["bins"]},
              open(OUT / "calibration_diag.json", "w"), indent=2)

    print(f"\nn={stats['n']}  joint-acc={stats['joint_acc']:.3f} CI{stats['joint_acc_ci95']}  "
          f"ECE={stats['ece']:.3f} CI{stats['ece_ci95']}  "
          f"AUROC={stats['auroc']:.2f} CI{stats['auroc_ci95']}")
    print("verdict:", "ANTI-correlated — Step B confirms L188 contingency; raw conf NOT usable"
          if stats["auroc"] < 0.5 else "some signal — temperature scaling may help")


if __name__ == "__main__":
    main()
