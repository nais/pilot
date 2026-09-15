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

Passing is not the same as passing quietly. See "Three answers".

`kubectl config ...` is local and never refused, since `use-context` is how one
fixes the mismatch this gate reports.

`NAIS_OK=1` in front of the command passes it through. The prefix is anchored
to the start of the command so it cannot hide inside a longer chain.

## Three answers

Connected, not connected, and not established. The third is not a shade of the
second, and collapsing the two is what this section exists to prevent.

cplt, the sandbox Nav runs coding agents in, denies unix-socket connects. Inside
it `nais device status` exits 1 with "unable to connect to naisdevice; make sure
naisdevice is running", which is byte for byte what a machine with naisdevice
stopped prints. A gate that reads that as disconnected refuses every cluster
command and advises `nais device connect`, which fails the same way: a loop with
no exit that looks like a naisdevice fault and is not one.

So the state is resolved in this order.

  1. `agent-status.json` in the naisdevice config directory, when it is present
     and fresh. nais/device#564 has the agent write it at startup, on every
     transition, and on a `heartbeatSeconds` ticker in between. A sandbox that
     will not open a socket will read a file.
  2. `nais device status`, when the file is not there. That is every machine
     until a naisdevice with #564 is released. Exit 0 is connected; "not
     connected to naisdevice" is the agent saying no; "unable to connect to
     naisdevice" is a stopped agent on a laptop and the blocked socket inside
     cplt, told apart by `__CPLT_WRAPPED`, which cplt sets in every process it
     wraps.
  3. Neither. Stale file, unreadable file, no CLI, an unreachable socket inside
     cplt: the gate says it is not enforcing, and gets out of the way.

Fresh means `updatedAt` is within `STALE_HEARTBEATS` × `heartbeatSeconds`, read
from the payload rather than assumed, because the agent owns that cadence. The
file survives a kill, so a stale file is an ordinary outcome rather than a
corrupt one, and its `connectionState` says what was true when the agent died.

Case 3 allows and says so as `additionalContext`, which is what the model
reads; stderr from a hook that exits 0 reaches nobody in Copilot CLI (measured,
1.0.83). The fail-open rule stands, but a user who believes the tenant rules are
being enforced while they are not is the failure the whole check exists to
prevent, so it does not get to be silent. In full the first time in a session,
one line after that: the same ten lines on every call is a notice nobody reads.

The file carries no secrets, which is the other reason to prefer it:
`nais device status --output json` puts the live session token in
`Tenants[].session.key`.

## Known edges

The check runs per matching tool call. When the status file answers, that costs
one open; when it does not, it spawns `nais device status` twice, a few hundred
milliseconds. There is no cache: naisdevice can drop mid-session, and a cached
"connected" is the one answer that would be wrong when it matters.
# ponytail: no caching, add a short TTL if the latency is ever measured to hurt

