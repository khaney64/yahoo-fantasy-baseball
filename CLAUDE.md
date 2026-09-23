# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is an **OpenClaw skill** for Yahoo Fantasy Baseball. It accesses league data via the Yahoo Fantasy Sports API using the [yahoo-fantasy-api](https://github.com/spilchen/yahoo_fantasy_api) Python library. The skill is **read-only** — it queries data and suggests optimizations but does not modify rosters.

## Architecture

```
yahoo-fantasy-baseball/
  SKILL.md                    — Skill manifest (frontmatter + docs)
  CLAUDE.md                   — This file
  yahoo-fantasy-baseball.py   — Entry point (--setup for deps, fail-fast if missing)
  requirements.txt            — yahoo_fantasy_api dependency
  .gitignore                  — .deps/, __pycache__, .env
  scripts/
    fantasy.py                — Main CLI (argparse subcommands)
    yahoo_api.py              — yahoo-fantasy-api wrapper: auth, config, league/team construction
    formatters.py             — Text, JSON, Discord output formatting
    mlb_client.py             — MLB Stats API client (stdlib only): schedule + probable pitchers
```

### Entry Point

`yahoo-fantasy-baseball.py` is the entry point. Run `--setup` to create the `.deps/` venv and install pinned dependencies from `requirements.txt`. On normal runs, it fails fast if deps are missing, then re-execs into the venv and calls `scripts/fantasy.py:main()`.

### Module Responsibilities

**`scripts/yahoo_api.py`** — API layer:
- `run_auth()` — Interactive OAuth setup, stores consumer key/secret to `~/.openclaw/credentials/yahoo-fantasy/oauth2.json` (0600 perms on Unix)
- `_migrate_legacy_env()` — Auto-migrates YFPY `.env` credentials to `oauth2.json` format
- `get_game(season)` — Returns authenticated `(yfa.Game, OAuth2)` tuple
- `get_league(league_id, season)` — Returns `yfa.League` instance
- `get_team(league, team_key)` — Returns `yfa.Team` instance
- `fetch_players_sorted(league, status, position, sort, sort_type, sort_season)` — Custom Yahoo API call bypassing the library to support sort params (`OR`, `AR`, `PTS`, `NAME`), status filtering (`FA`, `T`, `A`, `W`, `ALL`), and ownership data. `ALL` is synthetic — merges `T` + `A` results.
- `_parse_players_page(raw)` — Custom JSON parser for Yahoo player responses with `percent_owned` + `ownership` subresources (library only handles `percent_owned`)
- `load_config()` / `save_config()` — Read/write `yahoo-fantasy.json` defaults
- `resolve_league_id()` — Resolves league ID from args or config
- `resolve_team_key()` — Resolves team key from args, config, or auto-detection via `league.team_key()`

**`scripts/fantasy.py`** — CLI layer:
- Argparse with subcommands: `auth`, `config`, `leagues`, `teams`, `roster`, `lineup`, `standings`, `matchup`, `scoreboard`, `players`, `draft`, `transactions`, `injuries`, `today`, `day`, `lineup-check`, `standouts`, `optimize`
- All commands are read-only
- Each `cmd_*` function: resolves args → calls yahoo_api → calls formatters → prints

Two distinct scoring paths — do not conflate them:
- `_compute_standout_score()` — a **single-day** composite with fixed weights, used by `standouts` to rank one day's box scores. Correct for that job.
- `_score_pool()` — the **optimizer's** scorer. Derives weights from the league's own categories, works in rates rather than totals (`average_season` blended with `lastmonth` at `_RECENCY_WEIGHT`), normalizes batters and pitchers in separate pools, and emits a 0–100 `_opt_score`. Falls back to `_compute_standout_score` only when the league's categories can't be read.

Applying the daily formula to season totals is what made the optimizer volume-biased (it effectively ranked players by at-bats accumulated) and left rate categories like OBP contributing under 0.2% of a score. Keep the two paths separate.

**`scripts/formatters.py`** — Output layer:
- One `format_*` function per data type
- Each supports text (tabular), JSON (`json.dumps`), and discord (wrapped in code blocks)
- Helper functions handle dict-based data from yahoo-fantasy-api via `_safe()` accessor

