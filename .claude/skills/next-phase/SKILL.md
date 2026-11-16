---
name: next-phase
description: Resume the ask-analytics build at the next unticked phase in docs/PLAN.md
disable-model-invocation: true
---
1. Read CLAUDE.md and docs/PLAN.md. Find the first phase with unticked boxes and summarise where it stands: last log entry, failing tests, open reviewer findings.
2. Read the SPEC and ARCHITECTURE sections that phase touches. Check current docs or installed source for every library the phase uses.
3. Propose the step list for the phase and the risks you see, then wait for approval.
4. Execute with the working loop in CLAUDE.md: failing test first, implement, `make check`, the `reviewer` subagent on the phase diff, fixes, the phase gate, evidence pasted into the phase log, commit, pull request, merge on green CI.

Extra instructions from Apollo, if any: $ARGUMENTS
