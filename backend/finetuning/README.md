# Qwen orchestration fine-tuning

This dataset trains only conversation, allowlisted tool selection, explicit
field extraction, and safe boundary responses. It does not train diagnosis,
treatment generation, or risk scoring.

Build and validate the tracked train/validation/test splits:

```bash
make build-qwen-data
```

On Apple Silicon, install the isolated MLX training environment and run LoRA:

```bash
make install-qwen-training
make finetune-qwen
```

Do not promote an adapter because training loss improved. First fuse/export it,
evaluate it directly with `make eval-qwen-adapter`, and compare it with the
untuned Q8 baseline from `make eval-qwen`. Only fuse and package an adapter
after it passes this gate, avoiding unnecessary model copies. Promotion
requires higher direct Qwen routing accuracy, unchanged emergency recall, a
100% JSON-contract and policy pass rate, and manual review of every extraction
failure.

## Current experiment (2026-08-27)

The untuned Docker Model Runner baseline scored 30% direct routing accuracy on
the ten-scenario local suite; deterministic hybrid reconciliation scored 100%.
The first 55-example adapter reached 60% direct accuracy but failed the output
contract and evidence checks, so it was rejected. A second 75-example adapter
reached 50% direct accuracy with 100% contract-valid and evidence-grounded
outputs. It is retained only as an experimental artifact and is **not promoted**
to the runtime. The application continues to use constrained Qwen output plus
the deterministic router and policy validator.

This is a useful negative result: the small adapter improves output discipline,
but the current dataset is not large or diverse enough to replace deterministic
tool authorization. Future runs should use a larger independently authored
holdout set and rebalance supported-route examples before changing the runtime.
