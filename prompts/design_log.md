# Extraction prompt — design log (Loop A)

Loop A tunes the **extraction** prompt against the deterministic metric (F1). This log
records what each iteration changed, what the data showed, and the rules we settled on.

## The variables are now STYLE, not content

As of this iteration the three prompts encode the **same rule-set**, differing only in
presentation. This turns v1/v2/v3 into a controlled ablation of prompt *style*:

| Prompt | Style | Intent |
|--------|-------|--------|
| `openai_oss_120b_prompt_v1.txt` | **terse** — bullets, token-saving | cheapest; does compression hurt? |
| `openai_oss_120b_prompt_v2.txt` | **hybrid** — bullets + brief rationale + a few examples | middle ground |
| `openai_oss_120b_prompt_v3.txt` | **verbose** — full prose, worked example, the "why" | most guidance; does it help enough to justify tokens? |

Because content is held constant, a difference in F1 is attributable to style/length.

## Results so far (gpt-oss-120b, n_shots=4, 4 runs each, v3 curated)

| Prompt | avg F1 |
|--------|--------|
| v3 (verbose) | 70.9% |
| v1 (terse)   | 70.7% |
| v2 (hybrid)  | 68.5% |

**Finding:** within noise. Prompt verbosity has a marginal effect here; the extraction
ceiling is set by the *rules* and by data/curation issues, not by how wordily we state
them. (Run-to-run variance ~6 F1 points dwarfs the v1↔v3 gap of 0.2.) → favor the terse
prompt for cost unless a verbose rule demonstrably fixes a failure mode.

## Iteration history

- **v1 (original)** — compact rules: scope, catalyst naming, unit conversions, source
  tracking, one example.
- **v2 (expansion)** — heavily expanded (~250 lines): role/persona, negative examples
  (skip literature/RSM), chemistry primer, ordered unit conversions, cross-reference
  resolution, reasoning steps, null-handling-by-field, worked example, "don't confuse
  selectivity with yield". Cut pure-FP 76→34 (precision up) but recall dropped.
- **v3 (trim)** — pared v2 back to the load-bearing parts; dropped the restated JSON
  schema (already enforced by `response_format`) and the step-by-step reasoning block.
- **v4** — (config exists; folded into this reframing).
- **now** — one canonical rule-set rendered in three styles (above), plus the rules
  below distilled from per-paper error analysis.

## The canonical rule-set (must appear in all three, styled differently)

1. Extract **this-work** experiments from text+tables; unreported = null.
2. **Skip**: literature/cited rows (Ref., [n], "et al."), RSM/optimization/DOE tables,
   figure-only data, characterization/kinetics tables (NMR, bond length, Arrhenius).
3. **Completeness**: every qualifying row → one record; don't merge or stop early.
4. **Catalyst naming**: bracket notation, no subscripts, embed stoichiometry, mixtures
   joined, none/uncatalyzed → "none"; **coded catalysts** (PIL3, IL-1) kept verbatim
   unless the paper defines a clean name.
5. **Global conditions**: values stated once (methods/footnote) apply to every row of a
   table — propagate; convert wt% / ratio / molar → grams (PET unit ≈ 192 g/mol).
6. **Placeholders**: ignore placeholder wording ("a certain amount", "specific
   temperature", symbols) — use the concrete table value, else null.
7. **Values**: temperature copied exactly (never converted); time → minutes; yield /
   selectivity / conversion are distinct fields, never swapped.
8. **Nulls**: null (not 0) when unreported; pressure null unless a number is stated.
9. **Source chunks**: list the `ID:` chunks that supplied values.

## Avoiding overfitting the prompt to the eval set

The prompt must encode **general domain rules**, never verbatim content from the papers we
score on. Early drafts leaked test-set answers — e.g. a "worked example" that reproduced the
110050 result (PIL3 → 87.3% BHET yield), and the exact column headers / catalyst strings from
our tables. That inflates F1 and measures *tuning to these 24 papers*, not extraction skill.

Rules for examples in the prompt:
- **Keep** general chemistry facts (PET repeat unit ≈ 192 g/mol; wt%→g; h→min; that yield,
  selectivity, conversion are distinct). These are domain knowledge, not leakage.
- **Genericize** every illustration: placeholder catalysts ("Cat-A", "IL-1"), schematic tables
  ("Ref. N", coded factors), and a fully synthetic worked example using letter placeholders.
- **Never** put a real (catalyst, conditions, result) tuple from the dataset into the prompt.

Related discipline: tune prompts on fixtures + a dev split, freeze, then report on the held-out
set — and be mindful that few-shot exemplars are drawn from the curated set, so they should come
from dev papers only (leave-one-out), never the paper being scored.

## Per-paper findings (evidence behind the rules)

- **10.1016/j.polymdegradstab.2022.110050** — every run scored 0. Catalysts are codes
  `PIL1–PIL5` (defined by a synthesis recipe, not a formula) and the methods use
  placeholder language ("a certain amount", "specific temperature"); real values are in
  Table 1. → rules **4 (coded catalyst verbatim)** and **6 (ignore placeholders)**.
- **10.1021/ie503677w** — high false positives (over-extraction). → reinforce rule **2**
  (skip literature/RSM/characterization rows).
- **10.1021/acssuschemeng.1c04060** — model matched catalyst/temp/time/yield/conversion
  exactly, but was rejected (MISMATCH) on **amount** fields: it correctly propagated
  `pet_amount_g=0.1` and `solvent_amount_g=0.4` (global conditions) to every row, yet the
  **curated data has those null on some rows and filled on others** — so the metric
  penalized the model for being *more* consistent than the ground truth. Also the model
  missed `catalyst_amount_g` (0.01872, from a molar ratio). → rule **5 (propagate global
  conditions + compute catalyst amount)**, AND a flag that this is a **curation
  inconsistency** and a prime **judge target**: the deterministic metric issues a false
  failure here that a human/LLM judge should overturn.

## Open items

- Curation pass: make global reaction conditions consistent across a paper's rows
  (the acssuschemeng case).
- These false-failure cases (catalyst equivalence, curation gaps) are exactly what the
  LLM judge (Loop B) is meant to catch — track them as validation targets.
