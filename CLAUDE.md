# bartertown — spec and rules for coding agents

This file is the source of truth. Coding agents (implementation, review, fix) must read it
before doing anything. If an issue conflicts with this file, follow this file and say so in
the PR under **Decisions**.

---

## 1. What we are building

A multi-agent barter game. Eight LLM agents (from Claude, OpenAI, Gemini, Grok, DeepSeek)
each start with a paperclip and a few junk items. Over a game they trade, bid in auctions,
and craft, trying to "trade up" (one-red-paperclip style). Viral-style trend shocks change
what is valuable. At the end two leaderboards are produced:

- **Satisfaction** — numeric, no LLM: sum over inventory of `base_value × own_preference`.
- **Impressiveness** — a blind, multi-family LLM judge panel compares final inventories.

A tournament plays each world seed with seats rotated (duplicate format) so luck cancels.

---

## 2. Tournament

- `config/tournament.yaml` → `tournament.seeds` (default 3 seeds).
- Each seed is played **8 times**; game `k` (0..7) shifts every model `k` seats, so every
  model plays every seat's starting hand once. 3 seeds × 8 rotations = **24 games**.
- A seed fixes everything random about a game *except* LLM sampling: item pool draw,
  starting inventories, private preferences, auction drip order, trend schedule, tie-breaks.
- Runner must be **resumable**: each finished game writes `results/<run_id>/games/<seed>_<rot>.json`;
  re-running skips finished games.
- Output: `results/<run_id>/leaderboard.md`, `leaderboard.csv`, per-game JSON, and
  `calls.jsonl` (every LLM call: model, role, tokens, cost estimate, latency).

Seat → model mapping lives in config (`seats:`), 8 entries, model strings in LiteLLM format.

---

## 3. Value layers (do not mix these up)

1. **Base value** — hidden ground truth per item, float > 0. Set from the item catalog at
   world generation. Trend shocks multiply base values of affected categories.
   Agents never see base values directly.
2. **Private preferences** — per agent, a multiplier per category (e.g. `music: 2.0`,
   `furniture: 0.5`). Drawn from the seed. Each agent sees only its own.
3. **Impressiveness** — judged only at the end by the panel. Not based on preferences.

The 1.5× crafting cap applies to **base value only** (§6).

---

## 4. World generation (from seed)

- Item catalog: `data/items.yaml` — each item: `id, name, category, base_value, description`.
  ~80–120 items, categories like `office, kitchen, music, tech, sports, collectible,
  furniture, fashion, vehicle, experience`. Base values span ~1 (paperclip) to ~2000.
- Each agent starts with: 1 paperclip + `game.starting_items_per_agent - 1` random items
  from the low end of the catalog (base value ≤ `game.starting_value_ceiling`).
- **Reserve pool** — items not dealt out, used for auction drip (§5.2).
- **Trend schedule** — every `game.trend_shock_every` turns one shock fires:
  `{category, multiplier}` with multiplier in [0.5, 3.0]. Shocks are announced publicly
  at the start of the turn they fire, as a short headline (generated from a template, no LLM).

---

## 5. Game loop

A game is `game.turns` turns. Each turn runs these phases in order.

### 5.1 News
Announce any trend shock firing this turn. Apply multiplier to base values.

### 5.2 Auction (the item drip)
- Draw `game.auction_items_per_turn` items from the reserve pool (seeded order).
- For each lot, sealed-bid, first-price: every agent may bid a **bundle of 1–3 items from
  its inventory**, or pass. Agents see the lot's name, category, and description, not its value.
- Winner = bid with highest **total current base value** (hidden). Ties → seeded RNG.
- Winner receives the lot; the winning bundle goes **into the reserve pool** (recycled).
  Losing bids are returned. If everyone passes, the lot returns to the reserve pool.
- Agents learn who won and what the winning bundle was, not the values.

### 5.3 Trading
- Up to `game.trade_rounds_per_turn` rounds. In each round every agent (in seat order
  rotated by turn number) may send **one offer** to one other agent:
  `give: [item_ids]`, `want: [item_ids]`, optional short `message` (≤ 280 chars).
  Many-for-one and one-for-many are allowed. Max 5 items per side.
- The recipient answers `accept` or `reject` (optionally with a ≤ 280 char reply).
  No counter-offer object; counters happen by sending a new offer next round.
- Engine validates ownership at execution time; invalid offers are rejected and logged.

### 5.4 Crafting
- Each agent may craft at most once per turn: choose 2–4 owned items, give a proposed
  `name` and `description` (≤ 200 chars).
- Pipeline:
  1. **Normalizer** (cheap model, `judges.normalizer`) rewrites the proposal into a plain,
     neutral description and assigns one category from the fixed list. Strips hype.
  2. **Crafting panel** scores the normalized item's base value (§7 rules apply).
  3. `value = min(panel_median, game.craft_value_cap × sum(input base values))`.
  4. Inputs are destroyed; new item added with `crafted: true`, `crafted_by`, lineage.
