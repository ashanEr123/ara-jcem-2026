"""Calibrate the complexity weights (alpha) and routing threshold (tau) from data,
following the method in Caliberation.pdf.

  1.1 Labels: KB-sufficiency. If the CSV has 'coverage' and 'contradiction'
      columns, y = simple iff coverage >= COVERAGE_MIN and contradiction <=
      CONTRADICTION_MAX; otherwise the provided 'label' column (simple/complex)
      is used directly.
  1.2 Features: the five aggregated features x(Q) = (|T|, Ops, Depth, Amb, Dom).
  1.3 Weights: regularised logistic regression  min -loglik + lambda||alpha||^2.
      We report the PLAIN (unconstrained) fit AND a NON-NEGATIVITY-constrained fit.
      The model assumes each feature contributes non-negatively to complexity, so
      the constrained alpha is what we deploy; the unconstrained fit is a diagnostic.
  1.4 Threshold: model C(Q) per class as Gaussians and take the Bayes-optimal tau*
      (Eq. 1, equal-variance closed form). With balanced priors tau* = (mu0+mu1)/2.

Ambiguity needs corpus statistics -log p(t|D). Priority:
  (a) an existing vector-DB corpus (vectordb/corpus_stats.json from ingest.py) —
      best, because it matches deployment;
  (b) reference answers in calibration/calibration_full.csv — KB proxy, built here;
  (c) none -> Amb is constant (warned).

Usage:
  python calibrate.py                          # uses calibration_full.csv if present
  python calibrate.py --unconstrained          # deploy the plain logistic fit
  python calibrate.py --priors empirical       # use class proportions, not 50/50
  python calibrate.py path/to/set.csv
"""
import argparse
import csv
import json
import math
import os
import sys
from collections import Counter

import numpy as np

import config
from ara.preprocess import tokenize
from ara import complexity

try:
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import StratifiedKFold, cross_val_score
    from sklearn.pipeline import make_pipeline
except ImportError:
    sys.exit("scikit-learn is required: pip install scikit-learn")
try:
    from scipy.optimize import minimize
except ImportError:
    sys.exit("scipy is required: pip install scipy")

FN = complexity.FEATURES  # ["T","Ops","Depth","Amb","Dom"]
OUT_PATH = config.LEARNED_WEIGHTS_PATH


def load_data(path):
    """Return (queries, answers, labels[0/1]). Labels from coverage/contradiction
    diagnostics if present, else from the 'label' column."""
    with open(path, newline="", encoding="utf-8") as f:
        rows = [{(k or "").strip().lower(): v for k, v in r.items()}
                for r in csv.DictReader(f)]
    queries, answers, y = [], [], []
    cov_min, con_max = config.COVERAGE_MIN, config.CONTRADICTION_MAX
    use_diag = rows and "coverage" in rows[0] and "contradiction" in rows[0]
    for r in rows:
        q = (r.get("query") or "").strip()
        if not q:
            continue
        if use_diag:
            try:
                cov, con = float(r["coverage"]), float(r["contradiction"])
                label = 0 if (cov >= cov_min and con <= con_max) else 1
            except (TypeError, ValueError):
                continue
        else:
            lab = (r.get("label") or "").strip().lower()
            label = 1 if lab in ("1", "complex", "insufficient", "gym") else 0
        queries.append(q)
        answers.append((r.get("reference_answer") or r.get("answer") or "").strip())
        y.append(label)
    return queries, answers, np.array(y), use_diag


def build_amb_corpus(answers):
    """Ensure Source-A ambiguity stats exist. Prefer a real calibration KB built by
    `ingest.py --calibration` (Source A); else fall back to the calibration-set
    reference answers (a Source-A proxy), written to CALIB_STATS_PATH."""
    if os.path.exists(config.CALIB_STATS_PATH):
        print(f"Using Source-A calibration Amb stats: {config.CALIB_STATS_PATH}")
        return True
    if config.AMB_MODE == "clarity" and os.path.isdir(config.CALIB_DB_DIR):
        print(f"Using Source-A calibration index (clarity): {config.CALIB_DB_DIR}")
        return True
    text = [a for a in answers if a]
    if not text:
        print("WARNING: no Source-A calibration KB and no reference answers -> Amb constant.\n"
              "Run `python ingest.py --calibration` on Source A first.")
        return False
    print("NOTE: no calibration KB found; building Amb stats from the calibration-set "
          "reference answers (Source-A proxy). For the paper, run "
          "`python ingest.py --calibration` on the actual Source A contract.")
    tc, total = Counter(), 0
    for a in text:
        _, terms = tokenize(a)
        tc.update(terms)
        total += len(terms)
    vocab = max(len(tc), 1)
    neg_log_p = {t: round(-math.log((c + 1) / (total + vocab)), 4) for t, c in tc.items()}
    default = round(-math.log(1.0 / (total + vocab)), 4)
    os.makedirs(os.path.dirname(config.CALIB_STATS_PATH) or ".", exist_ok=True)
    with open(config.CALIB_STATS_PATH, "w") as f:
        json.dump({"total_terms": total, "default_neg_log_p": default,
                   "neg_log_p": neg_log_p, "source": "calibration reference answers (Source-A proxy)"}, f)
    print(f"Built Amb proxy stats -> {config.CALIB_STATS_PATH}")
    return True