**`scripts/mlb_client.py`** — MLB schedule layer (stdlib only):
- `teams_playing_today(date_str)` — Set of team abbreviations with games today
- `probable_pitchers_today(date_str)` — Dict of team abbr → pitcher name
- `game_opponents_today(date_str)` — Dict of team abbr → opponent abbr
- `normalize_team_abbr(yahoo_abbr)` — Convert Yahoo team abbr to MLB Stats API abbr

## Running

```bash
# First time: install dependencies
python yahoo-fantasy-baseball.py --setup

# Normal usage
python yahoo-fantasy-baseball.py roster

# Or from scripts/ directly (requires venv active)
cd scripts && python fantasy.py roster
```

## Key yahoo-fantasy-api Methods Used

| Command | yahoo-fantasy-api Method |
|---------|--------------------------|
| `leagues` | `gm.league_ids(seasons=[year])` |
| `teams` | `league.teams()` |
| `roster` | `team.roster(day=date)` |
| `lineup` | roster + `league.stat_categories()` + `league.player_stats()` |
| `standings` | `league.standings()` |
| `matchup` | `team.matchup(week)` |
| `scoreboard` | `league.matchups(week)` |
| `players` | `league.free_agents(position)` / `league.player_details(name)` / `yahoo_api.fetch_players_sorted()` (with `--sort`, `--status`, or `--status ALL`). With `--position`, also fetches `league.stat_categories()` + `league.player_stats()` to display stat columns (batting or pitching based on position type). `--stat-season` controls which season's stats to show (auto-detects pre-season → previous year). |
| `draft` | `league.draft_results()` |
| `transactions` | `league.transactions(types, count)` |
| `injuries` | `team.roster(day=today)` filtered |
| `today` | roster + `mlb_client.teams_playing_today()` + `mlb_client.probable_pitchers_today()` (shortcut for `day` with today's date) |
| `day` | roster + `mlb_client.teams_playing_today(date)` + `mlb_client.probable_pitchers_today(date)` |
| `standouts` | `league.teams()` + `team.roster(day=date)` x N + `league.player_stats(ids, "date", date=yesterday)` |
| `optimize` | roster + MLB schedule + position analysis + `league.stat_categories()` + `league.player_stats()` across three windows (`season`, `average_season`, `lastmonth`) |

## Data Format

yahoo-fantasy-api returns plain Python dicts (not custom objects). Key shapes:

- **Roster player**: `{"player_id": int, "name": str, "position_type": "B"|"P", "eligible_positions": [str], "selected_position": str, "status": str}`
- **Teams**: `dict[team_key, team_dict]` — keyed by team_key string
- **Standings**: `list[dict]` — ordered by rank (1st = index 0)
- **Free agents**: `list[dict]` — same shape as roster players plus `percent_owned`
- **Draft picks**: `list[dict]` — with `round`, `pick`, `team_key`, `player_id`, enriched with `team_name`, `player_name`, `player_position` via `league.teams()` and `league.player_details()`

## Credential Storage

**Preferred:** Set `YAHOO_CONSUMER_KEY` and `YAHOO_CONSUMER_SECRET` env vars (via OpenClaw config or shell). The skill writes them to `oauth2.json` for yahoo_oauth token management, but the static secrets don't need to be entered interactively.

```
~/.openclaw/credentials/yahoo-fantasy/
  oauth2.json             — OAuth consumer key/secret + tokens (managed by yahoo_oauth, 0600 perms on Unix)
  yahoo-fantasy.json      — Default league_id, team_id, season
```

Legacy `.env` credentials from YFPY are auto-migrated to `oauth2.json` on first use.

## Dependencies

- **yahoo_fantasy_api==2.12.2** (installed via `--setup`) — Yahoo Fantasy Sports API wrapper
- **yahoo_oauth** (dependency of yahoo_fantasy_api) — OAuth2 authentication
- Python 3.10+

## Key Conventions

- Data from yahoo-fantasy-api is plain dicts. Use `formatters._safe(obj, key, default)` to safely access values.
- The game code for MLB is `"mlb"`. Game keys vary by season.
- Team auto-detection uses `league.team_key()` which returns the current user's team key.
- All output goes to stdout. Errors go to stderr.
- All commands are read-only — no roster modifications.
- MLB schedule data comes from the MLB Stats API (stdlib only, no dependencies).
