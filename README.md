# nais/pilot

An agentpakke for engineers who **build** the Nais platform.

Not for application developers deploying onto Nais. [navikt/copilot](https://github.com/navikt/copilot) ships that. Its `nais` skill is about manifests and pod troubleshooting, and its observability skill queries one tenant's application metrics. This package is about the platform itself: seven tenants, OpenTofu and Atlantis, Fasit's feature model, and the platform's own telemetry.

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

| Hook | |
|---|---|
| `nais-cluster-gate` | refuses a cluster command the machine cannot service |

### The cluster gate

`kubectl` against a Nais cluster goes through a naisdevice gateway. Disconnected, it does not fail fast: it hangs until a timeout and then reports a network error, and an agent reading that error starts debugging the cluster, the manifest or the context instead of the tunnel. Worse, a kubectl context belonging to a different tenant than the active one does not fail at all, it succeeds against the wrong cluster.

The gate stops both before the call, and refuses only what it can establish:

- naisdevice is not connected
- the context provably belongs to another tenant, which is true of a context prefixed with a known tenant name, and of `dev-gcp` and `prod-gcp`, the two names nais/cli mints for `nav` alone

Context names are tenant-dependent, so most of them prove nothing: for tenants other than `nav` the `nais-` prefix is stripped, leaving bare names like `dev`. The gate does not judge those. Anything it cannot resolve, including a machine with no `nais` CLI, passes.

`NAIS_OK=1` in front of a command passes it through.

Tenant switching needs the agent's hidden `ILoveNinetiesBoybands` setting, whose help text in nais/cli reads "Enable tenant switching":

```bash
nais device config set ILoveNinetiesBoybands true
```

Without it the agent keeps no tenant list, so there is no active tenant and only the connection half of the gate applies. Switching between tenants happens in the naisdevice menu; the CLI has no command for it.

Hooks reach Copilot only. They install into `~/.copilot/hooks/` for `--user`, or merge into `.github/hooks/copilot-hooks.json` for a repo, so an engineer running this package under opencode or pi gets the skills and agents but not the gate.

### Reaching the reviewer

**OpenCode**: both agents are primaries; switch with Tab.

**Copilot** and **pi**: pick the agent with `--persona`.

```bash
nav-pilot --persona nais-review
```

Without the flag the first declared agent starts, which is `nais-platform`. A name this package does not declare is refused with the list of those it does, rather than passed to the client. The flag needs nav-pilot from 2026-09-13 or later; before that, start the reviewer directly with `copilot --agent nais-review`.

A model pinned in agent frontmatter applies only to a directly launched agent. A subagent inherits its parent's model. So a reviewer invoked as a subagent of the implementer runs on the implementer's model, and the separation is of role, not of model.

## Prerequisites

The agent assumes naisdevice is connected to the target tenant and that `gh` can read the `nais` org. `nais/nais-terraform-modules`, `nais/helm-charts` and `nais/system` are internal: a 404 there means missing access, not a missing repo.

Default tenant for platform work is `dev-nais`. The skills teach discovery commands rather than hardcoded lists, so they stay correct as tenants and features change.

## Contributing

```bash
nav-pilot validate --source "$PWD"
```

Skills state the rule, then the exception. Document what the code does not show: the reason, the trap, the thing that will surprise someone. Verify against source before asserting. Where a doc and the code disagree, the code wins.

## Licence

MIT. Third-party attribution in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md); what was imported, adapted and rejected is in [PROVENANCE.md](PROVENANCE.md).
