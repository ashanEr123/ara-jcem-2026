"""Task 6 — compute PRM agreement statistics (PLAN.md §6).

Run after experts return completed workbooks as:
  experts/E1_completed.xlsx, E2_completed.xlsx, E3_completed.xlsx
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from openpyxl import load_workbook
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parents[1]))

from experiments.prm_agreement.prm_utils import (
    argmax_set,
    is_ratable,
    load_jsonl_dir,
    prm_winner_ids,
    top1_agree,
)

RUNS = ROOT / "runs"
EXPERTS = ROOT / "experts"
RESULTS_JSON = ROOT / "results.json"
RESULTS_MD = ROOT / "results.md"

BOOTSTRAP_N = 1000
BOOTSTRAP_SEED = 42
EXPERT_IDS = ("E1", "E2", "E3")
SCORE_COLS = ("usefulness (1-5)", "relevance (1-5)", "efficiency (1-5)")


def load_ratable_steps():
    steps = {}
    for rec in load_jsonl_dir(RUNS):
        if not is_ratable(rec):
            continue
        key = (rec["query_id"], rec["step"])
        steps[key] = rec
    return steps


def load_expert_ratings(path):
    wb = load_workbook(path, read_only=True, data_only=True)
    if "Ratings" not in wb.sheetnames:
        raise ValueError(f"{path} missing 'Ratings' sheet")
    ws = wb["Ratings"]
    rows = list(ws.iter_rows(values_only=True))
    wb.close()
    if not rows:
        return {}

    headers = [str(h).strip() if h is not None else "" for h in rows[0]]
    idx = {name: headers.index(name) for name in (
        "query_id", "step", "candidate_id", *SCORE_COLS
    )}

    ratings = defaultdict(dict)
    for row in rows[1:]:
        if not row or row[idx["query_id"]] is None:
            continue
        qid = str(row[idx["query_id"]]).strip()
        step = int(row[idx["step"]])
        cid = int(row[idx["candidate_id"]])
        scores = [row[idx[c]] for c in SCORE_COLS]
        if any(s is None for s in scores):
            raise ValueError(
                f"{path}: missing score for {qid} step {step} candidate {cid}"
            )
        composite = sum(float(s) for s in scores) / len(scores)
        ratings[(qid, step)][cid] = composite
    return ratings


def expert_winner_ids(ratings_for_step):
    return argmax_set(ratings_for_step.items())


def modal_winner_ids(expert_winner_sets):
    votes = Counter()
    for winners in expert_winner_sets:
        for cid in winners:
            votes[cid] += 1
    modal = {cid for cid, n in votes.items() if n >= 2}
    return modal, votes


def spearman_vec(rec, ratings_for_step):
    cands = rec.get("candidates") or []
    prm = rec.get("prm_scores") or []
    ids, prm_vals, expert_vals = [], [], []
    for i, cand in enumerate(cands):
        cid = cand["id"]
        if cid not in ratings_for_step:
            return None
        ids.append(cid)
        prm_vals.append(float(prm[i]))
        expert_vals.append(ratings_for_step[cid])
    if len(ids) < 2:
        return None
    rho, _ = spearmanr(prm_vals, expert_vals)
    return None if np.isnan(rho) else float(rho)


def build_decision_table(steps, expert_ratings):
    rows = []
    for key in sorted(steps):
        rec = steps[key]
        prm_winners = prm_winner_ids(rec)
        prm_pick = rec.get("prm_pick")
        expert_sets = []
        expert_rhos = {}
        for eid in EXPERT_IDS:
            ratings = expert_ratings[eid].get(key, {})
            expert_sets.append(expert_winner_ids(ratings))
            expert_rhos[eid] = spearman_vec(rec, ratings)

        modal, vote_counts = modal_winner_ids(expert_sets)
        has_modal = bool(modal)

        row = {
            "query_id": key[0],
            "step": key[1],
            "n_candidates": len(rec.get("candidates") or []),
            "prm_winner_ids": sorted(prm_winners),
            "prm_pick": prm_pick,
            "prm_pick_in_winner_set": prm_pick in prm_winners if prm_pick is not None else None,
            "prm_tie": len(prm_winners) > 1,
            "expert_winner_ids": {eid: sorted(s) for eid, s in zip(EXPERT_IDS, expert_sets)},
            "modal_winner_ids": sorted(modal) if has_modal else [],
            "has_modal": has_modal,
            "vote_counts": dict(vote_counts),
            "top1_prm_vs_expert": {
                eid: top1_agree(prm_winners, wins)
                for eid, wins in zip(EXPERT_IDS, expert_sets)
            },
            "top1_prm_vs_modal": top1_agree(prm_winners, modal) if has_modal else None,
            "spearman": expert_rhos,
            "fallback_used": bool(rec.get("fallback_used")),
        }
        rows.append(row)
    return rows


def mean_top1_prm_vs_experts(rows):
    vals = []
    for row in rows:
        vals.append(np.mean(list(row["top1_prm_vs_expert"].values())))
    return float(np.mean(vals)) if vals else float("nan")


def mean_top1_prm_vs_modal(rows):
    eligible = [r for r in rows if r["has_modal"]]
    if not eligible:
        return float("nan"), 0
    rate = np.mean([r["top1_prm_vs_modal"] for r in eligible])
    return float(rate), len(eligible)


def mean_spearman(rows, expert=None):
    vals = []
    for row in rows:
        if expert:
            rho = row["spearman"].get(expert)
            if rho is not None:
                vals.append(rho)
        else:
            rhos = [v for v in row["spearman"].values() if v is not None]
            if rhos:
                vals.append(np.mean(rhos))
    return float(np.mean(vals)) if vals else float("nan")


def pairwise_expert_top1(rows):
    pairs = [("E1", "E2"), ("E1", "E3"), ("E2", "E3")]
    vals = []
    for row in rows:
        for a, b in pairs:
            wins_a = set(row["expert_winner_ids"][a])
            wins_b = set(row["expert_winner_ids"][b])
            vals.append(top1_agree(wins_a, wins_b))
    return float(np.mean(vals)) if vals else float("nan")


def pairwise_expert_spearman(rows):
    pairs = [("E1", "E2"), ("E1", "E3"), ("E2", "E3")]
    vals = []
    for row in rows:
        for a, b in pairs:
            ra, rb = row["spearman"].get(a), row["spearman"].get(b)
            if ra is not None and rb is not None:
                vals.append((ra + rb) / 2)
    return float(np.mean(vals)) if vals else float("nan")


def bootstrap_ci(rows, stat_fn, n=BOOTSTRAP_N, seed=BOOTSTRAP_SEED):
    if not rows:
        return {"point": float("nan"), "ci_low": float("nan"), "ci_high": float("nan")}
    rng = np.random.default_rng(seed)
    point = stat_fn(rows)
    n_rows = len(rows)
    samples = []
    for _ in range(n):
        idx = rng.integers(0, n_rows, size=n_rows)
        sample = [rows[i] for i in idx]
        samples.append(stat_fn(sample))
    low, high = np.percentile(samples, [2.5, 97.5])
    return {"point": float(point), "ci_low": float(low), "ci_high": float(high)}


def pct(x):
    return round(100.0 * x, 1)


def write_results_md(results):
    m = results["metrics"]
    lines = [
        "# PRM agreement results",
        "",
        f"- Decision points (ratable): **{results['n_decision_points']}**",
        f"- PRM tie steps (multiple max-score winners): **{results['n_prm_tie_steps']}**",
        f"- Steps with no modal expert pick: **{results['n_no_modal_steps']}**",
        f"- Fallback rate: **{results['fallback_rate_pct']}%**",
        "",
        "## Top-1 agreement (ties treated as winner sets)",
        "",
        "| Metric | Point | 95% CI |",
        "|---|---:|---:|",
        f"| PRM vs E1 | {pct(m['top1_prm_vs_E1']['point'])}% | "
        f"[{pct(m['top1_prm_vs_E1']['ci_low'])}%, {pct(m['top1_prm_vs_E1']['ci_high'])}%] |",
        f"| PRM vs E2 | {pct(m['top1_prm_vs_E2']['point'])}% | "
        f"[{pct(m['top1_prm_vs_E2']['ci_low'])}%, {pct(m['top1_prm_vs_E2']['ci_high'])}%] |",
        f"| PRM vs E3 | {pct(m['top1_prm_vs_E3']['point'])}% | "
        f"[{pct(m['top1_prm_vs_E3']['ci_low'])}%, {pct(m['top1_prm_vs_E3']['ci_high'])}%] |",
        f"| PRM vs mean expert | {pct(m['top1_prm_vs_mean_expert']['point'])}% | "
        f"[{pct(m['top1_prm_vs_mean_expert']['ci_low'])}%, "
        f"{pct(m['top1_prm_vs_mean_expert']['ci_high'])}%] |",
        f"| PRM vs modal expert | {pct(m['top1_prm_vs_modal']['point'])}% | "
        f"[{pct(m['top1_prm_vs_modal']['ci_low'])}%, {pct(m['top1_prm_vs_modal']['ci_high'])}%] |",
        f"| Inter-expert ceiling (top-1) | {pct(m['top1_inter_expert']['point'])}% | "
        f"[{pct(m['top1_inter_expert']['ci_low'])}%, {pct(m['top1_inter_expert']['ci_high'])}%] |",
        "",
        "## Spearman ρ (PRM score vector vs expert composite vector)",
        "",
        "| Metric | ρ | 95% CI |",
        "|---|---:|---:|",
        f"| PRM vs mean expert | {m['spearman_prm_vs_mean_expert']['point']:.3f} | "
        f"[{m['spearman_prm_vs_mean_expert']['ci_low']:.3f}, "
        f"{m['spearman_prm_vs_mean_expert']['ci_high']:.3f}] |",
        f"| Inter-expert ceiling | {m['spearman_inter_expert']['point']:.3f} | "
        f"[{m['spearman_inter_expert']['ci_low']:.3f}, "
        f"{m['spearman_inter_expert']['ci_high']:.3f}] |",
        "",
        "## Sanity",
        "",
        f"- PRM top-1 ≤ inter-expert ceiling: **{results['sanity_passed']}**",
    ]
    if not results["sanity_passed"]:
        lines.append(
            "- Investigate rating forms for leaked PRM information before reporting."
        )
    RESULTS_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    completed = [EXPERTS / f"{eid}_completed.xlsx" for eid in EXPERT_IDS]
    missing = [p for p in completed if not p.exists()]
    if missing:
        sys.exit(
            "Waiting for completed expert workbooks:\n"
            + "\n".join(f"  - {p}" for p in missing)
            + "\nRename returned files to E{n}_completed.xlsx and re-run."
        )

    steps = load_ratable_steps()
    if not steps:
        sys.exit(f"No ratable steps in {RUNS}. Run run_subset.py first.")

    expert_ratings = {}
    for eid, path in zip(EXPERT_IDS, completed):
        expert_ratings[eid] = load_expert_ratings(path)

    for key in steps:
        for eid in EXPERT_IDS:
            if key not in expert_ratings[eid]:
                sys.exit(f"{eid} missing ratings for {key[0]} step {key[1]}")

    rows = build_decision_table(steps, expert_ratings)

    n_no_modal = sum(1 for r in rows if not r["has_modal"])
    n_prm_ties = sum(1 for r in rows if r["prm_tie"])
    n_fallback = sum(1 for r in rows if r["fallback_used"])

    def stat_top1_prm_e1(rs):
        return float(np.mean([r["top1_prm_vs_expert"]["E1"] for r in rs]))

    def stat_top1_prm_e2(rs):
        return float(np.mean([r["top1_prm_vs_expert"]["E2"] for r in rs]))

    def stat_top1_prm_e3(rs):
        return float(np.mean([r["top1_prm_vs_expert"]["E3"] for r in rs]))

    def stat_top1_prm_mean(rs):
        return mean_top1_prm_vs_experts(rs)

    def stat_top1_prm_modal(rs):
        eligible = [r for r in rs if r["has_modal"]]
        if not eligible:
            return float("nan")
        return float(np.mean([r["top1_prm_vs_modal"] for r in eligible]))

    metrics = {
        "top1_prm_vs_E1": bootstrap_ci(rows, stat_top1_prm_e1),
        "top1_prm_vs_E2": bootstrap_ci(rows, stat_top1_prm_e2),
        "top1_prm_vs_E3": bootstrap_ci(rows, stat_top1_prm_e3),
        "top1_prm_vs_mean_expert": bootstrap_ci(rows, stat_top1_prm_mean),
        "top1_prm_vs_modal": bootstrap_ci(rows, stat_top1_prm_modal),
        "top1_inter_expert": bootstrap_ci(rows, pairwise_expert_top1),
        "spearman_prm_vs_mean_expert": bootstrap_ci(rows, lambda rs: mean_spearman(rs)),
        "spearman_inter_expert": bootstrap_ci(rows, pairwise_expert_spearman),
    }

    prm_mean_top1 = metrics["top1_prm_vs_mean_expert"]["point"]
    inter_top1 = metrics["top1_inter_expert"]["point"]
    sanity_passed = prm_mean_top1 <= inter_top1 + 1e-9

    modal_point, modal_n = mean_top1_prm_vs_modal(rows)
    results = {
        "n_decision_points": len(rows),
        "n_no_modal_steps": n_no_modal,
        "n_modal_eligible_steps": modal_n,
        "n_prm_tie_steps": n_prm_ties,
        "fallback_rate_pct": pct(n_fallback / len(rows)) if rows else 0.0,
        "composite_score": "mean(usefulness, relevance, efficiency)",
        "tie_handling": (
            "PRM and expert argmax are sets of tied top-scoring candidate ids; "
            "top-1 agreement is true when the sets overlap."
        ),
        "metrics": metrics,
        "sanity_passed": sanity_passed,
        "decision_points": rows,
    }

    RESULTS_JSON.write_text(json.dumps(results, indent=2), encoding="utf-8")
    write_results_md(results)
    print(f"Wrote {RESULTS_JSON}")
    print(f"Wrote {RESULTS_MD}")
    print(
        f"Decision points: {len(rows)}  PRM ties: {n_prm_ties}  "
        f"no-modal: {n_no_modal}  fallback: {results['fallback_rate_pct']}%"
    )
    print(
        f"Top-1 PRM vs modal: {pct(metrics['top1_prm_vs_modal']['point'])}%  "
        f"Inter-expert ceiling: {pct(inter_top1)}%"
    )

    if not sanity_passed:
        sys.exit(
            "SANITY FAIL: PRM top-1 agreement exceeds inter-expert ceiling — "
            "investigate for leaked PRM info before reporting."
        )


if __name__ == "__main__":
    main()
