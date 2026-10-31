# On-device models (GGUF)

The earlier safetensors weights (`Qwen3-0.6B`, `gemma-3-270m-it`, plus the 350M
candidates) were deleted. On-device inference now runs on quantised GGUF models
served by `llama-server`, which exposes an OpenAI-compatible `/v1` surface — so
the agents reach them through the same `ConfiguredEndpointProvider` as any cloud
endpoint, with no architecture-specific code.

| slot | model | quant | size | port |
|---|---|---|---|---|
| generation / translation | Qwen3.5-2B | Q4_K_M | 1.2 GB | 18081 |
| review / rubric JSON | LFM2.5-1.2B-Instruct | Q4_K_M | 697 MB | 18082 |

Weights live in `~/Models/gguf/`; the registry is `RESULTS/edge_gguf_registry.json`.

## Start / stop

```zsh
~/Models/gguf/start_edge.sh start    # both servers, waits for /health
~/Models/gguf/start_edge.sh status
~/Models/gguf/start_edge.sh stop
```

`edge-gen` is served with `--chat-template-kwargs '{"enable_thinking": false}'`;
without it the model spends its budget on reasoning tokens and blows a 60 s
timeout.

## Point the pipeline at them

```zsh
export TRANSCODER_ENDPOINT_EDGE_GEN_BASE_URL=http://127.0.0.1:18081/v1
export TRANSCODER_ENDPOINT_EDGE_GEN_MODELS=Qwen3.5-2B-Q4_K_M.gguf
export TRANSCODER_ENDPOINT_EDGE_REV_BASE_URL=http://127.0.0.1:18082/v1
export TRANSCODER_ENDPOINT_EDGE_REV_MODELS=LFM2.5-1.2B-Instruct-Q4_K_M.gguf
```

## A/B against the paper's numbers

`python RESULTS/tools/gguf_abtest.py` runs the 14 reference pairs through
`edge-gen` then `edge-rev` with the pipeline's own reviewer prompt and
validator. Result on this machine (Apple M4, 16 GB, CPU-only):

| metric | paper (Qwen3-0.6B + gemma3:270m) | GGUF pair |
|---|---|---|
| reviewer parse rate | 2/37 = 5.4% | 8/14 and 9/14 over two runs (57-64%) |
| mean BLEU (per segment) | 2.71 (G1) / 2.60 (G5) | 4.17 and 5.11 over two runs |
| median seconds per pair (translate + review) | 120.3 (G5) | 8.6-9.4 |

So the parse-rate failure reported in the paper is a property of the 270M
reviewer, not of the protocol; a 1.2B reviewer clears the schema more than ten
times as often, and a 2B translator roughly doubles BLEU at a twelfth of the
wall-clock time.

## Full-matrix rerun (Condition B)

`run_experiment.py --groups G0,G1,G4,G5 --refs-only --seed 42` with the two endpoints
above produced `RESULTS/<G>/results_s42_refs.json` (56 runs, zero errors) and
`RESULTS/gguf_matrix_summary.json`. Two bookkeeping notes: the G5 row below was recorded
under the model-flag pass policy and its file was later overwritten by the scores-policy
rerun; and all BLEU cells originally used drop semantics (a call returning an empty
translation was omitted from the mean). Under the corrected tally — empty call scores zero,
recomputed by `RESULTS/tools/recompute_empty.py`, output in
`gguf_matrix_summary_corrected.json` — G0/G1/G4 are unchanged and this G5 cell becomes
12.71:

| group | BLEU | corpus en/fr/ja | online tokens | median wall | parse |
|---|---|---|---|---|---|
| G0 cloud | 19.24 | 8.65 / 12.53 / 39.64 | 3,244 | 1.6 s | — |
| G1 edge | 7.28 | 6.66 / 0.56 / 7.27 | 0 | 4.9 s | — |
| G4 + local review | 7.18 | 6.47 / 0.55 / 6.96 | 0 | 33.7 s | 9/14 |
| G5 + online review | 9.16 | 7.05 / 2.37 / 12.91 | 35,250 | 31.6 s | 14/14 |

Legacy Condition A (0.6B + 270M) is archived under `RESULTS/archive/legacy_06b/`.

## Pass rule, threshold sweep, and the second G5 run (2026-10-20)

The reviewer reply was originally accepted only when the model's own `pass` flag was true
**and** every rubric dimension was at least 7, and any `accuracy`/`terminology` issue
blocked the review. Under that rule the 1.2B reviewer passed 0 of 14 translations even
though it scored them 8-9, because it copied `{"type": "accuracy", "span": ""}` from its
own schema while writing `"pass": true`. Two changes made the rule explicit:

- `validate_review_json(raw, threshold, policy)` and `ReviewerAgent(..., pass_threshold,
  pass_policy)`; `run_experiment.py --pass-threshold T --pass-policy scores|model|both`.
- default policy `scores`: the rubric decides, the model's boolean is advisory;
- a blocking issue now has to quote a faulty span (`span` non-empty), otherwise it is noise.

`tests/test_review_schema.py` covers all of it (10 tests, all passing).

Score criterion read off the recorded rubrics (`span` blocking excluded):

| threshold | G4 (1.2B local) | G5 (online) |
|---|---|---|
| 6.0 | 9/9 | 9/14 |
| 6.5 | 8/9 | 6/14 |
| 7.0 | 8/9 | 6/14 |
| 7.5 | 2/9 | 4/14 |

At the operating point (7.0) span blocking removes 2 G4 calls and 3 G5 calls: operational
pass counts are 6/14 (G4) and 3/14 (G5). The threshold is a weak lever; the span rule is
what moved the count.

Two G5 runs, same 14 pairs, same endpoints:

