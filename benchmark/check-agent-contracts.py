from pathlib import Path

# Static source contracts, not evidence of model compliance.
agents = Path(__file__).resolve().parents[1] / "agents"
platform = (agents / "nais-platform.agent.md").read_text()
review = (agents / "nais-review.agent.md").read_text()

for rule in (
    "load and follow `nais-change-workflow`",
    "Only under `$__CPLT_WRAPPED`",
    "never worktrees or unfinished work, even if pre-approved or requested in a brief",
    "beneath non-empty `$CPLT_WORKTREE_ROOT`, only for the known launch repository",
    "matching launch and target repositories",
    "persistent, in-scope checkout verified as the target repository, or stop",
    "Require workers to reject unsafe paths even when supplied in a brief",
    "Never fall back to scratch",
    "Leave permissions and `git worktree remove` to the user outside cplt",
    "No nested repositories or outward symlinks",
):
    assert rule in platform, rule

assert "Load and follow `nais-adversarial-review`" in review
assert "You do not write them" in review
print("Agent contracts passed")
