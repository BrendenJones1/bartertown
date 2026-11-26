# bartertown

The opposite of a paperclip maximizer. LLM agents start with a paperclip and a bag of junk,
then barter, bid, craft, and chase viral trends to trade up. A blind, multi-family judge
panel decides who won.

**Seats:** 8 agents from Claude, OpenAI, Gemini, Grok, and DeepSeek.
**Format:** duplicate tournament: each world seed is replayed 8 times with seats rotated,
so every model plays every starting hand and luck cancels out.
**Scores:** *Satisfaction* (value of your stuff by your own private preferences) and
*Impressiveness* (pairwise, leave-one-out judge panel).

See [`CLAUDE.md`](CLAUDE.md) for the full game spec and [`SETUP.md`](SETUP.md) for the
agent-driven development workflow.

## Quick start

```bash
uv sync
uv run pytest -q
uv run paperclip smoke                               # mock agents, no API keys
uv run paperclip run --config config/dev.yaml        # all-Haiku table, cheap
uv run paperclip run --config config/tournament.yaml # full 24-game tournament
```
