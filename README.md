# ARA: Adaptive Retrieval-Augmented Architecture for Construction Contract Interpretation

Reproducibility artifacts for the paper:

> *A Dual-Pipeline Retrieval-Augmented Generation Architecture for Construction Contract Interpretation Using Query Complexity Assessment*
> Uduwage-Don, N.L.S., Sivanraj, S., Maung, L.M., Boteju, L.S.W., & Kudabalage, A.E. (2026).
> *Journal of Construction Engineering and Management*, ASCE. Manuscript COENG-19357.

**Persistent DOI (Zenodo):** [to be minted at final submission — Zenodo assigns a DOI when you tag the first release]
**GitHub:** https://github.com/ashanEr123/ara-jcem-2026

## What this repository is (and is not)

This repository releases the **calibration data, benchmark queries, calibrated model parameters, evaluation code, and analysis outputs** needed to reproduce the quantitative claims in the paper. It does **not** release the full ARA codebase, the source contract PDFs (which are third-party contracts not owned by the authors), or expert names.

Everything in this repository can be inspected and re-run without access to the ARA production system. Where an artifact depends on an LLM API call, we have pre-computed and released the outputs so the pipeline can be reproduced without incurring API costs.

## What you need to reproduce our results

**Software.** Python ≥ 3.10, with the packages listed in `requirements.txt` (scikit-learn, numpy, pandas, matplotlib, scipy). Install with:

```
pip install -r requirements.txt
```

**Data.** All calibration data, benchmark queries, and PRM traces are in this repository. You do **not** need access to any external corpus, third-party contract, or LLM API to reproduce the numbers in the paper — the ratings, traces, and computed scores are all pre-recorded here.

**Compute.** All scripts run in under five minutes on a laptop. No GPU required.

## Repository layout

```
ara-jcem-2026/
├── README.md                          this file
├── LICENSE                            MIT (code); CC BY 4.0 (data)
├── requirements.txt                   pinned Python dependencies
│
├── calibration/                       Section 3.2.6 of the paper
│   ├── calibration_set.csv            [1] 150-query balanced calibration set
│   ├── calibrate.py                   [2] logistic-regression + Gaussian-mixture τ script
│   └── calibration_recovered.json     [3] fitted α weights, τ, and CV diagnostics
│
├── benchmark/                         Section 4.1 of the paper
│   └── query_register.csv             [4] 30-query benchmark with strata, scores, routing
│
└── experiments/
    ├── prm_agreement/                 Section 4.2 of the paper
    │   ├── prm_prompt.txt             [5] verbatim LLM-as-judge prompt
    │   ├── runs/                      [6] per-query JSONL PRM decision traces
    │   ├── experts/                   [7] anonymised expert ratings (E1, E2, E3)
    │   ├── analyze.py                 [8] agreement analysis script
    │   └── results.json               [9] analysis outputs (top-1 agreement, ρ, CIs)
    │
    └── tau_sensitivity/               Section 4.1 and Figure 3
        ├── run.py                     [10] τ sweep script
        └── results.csv                [11] sensitivity data for Figure 3
```

Numbered items map to the artifacts listed in Section 8 (Data Availability Statement).

## Which paper number came from which file

If you want to verify a specific claim in the paper, this table tells you where to look:

| Claim in paper | Where to find it |
|---|---|
| Calibrated weights α = (1.00, 2.53, 6.99, 6.54, 0.94) — §3.2.6, Eq. 5 | `calibration/calibration_recovered.json` |
| Calibrated threshold τ = 77.27 — §3.2.6, §4.1 | `calibration/calibration_recovered.json` |
| Cross-validation AUC ≈ 0.94 — §3.2.6 | `calibration/calibration_recovered.json` |
| 30-query benchmark composition — §4.1 | `benchmark/query_register.csv` |
| Routing accuracy: 90 % overall, 70 % borderline — §4.1 | Run `experiments/tau_sensitivity/run.py` |
| Figure 3 sensitivity curves — §4.1 | `experiments/tau_sensitivity/results.csv` |
| PRM top-1 agreement 75.0 %, ρ = 0.38 — §4.2 | `experiments/prm_agreement/results.json` |
| 21 ratable decisions, 0 % fallback — §4.2 | `experiments/prm_agreement/results.json` |

## Reproducing the paper's numbers in order

**Calibration (§3.2.6).**

```
cd calibration/
python calibrate.py
```

This reads `calibration_set.csv`, fits the L2-regularised logistic regression, runs the Gaussian-mixture τ derivation, and prints the calibrated α and τ. The output should match `calibration_recovered.json` to at least three decimal places. If it doesn't, `numpy` or `scikit-learn` version drift is the likely cause; check `requirements.txt`.

