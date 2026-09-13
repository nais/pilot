# What to ask Nais developers

Everything measured so far says this package is cheaper and more accurate than the alternatives on four of five task shapes. None of it says a Nais engineer is better off using it. Five tasks, chosen by the person who wrote the package, in domains the package covers.

This is the missing measurement. It needs people, not another harness.

## The three questions worth ten minutes each

Ask before showing anyone the package. The point is to find out whether it targets real problems, and a demo first will bias the answer.

**1. What did you lose time to last week?**

Open, no prompting. Write down the concrete instance, not the category. "Spent two hours working out why the feature did not deploy to ssb" is usable; "documentation" is not.

What we are checking: whether the five domains — API, tenants, Fasit, terraform, observability — are where the time actually goes. They came from a conversation with one person and from mining issues, which is proxy evidence. If three engineers name none of them, the package is well built and pointed at the wrong thing.

**2. When you needed a fact about the platform last week, where did you look, and how long did it take?**

Specifically: did you ask a person? Which one? This matters because interrupting a colleague is a cost that never appears in any log, and it is the cost the package is best placed to remove.

**3. Where would you not trust an agent, and why?**

Watch for anything the package currently encourages. If someone says "I would not let it near terraform", the terraform skill needs a different framing, or a hook rather than prose.

## The one thing to measure rather than ask

Give it to two or three volunteers. **After two weeks, check whether it is still installed.** Retention is blunt but honest, and unlike a satisfaction question it cannot be answered politely.

If it has been uninstalled, ask what they reached for instead.

## The gap our benchmark does not cover

The suites test single turns: one question, one file, one review. The package's central claim is a **loop** — plan, review the plan, implement, adversarially review, draft PR — and no benchmark here exercises it end to end.

That gap matters most for **Go**, which is where Nais engineers spend much of their time and the one suite the package lost (3.1m tokens against 2.3m for a bare client, same result). The loss was measured on authoring a package inside a checkout, where the repo already holds the answer. It says nothing about whether the loop produces a better change over a whole task.

Two ways to close it, in order of cost:

- **Watch one real task.** A volunteer takes a change they were going to make anyway through the loop, and we record where it helped and where it was ceremony. One session, and far more informative than another synthetic suite.
- **A multi-turn suite.** A task with a planted trap the loop should catch and a single turn would not — a change whose blast radius grows during implementation, for instance. Expensive to build, and it would still be a task we chose.

Start with the first.

## What not to ask

**"Is this useful?"** People say yes. It costs them nothing and disappoints no one.

**"Would you use this?"** Predicts nothing. Use the two-week retention check instead.

**Anything that presumes the package should exist.** "What would make this better" skips the question of whether it should be there at all, and that question is still open.

## What we would change on each answer

| If they say | Then |
|---|---|
| The five domains are not where time goes | Re-scope to what they name. The domains are the package's premise, not a detail. |
| They ask a colleague for platform facts | The package is aimed correctly; measure how often it replaces that. |
| They would not trust it with terraform or deploys | Move the non-negotiables from prose into a `preToolUse` hook. Prose is measured not to work for process rules. |
| They uninstalled it | Ask what they reached for instead, and believe that over anything here. |
