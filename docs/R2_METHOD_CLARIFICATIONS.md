# Method and interpretation clarifications — 16 October 2026

These clarifications accompany the earlier clean supplement in this repository. They do not change numeric observations or evaluator scores.

## Correctness and routing

C03 accounts for the complete supplementary mean correctness lead of ARA over FLOW and grounded GPT (0.10 points). ARA selected GYM on C03; the difference from standalone GYM is variation between separate executions of the same agentic retrieval and generation pipeline, not an effect of selecting a different pipeline. Without C03, ARA scores below GYM. The supplementary correctness results do not demonstrate an improvement attributable to routing. The same distinction applies to primary matched questions on which ARA and a comparator used the same pipeline; intended strata alone do not establish route identity.

## Abstention rubric

The authors confirmed that both evaluators awarded full correctness (2) to justified abstentions when the available corpus did not support the requested answer. A score of 0 for an unanswered question refers to an unjustified failure to answer, not a correct evidence-based abstention. This clarifies the procedure already used and does not amend scores. Where citation or factual-claim denominators are zero, corresponding rates are not applicable.

## Calibration labels

The classifier was fitted using the supplied binary calibration labels. Separate coverage and contradiction measurements were unavailable, so adherence to the proposed coverage >= 0.6 and contradiction <= 0.2 label rule cannot be verified from the retained records. The rule should not be presented as a measured and verified label-generation procedure.

## Concealment of system identities

The authors confirmed that system identities were concealed during scoring. This procedural confirmation should be distinguished from claims established by the retained forms. Anonymous evaluator IDs alone do not establish system masking. The supplied supplementary forms use blind answer identifiers and a separate answer key.

## Availability

The public R2 data are numeric derivatives, not complete raw response logs. Corpus PDFs, OCR strings, corrected transcriptions, generated answer text, retrieved passages and evaluator comments are excluded. Public numeric results can be recomputed without API access. Reassessing semantic correctness or validating OCR edit counts requires the corresponding restricted text. The earlier PRM prompt and primary artifacts remain in their existing repository paths.
