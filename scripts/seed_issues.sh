#!/usr/bin/env bash
# Creates labels and the initial backlog of agent tasks, in dependency order.
# Run once from the repo root:  bash scripts/seed_issues.sh
# Issues are NOT labeled `agent`; you start each one yourself (one at a time):
#   gh issue edit <n> --add-label agent
set -euo pipefail

gh label create agent       --color 5319e7 --description "Run by the implementation agent" --force
gh label create task        --color 0e8a16 --description "Scoped agent task" --force
gh label create needs-human --color d93f0b --description "Agents stopped; needs a human" --force

new_issue() { # title, body -> prints issue number
  gh issue create --title "$1" --label task --body "$2" | grep -oE '[0-9]+$'
}

i1=$(new_issue "Config models and seeded RNG" "## Goal
Pydantic models for config/*.yaml (CLAUDE.md §2, §8) and a seeded RNG helper.
## Scope
- src/paperclip/config.py: load + validate tournament.yaml/dev.yaml (exactly 8 seats, unique ids, families present).
- src/paperclip/rng.py: rng_for(seed, purpose) -> random.Random, stable across runs.
## Acceptance criteria
- [ ] Both configs load; invalid configs raise clear errors
- [ ] rng_for is deterministic and purpose-separated (tests)
## Depends on
none")

i2=$(new_issue "Item catalog, anchors, and world generation" "## Goal
World generation from a seed (CLAUDE.md §3, §4).
## Scope
- data/items.yaml (~100 items, categories from §4, values ~1..2000, paperclip=1)
- data/anchors.yaml (judge anchors, §7)
- src/paperclip/world.py: starting inventories, private preferences, reserve pool, trend schedule
## Acceptance criteria
- [ ] Same seed -> identical world; different seeds differ
- [ ] Every agent starts with a paperclip + (n-1) items under the value ceiling
- [ ] Seat rotation helper: rotation k shifts models k seats over fixed hands
## Depends on
#$i1")

i3=$(new_issue "Game engine: state, news phase, trading phase" "## Goal
Pure deterministic engine (CLAUDE.md §5.1, §5.3, §8). No LLM imports.
## Scope
- src/paperclip/engine.py, src/paperclip/actions.py (JSON schemas + validation)
- src/paperclip/agents/base.py (Agent interface) and agents/scripted.py
- Trend shocks, offers (many-for-one), accept/reject, ownership validation, public trade ticker
## Acceptance criteria
- [ ] Full game with scripted agents runs deterministically for a seed
- [ ] Invalid offers rejected and logged; items conserved by trades
## Depends on
#$i2")

i4=$(new_issue "Auction phase (item drip)" "## Goal
Sealed-bid first-price auction with item-bundle bids (CLAUDE.md §5.2).
## Scope
- Lot drawing from reserve, 1–3 item bids or pass, winner by hidden total base value, seeded ties
- Winning bundle recycled into reserve; losers refunded; public result announcement
## Acceptance criteria
- [ ] Tests for win, tie, all-pass, invalid bid
- [ ] Agents never receive values in observations
## Depends on
#$i3")

i5=$(new_issue "LLM client layer: LiteLLM wrapper, logging, replay, mock" "## Goal
Single entry point for every LLM call (CLAUDE.md §8).
## Scope
- llm/client.py: LiteLLM call w/ retries, timeouts, token+cost logging to calls.jsonl
- llm/replay.py: record/replay cassettes; llm/mock.py: deterministic mock provider
## Acceptance criteria
- [ ] Tests run with mock/replay only, no network
- [ ] Missing API key gives a clear error naming the env var
## Depends on
#$i1")

i6=$(new_issue "LLM agents: observations and prompts" "## Goal
LLM-backed agent (CLAUDE.md §6).
## Scope
- Observation builder (exactly what §6 allows), system prompt with both scoring goals
- Per-phase JSON action prompts; one retry on invalid JSON, then pass
## Acceptance criteria
- [ ] Test asserting observations contain no base values / other agents' preferences
- [ ] Game runs end-to-end with mock provider agents
## Depends on
#$i4, #$i5")

i7=$(new_issue "Crafting phase with normalizer and crafting panel" "## Goal
Crafting (CLAUDE.md §5.4) using judging rules (§7).
## Scope
- Normalizer, leave-one-out panel, anchors, median, 1.5x base-value cap, lineage
## Acceptance criteria
- [ ] Cap enforced (test); leave-one-out excludes crafter's family (test)
- [ ] Inputs destroyed, output owned by crafter; agent sees no value
## Depends on
#$i6")

i8=$(new_issue "Final scoring: satisfaction and impressiveness panel" "## Goal
End-of-game scoring (CLAUDE.md §5.5, §7).
## Scope
- scoring.py: satisfaction; judges.py: pairwise both-orders panel, leave-one-out, median; win rate + Bradley–Terry
## Acceptance criteria
- [ ] Order-disagreement counts as tie (test); identities hidden in judge prompts (test)
## Depends on
#$i7")

i9=$(new_issue "Tournament runner, CLI, and smoke mode" "## Goal
Seeds x rotations, resume, outputs (CLAUDE.md §2) and CLI.
## Scope
- tournament.py, report.py (leaderboard.md/csv), cli.py: run / smoke / report
- \`paperclip smoke\` = one short game with mock agents and mock judges, no network
## Acceptance criteria
- [ ] Re-running skips finished games
- [ ] \`uv run paperclip smoke\` passes in CI (owner then sets SMOKE_REQUIRED=true)
## Depends on
#$i8")

i10=$(new_issue "Report: charts and trade-log highlights for the write-up" "## Goal
Shareable outputs for a LinkedIn post.
## Scope
- Leaderboard chart (mean rank with 95% CI per model, both scores)
- Highlights: biggest trade-ups, worst fleecings, funniest crafted items
## Acceptance criteria
- [ ] \`paperclip report results/<run_id>\` writes PNGs + highlights.md
## Depends on
#$i9")

echo "Created issues #$i1..#$i10. Start with: gh issue edit $i1 --add-label agent"
