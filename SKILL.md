---
name: yahoo-fantasy-baseball
description: >
  Manage your Yahoo Fantasy Baseball team: view roster, standings, matchups,
  free agents, draft results, transactions, and injuries. Daily roster
  optimization detects inactive players, suggests bench swaps, and manages IL
  slots. Execute roster changes: swap positions, add/drop players, and submit
  waiver claims. Use when the user asks about their fantasy baseball team,
  who to start or sit, league standings, available free agents, roster moves,
  or injury updates.
metadata: {"openclaw":{"emoji":"⚾","requires":{"bins":["python3"]}}}
---

# Yahoo Fantasy Baseball

Manage your Yahoo Fantasy Baseball league: view data, optimize your daily lineup, and execute roster changes via the Yahoo Fantasy Sports API.

## Requirements

- Python 3.10+
- `yahoo_fantasy_api` — Yahoo Fantasy Sports API wrapper

**Installation:** No manual `pip install` needed. On first run, `yahoo-fantasy-baseball.py` creates a local `.deps/` virtual environment inside the skill directory and installs dependencies from `requirements.txt`. Subsequent runs reuse the existing venv. To force a clean reinstall, delete the `.deps/` directory and run any command again.

## Setup

### 1. Create a Yahoo Developer App

1. Go to [https://developer.yahoo.com/apps/](https://developer.yahoo.com/apps/)
2. Click "Create an App"
3. Set **Redirect URI** to `oob` (out-of-band — Yahoo displays the auth code on screen instead of redirecting to a URL)
4. Copy the **Consumer Key** and **Consumer Secret**

### 2. Authenticate

```bash
python yahoo-fantasy-baseball.py auth
```

Follow the prompts to enter your Consumer Key and Secret. A browser window opens for Yahoo OAuth authorization. Tokens are cached automatically — you only need to do this once.

### 3. Find Your League

```bash
python yahoo-fantasy-baseball.py leagues
```

### 4. Set Defaults

```bash
python yahoo-fantasy-baseball.py config --league 12345
```

The skill auto-detects your team within the league. You can also set it explicitly:

```bash
python yahoo-fantasy-baseball.py config --league 12345 --team 3
```

## Quick Start

```bash
# View your roster
python yahoo-fantasy-baseball.py roster

# Daily roster status (who's playing, who's off)
python yahoo-fantasy-baseball.py today

# Get optimization suggestions
python yahoo-fantasy-baseball.py optimize

# Auto-swap inactive players for bench players
python yahoo-fantasy-baseball.py swap --auto --confirm

# Add a free agent
python yahoo-fantasy-baseball.py add --player "Jake Burger" --confirm

# League standings
python yahoo-fantasy-baseball.py standings
```

## Commands

### Data Commands (Read)

```bash
# Auth & Config
python yahoo-fantasy-baseball.py auth
python yahoo-fantasy-baseball.py config --league 12345 --team 3 --season 2026
python yahoo-fantasy-baseball.py config

# Leagues & Teams
python yahoo-fantasy-baseball.py leagues [--season YEAR]
python yahoo-fantasy-baseball.py teams

# Roster & Lineup
python yahoo-fantasy-baseball.py roster [--date YYYY-MM-DD]
python yahoo-fantasy-baseball.py lineup [--week N]

# Standings & Matchups
python yahoo-fantasy-baseball.py standings
python yahoo-fantasy-baseball.py matchup [--week N]
python yahoo-fantasy-baseball.py scoreboard [--week N]

# Players & Draft
python yahoo-fantasy-baseball.py players [--search NAME] [--position POS] [--status FA|A|T|W|ALL] [--sort OR|AR|PTS|NAME|HR|ERA|...] [--sort-type season|lastweek|lastmonth] [--stat-season YEAR] [--count N]
python yahoo-fantasy-baseball.py draft [--team ID]
python yahoo-fantasy-baseball.py transactions [--type add,drop,trade]
python yahoo-fantasy-baseball.py injuries
```

### Daily Management

```bash
# Today: roster status with MLB schedule awareness
python yahoo-fantasy-baseball.py today
```

Groups your roster into ACTIVE (team playing), NOT PLAYING (team off), INJURED, and BENCH. Flags probable starting pitchers.

```bash
# Optimize: smart roster analysis with suggestions
python yahoo-fantasy-baseball.py optimize
```

Three analysis categories:
1. **Lineup swaps** — inactive starters with eligible bench replacements
2. **Pitcher rotation** — probable starters on bench, active pitchers on off days
3. **IL management** — injured players not in IL slots, cleared players still in IL

### Write Commands

All write commands show a preview by default. Add `--confirm` to execute.

```bash
# Swap a player to a different position slot
python yahoo-fantasy-baseball.py swap --player "Aaron Judge" --to BN [--confirm]

# Auto-execute all optimize swap suggestions
python yahoo-fantasy-baseball.py swap --auto [--confirm]

# Move injured player to IL slot
python yahoo-fantasy-baseball.py move-to-il --player "Zack Wheeler" [--confirm]

# Add a free agent
python yahoo-fantasy-baseball.py add --player "Jake Burger" [--confirm]

# Drop a player
python yahoo-fantasy-baseball.py drop --player "Jake Burger" [--confirm]

# Atomic add + drop
python yahoo-fantasy-baseball.py add-drop --add "Jake Burger" --drop "Luis Arraez" [--confirm]

# Waiver claim (with optional FAAB bid and drop)
python yahoo-fantasy-baseball.py claim --player "Jake Burger" [--drop "Luis Arraez"] [--faab 15] [--confirm]
```

## Common Flags

| Flag | Description |
|------|-------------|
| `--league ID` | League ID (overrides config default) |
| `--team ID` | Team ID (overrides config/auto-detect) |
| `--season YEAR` | Season year (for historical data) |
| `--week N` | Scoring week number |
| `--date YYYY-MM-DD` | Specific date (roster command) |
| `--format text\|json\|discord` | Output format (default: text) |
| `--status FA\|A\|T\|W\|ALL` | Player status filter: FA (free agents), A (available=FA+W), T (taken), W (waivers), ALL (every player) |
| `--sort OR\|AR\|PTS\|NAME\|{stat}` | Sort order for players. See stat sort reference below |
| `--sort-type season\|lastweek\|lastmonth` | Sort period (used with --sort) |
| `--stat-season YEAR` | Season year for stat columns (auto-detects: falls back to previous year if league hasn't started) |
| `--confirm` | Execute write operations (without this, preview only) |

### Sort Reference

Built-in sort modes:

| Value | Description |
|-------|-------------|
| `OR` | Overall Rank (preseason/projected) |
| `AR` | Actual Rank (by real performance) |
| `PTS` | Fantasy Points |
| `NAME` | Alphabetical |

Batting stats:

| Abbrev | Description |
|--------|-------------|
| `R` | Runs |
| `H` | Hits |
| `1B` | Singles |
| `2B` | Doubles |
| `3B` | Triples |
| `HR` | Home Runs |
| `RBI` | Runs Batted In |
| `SB` | Stolen Bases |
| `BB` | Walks |
| `K` | Strikeouts |
| `AVG` | Batting Average |
| `OBP` | On-base Percentage |
| `SLG` | Slugging Percentage |
| `OPS` | On-base + Slugging |
| `AB` | At Bats |
| `PA` | Plate Appearances |
| `TB` | Total Bases |
| `XBH` | Extra Base Hits |

Pitching stats:

| Abbrev | Description |
|--------|-------------|
| `W` | Wins |
| `L` | Losses |
| `SV` | Saves |
| `HLD` | Holds |
| `SV+H` | Saves + Holds |
| `BSV` | Blown Saves |
| `ERA` | Earned Run Average |
| `WHIP` | Walks + Hits per Inning Pitched |
| `IP` | Innings Pitched |
| `QS` | Quality Starts |
| `K9` | Strikeouts per 9 Innings |
| `BB9` | Walks per 9 Innings |

## Output Format

### Text (Default)

**roster:**

```
Roster — Team Name
Name                      Pos          Slot  Team   Status
----------------------------------------------------------
Aaron Judge               OF,Util      OF    NYY
Mookie Betts              SS,OF,Util   SS    LAD
Zack Wheeler              SP           IL    PHI    IL-60
```

**today:**

```
Today — Team Name

  ACTIVE (team playing today) (8)
    Aaron Judge            OF    NYY
    Gerrit Cole            SP    NYY   [PROBABLE STARTER]

  NOT PLAYING (team off today) (3)
    Mookie Betts           SS    LAD

  INJURED LIST (1)
    Zack Wheeler           IL    PHI   (IL-60)

  BENCH (3)
    Jake Burger            BN    MIA
```

**optimize:**

```
Roster Optimization Suggestions
==================================================

  LINEUP SWAPS (1 suggested)
    Swap Jake Burger (BN, MIA playing)
      ↔  Mookie Betts (SS, LAD off)

  PITCHER ROTATION (1 alerts)
    Gerrit Cole (NYY) is a probable starter today but is on the bench.

  IL MANAGEMENT (1 suggested)
    Move Zack Wheeler (IL-60) from SP slot to IL to free a roster spot.

Total: 3 suggestion(s)
```

### JSON

All commands support `--format json` for structured output.

### Discord

All commands support `--format discord` which wraps text output in code blocks.

## Output Fields

- **name** — Player's full name
- **player_id** — Yahoo player ID (numeric)
- **positions** — Eligible fantasy positions (e.g., OF, SP, Util)
- **selected_position** — Current lineup slot
- **team** — Real MLB team abbreviation
- **status** — Injury designation (IL, IL-60, DTD, etc.)
- **percent_owned** — Ownership percentage (free agents)
- **player_position** — Display position (draft results)

## Limitations

- **Rate limits**: Yahoo enforces API rate limits. Avoid rapid-fire requests.
- **Season scope**: Data is scoped to the configured season. Use `--season` for historical data.
- **OAuth tokens**: Tokens auto-refresh but may eventually expire, requiring re-authentication via `auth`.
- **MLB schedule**: The `today` and `optimize` commands use the MLB Stats API for schedule data (off days, probable pitchers). This data is not available from the Yahoo Fantasy API.

## Credential Storage

Credentials are stored in `~/.openclaw/credentials/yahoo-fantasy/`:
- `oauth2.json` — OAuth consumer key/secret and tokens (managed by yahoo_oauth)
- `yahoo-fantasy.json` — Default league_id, team_id, season

Legacy YFPY `.env` credentials are auto-migrated to `oauth2.json` on first use.

## Notes

- Data is sourced from the Yahoo Fantasy Sports API via the [yahoo-fantasy-api](https://github.com/spilchen/yahoo_fantasy_api) library.
- MLB schedule and probable pitcher data comes from the [MLB Stats API](https://statsapi.mlb.com/) (stdlib only, no dependencies).
- On first run, a local venv is created at `.deps/` and dependencies are installed automatically.
- Auto-detect identifies your team using `league.team_key()`. If detection fails, use `config --team <ID>` to set it manually.
- Write operations always preview changes before executing. Use `--confirm` to apply changes.