The tenant comes from the naisdevice agent, which reports domains rather than
the short names the rest of the platform uses, so every name goes through
`short_name` before it is compared. Tenant switching is behind a hidden agent
setting, `nais device config set ILoveNinetiesBoybands true`, whose help text in
nais/cli reads "Enable tenant switching". Without it `runtimeconfig.go` still
seeds one compiled-in tenant, `NAV`, marked active, so an engineer on a
single-tenant setup has an active tenant and sees only the contexts it matches.
Switching happens in the naisdevice menu; the CLI exposes status, gateway,
doctor, connect, disconnect and config, and nothing else.
"""

import collections
import datetime
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

# The agent reports domains, not the short names that appear in hosts, cluster
# names and kubectl contexts. `runtimeconfig.go` seeds the list with the
# compiled-in `NAV`, and `PopulateTenants` appends the object names of the
# `naisdevice-enroll-discovery` bucket, which are `nav.no`, `dev-nais.io`,
# `ssb.no` and the rest. Comparing those against `dev-nais` or `ssb-dev` never
# matches, so both tenant rules below were dead until this was normalised.
#
# The short name is the label in the tenant's console URL, from
# storage.googleapis.com/nais-tenant-data/<domain>.json:
#
#   arbeidstilsynet.no        console.atil.cloud.nais.io       atil
#   ci-nais.io                console.ci-nais.cloud.nais.io    ci-nais
#   dev-nais.io               console.dev-nais.cloud.nais.io   dev-nais
#   landbruksdirektoratet.no  console.ldir.cloud.nais.io       ldir
#   miljodir.no               console.miljodir.cloud.nais.io   miljodir
#   nav.no                    console.nav.cloud.nais.io        nav
#   ssb.no                    console.ssb.cloud.nais.io        ssb
#   test-nais.no              console.test-nais.cloud.nais.io  test-nais
#
# Six of the eight are the domain with its suffix dropped. That is the rule;
# these two are the exceptions. A ninth tenant whose short name is not its
# domain label fails open, not closed: nothing here knows that name, so its
# URLs and contexts go unjudged until it is added to this table.
TENANT_SHORT_NAMES = {"arbeidstilsynet": "atil", "landbruksdirektoratet": "ldir"}

TENANT_SUFFIX = re.compile(r"\.(no|io)$")

# Two enroll-discovery objects are not tenants. `default` and `nais.io` each
# carry an enroller URL, but neither has a console, a project label or a record
# in nais-tenant-data. Kept in, a kubectl context named `default` (k3s) or
# `nais-io` (nais/cli mints that name verbatim, gcpcluster.go) is refused as
# another tenant's.
NOT_TENANTS = frozenset({"default", "nais.io"})

# The short name of every tenant in the table above. The agent hands over the
# whole list on the gRPC path; the status file carries the active tenant alone,
# so this is what "belongs to another tenant" is judged against there. A ninth
# tenant missing from here fails open, exactly as the table says.
KNOWN_TENANTS = ("atil", "ci-nais", "dev-nais", "ldir", "miljodir", "nav",
                 "ssb", "test-nais")

TIMEOUT_SEC = 3

# nais/device#564. The agent publishes its state next to agent-config.json,
# because a sandbox that refuses to open a socket will still read a file.
STATUS_FILE = "agent-status.json"
CONNECTED = "Connected"

# How many heartbeats a file may miss before it stops meaning anything. The
# agent rewrites it every heartbeatSeconds, so one missed beat is a laptop that
# just woke or a disk that stalled, not a dead agent. Four is two minutes at the
# cadence the agent ships with: long enough to survive a wake, short enough that
# an agent killed three hours ago is never read as connected.
STALE_HEARTBEATS = 4

# Used only when the payload does not say, or says something impossible. The
# agent's own value wins; this is the floor and the ceiling around it.
HEARTBEAT_DEFAULT_SEC = 30
HEARTBEAT_MAX_SEC = 300

# connected is True, False or None. None is an answer of its own: nothing was
# established. active is the short tenant name or None; known is what active is
# compared against.
State = collections.namedtuple("State", "connected active known")

# deny=True refuses the call. deny=False allows it and says why nothing was
# checked, which is not the same as saying nothing.
Decision = collections.namedtuple("Decision", "deny reason")


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
    """Runs a command and returns (returncode, stdout, stderr). None when it cannot run."""
    try:
        p = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SEC,
        )
        return p.returncode, p.stdout, p.stderr
    except (OSError, subprocess.SubprocessError):
        return None


def in_sandbox():
    """True inside cplt, which sets this in every wrapped process."""
    return bool(os.environ.get("__CPLT_WRAPPED"))


def naisdevice_connected(runner):
    """True, False, or None when the answer cannot be established.

    `nais device status` exits non-zero with one of two messages, and they are
    different answers (nais/cli internal/naisdevice/status.go, naisdevice.go):

      "not connected to naisdevice"      the agent answered, and said no
      "unable to connect to naisdevice"  no agent could be reached at all

    The second is a stopped agent on a laptop, which is not connected, and the
    blocked socket inside cplt, which says nothing about the tunnel. Only
    `__CPLT_WRAPPED` tells the two apart. Any other failure is not an answer.

    Do not add --quiet: it turns the disconnected case into exit 0 and no
    output, which is the one reading this gate must not get wrong.
    """
    result = runner(["nais", "device", "status"])
    if result is None:
        return None
    code, out, err = result
    if code == 0:
        return True
    text = (out + err).lower()
    if "not connected to naisdevice" in text:
        return False
    if "unable to connect to naisdevice" in text:
        return None if in_sandbox() else False
    return None


def status_file_path():
    """Where the agent writes agent-status.json.

    `config.UserConfigDir()` in nais/device is Go's `os.UserConfigDir()` plus
    `naisdevice`: `~/Library/Application Support/naisdevice` on macOS, and
    `$XDG_CONFIG_HOME/naisdevice` or `~/.config/naisdevice` on Linux.
    """
    if sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, "naisdevice", STATUS_FILE)


def heartbeat_window(heartbeat):
    """How old `updatedAt` may be before the file answers nothing.

    Missing, non-numeric, zero, negative or absurd falls back to the 30 seconds
    the agent currently uses. A file claiming a one-day heartbeat would
    otherwise license a day-old answer, and the point of the field is to bound
    how wrong a reader can be.
    """
    if isinstance(heartbeat, bool) or not isinstance(heartbeat, (int, float)):
        heartbeat = HEARTBEAT_DEFAULT_SEC
    elif not 1 <= heartbeat <= HEARTBEAT_MAX_SEC:
        heartbeat = HEARTBEAT_DEFAULT_SEC
    return heartbeat * STALE_HEARTBEATS


def parse_time(value):
    """RFC3339 as Go writes it, or None. Python spells `Z` as `+00:00`."""
    if not isinstance(value, str):
        return None
    try:
        stamp = datetime.datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    # Go always writes an offset. One without is read as local time rather than
    # refused, since the alternative is calling a readable file unreadable.
    return stamp.astimezone()


def read_status_file(path=None, now=None):
    """What the agent says about itself, or None when the file cannot say.

    None covers missing, unreadable, truncated, not JSON, missing fields and
    stale alike. Every one of them means ask the CLI instead; not one of them
    means disconnected.
    """
    try:
        with open(path or status_file_path(), encoding="utf8") as fh:
            payload = json.load(fh)
    except (OSError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None

    state = payload.get("connectionState")
    if not isinstance(state, str) or not state.strip():
        return None

    stamp = parse_time(payload.get("updatedAt"))
    if stamp is None:
        return None
    now = now or datetime.datetime.now(datetime.timezone.utc)
    age = abs((now - stamp).total_seconds())
    # abs, because a timestamp from the future is a clock that moved, not a file
    # that is fresher than fresh.
    if age > heartbeat_window(payload.get("heartbeatSeconds")):
        return None

    # The agent writes an empty tenant when none is active, and reports domains
    # rather than short names, the same as the gRPC path.
    tenant = payload.get("tenant")
    active = None
    if isinstance(tenant, str) and tenant.strip():
        if tenant.strip().lower() not in NOT_TENANTS:
            active = short_name(tenant)
    return State(state.strip() == CONNECTED, active, KNOWN_TENANTS)


def naisdevice_state(runner, status_path=None, now=None):
    """The connection state and the tenant: the file first, the CLI second."""
    state = read_status_file(status_path, now)
    if state is not None:
        return state
    connected = naisdevice_connected(runner)
    if connected is not True:
        # False needs no tenant, and None has no way to ask for one.
        return State(connected, None, ())
    return State(True, *tenants(runner))


def unresolved_message(path=None):
    """Said when the gate allows without having checked anything.

    One message for the sandbox and another for a laptop, because the fix is
    different and a reader who gets both reads neither.
    """
    head = (
        "The gate cannot reach naisdevice, so it is NOT enforcing the tenant "
        "rules on this command. Nothing was refused, and nothing was checked.\n\n"
    )
    if in_sandbox():
        return head + (
            "Inside cplt the agent socket is blocked by design. The agent also "
            "publishes its state to a file, which the sandbox can be allowed to "
            "read; ask the user to run, outside the sandbox:\n\n"
            '  cplt config set allow.read "%s"\n\n'
            "Until then, check the tenant yourself before you trust what comes back."
            % (path or status_file_path())
        )
    return head + (
        "Usually naisdevice is not installed, or `nais` is not on PATH. Say so "
        "before running more cluster commands, and check the tenant yourself "
        "before you trust what comes back."
    )


UNRESOLVED_SHORT = (
    "nais gate: naisdevice still unreachable, tenant rules NOT enforced on this "
    "command (see the notice earlier this session)."
)


def first_time_this_session(session):
    """True the first time this is asked in a session, False after; True when
    there is no session to remember, or nowhere to remember it.

    A marker in the temp dir, because the full notice once and a line after
    that is read, and the full notice on every call is not.
    """
    if not session or not re.fullmatch(r"[A-Za-z0-9._-]{1,128}", str(session)):
        return True
    import tempfile
    marker = os.path.join(tempfile.gettempdir(), "nais-cluster-gate." + str(session))
    try:
        fd = os.open(marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        return False
    except OSError:
        return True
    os.close(fd)
    return True


def short_name(name):
    """The short tenant name a host, a cluster name or a kubectl context uses.

    `NAV` has no suffix and lowercases to the right answer, which is why it
    needs no case of its own: the two `dev-gcp` / `prod-gcp` contexts that exist
    for that tenant alone are handled by NAV_ONLY_CONTEXTS.

    Baked in rather than read from the bucket. A preToolUse hook runs per tool
    call, so a lookup would be a network round trip each time, and it would fail
    inside a sandbox that blocks egress — which is where being wrong costs most.
    """
    name = TENANT_SUFFIX.sub("", name.strip().lower())
    return TENANT_SHORT_NAMES.get(name, name)


def tenants(runner):
    """(active tenant, all tenant names) from the agent, or (None, []).

    Field names come from the generated protobuf in nais/device:
    AgentStatus.Tenants, each with name and active. Key lookup is
    case-insensitive because the encoder that renders them is the CLI's
    choice, not ours.

    Names come back through `short_name`, so every caller compares the short
    form the rest of the platform uses rather than the domain the agent reports.
    """
    result = runner(["nais", "device", "status", "--output", "json"])
    if result is None:
        return None, []
    code, out, _ = result
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
        if not name or name.lower() in NOT_TENANTS:
            continue
        name = short_name(name)
        names.append(name)
        if is_active:
            active = name
    return active, names


def kube_context(runner):
    result = runner(["kubectl", "config", "current-context"])
    if result is None:
        return None
    code, out, _ = result
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


def decide(payload, runner=run, status_path=None):
    tool = str(payload.get("toolName") or payload.get("tool_name") or "")
    if not re.search(r"bash|shell|execute", tool, re.I):
        return None

    args = payload.get("toolArgs") or payload.get("tool_input") or {}
    # Held rather than returned, so a payload whose second command is refusable
    # is still refused. A refusal outranks a notice; the notice is what is left
    # when nothing was refused.
    unresolved = None
    for command in command_text(args, []):
        if not command.strip() or NAIS_OK.match(command):
            continue

        # The observability rules read the command itself, so they hold on a
        # machine where the agent cannot be reached at all.
        if LGTM_HOST.search(command):
            if FEDERATED.search(command):
                return Decision(True,
                    "X-Scope-OrgID names both orgs. Tenant federation is off, so "
                    "the server rejects the value instead of merging.\n\n"
                    "  Platform data:  X-Scope-OrgID: nais\n"
                    "  Workload data:  X-Scope-OrgID: tenant\n\n"
                    "Both means two requests."
                )
            if not ORG_ID.search(command):
                return Decision(True,
                    "Loki, Mimir and Tempo return 401 without X-Scope-OrgID. "
                    "There is no default org.\n\n"
                    "  Mimir:  bash \"$NAV_PILOT_SKILLS_DIR/nais-observability/mimir-query.sh\" "
                    "<tenant> <promql>\n"
                    "  Loki:   bash \"$NAV_PILOT_SKILLS_DIR/nais-observability/loki-query.sh\" "
                    "<tenant> <logql>\n\n"
                    "They send the header and default to the platform org. Pass "
                    "`--org tenant` for workload data.\n\n"
                    "Raw curl, or Tempo, which has no wrapper:\n"
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

        state = naisdevice_state(runner, status_path)
        if state.connected is False:
            return Decision(True,
                "naisdevice is not connected. Every Nais cluster API sits behind "
                "its gateway, so this command would hang until it times out and "
                "then report a network error.\n\n"
                "  Connect:  nais device connect\n"
                "  Check:    nais device status\n\n"
                "If status says it is unable to connect to naisdevice, the agent "
                "itself is not running: start naisdevice first.\n\n"
                "Does not need the gateway? Put `NAIS_OK=1` in front of the command."
            )
        if state.connected is None:
            # No status file, no nais CLI, no agent socket, or a timeout.
            # Nothing established, so nothing refused — out loud.
            unresolved = unresolved or Decision(False, unresolved_message(status_path))
            continue

        active, known = state.active, state.known
        if not active:
            continue

        # A URL names its tenant outright, so it is checked before the context,
        # which usually names nothing.
        url_tenant = host_tenant(command)
        if url_tenant and url_tenant in known and url_tenant != active:
            return Decision(True,
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
            return Decision(True,
                f"The active naisdevice tenant is {active}, but the kubectl "
                f"context {context} belongs to {belongs}. The command would "
                "succeed against the wrong tenant's cluster.\n\n"
                "  Switch tenant:      the naisdevice menu. The nais CLI has no "
                "command for it.\n"
                f"  Or switch context:  kubectl config use-context <a context for {active}>\n"
                "  List contexts:      kubectl config get-contexts\n\n"
                f"Meant {belongs}? Put `NAIS_OK=1` in front of the command."
            )
    return unresolved


def main():
    try:
        raw = sys.stdin.read()
        debug = os.environ.get("NAV_PILOT_HOOK_DEBUG")
        if debug:
            with open(debug, "a", encoding="utf8") as fh:
                fh.write(raw.rstrip("\n") + "\n")
        payload = json.loads(raw)
        decision = decide(payload) if isinstance(payload, dict) else None
    except Exception:
        # Fail-open. A preToolUse hook that fails refuses the call, and a gate
        # that refuses everything is worse than no gate.
        decision = None

    if decision and not decision.deny:
        # Allowed without having checked. No permissionDecision, because
        # "allow" would approve a call the user would otherwise be asked about,
        # and the gate has nothing to approve here. The text goes out as
        # additionalContext: Copilot CLI drops a hook's stderr on exit 0
        # (measured, 1.0.83), and this is what the model reads. stderr too, for
        # anyone running the hook by hand.
        session = payload.get("sessionId") or payload.get("session_id")
        reason = decision.reason if first_time_this_session(session) else UNRESOLVED_SHORT
        print(reason, file=sys.stderr)
        json.dump(
            {
                "additionalContext": reason,
                "hookSpecificOutput": {
                    "hookEventName": "preToolUse",
                    "additionalContext": reason,
                },
            },
            sys.stdout,
        )
    elif decision:
        reason = decision.reason
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


# A field set to _DROP is left out, which is how the missing-field cases are
# written without a second builder.
_DROP = object()


def _write(tmp, name, body):
    """A status file holding body: a dict, or raw text for the broken cases."""
    path = os.path.join(tmp, name + ".json")
    with open(path, "w", encoding="utf8") as fh:
        fh.write(body if isinstance(body, str) else json.dumps(body))
    return path


def _status(tmp, name, age=0, **fields):
    """Fresh and connected to NAV unless told otherwise. age is seconds old.

    The payload is nais/device#564's, field for field.
    """
    stamp = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=age)
    body = {
        "connectionState": "Connected",
        "tenant": "NAV",
        "updatedAt": stamp.isoformat(),
        "heartbeatSeconds": 30,
        "warning": "best effort, may be missing or stale, format may change, "
                   "may be removed at any time, do not depend on it",
    }
    body.update(fields)
    return _write(tmp, name, {k: v for k, v in body.items() if v is not _DROP})


def _outcome(decision):
    """The three answers, named. `notice` is allowed but not enforced."""
    if decision is None:
        return "allow"
    return "deny" if decision.deny else "notice"


# What `nais device status --output json` actually reports: the compiled-in
# `NAV` plus the object names of the naisdevice-enroll-discovery bucket. Fed to
# the gate verbatim, because a suite built on short names the agent never emits
# is what let both tenant rules sit dead while reporting green.
REPORTED = ("NAV", "arbeidstilsynet.no", "ci-nais.io", "default", "dev-nais.io",
            "landbruksdirektoratet.no", "miljodir.no", "nais.io", "nav.no",
            "ssb.no", "test-nais.no")


# The two things `nais device status` says on exit 1, verbatim from nais/cli.
NOT_CONNECTED = "Error: not connected to naisdevice\n"
UNREACHABLE = "Error: unable to connect to naisdevice; make sure naisdevice is running\n"


def _runner(connected=True, active="NAV", tenant_names=REPORTED,
            context="dev-gcp", missing=False, error=NOT_CONNECTED):
    """A stubbed machine. missing=True is "nais is not installed"; error is
    what the CLI prints when connected=False."""

    def runner(args):
        if missing:
            return None
        if args[:3] == ["nais", "device", "status"]:
            if "--output" in args:
                if not connected:
                    return 1, "", error
                payload = {
                    "connectionState": "Connected",
                    "Tenants": [
                        {"name": name, "active": name == active}
                        for name in tenant_names
                    ],
                }
                return 0, json.dumps(payload), ""
            return (0, "Connected\n", "") if connected else (1, "", error)
        if args[:3] == ["kubectl", "config", "current-context"]:
            return (0, context + "\n", "") if context else (1, "", "")
        return None

    return runner


def _selftest():
    import tempfile

    tmp = tempfile.mkdtemp(prefix="nais-cluster-gate-selftest-")
    tempfile.tempdir = tmp
    # Every CLI case points at a file that is not there, so the suite says the
    # same thing on a machine where naisdevice has already shipped #564.
    absent = os.path.join(tmp, "absent.json")

    cases = [
        # name, payload, runner, want_deny
        ("disconnected blocks kubectl",
         _payload("kubectl get pods -n myteam"), _runner(connected=False), "deny"),
        ("connected allows kubectl",
         _payload("kubectl get pods -n myteam"), _runner(), "allow"),
        # Allowed, but no longer in silence: nothing was checked, and the
        # reader is the one who has to know that.
        ("no nais binary allows, out loud",
         _payload("kubectl get pods"), _runner(missing=True), "notice"),
        ("NAIS_OK passes through",
         _payload("NAIS_OK=1 kubectl get pods"), _runner(connected=False), "allow"),
        ("non-cluster command ignored",
         _payload("ls -la"), _runner(connected=False), "allow"),
        ("kubectl config is local",
         _payload("kubectl config use-context dev-gcp"), _runner(connected=False), "allow"),
        ("nav context while ssb active",
         _payload("kubectl get pods"), _runner(active="ssb.no", context="prod-gcp"), "deny"),
        ("prefixed context of another tenant",
         _payload("kubectl get pods"), _runner(active="NAV", context="ssb-dev"), "deny"),
        ("bare dev context is not judged",
         _payload("kubectl get pods"), _runner(active="ssb.no", context="dev"), "allow"),
        ("nav context with nav active",
         _payload("kubectl get pods"), _runner(active="nav.no", context="dev-gcp"), "allow"),
        ("prefixed context of the active tenant",
         _payload("kubectl get pods"), _runner(active="ssb.no", context="ssb-dev"), "allow"),
        ("unknown context is not judged",
         _payload("kubectl get pods"), _runner(active="NAV", context="kind-local"), "allow"),
        ("no context is not judged",
         _payload("kubectl get pods"), _runner(active="NAV", context=""), "allow"),
        ("stern is a cluster command",
         _payload("stern myapp"), _runner(connected=False), "deny"),
        ("non-bash tool ignored",
         _payload("kubectl get pods", tool="str_replace"), _runner(connected=False), "allow"),
        # The CLI's two exit-1 messages are two answers. "unable to connect"
        # on a laptop is a stopped agent; inside cplt it is the blocked socket,
        # and the sandbox cases below are run with __CPLT_WRAPPED set.
        ("unable to connect outside a sandbox is a stopped agent",
         _payload("kubectl get pods"), _runner(connected=False, error=UNREACHABLE), "deny"),
        ("an unknown CLI error is not an answer",
         _payload("kubectl get pods"),
         _runner(connected=False, error="Error: context deadline exceeded\n"), "notice"),

        # Observability. The first four need no agent at all, so they are run
        # against a machine with no nais CLI to prove it.
        ("mimir query without the header",
         _payload('curl -s "https://mimir.dev-nais.cloud.nais.io/prometheus/api/v1/query?query=up"'),
         _runner(missing=True), "deny"),
        # The header rule is satisfied, so nothing is refused. The host still
        # names a tenant nobody could check on a machine with no agent to ask,
        # which is what the notice says.
        ("loki query with the header passes, tenant unchecked",
         _payload('curl -s -H "X-Scope-OrgID: nais" -G "https://loki.dev-nais.cloud.nais.io/loki/api/v1/query_range"'),
         _runner(missing=True), "notice"),
        ("logcli --org-id counts as the header",
         _payload("logcli --addr=https://loki.dev-nais.cloud.nais.io --org-id=nais query '{app=\"x\"}'"),
         _runner(missing=True), "notice"),
        ("federated org is refused",
         _payload('curl -H "X-Scope-OrgID: nais|tenant" https://mimir.dev-nais.cloud.nais.io/prometheus/api/v1/query'),
         _runner(missing=True), "deny"),
        ("grafana is not an LGTM query host",
         _payload("curl -s https://grafana.dev-nais.cloud.nais.io/api/health"),
         _runner(missing=True), "notice"),
        ("tempo host names the tenant behind the env",
         _payload('curl -H "X-Scope-OrgID: nais" https://tempo.dev.dev-nais.cloud.nais.io/api/search'),
         _runner(active="NAV", context=""), "deny"),
        ("tempo host of the active tenant passes",
         _payload('curl -H "X-Scope-OrgID: nais" https://tempo.dev.dev-nais.cloud.nais.io/api/search'),
         _runner(active="dev-nais.io", context=""), "allow"),
        ("nais host while disconnected",
         _payload('curl -H "X-Scope-OrgID: nais" https://loki.dev-nais.cloud.nais.io/loki/api/v1/labels'),
         _runner(connected=False), "deny"),
        ("unknown tenant in a host is not judged",
         _payload('curl -H "X-Scope-OrgID: nais" https://loki.made-up.cloud.nais.io/loki/api/v1/labels'),
         _runner(active="NAV", context=""), "allow"),
        ("a non-nais URL is not touched",
         _payload("curl -s https://example.com/api"), _runner(connected=False), "allow"),

        # The names the agent reports, against the short names a host and a
        # context use. Every one of these allowed before `short_name`, because
        # `ssb` is not `ssb.no` and no reported name is a prefix of `ssb-dev`.
        ("reported names: an ssb URL while dev-nais.io is active",
         _payload('curl -H "X-Scope-OrgID: nais" https://loki.ssb.cloud.nais.io/loki/api/v1/labels'),
         _runner(active="dev-nais.io", context=""), "deny"),
        ("reported names: a nav-only context while ssb.no is active",
         _payload("kubectl get pods"), _runner(active="ssb.no", context="prod-gcp"), "deny"),
        ("reported names: an atil URL while NAV is active",
         _payload('curl -H "X-Scope-OrgID: nais" https://loki.atil.cloud.nais.io/loki/api/v1/labels'),
         _runner(active="NAV", context=""), "deny"),
        ("reported names: an ldir context while NAV is active",
         _payload("kubectl get pods"), _runner(active="NAV", context="ldir-dev"), "deny"),
        ("reported names: the active tenant's own URL passes",
         _payload('curl -H "X-Scope-OrgID: nais" https://loki.ssb.cloud.nais.io/loki/api/v1/labels'),
         _runner(active="ssb.no", context=""), "allow"),
        # NAV is the compiled-in name, dev-gcp is that tenant's own context.
        # Before `short_name` this denied a correct command, because the gate
        # compared the context's "nav" against an active tenant of "NAV".
        ("reported names: a nav context while NAV is active",
         _payload("kubectl get pods"), _runner(active="NAV", context="dev-gcp"), "allow"),
        # `default` and `nais.io` are enroll-discovery objects, not tenants.
        # nais/cli mints a context named `nais-io` verbatim and k3s names its
        # context `default`; neither belongs to another tenant.
        ("reported names: the nais-io context is not judged",
         _payload("kubectl get pods"), _runner(active="NAV", context="nais-io"), "allow"),
        ("reported names: a context named default is not judged",
         _payload("kubectl get pods"), _runner(active="NAV", context="default"), "allow"),
    ]

    # The status file. The CLI is stubbed out with missing=True wherever the
    # point is that the file answered on its own.
    #
    # name, payload, runner, status file, want, a fragment of the reason
    file_cases = [
        ("file: connected, tenant matches",
         _payload("kubectl get pods"), _runner(missing=True),
         _status(tmp, "ok"), "allow", None),
        ("file: URL names another tenant",
         _payload('curl -H "X-Scope-OrgID: nais" https://loki.ssb.cloud.nais.io/loki/api/v1/labels'),
         _runner(missing=True), _status(tmp, "devnais", tenant="dev-nais.io"),
         "deny", "dev-nais"),
        # The CLI says disconnected and the file says connected: the file wins,
        # and the command is judged on its context rather than on the tunnel.
        ("file: context names another tenant",
         _payload("kubectl get pods"), _runner(connected=False, context="ssb-dev"),
         _status(tmp, "nav"), "deny", "ssb"),
        ("file: disconnected denies with the connect advice",
         _payload("kubectl get pods"), _runner(missing=True),
         _status(tmp, "down", connectionState="Disconnected"),
         "deny", "nais device connect"),
        # Anything that is not Connected is not connected. The CLI draws the
        # line in the same place.
        ("file: a transient state is not connected",
         _payload("kubectl get pods"), _runner(missing=True),
         _status(tmp, "boot", connectionState="Bootstrapping"), "deny", None),
        ("file: stale and no CLI cannot determine",
         _payload("kubectl get pods"), _runner(missing=True),
         _status(tmp, "stale", age=600), "notice", "NOT enforcing"),
        # Stale means ask the CLI, not give up: this one is decided by the CLI.
        ("file: stale falls back to the CLI",
         _payload("kubectl get pods"), _runner(active="ssb.no", context="prod-gcp"),
         _status(tmp, "stale2", age=600), "deny", "ssb"),
        ("file: a timestamp from the future is stale",
         _payload("kubectl get pods"), _runner(missing=True),
         _status(tmp, "future", age=-3600), "notice", None),
        ("file: absent, CLI connected, unchanged",
         _payload("kubectl get pods"), _runner(), absent, "allow", None),
        ("file: absent, CLI disconnected, unchanged",
         _payload("kubectl get pods"), _runner(connected=False), absent,
         "deny", "nais device connect"),
        ("file: absent, CLI names another tenant, unchanged",
         _payload("kubectl get pods"), _runner(active="ssb.no", context="prod-gcp"),
         absent, "deny", "ssb"),
        ("file: unparseable",
         _payload("kubectl get pods"), _runner(missing=True),
         _write(tmp, "garbage", "{not json"), "notice", None),
        ("file: truncated",
         _payload("kubectl get pods"), _runner(missing=True),
         _write(tmp, "trunc", '{"connectionState":"Conn'), "notice", None),
        ("file: empty",
         _payload("kubectl get pods"), _runner(missing=True),
         _write(tmp, "empty", ""), "notice", None),
        ("file: JSON that is not an object",
         _payload("kubectl get pods"), _runner(missing=True),
         _write(tmp, "list", "[]"), "notice", None),
        ("file: no connectionState",
         _payload("kubectl get pods"), _runner(missing=True),
         _status(tmp, "nostate", connectionState=_DROP), "notice", None),
        ("file: no updatedAt",
         _payload("kubectl get pods"), _runner(missing=True),
         _status(tmp, "nostamp", updatedAt=_DROP), "notice", None),
        ("file: updatedAt is not a timestamp",
         _payload("kubectl get pods"), _runner(missing=True),
         _status(tmp, "badstamp", updatedAt="yesterday"), "notice", None),
        # Disconnected, so freshness is visible in the answer: fresh denies,
        # stale gives up.
        ("file: no heartbeatSeconds falls back to 30",
         _payload("kubectl get pods"), _runner(missing=True),
         _status(tmp, "nohb", age=60, connectionState="Disconnected",
                 heartbeatSeconds=_DROP), "deny", None),
        ("file: heartbeatSeconds of 0 falls back to 30",
         _payload("kubectl get pods"), _runner(missing=True),
         _status(tmp, "zerohb", age=60, connectionState="Disconnected",
                 heartbeatSeconds=0), "deny", None),
        ("file: an absurd heartbeatSeconds is not believed",
         _payload("kubectl get pods"), _runner(missing=True),
         _status(tmp, "hugehb", age=600, connectionState="Disconnected",
                 heartbeatSeconds=86400), "notice", None),
        # 300 seconds old is stale at the default cadence and fresh at this
        # one, so the threshold is the agent's number and not a constant here.
        ("file: a slower heartbeat widens the window",
         _payload("kubectl get pods"), _runner(missing=True),
         _status(tmp, "slowhb", age=300, connectionState="Disconnected",
                 heartbeatSeconds=120), "deny", None),
        ("file: an empty tenant is not a tenant",
         _payload('curl -H "X-Scope-OrgID: nais" https://loki.ssb.cloud.nais.io/loki/api/v1/labels'),
         _runner(missing=True), _status(tmp, "notenant", tenant=""), "allow", None),
        ("file: nais.io is not a tenant",
         _payload("kubectl get pods"), _runner(connected=False, context="ssb-dev"),
         _status(tmp, "naisio", tenant="nais.io"), "allow", None),
        # The notice must not shadow a refusal later in the same payload.
        ("file: a refusable second command still wins",
         {"toolName": "bash", "toolArgs": {"steps": [
             {"command": "kubectl get pods"},
             {"command": 'curl -s "https://mimir.dev-nais.cloud.nais.io/'
                         'prometheus/api/v1/query?query=up"'}]}},
         _runner(missing=True), absent, "deny", "X-Scope-OrgID"),
        ("file: NAIS_OK still passes through",
         _payload("NAIS_OK=1 kubectl get pods"), _runner(missing=True),
         _status(tmp, "down2", connectionState="Disconnected"), "allow", None),
    ]

    failed = 0

    # The two tenant tables cannot be derived from each other, so this is what
    # keeps them from drifting apart in silence.
    for name, ok in [
        ("every short-name exception is a known tenant",
         set(TENANT_SHORT_NAMES.values()) <= set(KNOWN_TENANTS)),
        ("no non-tenant is a known tenant",
         not (set(NOT_TENANTS) & set(KNOWN_TENANTS))),
        ("known tenants are short names",
         all(short_name(t) == t for t in KNOWN_TENANTS)),
    ]:
        print(f"{'✅' if ok else '❌'} {name}")
        if not ok:
            failed += 1

    # Inside cplt, the same CLI output is not an answer.
    os.environ["__CPLT_WRAPPED"] = "1"
    try:
        for name, payload, runner, want, fragment in [
            ("sandbox: unable to connect cannot determine",
             _payload("kubectl get pods"), _runner(connected=False, error=UNREACHABLE),
             "notice", "cplt config set allow.read"),
            ("sandbox: the agent saying disconnected still denies",
             _payload("kubectl get pods"), _runner(connected=False), "deny", None),
            ("sandbox: the file still wins over the CLI",
             _payload("kubectl get pods"), _runner(connected=False, error=UNREACHABLE),
             "allow", None),
        ]:
            path = _status(tmp, "sandbox-ok") if want == "allow" else absent
            decision = decide(payload, runner, path)
            got = _outcome(decision)
            ok = got == want and (not fragment or fragment in decision.reason)
            print(f"{'✅' if ok else '❌'} {name}" + ("" if ok else f" (got {got}, want {want})"))
            if not ok:
                failed += 1
    finally:
        del os.environ["__CPLT_WRAPPED"]

    laptop = decide(_payload("kubectl get pods"), _runner(missing=True), absent)
    ok = "cplt" not in laptop.reason and "not installed" in laptop.reason
    print(f"{'✅' if ok else '❌'} laptop: the notice does not talk about cplt")
    if not ok:
        failed += 1

    # Once in full per session, one line after that; no session, always full.
    session = "selftest-" + os.path.basename(tmp)
    seq = [first_time_this_session(session), first_time_this_session(session),
           first_time_this_session(None), first_time_this_session("../../etc")]
    ok = seq == [True, False, True, True]
    print(f"{'✅' if ok else '❌'} the full notice is said once per session (got {seq})")
    if not ok:
        failed += 1

    for heartbeat, want in [
        (30, 120),
        (120, 480),
        (None, 120),
        ("30", 120),
        (True, 120),
        (0, 120),
        (-30, 120),
        (86400, 120),
        (301, 120),
    ]:
        got = heartbeat_window(heartbeat)
        ok = got == want
        print(f"{'✅' if ok else '❌'} heartbeat_window({heartbeat!r}) == {want}")
        if not ok:
            failed += 1

    for reported, want in [
        ("NAV", "nav"),
        ("nav.no", "nav"),
        ("dev-nais.io", "dev-nais"),
        ("ssb.no", "ssb"),
        ("test-nais.no", "test-nais"),
        ("arbeidstilsynet.no", "atil"),
        ("landbruksdirektoratet.no", "ldir"),
        ("dev-nais", "dev-nais"),
    ]:
        got = short_name(reported)
        ok = got == want
        print(f"{'✅' if ok else '❌'} short_name({reported!r}) == {want!r}")
        if not ok:
            failed += 1

    for name, payload, runner, want in cases:
        got = _outcome(decide(payload, runner, absent))
        ok = got == want
        print(f"{'✅' if ok else '❌'} {name}" + ("" if ok else f" (got {got}, want {want})"))
        if not ok:
            failed += 1

    for name, payload, runner, path, want, fragment in file_cases:
        decision = decide(payload, runner, path)
        got = _outcome(decision)
        ok = got == want
        if ok and fragment:
            ok = decision is not None and fragment in decision.reason
        print(f"{'✅' if ok else '❌'} {name}" + ("" if ok else f" (got {got}, want {want})"))
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

    # The unresolved path on the wire: no nais, no kubectl, no status file, and
    # a config directory that is empty on purpose. It must allow — no
    # permissionDecision, exit 0 — and still say so, as additionalContext.
    unresolved = subprocess.run(
        [sys.executable, __file__],
        input=json.dumps(_payload("kubectl get pods")),
        capture_output=True,
        text=True,
        env={"PATH": "", "HOME": tmp, "XDG_CONFIG_HOME": tmp},
    )
    try:
        wire = json.loads(unresolved.stdout)
    except ValueError:
        wire = {}
    loud_ok = (
        unresolved.returncode == 0
        and "permissionDecision" not in unresolved.stdout
        and "NOT enforcing" in wire.get("additionalContext", "")
        and "NOT enforcing" in unresolved.stderr
    )
    print(f"{'✅' if loud_ok else '❌'} allows out loud when the state cannot be read")
    if not loud_ok:
        failed += 1

    # The same session again: one line, not the full notice.
    again = subprocess.run(
        [sys.executable, __file__],
        input=json.dumps(dict(_payload("kubectl get pods"), sessionId="wire-" + os.path.basename(tmp))),
        capture_output=True,
        text=True,
        env={"PATH": "", "HOME": tmp, "XDG_CONFIG_HOME": tmp, "TMPDIR": tmp},
    )
    again2 = subprocess.run(
        [sys.executable, __file__],
        input=json.dumps(dict(_payload("kubectl get pods"), sessionId="wire-" + os.path.basename(tmp))),
        capture_output=True,
        text=True,
        env={"PATH": "", "HOME": tmp, "XDG_CONFIG_HOME": tmp, "TMPDIR": tmp},
    )
    short_ok = "NOT enforcing" in again.stdout and UNRESOLVED_SHORT in again2.stdout \
        and "NOT enforcing" not in again2.stdout.replace(UNRESOLVED_SHORT, "")
    print(f"{'✅' if short_ok else '❌'} the second call in a session gets one line")
    if not short_ok:
        failed += 1

    print(f"\n{'all green' if failed == 0 else str(failed) + ' failed'}")
    return 1 if failed else 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(_selftest())
    main()
