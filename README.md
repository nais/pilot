# nais/pilot

An agentpakke for engineers who **build** the Nais platform.

It **reuses** [navikt/copilot](https://github.com/navikt/copilot), so installing it gives you Nav's agentpakke as well as this one. You do not choose between them.

Nav's half is for building applications: `klarsprak`, `code-review`, `conventional-commit`, `security-review`, the Go and GitHub Actions instructions, the `nais` skill about manifests and pod troubleshooting. This half is about the platform those applications run on: seven tenants, OpenTofu and Atlantis, Fasit's feature model, and the platform's own telemetry.

The difference between the two observability skills is one header value. `X-Scope-OrgID: tenant` returns a tenant's workloads; `X-Scope-OrgID: nais` returns `nais-system`. Same endpoint, different question.

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

Two agents: `nais-platform` implements, `nais-review` reviews work it did not write. Two instructions: `nais-platform` for cross-cutting conventions, and `output-style` for an output style that prefers less. The second deliberately shadows Nav's instruction of the same name, so one output style is loaded rather than two.

| Hook | |
|---|---|
| `nais-cluster-gate` | refuses a cluster or observability command the machine cannot service |

## Built on navikt/copilot

`.nav-pilot/agentpakke.lock.json` in this repo is the whole of it:

```json
{
  "contractVersion": "1",
  "source": "navikt/copilot",
  "sha": "6dc457badd90b781fa707f5b2a3700144859b839"
}
```

Nav's pakke is taken whole. There is no `items` block, because `items` is an allowlist: excluding a handful of artifacts means enumerating the fifty-odd that remain and then maintaining that list by hand forever, and every artifact Nav adds afterwards would silently never reach a Nais engineer. A skill that never triggers costs nothing; a skill nobody knows exists costs a person.

The pin moves by command, not by hand:

```bash
nav-pilot sync --apply
```

That rewrites the one `sha` line, so an upstream update arrives as a reviewable diff.

**When a name exists in both, the nearer one wins** — this package's. That is how `output-style` above replaces Nav's rather than stacking on it. Nothing else collides: `nais-observability` and Nav's `observability-setup` / `observability-debugging` are different skills for different scopes, and Nav's `nais` skill is for deploying onto the platform, not building it.

Only the whole-package install and `sync` compose. `install --all`, the interactive picker, and installing a single artifact by name read this repo's content alone ([navikt/copilot#844](https://github.com/navikt/copilot/issues/844)). `nav-pilot list --source nais/pilot` likewise shows only this package.

### The cluster gate

`kubectl` against a Nais cluster goes through a naisdevice gateway. Disconnected, it does not fail fast. It hangs until a timeout, reports a network error, and the agent starts debugging the cluster, the manifest or the context instead of the tunnel. A kubectl context belonging to another tenant is worse: it does not fail at all, it succeeds against the wrong cluster.

The LGTM stack adds two of the same kind. A Loki, Mimir or Tempo query without `X-Scope-OrgID` returns 401, a header failure that reads like a query problem. A value naming both orgs, `nais|tenant`, is rejected because tenant federation is off.

The gate stops all four before the call. It refuses only what it can establish:

- naisdevice is not connected
- the kubectl context provably belongs to another tenant: a context prefixed with a known tenant name, or `dev-gcp` and `prod-gcp`, the two names nais/cli mints for `nav` alone
- the URL names another tenant. `loki.<tenant>.cloud.nais.io` says which one, and `tempo.<env>.<tenant>.cloud.nais.io` still puts the tenant last, so this check is certain where the context check usually is not
- a Loki, Mimir or Tempo query has no `X-Scope-OrgID`, or names both orgs. Grafana is left out: it has its own session auth

Context names are tenant-dependent, so most prove nothing. For tenants other than `nav` the `nais-` prefix is stripped, leaving bare names like `dev`, and the gate does not judge those. Anything it cannot resolve, including a machine with no `nais` CLI, passes.

The two URL rules read the command itself, so they work when the agent cannot be reached.

`NAIS_OK=1` in front of a command passes it through.

Tenant switching needs the agent's hidden `ILoveNinetiesBoybands` setting, whose help text in nais/cli reads "Enable tenant switching":

```bash
nais device config set ILoveNinetiesBoybands true
```

Without it the agent keeps no tenant list, so there is no active tenant and only the connection half of the gate applies. Switching happens in the naisdevice menu; the CLI has no command for it.

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