**Threshold sensitivity (§4.1, Figure 3).**

```
cd experiments/tau_sensitivity/
python run.py
```

This produces `results.csv` (thirteen rows across τ ∈ [0.7·τ, 1.3·τ]) and — if `matplotlib` is installed — a PDF version of Figure 3. Confirm overall accuracy = 0.90 and borderline accuracy = 0.70 at the calibrated τ = 77.27.

**PRM agreement study (§4.2).**

```
cd experiments/prm_agreement/
python analyze.py
```

This reads the JSONL traces from `runs/` and the anonymised expert ratings from `experts/`, then computes top-1 PRM-vs-modal-expert agreement, Spearman ρ, and bootstrap 95 % CIs. Output should match `results.json`. The bootstrap uses seed = 42 for reproducibility.

## What is deliberately not in this repository

To be explicit about what has been withheld and why:

- **Source contract PDFs.** The three contract sources (ADB consultancy, FIDIC MDB steel bridge, Link Engineering adjudication file) are third-party documents whose copyright is not held by the authors. The benchmark queries and computed complexity scores are released; the source PDFs are not. Interested readers can obtain equivalent standard-form contracts directly from FIDIC and ICTAD/CIDA.
- **Full ARA production codebase.** The web-console, ingestion pipeline, and CLI orchestrator are not released. The paper's quantitative claims do not depend on these — they depend on the calibration procedure, the routing rule, and the evaluation traces, all of which are here. Interested collaborators can contact the corresponding author for the full codebase under a research collaboration agreement.
- **LLM API keys and vendor-specific configuration.** No credentials are included. The PRM traces in `runs/` are pre-recorded outputs, so no live API access is needed to reproduce the analysis.
- **Expert identities.** The five expert raters described in Table 3 and the three expert raters used in the PRM agreement study are identified by codes (E1–E5 for the main evaluation, separate E1–E3 for the agreement study). Real names, contact information, and per-rater metadata are not released. The panel composition and qualifications are described in the paper.

## Data anonymisation policy

Expert ratings in `experiments/prm_agreement/experts/` have been processed as follows before release:

- Rater names replaced with codes (E1, E2, E3)
- Email addresses, institutional affiliations, and free-text comments containing identifying information removed
- Original file metadata (Excel Author field, timestamps) stripped
- Raw ratings and scores are preserved verbatim; only identifying information has been altered

## Verifying the artifacts

Every CSV and JSON file in this repository has a corresponding SHA-256 hash listed in `manifest.sha256`. To verify:

```
sha256sum -c manifest.sha256
```

If any file has been tampered with or corrupted in transit, the check will flag it.

## Citing this artifact

If you use these artifacts, please cite both the paper and the Zenodo record:

```bibtex
@article{ara2026,
  title   = {A Dual-Pipeline Retrieval-Augmented Generation Architecture for
             Construction Contract Interpretation Using Query Complexity Assessment},
  author  = {Uduwage-Don, N.L.S. and Sivanraj, S. and Maung, L.M. and
             Boteju, L.S.W. and Kudabalage, A.E.},
  journal = {Journal of Construction Engineering and Management},
  year    = {2026},
  publisher = {ASCE},
  note    = {Manuscript COENG-19357: Under Review}
}

@dataset{ara2026_zenodo,
  title     = {ARA: Reproducibility artifacts for JCEM COENG-19357},
  author    = {Uduwage-Don, N.L.S. and Sivanraj, S. and Maung, L.M. and
               Boteju, L.S.W. and Kudabalage, A.E.},
  year      = {2026},
  publisher = {Zenodo},
  doi       = {10.5281/zenodo.21426461}
}
```

## Contact

Corresponding author: **Kudabalage Ashan Eranga**, Lecturer, School of Engineering, King Mongkut's Institute of Technology Ladkrabang, Bangkok, Thailand.
Email: ashan.ku@kmitl.ac.th

For issues with the artifacts, please open a GitHub issue rather than emailing directly — this creates a public record that helps other users.

## License

- Code (`*.py`) is released under the MIT License (see `LICENSE`).
- Data (CSV, JSON, JSONL, prompt files) is released under CC BY 4.0.
- Documentation (this README) is CC BY 4.0.

Attribution: cite the paper and the Zenodo DOI.

## Acknowledgements

The authors thank the eight domain experts whose ratings and PRM validations underpin this evaluation. Their contributions are described in the paper (Table 3, §4.2) but they are not named here to preserve rater anonymity.
