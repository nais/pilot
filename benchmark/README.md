# Benchmark

Does this package help, and what does it cost? These are the runs behind the claims in the top-level README. Reproduce them before believing any of it.

## Method

Three arms, each a real install into an isolated `HOME`, driven through the actual product path, not skills copied into another client.

| arm | contents |
|---|---|
| `a1` bare copilot | nothing |
| `a2` stock nav-pilot | 10 agents, 33 skills, 17 instructions |
| `a3` nais/pilot | 2 agents, 8 skills, 2 instructions |

```bash
nav-pilot install nav-pilot     --user --source navikt/copilot   # a2
nav-pilot install nais-platform --user --source nais/pilot       # a3
```

Then `copilot -p "<task>" --model gpt-5.6-sol --agent <persona> --allow-all-tools`, with `GITHUB_TOKEN=$(gh auth token)`.

The CLI reports its own `Tokens ↑` and `AI Credits`; those are the cost figures, not an estimate.

## Suites

**Recall** (`tasks.tsv`). Three questions with verifiable answers: the Mimir base URL and `X-Scope-OrgID` value, the `Feature.yaml` top-level keys, the blast radius of a change under `modules/`.

**Authoring** (`task-auth.txt`). Write a complete `Feature.yaml` meeting six requirements. `grade2.py` grades it against Fasit's published JSON schema at `https://storage.googleapis.com/fasit-jsonschema/feature.json`, plus a check per requirement. Objective pass/fail.

## Results, 2026-09-12

Recall, n=2 per cell:

| arm | correct | avg ↑ tokens | avg credits |
|---|---|---|---|
| bare copilot | 5/6 | 129,800 | 14.37 |
| stock nav-pilot | 4/6 | 203,583 | 26.15 |
| nais/pilot | **6/6** | **35,500** | **4.00** |

Authoring, n=2 per cell. All three produced schema-valid files meeting all six requirements:

| arm | avg ↑ tokens | avg credits |
|---|---|---|
| bare copilot | 293,100 | 42.64 |
| stock nav-pilot | 552,650 | 49.20 |
| nais/pilot | **275,750** | **30.43** |

The package's advantage is largest on recall, where the answer is buried in a schema on a bucket or in a terraform tree. On authoring all three arms get there and the package mostly saves the search.

Stock nav-pilot came last on both. Its 33 skills target application developers; nothing in them covers Fasit, so on `Feature.yaml` keys it spent 418.9k tokens searching, 12× this package. On blast radius it answered wrongly twice.

Run-to-run spread matters as much as the average. This package was 35.3k–35.6k across all six recall runs; bare copilot ranged 52k–228k and stock 87k–419k.

## What this does not show

- **n=2.** Directional, not a benchmark. Separating these properly needs ~50 runs per arm.
- **No user evidence.** Nobody has measured whether a Nais engineer works better with it. That is the measurement that actually matters and it is not here.
- **Recall is the easy case.** Three questions, chosen by the package's author, in domains the package covers.
- **One model.** `gpt-5.6-sol`.

## Two graders that lied

Stated because they would have produced a confident, wrong writeup.

An earlier round ran the skills inside a different client, without the agent body or instructions, and reported the package **1.6× more expensive** on authoring. On the real path it is cheaper. That configuration is not one anyone runs; the number was discarded, not averaged in.

The first authoring grader read `environmentKinds` out of a *grep tool log* rather than the model's answer, and scored this package 0/2 when its output was perfect. Extract the last block, not the first match.
