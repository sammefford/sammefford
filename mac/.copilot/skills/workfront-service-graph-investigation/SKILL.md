---
name: workfront-service-graph-investigation
description: 'Use when evaluating cross-repo blast radius of change, investigating an incident, finding the source/deployment repository, tracing request middleware or dependency boundaries, or consulting ~/dev/workfront-service-graph before proposing a fix. Guides evaluation of cross-service request routing and falsifiable local checks; not package upgrades, deployments, or proof of incident causality.'
argument-hint: 'Incident, blast radius, endpoint, cross-service, or trace'
user-invocable: true
---

# Workfront Service Graph Investigation

Use the partial evidence inventory at `~/dev/workfront-service-graph` to choose
where to investigate, not to declare a root cause. Produce a bounded ownership
and dependency assessment, then move to the code or request evidence that can
discriminate the current hypothesis.

## Safety and Setup

- Default to local, read-only operations. Do not build, regenerate reports,
  recollect Datadog evidence, install tools, or edit the graph for this workflow.
  Its npm scripts maintain artifacts; they are not an incident-query CLI.
- Keep internal architecture private. Never read secret-bearing files, expose
  credentials/auth headers, or include raw traces, payloads, customer identities,
  or personal identifiers. Use aggregate metadata and synthetic fixture data.
- Do not deploy, mutate tenant objects, file defects, or post comments under this
  skill. Do not disable authorization or blindly retry mutating MCP calls.
  Live Workfront tenant checks require separate scope and interactive authorization;
  a synthetic fixture is not evidence of tenant behavior.
- Use installed `git` and `jq`. If unavailable, disclose the limitation and use
  bounded file-reading tools on the reviewed JSON; do not silently install them.

## 1. Anchor the Investigation

Capture the concrete endpoint, exact service/container label, namespace, image,
error, or sanitized trace reference already available, plus environment and UTC
incident window. State the question, such as "Which repository controls body
processing on this route?" Do not assume the current workspace or error emitter
owns the failing behavior.

Read applicable repository instructions before inspecting the graph or any owning
repository. Start with the graph's `README.md` and `docs/MODEL.md`; consult only
relevant sections of `docs/CALLS.md` and `docs/RESEARCH.md` for coverage/background.
These describe the inventory, not a substitute for curated product specifications.
If required knowledge services are unavailable, disclose it; do not invent specs.

```sh
GRAPH="$HOME/dev/workfront-service-graph"
git -C "$GRAPH" rev-parse HEAD
git -C "$GRAPH" status --short
```

Record the graph commit, dirty state, batch `reviewedOn`, source revisions, and
runtime windows relevant to the anchor. Dirty data may not match generated Turtle;
report discrepancies rather than rebuilding or overwriting concurrent edits.

## 2. Resolve Identities, Then Inspect One Hop

The reviewed input is `data/claims.json` plus `data/*.claims.json`. Each batch
contains `reviewedOn`, a `services` object keyed by identity, a `repositories`
object keyed by repository ID, and a `claims` array. The portable artifacts are
`graph/calls.ttl` (accepted calls) and `graph/workfront-services.ttl` (evidence
and candidates). Use the JSON for bounded queries; do not grep Turtle as a parser.

Discover candidates with a narrow pattern; replace the example with incident terms:

```sh
jq -s --arg needle 'mcp|gateway|resolver' '
  [.[] as $batch | $batch.services | to_entries[]
   | select(([.key, .value.label, (.value.aliases // [])] | tostring)
            | test($needle; "i"))
   | {id: .key, label: .value.label, aliases: .value.aliases,
      reviewedOn: $batch.reviewedOn}]
' "$GRAPH"/data/claims.json "$GRAPH"/data/*.claims.json
```

A discovery substring is not identity equivalence. Select an exact ID or an
explicit alias; keep ambiguous labels separate and report unresolved mappings.
`group` is descriptive, not a team, deployment, or ownership field. The inventory
does not provide an authoritative owner registry.

Query incoming and outgoing claims for the selected ID, preserving candidates and
the evidence needed to follow a source lead:

```sh
jq -s --arg id 'wf-instance-resolver' '
  [.[] as $batch | $batch.claims[]
   | select(.caller == $id or .callee == $id)
   | {id, caller, callee, status, kind, scope,
      reviewedOn: $batch.reviewedOn,
      evidence: [.evidence[] | . as $evidence
        | . + (if .repo then
                 {repository: $batch.repositories[$evidence.repo]}
               else {} end)]}]
' "$GRAPH"/data/claims.json "$GRAPH"/data/*.claims.json
```

