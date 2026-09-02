# TeachIntent Public Results Export

This directory contains sanitized public tables exported from existing local experiment artifacts. The exporter does not rerun Hy3 generation, Judge evaluation, or Qwen3-TTS rendering.

The tables intentionally exclude provider raw bodies, full prompt text, local absolute paths, environment files, and credentials.

## Files

| CSV | Experiment | Evidence role | Rows |
| --- | --- | --- | ---: |
| evaluator_validation_pairs.csv | Evaluator diagnostic confirmatory run 20260829T154127Z | evaluator confirmatory evidence | 24 |
| evaluator_validation_families.csv | Evaluator diagnostic confirmatory family summary | evaluator confirmatory evidence | 8 |
| generator_v0_1_baseline_results.csv | Generator v0.1 baseline evaluation 20260830T095934Z | generator baseline descriptive evidence | 30 |
| prompt_v0_2_rc1_development_results.csv | Prompt v0.2-rc.1 paired development evaluation 20260831T103707Z | prompt development evidence, not held-out confirmatory | 30 |
| prompt_v0_2_rc2_development_results.csv | Prompt v0.2-rc.2 paired development evaluation 20260901T043729Z | prompt development evidence, not held-out confirmatory | 30 |
| release_sanity_results.csv | Release sanity run 20260901T093114Z | release sanity evidence, NOT FORMAL CONFIRMATORY EVIDENCE | 12 |

## Evidence Boundaries

- Evaluator validation tables are confirmatory evidence for Evaluator v0.1 under the frozen diagnostic protocol.
- Generator v0.1 baseline results are descriptive baseline evidence over the canonical 30-case Pilot.
- Prompt v0.2-rc.1 and v0.2-rc.2 tables are development evidence on the same Pilot cases. They are not held-out confirmatory evidence.
- Release sanity is a final integration check and is explicitly NOT FORMAL CONFIRMATORY EVIDENCE.

## Related Documentation

- [Results summary](../docs/RESULTS.md)
- [Evaluation method](../docs/EVALUATION_METHOD.md)
- [Failure analysis](../docs/FAILURE_ANALYSIS.md)