def feature_matrix(queries):
    return np.array([[complexity.feature_vector(q)[k] for k in FN] for q in queries], float)


def fit_unconstrained(X, y, lam):
    pipe = make_pipeline(StandardScaler(),
                         LogisticRegression(C=1.0 / lam, max_iter=5000))
    pipe.fit(X, y)
    sc = pipe.named_steps["standardscaler"]
    clf = pipe.named_steps["logisticregression"]
    return clf.coef_[0] / sc.scale_, pipe


def fit_constrained(X, y, lam):
    """Regularised logistic loss with alpha >= 0 (model monotonicity)."""
    mu, sd = X.mean(0), X.std(0) + 1e-9
    Xs = (X - mu) / sd

    def nll(w):
        a, b = w[:len(FN)], w[len(FN)]
        z = Xs @ a + b
        return np.sum(np.logaddexp(0, z) - y * z) + lam * np.sum(a * a)

    bnds = [(0, None)] * len(FN) + [(None, None)]
    res = minimize(nll, np.zeros(len(FN) + 1), method="L-BFGS-B", bounds=bnds)
    return res.x[:len(FN)] / sd


def normalize_alpha(raw):
    """Scale so the |T| weight is 1.0 (paper convention; routing is scale-invariant)."""
    base = raw[0] if abs(raw[0]) > 1e-9 else (max(abs(raw)) or 1.0)
    return raw / base


def bayes_threshold(C, y, priors):
    s0, s1 = C[y == 0], C[y == 1]
    mu0, mu1 = s0.mean(), s1.mean()
    v0, v1 = s0.var(ddof=1), s1.var(ddof=1)
    sig2 = ((len(s0) - 1) * v0 + (len(s1) - 1) * v1) / (len(s0) + len(s1) - 2)
    if priors == "empirical":
        p0, p1 = len(s0) / len(y), len(s1) / len(y)
    else:
        p0 = p1 = 0.5
    tau = (mu0 + mu1) / 2.0 + (sig2 / (mu1 - mu0)) * math.log(p0 / p1)
    return tau, (mu0, math.sqrt(v0)), (mu1, math.sqrt(v1)), math.sqrt(sig2)


