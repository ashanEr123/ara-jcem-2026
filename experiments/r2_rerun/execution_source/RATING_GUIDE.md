# Independent evaluation instructions

Rate each blinded answer independently, using its verified reference and the source PDFs. Do not consult the other evaluator or infer quality from writing style. A source-grounded answer must distinguish the respondent's assertions, requested relief, circular provisions at a particular date, and illustrative calculations from established findings. An answer can be factually plausible yet unsupported by these documents.

Enter integers in every numeric field of `ratings.csv`. A blank means missing, not zero. Do not change `blind_id`.

| Field | Rule |
|---|---|
| correctness | **2**: answers all essential elements accurately, with necessary attribution/qualifications; **1**: partially correct but omits an essential element or has a nonfatal error; **0**: substantially wrong, contradicts the source, or fails to answer an answerable question. Correctly identifies missing evidence on an unanswerable question: 2. |
| citation_total | Count distinct claim–citation links, not merely unique source labels. A sentence making two separable claims with one citation has two links. Page, clause, or retrieved-passage numbers count if the target can be identified from the available context; ambiguous/unresolvable targets still count but cannot be supported. |
| citation_supported | Of those links, count those where the cited location is identifiable and supports the associated claim with the stated scope. Wrong source/page/clause or overclaiming support scores 0 for that link. Must not exceed citation_total. |
| factual_claims | Count atomic, externally checkable factual/legal/source assertions. Split compound assertions when one component could be independently false. Include numerical/arithmetic assertions and claims that evidence is absent. Exclude rhetorical transitions and explicitly hypothetical suggestions. |
| unsupported_claims | Count those factual claims not supported by the supplied source corpus, including contradiction, invented facts, unattributed party assertions presented as settled findings, and unwarranted legal generalization. Correct arithmetic from cited source figures may be supported without appearing verbatim. Must not exceed factual_claims. |
| notes | Explain correctness deductions and unsupported/unresolvable citations; identify disputed segmentation, source passages, and material errors. |

No citations: enter citation_total=0 and citation_supported=0; the support proportion is **undefined**, not 100%. An appropriately cautious abstention can be fully correct. If it contains no factual assertion, enter factual_claims=0 and unsupported_claims=0; otherwise assess its assertions normally. Unsupported claims and correctness are assessed independently; do not derive one mechanically from the other.

Use PDF page numbers, not only printed pagination. For circular questions the evaluation corpus is pages 1, 14, 16, 17, 34, 35, 36 and 39; the other pages are included in the PDF for context but are not evidence available to the systems. For the defence, all 10 pages were available.

Practice claim segmentation together on an invented example before opening the packets, then score study answers independently. Example: “The submission gives a certified value of 10 and paid value of 6, so the balance is 4.” This contains three factual claims. If one citation supports both source amounts and the arithmetic is valid, all three may be supported. Record independent scores before discussing disagreements. Do not overwrite originals with consensus ratings.
