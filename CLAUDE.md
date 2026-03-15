# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is an **OpenClaw skill** for Yahoo Fantasy Baseball. It accesses league data and performs roster management via the Yahoo Fantasy Sports API using the [yahoo-fantasy-api](https://github.com/spilchen/yahoo_fantasy_api) Python library. The skill supports both **read operations** (viewing data) and **write operations** (roster moves, add/drops, waiver claims).

## Architecture

```
yahoo-fantasy-baseball/
  SKILL.md                    — Skill manifest (frontmatter + docs)
  CLAUDE.md                   — This file
  yahoo-fantasy-baseball.py   — Venv bootstrap entry point
  requirements.txt            — yahoo_fantasy_api dependency
  .gitignore                  — .deps/, __pycache__, .env
  scripts/
    fantasy.py                — Main CLI (argparse subcommands)
    yahoo_api.py              — yahoo-fantasy-api wrapper: auth, config, league/team construction
    formatters.py             — Text, JSON, Discord output formatting
    mlb_client.py             — MLB Stats API client (stdlib only): schedule + probable pitchers
```

### Entry Point

`yahoo-fantasy-baseball.py` is a bootstrap script. It auto-creates a `.deps/` venv, installs `yahoo_fantasy_api` from `requirements.txt`, re-execs into the venv, then calls `scripts/fantasy.py:main()`.

### Module Responsibilities

**`scripts/yahoo_api.py`** — API layer:
- `run_auth()` — Interactive OAuth setup, stores consumer key/secret to `~/.openclaw/credentials/yahoo-fantasy/oauth2.json`
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
- Argparse with subcommands organized into read and write operations
- Read: `auth`, `config`, `leagues`, `teams`, `roster`, `lineup`, `standings`, `matchup`, `scoreboard`, `players`, `draft`, `transactions`, `injuries`, `today`, `optimize`
- Write: `swap`, `move-to-il`, `add`, `drop`, `add-drop`, `claim`
- Write commands require `--confirm` flag to execute; without it they show a preview
- Each `cmd_*` function: resolves args → calls yahoo_api → calls formatters → prints

**`scripts/formatters.py`** — Output layer:
- One `format_*` function per data type
- Each supports text (tabular), JSON (`json.dumps`), and discord (wrapped in code blocks)
- Helper functions handle dict-based data from yahoo-fantasy-api via `_safe()` accessor
- Write operation previews via `format_preview()`

**`scripts/mlb_client.py`** — MLB schedule layer (stdlib only):
- `teams_playing_today(date_str)` — Set of team abbreviations with games today
- `probable_pitchers_today(date_str)` — Dict of team abbr → pitcher name
- `game_opponents_today(date_str)` — Dict of team abbr → opponent abbr
- `normalize_team_abbr(yahoo_abbr)` — Convert Yahoo team abbr to MLB Stats API abbr

## Running

```bash
# Direct (bootstraps venv on first run)
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
| `today` | roster + `mlb_client.teams_playing_today()` + `mlb_client.probable_pitchers_today()` |
| `optimize` | roster + MLB schedule + position analysis |
| `swap` | `team.change_positions(date, lineup)` |
| `move-to-il` | `team.change_positions(date, [{player_id, "IL"}])` |
| `add` | `team.add_player(player_id)` |
| `drop` | `team.drop_player(player_id)` |
| `add-drop` | `team.add_and_drop_players(add_id, drop_id)` |
| `claim` | `team.claim_player(id, faab)` / `team.claim_and_drop_players(add_id, drop_id, faab)` |

## Data Format

yahoo-fantasy-api returns plain Python dicts (not custom objects). Key shapes:

- **Roster player**: `{"player_id": int, "name": str, "position_type": "B"|"P", "eligible_positions": [str], "selected_position": str, "status": str}`
- **Teams**: `dict[team_key, team_dict]` — keyed by team_key string
- **Standings**: `list[dict]` — ordered by rank (1st = index 0)
- **Free agents**: `list[dict]` — same shape as roster players plus `percent_owned`
- **Draft picks**: `list[dict]` — with `round`, `pick`, `team_key`, `player_id`, enriched with `team_name`, `player_name`, `player_position` via `league.teams()` and `league.player_details()`

## Credential Storage

```
~/.openclaw/credentials/yahoo-fantasy/
  oauth2.json             — OAuth consumer key/secret + tokens (managed by yahoo_oauth)
  yahoo-fantasy.json      — Default league_id, team_id, season
```

Legacy `.env` credentials from YFPY are auto-migrated to `oauth2.json` on first use.

## Dependencies

- **yahoo_fantasy_api** (installed via bootstrap venv) — Yahoo Fantasy Sports API wrapper
- **yahoo_oauth** (dependency of yahoo_fantasy_api) — OAuth2 authentication
- Python 3.10+

## Key Conventions

- Data from yahoo-fantasy-api is plain dicts. Use `formatters._safe(obj, key, default)` to safely access values.
- The game code for MLB is `"mlb"`. Game keys vary by season.
- Team auto-detection uses `league.team_key()` which returns the current user's team key.
- All output goes to stdout. Errors go to stderr.
- Write operations require `--confirm` flag — without it, they show a preview and exit.
- MLB schedule data comes from the MLB Stats API (stdlib only, no dependencies).