def main():
    ap = argparse.ArgumentParser()
    default_path = ("calibration/calibration_full.csv"
                    if os.path.exists("calibration/calibration_full.csv")
                    else "calibration/calibration_set.csv")
    ap.add_argument("path", nargs="?", default=default_path)
    ap.add_argument("--lambda", dest="lam", type=float, default=1.0)
    ap.add_argument("--unconstrained", action="store_true",
                    help="deploy the plain logistic fit instead of the non-negative one")
    ap.add_argument("--priors", choices=["balanced", "empirical"], default="balanced")
    args = ap.parse_args()

    if not os.path.exists(args.path):
        sys.exit(f"Calibration set not found: {args.path}")

    queries, answers, y, use_diag = load_data(args.path)
    n0, n1 = int((y == 0).sum()), int((y == 1).sum())
    print(f"Loaded {len(y)} queries (simple={n0}, complex={n1})  "
          f"labels from {'coverage/contradiction diagnostics' if use_diag else 'label column'}")
    if n0 == 0 or n1 == 0:
        sys.exit("Need both classes to fit.")

    build_amb_corpus(answers)
    X = feature_matrix(queries)

    print("\nPer-feature class separation (Cohen's d):")
    cohens_d = {}
    for j, n in enumerate(FN):
        a0, a1 = X[y == 0, j], X[y == 1, j]
        psd = math.sqrt(((len(a0) - 1) * a0.var(ddof=1) + (len(a1) - 1) * a1.var(ddof=1))
                        / (len(a0) + len(a1) - 2)) or 1e-9
        d = (a1.mean() - a0.mean()) / psd
        cohens_d[n] = d
        flag = "  <- negligible separation" if abs(d) < 0.2 else ""
        print(f"  {n:5s}: simple={a0.mean():6.2f}  complex={a1.mean():6.2f}  "
              f"diff={a1.mean()-a0.mean():+.2f}  d={d:+.2f}{flag}")

    # cross-validated separability (diagnostic, unconstrained)
    k = min(5, n0, n1)
    if k >= 2:
        skf = StratifiedKFold(n_splits=k, shuffle=True, random_state=0)
        pipe = make_pipeline(StandardScaler(), LogisticRegression(C=1.0 / args.lam, max_iter=5000))
        acc = cross_val_score(pipe, X, y, cv=skf, scoring="accuracy")
        try:
            auc = cross_val_score(pipe, X, y, cv=skf, scoring="roc_auc")
            auc_s = f"AUC={auc.mean():.3f}+/-{auc.std():.3f}  "
        except ValueError:
            auc_s = ""
        print(f"\n{k}-fold CV separability: {auc_s}accuracy={acc.mean():.3f}+/-{acc.std():.3f}")

    raw_unc, _ = fit_unconstrained(X, y, args.lam)
    raw_con = fit_constrained(X, y, args.lam)
    a_unc = normalize_alpha(raw_unc)
    a_con = normalize_alpha(raw_con)

    print("\nLearned alpha (normalized so a1[|T|]=1.0):")
    print(f"  {'feature':6s}  {'unconstrained':>14s}  {'non-negative':>14s}")
    for n, u, c in zip(FN, a_unc, a_con):
        flag = "  <- negative!" if u < -1e-6 else ("  <- pinned to 0" if abs(c) < 1e-6 else "")
        print(f"  {n:6s}  {u:14.3f}  {c:14.3f}{flag}")

    deploy = a_unc if args.unconstrained else a_con
    label = "unconstrained" if args.unconstrained else "non-negative (monotonic)"
    alpha = {n: round(float(a), 4) for n, a in zip(FN, deploy)}

    artifacts = [n for n in FN if abs(cohens_d[n]) < 0.2 and abs(alpha[n]) > 0.5]
    if artifacts:
        print("\nWARNING: these features received a sizeable weight despite negligible "
              "class separation (|d|<0.2) - the weight is a low-variance artifact and "
              "acts as a near-constant offset (absorbed by tau):")
        for n in artifacts:
            print(f"  {n}: weight={alpha[n]:.2f}, d={cohens_d[n]:+.2f}  "
                  f"-> consider improving this feature or setting its weight to 0")

    C = X @ np.array([alpha[n] for n in FN])
    tau, (mu0, sd0), (mu1, sd1), sig = bayes_threshold(C, y, args.priors)

    print(f"\nDeploying the {label} alpha.")
    print(f"Score distribution: simple mu={mu0:.2f} sd={sd0:.2f} | complex mu={mu1:.2f} sd={sd1:.2f}  (pooled sigma={sig:.2f})")
    print(f"Bayes-optimal threshold tau* (Eq.1, {args.priors} priors) = {tau:.2f}")

    pred = (C > tau).astype(int)
    print(f"Routing accuracy at tau*: {(pred==y).mean():.3f}  "
          f"(simple->flow {np.mean(pred[y==0]==0):.2f}, complex->gym {np.mean(pred[y==1]==1):.2f})")

    print("\nRouting accuracy vs threshold:")
    for t in np.linspace(min(mu0, mu1), max(mu0, mu1), 9):
        a = ((C > t).astype(int) == y).mean()
        mark = "  <- tau*" if abs(t - tau) <= (abs(mu1 - mu0) / 16) else ""
        print(f"  tau={t:6.2f}  acc={a:.3f}{mark}")

    os.makedirs(os.path.dirname(OUT_PATH) or ".", exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump({"alpha": alpha, "tau": round(float(tau), 2),
                   "fit": label, "priors": args.priors,
                   "n_simple": n0, "n_complex": n1,
                   "score_dist": {"simple": [round(mu0, 2), round(sd0, 2)],
                                  "complex": [round(mu1, 2), round(sd1, 2)]}}, f, indent=2)
    print(f"\nWrote {OUT_PATH}. complexity.py now uses this learned alpha and tau.")
    print("Delete that file to revert to the paper's default weights.")


if __name__ == "__main__":
    main()
