# Provenance

What in this package came from elsewhere, and what did not.

## Imported

**`skills/nais-adversarial-review`** — adapted from `navikt/grillmester`'s `review` skill (MIT), with mechanisms grafted from `ekreloff/adversarial-reviewer` (MIT). Full licence text in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

Taken: the boundary rules (resolve the base; account for untracked files and read them in full; stop on an ambiguous base), the "review primary evidence, not the implementation summary" rule, the six axes, gate discovery, and the reporting contract.

Grafted: a mandatory finding per axis, severity promotion when two axes agree, the BLOCK/CONCERNS/CLEAN verdict, and the anti-pattern list.

Added here: the platform axes — blast radius, behaviour beyond `dev-nais`, what survives the `ci-nais` canary, and generated-code consistency.

Not taken: grillmester's orchestration roles, its Inspector verdict, and `guided-review`. Those describe a workflow this package does not have.

## Not imported

Everything else is written for this package: the seven other skills, both instructions, and both agents.

## Considered and rejected

**`grill-with-docs` as vendored in `nais/fasit`.** Three reasons. It is a verbatim copy of MIT-licensed work by Matt Pocock with the copyright notice removed, so copying that copy would propagate a licence defect. It is stale — upstream split it into `grilling` and `domain-modeling` in May 2026 and retired part of the format it teaches. And it is the wrong stage: a pre-implementation planning interview that blocks on human answers per question, not a review of a diff.

The technique is good and is used in anger in `nais/fasit`. If this package grows a planning-interview skill, take it from current upstream with the notice intact.

**`obra/superpowers` `requesting-code-review`.** Instructs the reviewer to acknowledge what was done well before listing issues. Balanced summaries are the failure mode this stage exists to prevent.

**`basicmachines-co/basic-memory`'s adversarial-review.** Best-engineered candidate found, but the repository is AGPL-3.0 while the skill's frontmatter claims otherwise. Unresolvable conflict; not adopted.