- The agent learns the new item's name, normalized description, and category, not its value.

### 5.5 End of game
- Satisfaction score computed numerically.
- Impressiveness panel run (§7).

---

## 6. What agents observe each turn

Exactly this, nothing more:
- Turn number / total turns, its own inventory (names, categories, descriptions — no values),
  its own private preferences, all public news so far, public auction results,
  a public trade ticker (who traded what with whom), and its own message history
  (truncated to the last `game.history_window` events).
- Other agents' inventories are **public** (names/categories only) so trading is possible.
- No base values, no other agents' preferences, no judge scores until the game ends.

Agents act through a JSON action schema (one schema per phase). Invalid JSON → one retry
with the validation error; second failure → treated as pass.

Agent system prompt must state the goals plainly: "You will be scored on (a) the value of
your final inventory to you, by your own preferences, and (b) how impressive your final
inventory is to a panel of judges." Do not tell agents which score matters more.

---

## 7. Judging rules (crafting panel and final panel)

- **Panel** = one strong model per provider family (`judges.panel`).
- **Leave-one-out**: when judging anything owned/created by a seat, exclude judges from that
  seat's provider family. (Two Claude seats → Claude judge excluded for both.)
- **Anchors**: every judge prompt includes the fixed anchor list from `data/anchors.yaml`
  (e.g. paperclip=1, used bike=40, used car=500, small house=2000).
- **Score first, then justify**, temperature 0, strict rubric in the prompt.
- **Median** across judges, never mean.
- **Final impressiveness**: pairwise comparisons of final inventories (normalized
  descriptions only, seat identities hidden, shuffled labels "Inventory A/B").
  Every pair asked in both orders; a pair counts only if both orders agree, otherwise tie.
  Rank by win rate; also fit Bradley–Terry and report both.

---

## 8. Architecture

Python 3.12, `uv`, package in `src/paperclip/`. Suggested modules:

```
config.py      # pydantic models for config/*.yaml
world.py       # world generation from seed (catalog, inventories, prefs, trends, reserve)
engine.py      # pure, deterministic game state + phase functions. NO network, NO LLM imports
actions.py     # JSON action schemas + validation
agents/        # Agent interface: act(observation, phase) -> action
  base.py
  llm.py       # LiteLLM-backed agent
  scripted.py  # deterministic scripted agents for tests
llm/
  client.py    # single LiteLLM wrapper: retries, timeouts, cost + token logging to calls.jsonl
  replay.py    # record/replay cassettes so tests never hit the network
  mock.py      # mock provider for CI smoke runs
judges.py      # normalizer, crafting panel, final pairwise panel
scoring.py     # satisfaction, win rate, Bradley–Terry
tournament.py  # seeds × rotations, resume, aggregation
report.py      # leaderboard.md/csv, highlight trade log, plots
cli.py         # `paperclip run`, `paperclip smoke`, `paperclip report`
```

Hard rules:
- All randomness through an explicit `random.Random` derived from `(seed, purpose)`.
  Never use the global `random` module or unseeded numpy.
- The engine never calls an LLM; agents and judges are injected.
- Every LLM call goes through `llm/client.py`.
- Provider API keys come only from env vars (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`,
  `GEMINI_API_KEY`, `XAI_API_KEY`, `DEEPSEEK_API_KEY`). Never log or commit them.

---

## 9. Rules for coding agents

1. **One issue → one branch → one PR.** Branch name: `agent/issue-<number>-<short-slug>`.
2. Read the issue and its comments (`gh issue view <n> --comments`). Check "Depends on";
   if a dependency is not merged into `main`, comment on the issue and stop.
3. Keep PRs small and focused (aim < 400 changed lines excluding data/test fixtures).
4. **Tests are required** for new logic. Tests must never hit the network: use scripted
   agents, the mock provider, or replay cassettes.
5. Before opening or updating a PR, all of these must pass:
   ```
   uv run ruff format .
   uv run ruff check .
   uv run pytest -q
   ```
6. **Never edit** `.github/**`, `CLAUDE.md`, or `config/tournament.yaml` seat/model lists
   unless the issue explicitly says so.
7. PR body must use the template: Summary, Closes #n, Decisions (any ambiguity you
   resolved and why), Test plan.
8. Never merge, approve, close others' PRs, or push to `main`. A human merges.
9. If the spec is ambiguous, choose the simplest option consistent with this file and list
   it under **Decisions**. Do not invent new game mechanics.

## 10. Rules for the review agent

- Review against this file and the linked issue. Priorities, in order: correctness vs spec,
  determinism/seeding, hidden-information leaks (agents seeing values/other prefs),
  network calls in tests, test coverage, then style.
- Run `uv run ruff check .` and `uv run pytest -q` yourself.
- Post exactly **one** review comment per run. Its last line must be exactly
  `VERDICT: LGTM` or `VERDICT: CHANGES_REQUESTED`.
- Only request changes for real problems; list each as a numbered item with file:line.
