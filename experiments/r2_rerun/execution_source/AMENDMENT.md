# Supplementary evaluation rerun amendment

Prepared 15 October 2026. This is a separate experiment, not a replacement of the original pilot records. No new model answers or human ratings are included.

## Reason for the rerun

The original pilot recorded intermediate completions that reached a 1,024 token allowance with empty visible content, followed by ValueError and fallback processing. The author also reports an OpenAI account deactivation notification received on 12 October 2026 at 08:28 Thailand time (01:28 UTC). The notification does not establish the cause of every historical failure. Preserve the original 540 attempts and their original statuses.

## Execution changes

- Intermediate structured calls: fixed allowance of 8,192 completion tokens instead of 1,024.
- Final answer calls: fixed allowance of 8,192 tokens for all six conditions, replacing the original varying allowances. This includes reasoning tokens where applicable; equal numeric caps do not imply equal reasoning or cost across models.
- No automatic increase in token allowance or repeated generation to obtain a successful answer. Incomplete output is retained and classified explicitly.
- OpenAI SDK automatic retries are disabled. The harness allows at most two transport attempts for connection/timeout/5xx errors, records both, and waits five seconds before a retry. Other request rejections, including unknown 429 errors, stop the batch.
- At least two seconds between starts of recorded provider requests within a process. OpenAI request timeout is 120 seconds. These settings are conservative technical defaults, not demonstrated optimal settings. Mistral SDK transport defaults may also apply.
- Account/access/quota rejection propagates through agent fallback handlers. The batch also stops after any non-ok formal run by default. Existing records are never overwritten on resume.
- Error messages, HTTP status, provider error code, request ID when exposed, traceback, completion usage, embedding events and fallback use are recorded. API keys are redacted from exception details.
- Original prompts, router coefficients, threshold, question order seed, retrieval parameters and source selection are retained. Model aliases are retained; actual response model identifiers are recorded when provided. Alias identity does not guarantee the same service snapshot across dates.
- The 20 supplied questions, source PDFs, OCR, corrected text and verification records are reused. Historical verification dates are retained. A new freeze is created only after technical checks; reference equality with the old freeze is not assumed. See input_provenance.json for hashes of packaged inputs.

## Planned execution and analysis

Six synthetic technical checks exercise ARA, Flow, Gym, grounded GPT, grounded Mistral and corrected Flow. They are excluded from the formal experiment. Change technical settings only before the new freeze and rerun the checks after any change.

Formal stage 1 comprises repetition zero: 20 questions by five methods, plus eight corrected Flow answers, giving 108 planned answers. Both human evaluators independently rate the eligible outputs using new anonymous packets. Do not transfer old ratings to new answers.

Formal stage 2 comprises repetitions one through four: 432 additional attempts. The full plan remains 540 attempts. Stage 1 alone supports quality analyses; it does not meet the original requirement of five successful repetitions per paired timing comparison.

Retain the original status eligibility rule: only ok runs enter the primary answer packet and complete-case timing. Degraded runs can contain answers, but their availability and errors must be reported separately. Do not relabel them retrospectively as ok. A recovered transport error or any fallback marks a generated answer as degraded.

Report unattempted jobs separately from failed attempts. A stopped batch has not attempted the remainder. Present completion denominators alongside answer quality. The analysis does not establish general superiority or resolve selective missingness.

Latency includes request pacing, retries and generation. Do not pool rerun timings with original timings; the execution conditions differ. If code/settings must change after freezing, preserve that folder and create a separately identified amended experiment. Do not delete freeze.json to bypass an input mismatch.

## API reference checked during preparation

OpenAI documents max_completion_tokens as including visible output and reasoning tokens:
https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create

The 8,192 allowance is a proposed technical starting point to verify, not a guarantee against truncation. Live provider operation was not tested when preparing this package.