| run | BLEU | online tokens | median wall | parse | pass |
|---|---|---|---|---|---|
| seed 42, model-flag policy | 9.16 | 35,250 | 31.6 s | 14/14 | 2/14 |
| seed 42, scores policy | 12.71 | 36,096 | 36.3 s | 14/14 | 3/14 |
| seed 43, scores policy | 10.81 | 35,215 | 53.8 s | 14/14 | 1/14 |
| seed 44, scores policy | 8.06 | 33,436 | 45.0 s | 14/14 | 1/14 |
| seed 45, scores policy | 7.35 | 39,105 | 32.1 s | 14/14 | 0/14 |

The remote reviewer ignores the sampling seed, so every row is a draw. The paper pools the
four scores-policy runs (the model-flag run is excluded because its decision rule differs):
per-pair mean 9.73 BLEU, run sd 2.48, 35,963 tokens, 40.0 s, with the three empty calls
(scored zero) included. RQ1 uses per-pair deltas (+2.45, 95% CI [−0.26, 5.69], 8/14 pairs
up; without the largest, a Japanese passage, +1.30 [−0.85, 3.56]; imputing the three empty
calls instead of zeroing them would give +2.87 [0.14, 5.99]). The empty calls — seed 42's
`la-ch9-fr` and seed 45's `la-ch1-fr`/`la-ch15-fr` — were `exceed_context_size_error`
rejections (4,538–4,647-token prompts against the server's 4,096 window). Recompute with
`RESULTS/tools/recompute_empty.py`; `RESULTS/tools/pool_g5.py` predates the correction.

G4 reproduced every BLEU score exactly across the two rules while its pass count changed
from 0/14 to 6/14 and its median wall fell from 33.7 s to 20.1 s: the local generator is
deterministic, and earlier stopping removes the second and third review round.

## Ablations (Condition B, seed 42, 14 reference pairs)

| arm | reviewer | rewrite | BLEU | online tokens | wall (s) | parse | pass |
|---|---|---|---|---|---|---|---|
| G1 direct (no guard) | — | — | 7.28 | 0 | 4.9 | — | — |
| G5, one round | online | no | 7.28 | 11,559 | 18.4 | 13/14 | 0/14 |
| G4, 1.2B local | 1.2B | yes | 7.19 | 0 | 20.1 | 9/14 | 6/14 |
| G4, 2B self-review | 2B (same model) | yes | 7.14 | 0 | 63.4 | 13/14 | 9/14 |
| G5, online | online | yes | 9.73 | 35,963 | 40.0 | 14/14 | 0–3/14 |

`python run_experiment.py --groups G5 --refs-only --seed 42 --team-rounds 1` produces the
no-rewrite arm (`RESULTS/G5/results_s42_rounds1.json`); pointing
`TRANSCODER_ENDPOINT_EDGE_REV_*` at the 2B server produces the self-review arm
(`RESULTS/G4/results_s42_selfreview.json`).

Reading: the terminology/memory context alone is worth 0.00 BLEU — the one-round arm
reproduces G1 exactly once the empty call is counted; review without rewriting changes
nothing by construction (the output is the same text); rewriting on a 1.2B or on the
2B model's own critique costs 0.09–0.14 against the no-rewrite arm; only rewriting on the
online reviewer's critique gains (+2.45). The 2B self-reviewer parses and passes more often
than the 1.2B one (13/14 and 9/14) and is still the worst arm: self-agreement is not quality.

G2/G3 were not rerun: the legacy reflection prompt returned Chinese for French and Japanese
targets in 2 of 6 pilot pairs, so the arm is recorded as a failure mode instead.

Guard ablation (adds to the table above): `--no-guard` disables the terminology/memory
guard. One round, guard off: **7.17** (16,167 tokens, 8.2 s); one round, guard on: 7.28 —
the guard is worth +0.11 BLEU before rewriting, inside the run-to-run spread. Three rounds,
guard off: 12.41 against 12.71 for the same seed; the guard's contribution is not
detectable once the online reviewer drives rewrites.

Round dose-response (same first translation; 2 and 3 rounds are means over seeds 42-45):

| rounds | BLEU | tokens | pass | wall |
|---|---|---|---|---|
| 1 | 7.28 | 11,559 | 0/14 | 18.4 |
| 2 | 7.60 | 26,927 | 1/14 | 21.5 |
| 3 | 9.73 | 35,963 | 0-3/14 | 40.0 |

The second round adds 0.32 BLEU for 15,368 extra tokens; the third adds 2.14 (paired
3-vs-2 delta +2.14, 95% CI [0.61, 4.09], 11/14 pairs positive). A two-round budget is
close to no rewriting at all.

Minimal-edit guard (`--minimal-edit`): a rewrite is rejected when it changes most of the
text while the quoted spans cover little of it (`transcoder.orchestrator.is_broad_rewrite`,
4 unit tests in `tests/test_minimal_edit.py`). Seed-42 rerun: **0 of 26 rewrites rejected**,
BLEU 12.10 vs 12.71, tokens 33,816 vs 36,096 — all inside the run-to-run spread. The
remaining errors are inside the quoted spans (right advice, wrong clause), so locality
constraints cannot fix them.

Span-local rewrite (`--span-rewrite`): one call per quoted clause, spliced back only if the
replacement is single-line and at most 4x the span (`TranslatorAgent.rewrite_spans`, tests in
`tests/test_span_rewrite.py`). Seed-42 rerun: BLEU **11.74** vs 12.71, tokens **46,288** vs
36,096, pass 1 vs 3. English mean delta +0.34, but Japanese pairs (which carry the gain)
fall (26.90 -> 14.02). Locality moves the error from collateral damage to stitching and
costs 28% more tokens; full-text rewrite stays the default.