Retain claim IDs, direction, status, kind, scope, and evidence references in the
assessment. An empty result is a coverage gap. Inspect another hop only when a
specific claim or unresolved boundary makes it necessary; do not traverse the
whole inventory. If a repository reference is missing, flag it instead of guessing.

## 3. Interpret Evidence Before Routing

| Evidence | Establishes | Does Not Establish |
| --- | --- | --- |
| `Accepted` / `SourceCode` | Implemented outbound call at the cited repository revision and path | Deployment, execution, or incident causality |
| `Accepted` / `RuntimeObservation` | Positive aggregate caller/peer activity in the recorded environment and window | Exact request path, independent deployment identity, or destination environment |
| `Accepted` / `Documentation` | Cited documented relationship within its scope | Current traffic or rollout state |
| `Candidate`, including `Configuration` | A lead requiring verification | An accepted call or confirmed request path |

Production tags describe caller instrumentation, not the destination. Span-hit
aggregates can overlap and are not unique requests. Use the actual batch windows,
not a hardcoded snapshot date, to judge incident relevance.

Missing edges mean unknown. Databases/brokers and some instrumentation labels are
deliberately excluded. A client-to-gateway call does not imply a downstream hop;
shared topics, imports, cycles, and deployment overlap do not prove direct calls
or failures. Preserve the graph's explicit alias and logical-API boundaries.

## 4. Follow Leads Into the Controlling Repository

Use source evidence `repo`, `path`, `start`, and `end`, joined to repository `url`
and full `revision`. Read the cited committed source rather than assuming local
HEAD or concurrent edits match. A repository URL identifies a source lead, not
necessarily a responsible team. Verify current ownership through applicable
CODEOWNERS, namespace manifests, deployment metadata, or current runbooks.

Keep these responsibilities separate, with evidence or an explicit unknown:

- Team/namespace bootstrap ownership.
- Deployment, route, policy, image pin, and rollout configuration ownership.
- Application source that computes or mutates the failing behavior.
- Upstream implementation/library ownership, distinct from an internal chart.
- Middleware or downstream collaborators relevant to this request boundary.

Trace only the request boundary implicated by the anchor, such as client body ->
gateway parser -> processor stream -> backend. Label each hop as graph-supported,
source/config-supported, request-observed, or unresolved; do not turn a logical
path into a claim that this request traversed it.

Before transferring a reproduction to the incident, reconcile deployed image/tag
or digest with source revision, effective route/policy, and protocol mode.
Unresolved mappings keep incident causality unverified. Follow a wiring-only file
to the nearest implementation that actually controls the behavior.

## 5. Return a Bounded Assessment

Stop graph exploration once you can provide:

1. The anchor, environment/window, and graph revision/freshness limitations.
2. Owner/repository candidates by responsibility, with evidence and unknowns.
3. The relevant one-hop dependencies and request boundaries, labeling certainty.
4. One falsifiable local hypothesis naming the controlling code path.
5. The cheapest safe discriminating check, including what result would falsify it.
6. Remaining coverage/access gaps and the next repository or evidence to inspect.

Prefer a focused existing test, synthetic fixture, or read-only source comparison.
For runtime attribution, propose correlated non-sensitive request/stream metadata,
not raw payload or auth logging. Recommend the check; do not execute live calls or
change code unless separately authorized. A mechanism reproduced locally remains
a mechanism, not the incident cause.

## Worked-Case Check: QA MCP HTTP 400

When the saved example is available, consult
`~/dev/mcp-eval-app/logs/qa-mcp-http400-fix-2026-10-02.md` rather than recreating
its fixture archive or incident report. It is optional context, not a dependency
of this skill. Validate routing with local read-only queries:

- Resolve `workfront-mcp-gateway` and `wf-instance-resolver`. The resolver's
  source claims should supply its pinned repository and paths; its AM and TMS
  clients are not themselves proof of a gateway extProc hop.
- If the graph lacks gateway deployment/upstream coverage, say so. Follow the
  saved report's separate evidence to `core-platform/agent-platform/agent-gateway`
  (deployment), `agentgateway/agentgateway` (Rust implementation),
  `core-platform/agent-platform/wf-instance-resolver` (processor), and namespace
  bootstrap evidence (Core Platform). These are report-derived leads, not graph
  ownership fields or invented edges. Reverify for a new incident.
- A useful hypothesis is that processor termination before body completion can
  yield an empty downstream body despite a valid client request. The saved
  synthetic fixture with an intact-body control is a discriminating check;
  preserved body bytes under the predicted condition falsify that mechanism.
- The workflow fails this check if it equates EOF with an empty client body,
  rollout proximity with a request/trace join, ordinary graceful draining with
  premature processor exit, or a reproduced mechanism with incident causality.
  Body-phase authorization also rules out unreviewed replay/bypass fallbacks.