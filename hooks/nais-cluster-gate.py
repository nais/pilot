#!/usr/bin/env python3
"""preToolUse gate: refuse a cluster or observability command the machine cannot service.

Four failures look like something else from inside an agent session.

naisdevice disconnected. Every Nais cluster API sits behind a naisdevice
gateway, so `kubectl` does not fail fast. It hangs until a timeout, reports a
network error, and the agent starts debugging the cluster, the manifest or the
context instead of the tunnel.

The active tenant and the kubectl context naming different tenants. This one
does not fail at all. The command succeeds against a real cluster, just not
the one the task meant.

A Loki, Mimir or Tempo query without `X-Scope-OrgID`. There is no default org,
so the query returns 401. It fails on a header and reads like a query problem.

A value naming both orgs, `nais|tenant`. Tenant federation is off, so the
server rejects it.

## What is refused

Only what can be established, never what is guessed:

  1. A cluster or observability command while naisdevice is not connected.
  2. A cluster command whose kubectl context provably belongs to a tenant other
     than the active one.
  3. A request to a Nais host belonging to a tenant other than the active one.
     The host names its tenant, so this check is certain where the context
     check usually is not.
  4. A Loki, Mimir or Tempo query with no `X-Scope-OrgID`, or one naming both
     orgs.

Rules 3 and 4 read the command text, so they hold on a machine where the agent
cannot be reached. Grafana is not covered by rule 4: it has its own session
auth, and the header is not how one talks to it.

"Provably" is narrow because context names are tenant-dependent. From
`internal/kubeconfig/gcpcluster.go` in nais/cli: for tenant `nav` the cluster
`nais-dev` is renamed `dev-gcp` and `nais-prod` becomes `prod-gcp`; for every
other tenant the `nais-` prefix is stripped, so `nais-dev` becomes `dev`; and
`--prefix-with-tenants` puts `<tenant>-` in front of either form.

So `dev` says nothing about its tenant, and a gate that required the context to
contain the tenant name would refuse almost every correct command. Two forms
are unambiguous and only those count:

  - a context prefixed with a known tenant name that is not the active one
  - `dev-gcp` or `prod-gcp`, which exist for tenant `nav` alone, while another
    tenant is active

## What passes

Everything else, including every case the gate cannot resolve. A missing `nais`
binary, an unreachable agent socket, a timeout, unparseable output: all pass.
The nav-pilot gates follow the same rule. A preToolUse hook that fails refuses
the call, so a gate that denies when confused is worse than no gate: it blocks
work for reasons the reader cannot act on.

`kubectl config ...` is local and never refused, since `use-context` is how one
fixes the mismatch this gate reports.

`NAIS_OK=1` in front of the command passes it through. The prefix is anchored
to the start of the command so it cannot hide inside a longer chain.

## Known edges

The check runs per matching tool call and spawns `nais device status` twice,
which costs a few hundred milliseconds. There is no cache: naisdevice can drop
mid-session, and a cached "connected" is the one answer that would be wrong
when it matters.
# ponytail: no caching, add a short TTL if the latency is ever measured to hurt

The tenant comes from the naisdevice agent, so an engineer on a single-tenant
setup never sees the tenant half of this gate. Tenant switching is behind a
hidden agent setting, `nais device config set ILoveNinetiesBoybands true`,
whose help text in nais/cli reads "Enable tenant switching". Without it the
agent keeps no tenant list, so there is no active tenant to compare against.
Switching happens in the naisdevice menu; the CLI exposes status, gateway,
doctor, connect, disconnect and config, and nothing else.
"""

import json
import os
import re
import subprocess
import sys

CLUSTER = re.compile(r"\b(kubectl|k9s|stern|helm|logcli|promtool)\b")
KUBECTL_CONFIG = re.compile(r"\bkubectl\s+config\b")
NAIS_OK = re.compile(r"^\s*NAIS_OK=1\b")

# Any Nais-managed host. The tenant is the label right before cloud.nais.io,
# which holds for the central services (loki.<tenant>.cloud.nais.io) and for
# per-environment Tempo (tempo.<env>.<tenant>.cloud.nais.io) alike.
NAIS_HOST = re.compile(r"https?://([a-z0-9.-]+\.cloud\.nais\.io)", re.I)

# The three that read X-Scope-OrgID. Grafana is left out: it carries its own
# session auth, and the header is not how one talks to it.
LGTM_HOST = re.compile(r"https?://(loki|mimir|tempo)\.[a-z0-9.-]*cloud\.nais\.io", re.I)

# The header, however it is spelled: a curl -H, a logcli --org-id, an env var.
ORG_ID = re.compile(r"x-scope-orgid|--org-id|\bORG_ID=", re.I)

