## Run metadata
- **Topic:** Open video generation models with native audio
- **Model:** claude-opus-5
- **Questions asked:** 18
- **Total model calls:** 21
- **Elapsed:** 198m 52s
- **Tokens:** 4,837 in / 204,783 out (209,620 total)
- **Est. cost (approx):** $91.7869
- **Generated:** 2026-08-20 14:26:43

---
# What we've learned about Open video generation models with native audio

## The problem in one sentence
Making two streams with wildly different structure agree about time — under a severe shortage of data showing them agreeing.

## Four constraints that generate everything else
1. **Token asymmetry (50–150:1).** Video ~16k tokens/5s at ~6 Hz; audio a few hundred at 20–90 Hz. Audio is *cheaper but temporally finer*. → twin towers, near-free cross-attention, global-audio/chunked-video for long form. Also a hazard: sparse-modality softmax collapse (fixed with audio sink tokens).
2. **Sync tolerance (~45 ms early / ~125 ms late) is finer than one video latent frame (~167 ms).** → positional encoding must index *physical time*, not array position. Plus a second asymmetry: articulation *precedes* sound, so causal masks must give video look-ahead into audio.
3. **Paired AV data is ~100× scarcer than unpaired video.** → frozen-tower, zero-init-fusion, staged curricula. This is the moat, not architecture.
4. **The joint property (correspondence) is measured far worse than marginal properties.** Most benchmark numbers are satisfiable by two uncoupled generators.

## Highest-leverage principles
- **Add capability by identity-initialization, then open gradually** (zero-init gates, frozen towers, narrow→broad schedules).
- **Index heterogeneous streams by physical quantities** — MOVA's "Aligned RoPE" (s = f_a/f_v), OmniForcing's integer-stride macro-blocks.
- **Unmeasured capabilities don't get built.** Best-validated principle here: dialogue benchmarks arrived, dialogue models followed. Evaluation shapes the frontier more than compute.
- **Always report a metric's value on real data.** Still universally unadopted — and worse under MLLM-as-judge, which has no anchor and no stable version.
- **Degradation has shape.** Causal masking preserves *local* structure (sync −2%) and destroys *global* structure (semantic coherence −15%).
- **Plan globally, render locally.** The recurring answer to every long-horizon coherence problem.

## State of play (mid-2026)
Open went from a handful of models to a broad field in ~9 months. **LTX-2** (open weights + training code, 4K/20s/stereo, mel+HiFi-GAN path, efficiency-optimized). **MOVA** (32B MoE, 14B video + 1.3B audio + 2.6B bridge, DAC-style 48 kHz continuous latent — beats LTX-2 on lip-sync and audio fidelity, exactly as the mel time-frequency argument predicts). **Ovi** at 10s with voice conditioning. Real-time streaming distillation (OmniForcing, Hallo-Live) runs ~25 FPS on one GPU — **only possible because weights were open; nobody distills an API.**

## Open problems, ranked
1. **AV any-order/editing** — V2A/A2V/inpainting from one model. Streaming is solved; editing isn't. MOVA's Dual Sigma Shift means this is now **a fine-tune, not a rebuild**.
2. **Cross-modal coherence under causality** (the AV-IB gap) — newly quantified, unclaimed.
3. **Stem separation** — three independent arguments (controllability, chunking, spatial representability); still unbuilt.
4. **Spatial *correspondence*** — benchmarks added spatial *quality* metrics and no correspondence metric, repeating the original marginal/joint error one dimension down.

Three of the top problems are **measurement** problems. That's where the leverage is.

## The meta-lesson
Every error in this walkthrough was a claim about an **absence** ("nobody does X") or a **universal** ("everyone does Y"). None was an error of mechanism. **Trust the reasoning; verify the inventory.**