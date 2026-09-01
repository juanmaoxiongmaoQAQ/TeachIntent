# TeachIntent Release Sanity v1 — QC Summary

**Status:** Frozen for release sanity  
**Date:** 2026-09-01  
**Use:** RELEASE SANITY EVIDENCE — NOT FORMAL CONFIRMATORY EVIDENCE

## Design check

The dataset contains 12 new zh-CN cases: two for each of the six frozen
pedagogical intents. Every intent has one Standard case and one Challenging
case. The six Challenging cases are split exactly into three Cross-domain and
three Hard/Adversarial cases.

The case IDs are deterministic:

```text
RS-V1-<intent code>-<STD|CHX|CHA>-01
```

## Offline validation

- JSON parsing: PASS, 12/12 records.
- TeachIntent Input JSON Schema `1.0.0-rc.2`: PASS, 12/12.
- TeachIntent Input Pydantic validation: PASS, 12/12.
- Unique and expected case-ID set: PASS, 12/12.
- Intent, Standard/Challenging, challenge-type, and language balance: PASS.
- Duplicate and obvious lexical near-copy screen against all 30 development
  cases: PASS, zero flagged comparisons.
- No model was called during authoring or QC.

The mechanical near-copy screen applies Unicode NFKC normalization,
case-folding, exact normalized-field/input checks, whole-case SequenceMatcher
comparison, and character 5-gram Jaccard comparison. The fixed alert thresholds
are 0.70 and 0.50 respectively. The largest observed SequenceMatcher value was
0.1688; the largest observed 5-gram Jaccard value was 0.0102.

## Human-readable review

Each case was read for coherence, input completeness, intent fit, and novelty.
The content anchor supplies enough authoritative information for the requested
teaching action. Standard cases are ordinary single-turn teaching situations.
Cross-domain cases require transfer without introducing unsupported content.
Hard/Adversarial cases preserve the requested intent under pressure, frustration,
or embedded instructions.

No case copies or lightly paraphrases a development case. Topics, learner
states, and target reasoning differ materially from the nearest development
examples. The cases were authored from the frozen intent and schema contracts,
not around observed rc.1 or rc.2 outputs.

## Freeze identity

- Exact-file SHA-256:
  `2322c212230f8bf1418dfa54bf10af821725663b6caafd28de05a03fb0702031`
- Canonical logical-dataset SHA-256:
  `b3268bdf8cc4dcb75c47cb6c022335cf5c51acbdb0c3a48780aec1fc74e81c17`

Any content change requires recomputing both hashes and rerunning the complete
offline validation before generation.
