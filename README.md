# nais/pilot

An agentpakke for engineers who **build** the Nais platform.

Not for application developers deploying onto Nais — [navikt/copilot](https://github.com/navikt/copilot) ships that. Its `nais` skill is about manifests and pod troubleshooting, and its observability skill queries one tenant's application metrics. This package is about the platform itself: seven tenants, OpenTofu and Atlantis, Fasit's feature model, and the platform's own telemetry.

The difference is one header value. `X-Scope-OrgID: tenant` returns a tenant's workloads; `X-Scope-OrgID: nais` returns `nais-system`. Same endpoint, different question.

## Install

Requires [nav-pilot](https://github.com/navikt/copilot).

```bash
nav-pilot list --source nais/pilot                          # what it offers
nav-pilot install nais-platform --source nais/pilot --user  # every repo
nav-pilot install nais-platform --source nais/pilot --repo  # this repo only
```

`--repo` writes `.nav-pilot/agentpakke.lock.json` pinning the revision; commit it so the team installs the same one. `--user` is not pinned.

Add `--dry-run` first to see what lands. For OpenCode:

```bash
nav-pilot export opencode --source nais/pilot
```

## Contents

| Skill | |
|---|---|
| `nais-api` | GraphQL control plane, local development, codegen |
| `nais-tenants` | tenancy model, discovering tenants, selecting a cluster |
| `nais-terraform` | OpenTofu, Atlantis, per-tenant roots, blast radius |
| `nais-fasit` | features, `Feature.yaml`, why a merge is a deploy |
| `nais-observability` | Loki, Mimir, Tempo, and the header that decides what you get |
| `nais-system` | ambitions and initiatives as pull requests |
| `nais-change-workflow` | plan, review, implement, adversarial review, draft PR |
| `nais-adversarial-review` | six axes, a finding per axis, BLOCK/CONCERNS/CLEAN |

Two agents: `nais-platform` implements, `nais-review` reviews work it did not write. Two instructions: cross-cutting conventions, and an output style that prefers less.

### Reaching the reviewer

Honest about where this works today.

**OpenCode**: both agents are primaries; switch with Tab.

**Copilot**: `nav-pilot` launches the first declared agent, so `nais-review` is not reachable through it yet. [navikt/copilot#798](https://github.com/navikt/copilot/issues/798) tracks a `--persona` flag; until it ships, start the reviewer directly:

```bash
copilot --agent nais-review
```

A model pinned in agent frontmatter applies only to a directly launched agent — a subagent inherits its parent's model. So a reviewer invoked as a subagent of the implementer runs on the implementer's model, and the separation is of role, not of model.

## Prerequisites

The agent assumes naisdevice is connected to the target tenant and that `gh` can read the `nais` org. `nais/nais-terraform-modules`, `nais/helm-charts` and `nais/system` are internal — a 404 there means missing access, not a missing repo.

Default tenant for platform work is `dev-nais`. The skills teach discovery commands rather than hardcoded lists, so they stay correct as tenants and features change.

## Contributing

```bash
nav-pilot validate --source "$PWD"
```

Skills state the rule, then the exception. Document what the code does not show: the reason, the trap, the thing that will surprise someone. Verify against source before asserting — where a doc and the code disagree, the code wins.

## Licence

MIT. Third-party attribution in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md); what was imported, adapted and rejected is in [PROVENANCE.md](PROVENANCE.md).
