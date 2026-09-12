# Benchmark

Does this package help, and what does it cost? These are the runs behind the claims in the top-level README. Reproduce them before believing any of it.

## Method

Three arms, each a real install into an isolated `HOME`, driven through the product path rather than skills copied into another client.

| arm | contents |
|---|---|
| `a1` bare copilot | nothing |
| `a2` stock nav-pilot | 10 agents, 33 skills, 17 instructions |
| `a3` nais/pilot | 2 agents, 9 skills, 2 instructions |

```bash
nav-pilot install nav-pilot     --user --source navikt/copilot   # a2
nav-pilot install nais-platform --user --source nais/pilot       # a3
```

Then `copilot -p "<task>" --model gpt-5.6-sol --agent <persona> --allow-all-tools`, with `GITHUB_TOKEN=$(gh auth token)`. The CLI reports its own `Tokens ↑` and `AI Credits`; those are the cost figures, not an estimate.

Install stock by name. `install --all` opens a picker and cancels silently without a TTY ([navikt/copilot#802](https://github.com/navikt/copilot/issues/802)).

## Suites

**Recall** (`tasks.tsv`) — three questions with verifiable answers: the Mimir base URL and `X-Scope-OrgID` value, the `Feature.yaml` top-level keys, the blast radius of a change under `modules/`.

**Authoring** (`task-auth.txt`) — write a `Feature.yaml` meeting six requirements. `grade2.py` validates it against Fasit's published JSON schema and checks each requirement.

**Rollout** (`task-rollout.txt`) — write the testing, monitoring and rollout plan for a feature-chart change. `grade-rollout.py` scores ten facts: `ci-nais` as the canary, merge is the deploy, Fasit as the delivery path, the `environmentKinds` split, on-prem, verify in dev, the platform org header, the observability host, fan-out, a back-out path.

**Go authoring** (`task-go.txt`) — add a working `resourcecreator` package to a real clone of `nais/naiserator`. Graded by `go build` and `go test`.

**Go review** (`goreview/`) — review a file carrying four defects no linter in these repos fails the build on: a blank-assigned error, user input logged unsanitised, an interface whose implementations are not updated, and a `t.Skip` on a missing database with no CI switch. `grade-gr.py` checks whether each is named.

## Results, 2026-09-13

n=2 per cell. Cost is the CLI's own `Tokens ↑`.

| suite | bare copilot | stock nav-pilot | nais/pilot |
|---|---|---|---|
| Recall | 5/6, 130k | 4/6, 204k | **6/6, 35.5k** |
| Rollout | 5.0/10, 467k | 4.5/10, 141k | **9.5/10, 54.9k** |
| Go review | 2.5/5, 66k | 2.0/5, 168k | **3.5/5, 107k** |
| Authoring | pass, 293k | pass, 553k | **pass, 276k** |
| Go authoring | **pass, 2.3m** | pass, 3.6m | pass, 3.1m |

The pattern: this package pays where the answer is in no repo, and costs where it is. Recall and rollout are large wins. Writing Go inside a checkout is a task the checkout answers, and there the package is a 35% tax for no measured gain.

Stock nav-pilot lost every suite and was never cheapest. Its 33 skills target application developers; nothing in them covers Fasit, so on `Feature.yaml` keys it spent 418.9k tokens searching, twelve times this package.

Run-to-run spread matters as much as the average. Recall was 35.3k–35.6k across six runs here; bare copilot ranged 52k–228k and stock 87k–419k.

Two facts on the rollout suite neither other arm ever produced, in four runs: that merging *is* the deploy, and where to watch it. A plan missing both reads as complete and would ship fleet-wide with nobody watching.

Two defects on the Go review suite neither other arm ever found: the unsanitised log line, and the skip with no CI switch. Both are what the Go skill exists for.

## What this does not show

- **n=2.** Directional, not a benchmark. Separating these properly needs ~50 runs per arm.
- **No user evidence.** Nobody has measured whether a Nais engineer works better with it. That is the measurement that matters and it is not here.
- **The tasks are the author's.** Five tasks, chosen by the person who wrote the package, in domains it covers.
- **One model**, `gpt-5.6-sol`.

## Three graders that lied

Stated because each would have produced a confident, wrong writeup, and all three erred in the same direction: understating the package.

An early round ran the skills inside a different client without the agent body or instructions, and reported the package **1.6× more expensive** on authoring. On the real path it is cheaper. Discarded, not averaged in.

The first authoring grader read `environmentKinds` out of a grep tool log rather than the model's answer, and scored the package 0/2 when its output was perfect. Extract the last block, not the first match.

The first Go review grader split the output on `Changes +` and truncated the findings, then scored 1.5/5 and reported the skip defect unfound — it had been named, with `REQUIRE_DB=1`, in the text the split removed. Search the whole transcript.

A measurement its author also interprets is not neutral evidence. Reading raw output caught all three; reading the summary caught none.
