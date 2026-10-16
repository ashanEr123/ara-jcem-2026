# ARA research artifacts

Reproducibility materials for the construction contract interpretation study, manuscript COENG-19357. This revision adds the completed October 2026 supplementary evaluation. The study remains a manuscript under review; no acceptance or publication is implied.

## Reproduce the supplementary analysis

From the repository root, with Python 3.10 or later:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r experiments/r2_rerun/requirements-analysis.txt
.venv\Scripts\python.exe experiments/r2_rerun/analyze_public.py
```

On macOS/Linux use `.venv/bin/python` instead. The script makes no API calls. It writes `experiments/r2_rerun/results/summary.json` from the released numeric observations. See `experiments/r2_rerun/DATA_DICTIONARY.md` for definitions and scope.

## Experiments and interpretation

The primary benchmark and the supplementary rerun are distinct experiments. Their scores and timings must not be pooled. Existing primary files in `calibration/`, `benchmark/`, and earlier `experiments/` folders remain part of the repository; this release adds supplementary artifacts without changing the earlier observations. The existing PRM prompt is available at `experiments/prm_agreement/prm_prompt.txt`. Historical threshold-sensitivity results are retained for provenance and are not validation of the current router.

Current primary routing-label agreement is 25/30 (83.3%), including 5/10 (50%) borderline agreement. The historical 90% and 70% figures in older documentation describe superseded results and must not be cited as the current configuration. Calibration used one document, Contract Document.pdf, with 116 indexed chunks. Available files and indexed evidence are distinct: the serving folder held three PDFs while its saved index held two documents and 432 chunks.

Original general-purpose GPT and Mistral conditions were ungrounded reference conditions. The new supplementary GPT_GROUNDED and MISTRAL_GROUNDED conditions use the same prompt and retrieved context as FLOW. All 200 matched comparisons had identical messages. ARA and GYM can retrieve further evidence from the same source-specific corpus; equal initial context does not imply equal retrieval effort.

The supplementary rerun contains 540 completed trials: 20 questions, five methods and five repetitions (500 trials), plus eight OCR-correction questions with five repetitions (40 trials). One failed attempt was archived before a successful retry, giving 541 recorded formal attempts. Smoke checks are excluded. Both evaluators independently rated the 108 designated repetition-0 answers, producing 216 rating rows. The other 432 completed answers provide repeated timing observations, not additional human ratings.

ARA's mean correctness was 1.90/2, compared with 1.85 for GYM, 1.80 for FLOW and grounded GPT, and 1.75 for grounded Mistral. All paired correctness intervals include zero. Mean query median latency was 39.87 seconds for ARA and 43.13 seconds for GYM. CIR-03 (original ID C03) alone accounts for the 0.10-point lead over FLOW and grounded GPT. ARA selected GYM on CIR-03 (original ID C03), so the gap from standalone GYM reflects separate executions of the same retrieval and generation pipeline, not a routing benefit. Excluding CIR-03 (original ID C03), ARA scores below GYM. The supplementary results do not demonstrate a correctness improvement attributable to routing. Latency is computational response time, not practitioner time savings.

## Files added by this release

- `experiments/r2_rerun/data/`: numeric trial records, two independent ratings, anonymous key, OCR edit counts, and hashed context comparisons.
- `experiments/r2_rerun/analyze_public.py`: offline analysis used for this public release.
- `experiments/r2_rerun/results/summary.json`: regenerated supplementary estimates.
- `experiments/r2_rerun/execution_source/`: original rerun code and settings for inspection. Private inputs are intentionally absent.
- `experiments/r2_rerun/provenance/`: original freeze hashes and release provenance.
- `docs/ARA_R2_supplement.docx`: clean supplementary document, including both primary and supplementary results.

## Access and reproducibility limits

We release numerical observations sufficient to recompute the supplementary score, agreement, timing and OCR-rate summaries. We withhold private PDFs, OCR and corrected text, questions derived from the private sources, generated answers, retrieval passages, vector databases, evaluator comments, and credentials. This prevents independent semantic re-rating and fresh answer generation from this public package alone. The OCR counts support pooled-rate calculation; validating those edit counts requires the withheld reference and OCR strings. Context hashes support comparison of the recorded hashes; independent examination of the messages requires authorized access to the original logs.

Execution code is preserved byte-for-byte from the completed archive. Its older comments and instructions are historical; use this README and the release documentation for the final results and public workflow. `execution_source/analyze.py` is the archived private-input analysis script, not the public entry point. This release does not claim that the full private execution environment is reproducible from public files alone.

## Licensing and citation

The preceding repository README declared MIT licensing for code and CC BY 4.0 for data and documentation. This update preserves those declarations and grants no rights to withheld corpus material. Cite the manuscript and the archived repository version: Rev3, https://doi.org/10.5281/zenodo.23416836. See `docs/DATA_AVAILABILITY.md` for the repository citation and public-data scope.

## Document clarifications

See `docs/R2_METHOD_CLARIFICATIONS.md` for author-confirmed rubric and reporting clarifications made after the accompanying supplement was generated. Its numeric results are unchanged.

## Identifier conventions

See `docs/IDENTIFIER_CONVENTIONS.md` for the contextual crosswalk. Supplementary Evaluator 1 is original expert PNL-01; Evaluator 2 is PNL-08. PRM labels identify workbooks and do not imply a verified correspondence to these evaluators. Original machine-readable identifiers remain unchanged.
