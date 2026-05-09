# Skill DPO for Format Evolution

**Date:** 2026-05-09  
**Status:** Design — schemas shipped, wiring in place

---

## Bottom Line

Every operator decision to promote or discard a proto-skill is a high-quality DPO signal. The chosen encoding (the promoted skill) beats all alternatives; the rejected encodings (discarded or edited drafts) show what loses. But whole-skill DPO only teaches the model *which* skills to keep — it doesn't teach *how to write sections well*. Section-level DPO fills that gap. When operator says "this trigger section is too generic, replace it," that preference pair trains the model to write specific, cold-agent-matchable trigger phrases for every future skill. The three schemas shipped today (skill_preference, skill_section_preference, skill_template) create a closed loop: verdicts produce pairs, pairs accumulate into templates, templates constrain new skill drafts.

---

## The Three Layers

**Layer 1 — skill_preference (whole-skill verdict).** One row per promote/discard/merge/edit decision. Captures the full SKILL.md + workflow.md verbatim at review time so section-diff mining can run automatically. The `verdict` + `rationale` fields are the DPO signal; the `skill_under_review.skill_md_content` is the training artifact. Analogous to `decision_preference.schema.json` for architectural decisions.

**Layer 2 — skill_section_preference (which paragraph wins).** One row per section comparison. The operator picks between two phrasings of the same section — "chosen" wins, "rejected" loses. The three quality scores (findability, execution_sufficiency, brevity) enable curriculum weighting: a pair with findability=0.92 is worth more for trigger-matching training than one with findability=0.55. Section pairs can be auto-mined: any two skill versions where one is promoted and the other discarded produce section pairs by diffing each section kind.

**Layer 3 — skill_template (schema that emerges).** A template is not hand-authored from scratch — it crystallizes from accumulated section_preference data. `derived_from_section_preference_count` tracks maturity. At count=3 (today's seed), the template is mostly hand-authored. At count=50+, it is data-derived and stable. Templates enforce section ordering, word-count ranges, and format constraints at draft time. A new proto-skill that violates the template fails validation before operator review.

---

## The Operator-Feedback Loop

The loop is now fully wired:

1. Operator runs `gad evolution promote <slug>` or `gad evolution discard <slug>`
2. The patched handler captures skill content before deletion, writes a `skill_preference` row to `.planning/datasets/skill-preference/<date>.jsonl`
3. The dataset curator picks up the JSONL on its next sweep
4. Delta-train consumes the new rows and adjusts the skill-writer model's priors
5. The next evolution sweep produces proto-skills that more closely match operator expectations — fewer edit-then-promote cycles, faster promotion rate

The discard path is equally load-bearing. Discarded skills teach the model what *not* to promote — redundant content, under-tested concepts, trigger phrases that over-fire. Without discard rows the model only learns positive examples.

---

## Section-Level Mining Sketch

For any pair of skill versions (A promoted, B discarded for the same concept), compute the diff per section_kind. If section A.triggers != section B.triggers, emit a `skill_section_preference` row with A as chosen and B as rejected. The `rationale_why_chosen` field can be auto-filled from the discard rationale when the discard reason maps cleanly (e.g., `trigger_too_narrow` → "triggers were too generic, see discard rationale"). Human review is a second-pass enrichment, not a gate. This means every promote+discard pair for related slugs becomes N section pairs automatically — today's 9 proto-skills, if some are discarded against promoted counterparts, could produce 30-40 section pairs without operator effort.

---

## Open Questions

1. **When does section_preference start training a skill-writer model?** The quality floor is probably 100+ operator-validated pairs per section_kind before section-level training is meaningful. At 3 seed pairs we are in data collection mode, not training mode. Target: 100 pairs by end of phase 180.

2. **Hand-curated exemplar bank.** Should promoted skills that are "exemplary" (quality_signal all > 0.9) be flagged as gold standard references for the template, separate from the training set? Risk: small gold set biases the model toward a narrow style. Benefit: clear target for new drafts.

3. **Auto-generate vs hand-curate skill_template.** Current approach: hand-curated with `derived_from_section_preference_count` as a maturity signal. Alternative: auto-generate templates from section_preference statistics (median word counts, modal formats). Auto-generation is correct at scale but noisy at low counts. Recommendation: hand-curate through count=50, then switch to auto-generation with human review gate.

4. **Rationale quality.** The `rationale` field in skill_preference rows written by `gad evolution promote/discard` is auto-generated and minimal ("Operator promoted via gad evolution promote at..."). Operator-written rationale is 5-10x more valuable. Add a `--rationale` flag to the promote/discard commands so operators who have a clear reason can capture it in one step.
