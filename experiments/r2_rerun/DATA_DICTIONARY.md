# Public data and analysis definitions

All files are UTF-8 JSON. Blank optional fields are omitted; a numeric zero is an observed zero. Numeric ratings are unchanged, apart from the explicitly supplied Evaluator 2 amendments. Free-text notes are excluded because they describe private source content.

| File | Unit and fields |
|---|---|
| data/trials.json | One completed trial. `id` joins to ratings; `qid` identifies the question; `source` is CIRCULARS or DEFENCE; `system` identifies the method; `rep` is 0–4. `elapsed_s` is end-to-end seconds including configured pacing and retries. `route`, complexity and retrieval counts are retained where recorded. UTC timestamps and freeze hash preserve provenance. |
| data/failed_attempts.json | One archived non-ok attempt before retry, including error class and elapsed time. It is excluded from successful-query median latency and retained in the attempt count. Error message bodies are withheld. |
| data/ratings.json | One evaluator–answer assessment. Evaluator is 1 or 2. Correctness is 0, 1 or 2. Citation support is supported citation links / total links; unsupported rate is unsupported claims / factual claims. Denominators are evaluator-specific. |
| data/rating_key.json | Anonymous blind-answer ID to repetition-0 trial ID. Releasing the key after ratings does not retroactively change the evaluation protocol. |
| data/ocr_page_counts.json | Edit counts and reference lengths per sampled page. Pooled CER and WER are sums of edit counts divided by sums of reference lengths. Strings are withheld. |
| data/context_comparisons.json | One FLOW–grounded baseline pair. Equality is checked on the original message objects. SHA-256 uses UTF-8 JSON with sorted keys, no extra separator whitespace, and Unicode retained. Hashes are evidence of the recorded comparison, not a substitute for releasing messages. |

## Analysis

Correctness comparisons average the two independent ratings per answer before pairing methods on the same question. No consensus or adjudicated score replaces either evaluator. Citation/claim totals remain independent and are not merged into a single count.

Latency first takes the median of all five successful repetitions for each question and method. Comparisons then use paired question medians; repetitions are not independent question samples. The reported overall latency is the mean of query medians, not the median of all 100 trial times.

Bootstrap: 10,000 percentile draws, NumPy default_rng seed 19357 reset for each contrast. For exact finite-draw reproducibility, query order follows ascending blind ID for the first method in the contrast (ARA for timing). Overall comparisons sample the CIRCULARS group then DEFENCE group in vectorized arrays, preserving 8 and 12 questions. Source-specific comparisons resample only that source. Changing row order can change finite-bootstrap endpoints slightly even when the statistical procedure is equivalent. The script fixes the order explicitly.

Intervals are exploratory and unadjusted, conditional on the selected documents. They do not capture between-document uncertainty or establish equivalence. The paired OCR comparison also changes extraction/chunking and therefore is not a pure recognition-only causal estimate.

`results/summary.json` is generated from these public numeric inputs. `execution_source/analyze.py` is an archived earlier script with private-input dependencies. Use `analyze_public.py` for public reproduction. Primary benchmark tables S1–S3 and historical pilot descriptions in the supplement are outside this supplementary analysis script's scope.

## Amendments

Evaluator 2 B050: correctness 2, citations 25 total / 24 supported, factual claims 9 / unsupported 0.

Evaluator 2 B054: correctness 2, citations 11 total / 8 supported, factual claims 7 / unsupported 3.

Evaluator 1 B050 remains correctness 1, citations 12 / 12, claims 8 / 0. Evaluator 1 B054 remains correctness 1, citations 16 / 8, claims 9 / 5. These disagreements remain visible in the released numeric records.
