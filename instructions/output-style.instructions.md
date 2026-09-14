---
applyTo: "**"
name: output-style
description: Output style for this package — short, exact, no filler
license: MIT
metadata:
  domain: style
  tags: terse output-style
---

# Less is more

Applies to everything you produce: replies, commit messages, PR bodies, comments, docs, code.

## Prose

Drop filler, hedging, preamble and summary-of-what-you-just-did. No "I'll now", no "Great question", no closing recap. Fragments are fine. Say the thing once.

Keep exact: code, identifiers, error strings, endpoints, headers, flags, numbers, units. Never compress those to save words.

Never drop a negation or a qualifier. "Only", "not", "except" carry the meaning.

## Code

Shortest change that works. No abstraction for one caller, no config for a constant, no scaffolding for later.

Comments explain **why**, never what. A comment restating the line is noise. Delete it. If the code needs a comment to be readable, fix the code first.

## Markdown, PRs, issues, comments, commits

Very brief unless asked to elaborate.

- **Commit subject**: one line, imperative, under ~60 chars. Body only when the *why* is not obvious from the diff.
- **PR body**: what and why, blast radius, what merging deploys, what the review found. Nothing else. No restating the diff.
- **Issue**: the problem, the evidence, what would resolve it. No narrative.
- **Review comment**: location, problem, fix. One line where one line does.

No status preamble, no "this PR introduces", no closing summary. If a reader can get it from the diff, leave it out.

## Docs

State the rule, then the exception. Skip the introduction. A table beats a list beats a paragraph.

Do not document what the code shows. Document what it does not: the reason, the trap, the thing that will surprise someone.

## Where to be explicit anyway

Terseness is a style, not a licence to omit. Stay full-length for:

- Blast radius and anything irreversible.
- Security and access decisions.
- Multi-step sequences where order matters.
- What you are uncertain about, and what would settle it.

Ambiguity costs more than words.
