# Backlog

Flat capture list — append one idea/bug/task per line, no structure
required at capture time. Triaged via the `/backlog` skill.

Canonical file lives in the `mac` dotfiles repo; `~/backlog.md` is a
symlink to it, so appends from any session are version-controlled.

- update datadog dashboard panel "Single-Measure — By Enterprise Context" so there's a third category, N/A, applied whenever neither side uses the enterprise context
- resolve cases/mcp/content-approvals/001/case.json ("replace Jason Carrick with John Atkinson as approver") in renzler-service — dropped from cases/tiers/fast.txt 2026-08-06 because grounding it safely needs two distinct real approvers, and both named people got substituted with Sam Mefford (to avoid emailing real third parties during fixture setup), collapsing the replace into a no-op. Needs either a second consenting test identity or a reworded prompt before it can be re-added with expected_tools grounding.
- content-approvals/000,003,004,005 in renzler-service still have no expected_tools grounding (no_eval_suite) as of 2026-08-06 — attempted to build a real fixture (a document + approval workflow on workfrontengineering.my.workfront.com's "Frescopa Special-2") to ground them, but approvals_create_or_update_approval_workflow 403'd on both candidate document versions ("isEditable check failed — the current version is not editable"), and there's no available Workfront tool to create a brand-new document to work around it. Blocked until either permissions/document state allow editing an existing doc's approval, or a document-creation tool becomes available. See also the fixture-support Workfront task (hub.workfront.com/task/6a751b6d00002536d37c85b50fb27867).
- investigate why workfront-tasks-brief.md briefly didn't list task 6a74ed5e00008658cab6156a7515abf2 (Sam's own open task, status "New", not closed) during the 2026-08-06 sync — a commit-with-workfront-task hook check missed it, then a later read of the same file showed it present at line 21. Check sync-tasks skill for a result-count cap, staleness window, or race with a concurrent sync run.
- how to compare a measure such as wall clock time, session score between runs