# A value naming both orgs at once. Tenant federation is off, so the server
# rejects it rather than merging the two.
FEDERATED = re.compile(r"x-scope-orgid\s*:\s*[^\"'\s]*\|", re.I)

# The two context names nais/cli mints only for tenant nav.
NAV_ONLY_CONTEXTS = ("dev-gcp", "prod-gcp")

TIMEOUT_SEC = 3


def command_text(node, out):
    """Collects command text recursively. Same shape as nav-pilot's gates."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key in ("command", "commandLine", "cmd", "script") and isinstance(value, str):
                out.append(value)
            else:
                command_text(value, out)
    elif isinstance(node, list):
        for item in node:
            command_text(item, out)
    return out


def run(args):
    """Runs a command and returns (returncode, stdout). None when it cannot run."""
    try:
        p = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SEC,
        )
        return p.returncode, p.stdout
    except (OSError, subprocess.SubprocessError):
        return None


def naisdevice_connected(runner):
    """True, False, or None when the answer cannot be established.

    `nais device status` exits non-zero and says "not connected to naisdevice"
    when the agent is not connected, so the exit code carries the answer.
    Do not add --quiet: it turns the disconnected case into exit 0 and no
    output, which is the one reading this gate must not get wrong.
    """
    result = runner(["nais", "device", "status"])
    if result is None:
        return None
    code, _ = result
    return code == 0


def tenants(runner):
    """(active tenant, all tenant names) from the agent, or (None, []).

    Field names come from the generated protobuf in nais/device:
    AgentStatus.Tenants, each with name and active. Key lookup is
    case-insensitive because the encoder that renders them is the CLI's
    choice, not ours.
    """
    result = runner(["nais", "device", "status", "--output", "json"])
    if result is None:
        return None, []
    code, out = result
    if code != 0 or not out.strip():
        return None, []
    try:
        status = json.loads(out)
    except ValueError:
        return None, []
    if not isinstance(status, dict):
        return None, []

    entries = []
    for key, value in status.items():
        if key.lower() == "tenants" and isinstance(value, list):
            entries = value
            break

    active, names = None, []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        name, is_active = None, False
        for key, value in entry.items():
            if key.lower() == "name" and isinstance(value, str):
                name = value
            elif key.lower() == "active":
                is_active = bool(value)
        if not name:
            continue
        names.append(name)
        if is_active:
            active = name
    return active, names


def kube_context(runner):
    result = runner(["kubectl", "config", "current-context"])
    if result is None:
        return None
    code, out = result
    if code != 0:
        return None
    return out.strip() or None


def host_tenant(command):
    """The tenant a Nais URL in the command names, or None.

    The host says it outright, which makes this the one tenant check that needs
    no agent: loki.dev-nais.cloud.nais.io is dev-nais, and
    tempo.dev.dev-nais.cloud.nais.io is dev-nais too, since the environment
    sits in front of the tenant rather than replacing it.
    """
    match = NAIS_HOST.search(command)
    if not match:
        return None
    labels = match.group(1).lower().split(".")
    try:
        cloud = labels.index("cloud")
    except ValueError:
        return None
    if cloud < 1:
        return None
    return labels[cloud - 1]


def context_tenant(context, active, known):
    """The tenant a context provably belongs to, or None when it says nothing.

    Only the two unambiguous forms answer: a known-tenant prefix, and the two
    names that exist for nav alone.
    """
    if context in NAV_ONLY_CONTEXTS:
        return "nav"
    for name in known:
        if context == name or context.startswith(name + "-"):
            return name
    return None


def decide(payload, runner=run):
    tool = str(payload.get("toolName") or payload.get("tool_name") or "")
    if not re.search(r"bash|shell|execute", tool, re.I):
        return None

    args = payload.get("toolArgs") or payload.get("tool_input") or {}
    for command in command_text(args, []):
        if not command.strip() or NAIS_OK.match(command):
            continue

        # The observability rules read the command itself, so they hold on a
        # machine where the agent cannot be reached at all.
        if LGTM_HOST.search(command):
            if FEDERATED.search(command):
                return (
                    "X-Scope-OrgID names both orgs. Tenant federation is off, so "
                    "the server rejects the value instead of merging.\n\n"
                    "  Platform data:  X-Scope-OrgID: nais\n"
                    "  Workload data:  X-Scope-OrgID: tenant\n\n"
                    "Both means two requests."
                )
            if not ORG_ID.search(command):
                return (
                    "Loki, Mimir and Tempo return 401 without X-Scope-OrgID. "
                    "There is no default org.\n\n"
                    "  Platform (nais-system, node-exporter, alerts):\n"
                    "    -H \"X-Scope-OrgID: nais\"\n"
                    "  The tenant's application workloads:\n"
                    "    -H \"X-Scope-OrgID: tenant\"\n\n"
                    "Platform work uses nais. kube_* and container_* land in both orgs."
                )

        if not CLUSTER.search(command) and not NAIS_HOST.search(command):
            continue
        # kubectl config is local, and use-context is the fix this gate names.
        if KUBECTL_CONFIG.search(command) and not re.search(
            r"\b(k9s|stern|helm)\b", command
        ):
            continue

        connected = naisdevice_connected(runner)
        if connected is False:
            return (
                "naisdevice is not connected. Every Nais cluster API sits behind "
                "its gateway, so this command would hang until it times out and "
                "then report a network error.\n\n"
                "  Connect:  nais device connect\n"
                "  Check:    nais device status\n\n"
                "Does not need the gateway? Put `NAIS_OK=1` in front of the command."
            )
        if connected is None:
            # No nais CLI, no agent socket, or a timeout. Nothing established,
            # so nothing refused.
            continue

        active, known = tenants(runner)
        if not active:
            continue

        # A URL names its tenant outright, so it is checked before the context,
        # which usually names nothing.
        url_tenant = host_tenant(command)
        if url_tenant and url_tenant in known and url_tenant != active:
            return (
                f"The active naisdevice tenant is {active}, but this request "
                f"goes to {url_tenant}. The gateway routes by tenant, so it "
                "would fail or answer for the wrong one.\n\n"
                "  Switch tenant:  the naisdevice menu. The nais CLI has no "
                "command for it.\n"
                f"  Or use the {active} host.\n\n"
                f"Meant {url_tenant}? Put `NAIS_OK=1` in front of the command."
            )

        context = kube_context(runner)
        if not context:
            continue
        belongs = context_tenant(context, active, known)
        if belongs and belongs != active:
            return (
                f"The active naisdevice tenant is {active}, but the kubectl "
                f"context {context} belongs to {belongs}. The command would "
                "succeed against the wrong tenant's cluster.\n\n"
                "  Switch tenant:      the naisdevice menu. The nais CLI has no "
                "command for it.\n"
                f"  Or switch context:  kubectl config use-context <a context for {active}>\n"
                "  List contexts:      kubectl config get-contexts\n\n"
                f"Meant {belongs}? Put `NAIS_OK=1` in front of the command."
            )
    return None


def main():
    try:
        raw = sys.stdin.read()
        debug = os.environ.get("NAV_PILOT_HOOK_DEBUG")
        if debug:
            with open(debug, "a", encoding="utf8") as fh:
                fh.write(raw.rstrip("\n") + "\n")
        payload = json.loads(raw)
        reason = decide(payload) if isinstance(payload, dict) else None
    except Exception:
        # Fail-open. A preToolUse hook that fails refuses the call, and a gate
        # that refuses everything is worse than no gate.
        reason = None

    if reason:
        json.dump(
            {
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
                "hookSpecificOutput": {
                    "hookEventName": "preToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                },
            },
            sys.stdout,
        )
    sys.exit(0)


# ─── Selftest ────────────────────────────────────────────────────────────────
# The naisdevice agent is stubbed, so the test says what the gate decides given
# a machine state, not whether this machine happens to have naisdevice running.
# Run: python3 hooks/nais-cluster-gate.py --selftest

def _payload(command, tool="bash"):
    return {"toolName": tool, "toolArgs": {"command": command}}


def _runner(connected=True, active="nav", tenant_names=("nav", "dev-nais", "ssb"),
            context="dev-gcp", missing=False):
    """A stubbed machine. missing=True is "nais is not installed"."""

    def runner(args):
        if missing:
            return None
        if args[:3] == ["nais", "device", "status"]:
            if "--output" in args:
                if not connected:
                    return 1, ""
                payload = {
                    "connectionState": "Connected",
                    "Tenants": [
                        {"name": name, "active": name == active}
                        for name in tenant_names
                    ],
                }
                return 0, json.dumps(payload)
            return (0, "Connected\n") if connected else (1, "")
        if args[:3] == ["kubectl", "config", "current-context"]:
            return (0, context + "\n") if context else (1, "")
        return None

    return runner


def _selftest():
    cases = [
        # name, payload, runner, want_deny
        ("disconnected blocks kubectl",
         _payload("kubectl get pods -n myteam"), _runner(connected=False), True),
        ("connected allows kubectl",
         _payload("kubectl get pods -n myteam"), _runner(), False),
        ("no nais binary allows",
         _payload("kubectl get pods"), _runner(missing=True), False),
        ("NAIS_OK passes through",
         _payload("NAIS_OK=1 kubectl get pods"), _runner(connected=False), False),
        ("non-cluster command ignored",
         _payload("ls -la"), _runner(connected=False), False),
        ("kubectl config is local",
         _payload("kubectl config use-context dev-gcp"), _runner(connected=False), False),
        ("nav context while ssb active",
         _payload("kubectl get pods"), _runner(active="ssb", context="prod-gcp"), True),
        ("prefixed context of another tenant",
         _payload("kubectl get pods"), _runner(active="nav", context="ssb-dev"), True),
        ("bare dev context is not judged",
         _payload("kubectl get pods"), _runner(active="ssb", context="dev"), False),
        ("nav context with nav active",
         _payload("kubectl get pods"), _runner(active="nav", context="dev-gcp"), False),
        ("prefixed context of the active tenant",
         _payload("kubectl get pods"), _runner(active="ssb", context="ssb-dev"), False),
        ("unknown context is not judged",
         _payload("kubectl get pods"), _runner(active="nav", context="kind-local"), False),
        ("no context is not judged",
         _payload("kubectl get pods"), _runner(active="nav", context=""), False),
        ("stern is a cluster command",
         _payload("stern myapp"), _runner(connected=False), True),
        ("non-bash tool ignored",
         _payload("kubectl get pods", tool="str_replace"), _runner(connected=False), False),

        # Observability. The first four need no agent at all, so they are run
        # against a machine with no nais CLI to prove it.
        ("mimir query without the header",
         _payload('curl -s "https://mimir.dev-nais.cloud.nais.io/prometheus/api/v1/query?query=up"'),
         _runner(missing=True), True),
        ("loki query with the header passes",
         _payload('curl -s -H "X-Scope-OrgID: nais" -G "https://loki.dev-nais.cloud.nais.io/loki/api/v1/query_range"'),
         _runner(missing=True), False),
        ("logcli --org-id counts as the header",
         _payload("logcli --addr=https://loki.dev-nais.cloud.nais.io --org-id=nais query '{app=\"x\"}'"),
         _runner(missing=True), False),
        ("federated org is refused",
         _payload('curl -H "X-Scope-OrgID: nais|tenant" https://mimir.dev-nais.cloud.nais.io/prometheus/api/v1/query'),
         _runner(missing=True), True),
        ("grafana is not an LGTM query host",
         _payload("curl -s https://grafana.dev-nais.cloud.nais.io/api/health"),
         _runner(missing=True), False),
        ("tempo host names the tenant behind the env",
         _payload('curl -H "X-Scope-OrgID: nais" https://tempo.dev.dev-nais.cloud.nais.io/api/search'),
         _runner(active="nav", tenant_names=("nav", "dev-nais"), context=""), True),
        ("tempo host of the active tenant passes",
         _payload('curl -H "X-Scope-OrgID: nais" https://tempo.dev.dev-nais.cloud.nais.io/api/search'),
         _runner(active="dev-nais", tenant_names=("nav", "dev-nais"), context=""), False),
        ("nais host while disconnected",
         _payload('curl -H "X-Scope-OrgID: nais" https://loki.dev-nais.cloud.nais.io/loki/api/v1/labels'),
         _runner(connected=False), True),
        ("unknown tenant in a host is not judged",
         _payload('curl -H "X-Scope-OrgID: nais" https://loki.made-up.cloud.nais.io/loki/api/v1/labels'),
         _runner(active="nav", tenant_names=("nav", "dev-nais"), context=""), False),
        ("a non-nais URL is not touched",
         _payload("curl -s https://example.com/api"), _runner(connected=False), False),
    ]

    failed = 0
    for name, payload, runner, want_deny in cases:
        got_deny = decide(payload, runner) is not None
        ok = got_deny == want_deny
        print(f"{'✅' if ok else '❌'} {name}")
        if not ok:
            failed += 1

    # The wire contract, exercised through a real subprocess: JSON in, JSON out,
    # exit 0 whichever way it decides.
    proc = subprocess.run(
        [sys.executable, __file__],
        input=json.dumps(_payload("ls -la")),
        capture_output=True,
        text=True,
    )
    wire_ok = proc.returncode == 0 and proc.stdout.strip() == ""
    print(f"{'✅' if wire_ok else '❌'} allows with empty stdout and exit 0")
    if not wire_ok:
        failed += 1

    malformed = subprocess.run(
        [sys.executable, __file__],
        input="not json",
        capture_output=True,
        text=True,
    )
    open_ok = malformed.returncode == 0 and malformed.stdout.strip() == ""
    print(f"{'✅' if open_ok else '❌'} fails open on malformed payload")
    if not open_ok:
        failed += 1

    print(f"\n{'all green' if failed == 0 else str(failed) + ' failed'}")
    return 1 if failed else 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(_selftest())
    main()
