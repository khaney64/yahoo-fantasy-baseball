#!/usr/bin/env python3
"""
Yahoo Fantasy Baseball — roster management, standings, matchups, free agents,
draft, transactions, injuries, daily roster optimization, and write operations
via the Yahoo Fantasy Sports API (yahoo-fantasy-api).

Usage:
    python scripts/fantasy.py auth
    python scripts/fantasy.py config --league 12345
    python scripts/fantasy.py leagues
    python scripts/fantasy.py roster [--format text|json|discord]
    python scripts/fantasy.py lineup [--week N] [--format text|json|discord]
    python scripts/fantasy.py standings [--format text|json|discord]
    python scripts/fantasy.py matchup [--week N] [--format text|json|discord]
    python scripts/fantasy.py scoreboard [--week N] [--format text|json|discord]
    python scripts/fantasy.py players [--search NAME] [--position POS] [--format text|json|discord]
    python scripts/fantasy.py draft [--format text|json|discord]
    python scripts/fantasy.py transactions [--type add,drop,trade] [--format text|json|discord]
    python scripts/fantasy.py injuries [--format text|json|discord]
    python scripts/fantasy.py today [--format text|json|discord]
    python scripts/fantasy.py optimize [--format text|json|discord]
    python scripts/fantasy.py swap --player "Name" --to POS [--confirm]
    python scripts/fantasy.py swap --auto [--confirm]
    python scripts/fantasy.py move-to-il --player "Name" [--confirm]
    python scripts/fantasy.py add --player "Name" [--confirm]
    python scripts/fantasy.py drop --player "Name" [--confirm]
    python scripts/fantasy.py add-drop --add "Name" --drop "Name" [--confirm]
    python scripts/fantasy.py claim --player "Name" [--drop "Name"] [--faab N] [--confirm]
"""

import argparse
import io
import sys
from datetime import datetime, date

# Ensure stdout handles Unicode (Windows consoles default to cp1252)
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ('utf-8', 'utf8'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import yahoo_api
import formatters


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_league_and_team(args, config, need_team=True):
    """Common setup: resolve league, optionally resolve team.

    Returns:
        (league, team_key, team_name) if need_team, else (league, None, None).
    """
    league_id = yahoo_api.resolve_league_id(getattr(args, "league", None), config)
    season = getattr(args, "season", None) or config.get("season")
    league = yahoo_api.get_league(league_id, season=season)

    if not need_team:
        return league, None, None

    team_key = yahoo_api.resolve_team_key(league, getattr(args, "team", None), config)
    # Get team name
    team_name = ""
    teams = league.teams()
    if team_key in teams:
        team_name = teams[team_key].get("name", "")
    return league, team_key, team_name


def _resolve_player_on_roster(roster, name_query):
    """Find a player on the roster by substring name match.

    Returns the player dict, or exits with error if not found or ambiguous.
    """
    query_lower = name_query.lower()
    matches = []
    for p in roster:
        pname = formatters._player_name(p).lower()
        if query_lower in pname:
            matches.append(p)

    if len(matches) == 0:
        print(f"Error: No player matching '{name_query}' found on roster.", file=sys.stderr)
        sys.exit(1)
    if len(matches) > 1:
        # Check for exact match
        exact = [p for p in matches if formatters._player_name(p).lower() == query_lower]
        if len(exact) == 1:
            return exact[0]
        print(f"Error: Ambiguous player name '{name_query}'. Matches:", file=sys.stderr)
        for p in matches:
            print(f"  - {formatters._player_name(p)}", file=sys.stderr)
        sys.exit(1)
    return matches[0]


def _resolve_free_agent(league, name_query):
    """Find a free agent by name search.

    Returns the player dict, or exits with error if not found or ambiguous.
    """
    # Use league.player_details() for name search
    try:
        results = league.player_details(name_query)
    except Exception as e:
        print(f"Error searching for player: {e}", file=sys.stderr)
        sys.exit(1)

    if not results:
        print(f"Error: No player matching '{name_query}' found.", file=sys.stderr)
        sys.exit(1)

    # Filter to just free agents by checking ownership
    query_lower = name_query.lower()
    matches = []
    for p in results:
        pname = formatters._player_name(p).lower()
        if query_lower in pname:
            matches.append(p)

    if not matches:
        matches = results  # Use all results if substring filter found nothing

    if len(matches) == 1:
        return matches[0]

    # Check for exact match
    exact = [p for p in matches if formatters._player_name(p).lower() == query_lower]
    if len(exact) == 1:
        return exact[0]

    print(f"Error: Multiple players match '{name_query}':", file=sys.stderr)
    for p in matches[:10]:
        print(f"  - {formatters._player_name(p)} (ID: {formatters._player_id(p)})", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Subcommand handlers — Read operations
# ---------------------------------------------------------------------------

def cmd_auth(args):
    """One-time OAuth setup."""
    yahoo_api.run_auth()


def cmd_config(args):
    """Set default league/team/season."""
    config = yahoo_api.load_config()

    if args.league:
        config["league_id"] = str(args.league)
    if args.team:
        config["team_id"] = str(args.team)
    if args.season:
        config["season"] = int(args.season)

    if not any([args.league, args.team, args.season]):
        if config:
            print("Current config:")
            for k, v in config.items():
                print(f"  {k}: {v}")
        else:
            print("No config set. Use --league, --team, or --season to configure.")
        return

    yahoo_api.save_config(config)
    print("Config updated:")
    for k, v in config.items():
        print(f"  {k}: {v}")


def cmd_leagues(args):
    """List user's fantasy baseball leagues."""
    gm, sc = yahoo_api.get_game()
    season = args.season if args.season else datetime.now().year

    try:
        league_ids = gm.league_ids(seasons=[str(season)])
    except Exception as e:
        print(f"Error fetching leagues: {e}", file=sys.stderr)
        sys.exit(1)

    if not league_ids:
        print(f"No fantasy baseball leagues found for {season}.")
        return

    # Build league info list
    leagues = []
    for lid in league_ids:
        try:
            lg = gm.to_league(lid)
            settings = lg.settings()
            leagues.append({
                "league_id": lid.split(".l.")[-1] if ".l." in lid else lid,
                "name": settings.get("name", ""),
                "season": settings.get("season", str(season)),
                "num_teams": settings.get("num_teams", ""),
                "league_key": lid,
            })
        except Exception:
            leagues.append({
                "league_id": lid.split(".l.")[-1] if ".l." in lid else lid,
                "name": "(unable to fetch)",
                "season": str(season),
                "num_teams": "",
                "league_key": lid,
            })

    print(formatters.format_leagues(leagues, fmt=args.format))


def cmd_teams(args):
    """List all teams in the league."""
    config = yahoo_api.load_config()
    league, _, _ = _get_league_and_team(args, config, need_team=False)

    try:
        teams = league.teams()
    except Exception as e:
        print(f"Error fetching teams: {e}", file=sys.stderr)
        sys.exit(1)

    if not teams:
        print("No teams found in league.")
        return

    print(formatters.format_teams(teams, fmt=args.format))


def cmd_roster(args):
    """Show current roster with positions and injury status."""
    config = yahoo_api.load_config()
    league, team_key, team_name = _get_league_and_team(args, config)
    tm = yahoo_api.get_team(league, team_key)

    try:
        if args.date:
            roster_date = datetime.strptime(args.date, "%Y-%m-%d").date()
            players = tm.roster(day=roster_date)
        else:
            players = tm.roster()
    except Exception as e:
        print(f"Error fetching roster: {e}", file=sys.stderr)
        sys.exit(1)

    if not players:
        print("No players found on roster.")
        return

    print(formatters.format_roster(players, team_name=team_name, fmt=args.format))


def cmd_lineup(args):
    """Roster with scoring categories and matchup context for start/sit analysis."""
    config = yahoo_api.load_config()
    league, team_key, team_name = _get_league_and_team(args, config)
    tm = yahoo_api.get_team(league, team_key)

    # Get stat categories
    categories = []
    try:
        stat_cats = league.stat_categories()
        categories = formatters._extract_categories_from_settings(stat_cats)
    except Exception:
        pass

    # Get roster
    try:
        players = tm.roster()
    except Exception as e:
        print(f"Error fetching lineup: {e}", file=sys.stderr)
        sys.exit(1)

    if not players:
        print("No players found on roster.")
        return

    # Get player stats if we have categories
    if categories and players:
        try:
            player_ids = [p.get("player_id") for p in players if p.get("player_id")]
            if player_ids:
                week = args.week
                if week:
                    stats = league.player_stats(player_ids, "week", week=week)
                else:
                    stats = league.player_stats(player_ids, "season")
                # Merge stats back into player dicts
                stats_by_id = {}
                for s in stats:
                    pid = s.get("player_id")
                    if pid:
                        stats_by_id[pid] = s
                for p in players:
                    pid = p.get("player_id")
                    if pid in stats_by_id:
                        p.update(stats_by_id[pid])
        except Exception:
            pass

    # Get matchup context
    matchup_info = None
    try:
        week = args.week or league.current_week()
        if week:
            opponent_key = tm.matchup(week)
            if opponent_key:
                teams = league.teams()
                opp_name = teams.get(opponent_key, {}).get("name", opponent_key)
                matchup_info = {
                    "week": week,
                    "opponent": opp_name,
                    "opponent_key": opponent_key,
                }
    except Exception:
        pass

    print(formatters.format_lineup(players, categories, matchup_info=matchup_info,
                                   team_name=team_name, fmt=args.format))


def cmd_standings(args):
    """Show league standings."""
    config = yahoo_api.load_config()
    league, _, _ = _get_league_and_team(args, config, need_team=False)

    try:
        standings = league.standings()
    except Exception as e:
        print(f"Error fetching standings: {e}", file=sys.stderr)
        sys.exit(1)

    print(formatters.format_standings(standings, fmt=args.format))


def cmd_matchup(args):
    """Show current week matchup details."""
    config = yahoo_api.load_config()
    league, team_key, team_name = _get_league_and_team(args, config)
    tm = yahoo_api.get_team(league, team_key)

    try:
        week = args.week or league.current_week()
        opponent_key = tm.matchup(week)
    except Exception as e:
        print(f"Error fetching matchup: {e}", file=sys.stderr)
        sys.exit(1)

    # Get opponent name
    opponent_name = opponent_key
    try:
        teams = league.teams()
        opponent_name = teams.get(opponent_key, {}).get("name", opponent_key)
    except Exception:
        pass

    print(formatters.format_matchup(opponent_key, my_team_name=team_name,
                                     opponent_name=opponent_name, week=week,
                                     fmt=args.format))


def cmd_scoreboard(args):
    """Show all league matchups for a week."""
    config = yahoo_api.load_config()
    league, _, _ = _get_league_and_team(args, config, need_team=False)

    try:
        week = args.week or league.current_week()
        scoreboard = league.matchups(week=week)
    except Exception as e:
        print(f"Error fetching scoreboard: {e}", file=sys.stderr)
        sys.exit(1)

    print(formatters.format_scoreboard(scoreboard, week=week, fmt=args.format))


def cmd_players(args):
    """Search/browse free agents and available players."""
    config = yahoo_api.load_config()
    league, _, _ = _get_league_and_team(args, config, need_team=False)

    position = args.position  # None means all players
    sort = getattr(args, "sort", None)
    sort_type = getattr(args, "sort_type", None)
    status = getattr(args, "status", None) or "FA"

    # Determine stat season early — needed for both sort_season and stat fetch
    stat_season = getattr(args, "stat_season", None)
    if not stat_season:
        season = getattr(args, "season", None) or config.get("season")
        try:
            settings = league.settings()
            start_date = settings.get("start_date", "")
            if start_date:
                from datetime import date as _date
                parts = start_date.split("-")
                league_start = _date(int(parts[0]), int(parts[1]), int(parts[2]))
                if _date.today() < league_start:
                    stat_season = int(parts[0]) - 1
        except Exception:
            pass
        if not stat_season and season:
            stat_season = int(season)

    try:
        if args.search:
            # Use player_details for name search
            players = league.player_details(args.search)
        elif sort or status != "FA":
            players = yahoo_api.fetch_players_sorted(
                league, status=status, position=position,
                sort=sort, sort_type=sort_type, sort_season=stat_season)
        else:
            # library free_agents() requires a position arg
            players = league.free_agents(position or "B")
    except Exception as e:
        print(f"Error fetching players: {e}", file=sys.stderr)
        sys.exit(1)

    if not players:
        print("No players found.")
        return

    # Apply count limit
    count = args.count if args.count else 25
    start = args.start or 0
    players = players[start:start + count]

    if not players:
        print("No players match the filter criteria.")
        return

    # Fetch stats only when --position is explicitly provided (skip for --search)
    categories = []
    if not args.search and args.position:
        try:
            # Fetch stat categories
            stat_cats = league.stat_categories()
            all_categories = formatters._extract_categories_from_settings(stat_cats)

            # Filter by position type: pitching positions get P stats, else B
            pitching_positions = {"SP", "RP", "P"}
            pos_type = "P" if position.upper() in pitching_positions else "B"
            categories = [c for c in all_categories if c.get("position_type") == pos_type]

            # Fetch player stats
            player_ids = [p.get("player_id") for p in players if p.get("player_id")]
            if player_ids:
                kwargs = {"season": stat_season} if stat_season else {}
                stats = league.player_stats(player_ids, "season", **kwargs)
                stats_by_id = {}
                for s in stats:
                    pid = s.get("player_id")
                    if pid:
                        stats_by_id[pid] = s
                for p in players:
                    pid = p.get("player_id")
                    if pid in stats_by_id:
                        p.update(stats_by_id[pid])
        except Exception:
            categories = []

    print(formatters.format_players(players, categories=categories, fmt=args.format))


def cmd_draft(args):
    """Show draft results."""
    config = yahoo_api.load_config()
    league, _, _ = _get_league_and_team(args, config, need_team=False)

    try:
        picks = league.draft_results()
    except Exception as e:
        print(f"Error fetching draft results: {e}", file=sys.stderr)
        sys.exit(1)

    if not picks:
        print("No draft results found.")
        return

    # Build team_key -> team_name mapping
    teams = league.teams()
    team_names = {}
    for tkey, tdata in teams.items():
        team_names[tkey] = tdata.get("name", tkey)

    # Filter by team if requested
    if args.team:
        target_keys = set()
        for tkey, tdata in teams.items():
            if str(tdata.get("team_id")) == str(args.team) or tkey.endswith(f".t.{args.team}"):
                target_keys.add(tkey)
        if target_keys:
            picks = [p for p in picks if p.get("team_key") in target_keys]

    # Resolve player names via batch player_details call
    player_ids = [p.get("player_id") for p in picks if p.get("player_id")]
    player_info = {}  # pid_str -> {"name": ..., "position": ...}
    if player_ids:
        try:
            details = league.player_details(player_ids)
            for d in details:
                pid = str(d.get("player_id", ""))
                name_obj = d.get("name", {})
                if isinstance(name_obj, dict):
                    name = name_obj.get("full", pid)
                else:
                    name = str(name_obj) if name_obj else pid
                pos = d.get("display_position", "") or d.get("primary_position", "")
                player_info[pid] = {"name": name, "position": pos}
        except Exception:
            pass  # Fall back to showing player_id if resolution fails

    # Enrich picks with resolved names and positions
    for pick in picks:
        pick["team_name"] = team_names.get(pick.get("team_key", ""), pick.get("team_key", ""))
        pid = str(pick.get("player_id", ""))
        info = player_info.get(pid, {})
        pick["player_name"] = info.get("name", pid if pid else "")
        pick["player_position"] = info.get("position", "")

    print(formatters.format_draft(picks, fmt=args.format))


def cmd_transactions(args):
    """Show recent league transactions."""
    config = yahoo_api.load_config()
    league, _, _ = _get_league_and_team(args, config, need_team=False)

    try:
        tran_types = args.type or "add,drop,trade"
        transactions = league.transactions(tran_types, "25")
    except Exception as e:
        print(f"Error fetching transactions: {e}", file=sys.stderr)
        sys.exit(1)

    if not transactions:
        print("No recent transactions found.")
        return

    print(formatters.format_transactions(transactions, fmt=args.format))


def cmd_injuries(args):
    """Show injured players on roster."""
    config = yahoo_api.load_config()
    league, team_key, team_name = _get_league_and_team(args, config)
    tm = yahoo_api.get_team(league, team_key)

    try:
        players = tm.roster(day=date.today())
    except Exception as e:
        print(f"Error fetching roster: {e}", file=sys.stderr)
        sys.exit(1)

    print(formatters.format_injuries(players, team_name=team_name, fmt=args.format))


# ---------------------------------------------------------------------------
# Phase 2: today command
# ---------------------------------------------------------------------------

def cmd_today(args):
    """Show daily roster status with MLB schedule awareness."""
    import mlb_client

    config = yahoo_api.load_config()
    league, team_key, team_name = _get_league_and_team(args, config)
    tm = yahoo_api.get_team(league, team_key)

    today_str = date.today().strftime("%Y-%m-%d")

    try:
        roster = tm.roster(day=date.today())
    except Exception as e:
        print(f"Error fetching roster: {e}", file=sys.stderr)
        sys.exit(1)

    if not roster:
        print("No players found on roster.")
        return

    # Fetch MLB schedule data
    teams_playing = mlb_client.teams_playing_today(today_str)
    probable_pitchers = mlb_client.probable_pitchers_today(today_str)

    # Build probable starters set (player names)
    probable_starter_names = set(probable_pitchers.values())

    # Group players
    IL_STATUSES = {"IL", "IL10", "IL15", "IL60", "DL", "IL-10", "IL-15", "IL-60"}
    BENCH_SLOTS = {"BN", "IL", "IL+", "DL", "DL+", "NA"}
    IL_SLOTS = {"IL", "IL+", "DL", "DL+"}

    groups = {"active": [], "not_playing": [], "injured": [], "bench": []}

    for player in roster:
        slot = formatters._player_selected_position(player)
        status = formatters._player_status(player)
        team_abbr = formatters._player_team(player)
        mlb_abbr = mlb_client.normalize_team_abbr(team_abbr)

        if slot.upper() in IL_SLOTS or status.upper() in IL_STATUSES:
            groups["injured"].append(player)
        elif slot.upper() in BENCH_SLOTS:
            groups["bench"].append(player)
        elif mlb_abbr in teams_playing:
            groups["active"].append(player)
        else:
            groups["not_playing"].append(player)

    print(formatters.format_today(groups, probable_starter_names,
                                   team_name=team_name, fmt=args.format))


# ---------------------------------------------------------------------------
# Phase 3: optimize command
# ---------------------------------------------------------------------------

def _normalize_pitcher_name(name):
    """Normalize a pitcher name for matching (lowercase, strip suffixes)."""
    name = name.lower().strip()
    for suffix in (" jr.", " jr", " sr.", " sr", " iii", " ii", " iv"):
        if name.endswith(suffix):
            name = name[:-len(suffix)].strip()
    return name


def _pitcher_names_match(roster_name, mlb_name):
    """Check if a roster pitcher name matches an MLB probable pitcher name."""
    rn = _normalize_pitcher_name(roster_name)
    mn = _normalize_pitcher_name(mlb_name)

    # Exact match
    if rn == mn:
        return True

    # Last name + first initial match
    r_parts = rn.split()
    m_parts = mn.split()
    if len(r_parts) >= 2 and len(m_parts) >= 2:
        if r_parts[-1] == m_parts[-1] and r_parts[0][0] == m_parts[0][0]:
            return True

    return False


def cmd_optimize(args):
    """Smart roster analysis with swap suggestions, pitcher rotation, and IL management."""
    import mlb_client

    config = yahoo_api.load_config()
    league, team_key, team_name = _get_league_and_team(args, config)
    tm = yahoo_api.get_team(league, team_key)

    today_str = date.today().strftime("%Y-%m-%d")

    try:
        roster = tm.roster(day=date.today())
    except Exception as e:
        print(f"Error fetching roster: {e}", file=sys.stderr)
        sys.exit(1)

    if not roster:
        print("No players found on roster.")
        return

    teams_playing = mlb_client.teams_playing_today(today_str)
    probable_pitchers = mlb_client.probable_pitchers_today(today_str)
    opponents = mlb_client.game_opponents_today(today_str)

    IL_STATUSES = {"IL", "IL10", "IL15", "IL60", "DL", "DTD", "IL-10", "IL-15", "IL-60"}
    IL_SLOTS = {"IL", "IL+", "DL", "DL+"}
    BENCH_SLOTS = {"BN"}

    suggestions = {"swaps": [], "pitcher_alerts": [], "il_moves": []}

    # Categorize players
    active_players = []  # In active slots
    bench_players = []   # On bench (BN)

    for player in roster:
        slot = formatters._player_selected_position(player).upper()
        if slot in IL_SLOTS:
            continue  # Skip IL players for swap analysis
        if slot in BENCH_SLOTS:
            bench_players.append(player)
        elif slot not in ("", "NA"):
            active_players.append(player)

    # 1. Inactive player detection + bench swap suggestions
    for active_p in active_players:
        active_team = mlb_client.normalize_team_abbr(formatters._player_team(active_p))
        active_slot = formatters._player_selected_position(active_p)

        if active_team and active_team not in teams_playing:
            # This active player's team is off — look for bench swaps
            active_positions = formatters._player_position(active_p).upper().split(",")

            for bench_p in bench_players:
                bench_team = mlb_client.normalize_team_abbr(formatters._player_team(bench_p))

                if bench_team and bench_team in teams_playing:
                    # Bench player's team is playing — check position eligibility
                    bench_positions = formatters._player_position(bench_p).upper().split(",")

                    # Can the bench player fill the active player's slot?
                    if active_slot.upper() in bench_positions or "UTIL" in bench_positions:
                        opp = opponents.get(bench_team, "?")
                        suggestions["swaps"].append({
                            "bench_player": formatters._player_name(bench_p),
                            "bench_player_id": formatters._player_id(bench_p),
                            "bench_slot": "BN",
                            "bench_team": bench_team,
                            "bench_opponent": opp,
                            "active_player": formatters._player_name(active_p),
                            "active_player_id": formatters._player_id(active_p),
                            "active_slot": active_slot,
                            "active_team": active_team,
                            "target_slot": active_slot,
                        })
                        break  # One suggestion per inactive active player

    # 2. Pitcher rotation alerts
    for player in roster:
        slot = formatters._player_selected_position(player).upper()
        team_abbr = mlb_client.normalize_team_abbr(formatters._player_team(player))
        name = formatters._player_name(player)
        positions = formatters._player_position(player).upper()

        if "SP" not in positions and "RP" not in positions:
            continue

        # Check if this pitcher is a probable starter
        is_probable = False
        if team_abbr in probable_pitchers:
            if _pitcher_names_match(name, probable_pitchers[team_abbr]):
                is_probable = True

        if is_probable and slot == "BN":
            # Probable starter is on bench
            suggestions["pitcher_alerts"].append({
                "type": "probable_starter_benched",
                "player": name,
                "player_id": formatters._player_id(player),
                "team": team_abbr,
                "message": f"{name} ({team_abbr}) is a probable starter today but is on the bench.",
            })
        elif not is_probable and slot in ("SP", "P") and team_abbr not in teams_playing:
            suggestions["pitcher_alerts"].append({
                "type": "active_pitcher_not_playing",
                "player": name,
                "player_id": formatters._player_id(player),
                "team": team_abbr,
                "message": f"{name} ({team_abbr}) is in an active pitching slot but their team is off today.",
            })

    # 3. IL slot management
    for player in roster:
        slot = formatters._player_selected_position(player).upper()
        status = formatters._player_status(player).upper()
        name = formatters._player_name(player)

        # Player has IL-eligible status but NOT in an IL slot
        if status in IL_STATUSES and slot not in IL_SLOTS:
            suggestions["il_moves"].append({
                "type": "move_to_il",
                "player": name,
                "player_id": formatters._player_id(player),
                "current_slot": slot,
                "status": status,
                "message": f"Move {name} ({status}) from {slot} slot to IL to free a roster spot.",
            })

        # Player is in an IL slot but has NO injury status (cleared)
        if slot in IL_SLOTS and not status:
            suggestions["il_moves"].append({
                "type": "activate_from_il",
                "player": name,
                "player_id": formatters._player_id(player),
                "current_slot": slot,
                "message": f"Activate {name} from {slot} — player has no injury designation.",
            })

    print(formatters.format_optimize(suggestions, fmt=args.format))


# ---------------------------------------------------------------------------
# Phase 4: Write operations
# ---------------------------------------------------------------------------

def cmd_swap(args):
    """Change lineup positions (swap player to a new slot)."""
    config = yahoo_api.load_config()
    league, team_key, team_name = _get_league_and_team(args, config)
    tm = yahoo_api.get_team(league, team_key)
    today = date.today()

    roster = tm.roster(day=today)

    if args.auto:
        # Run optimize logic and execute all swap suggestions
        import mlb_client

        today_str = today.strftime("%Y-%m-%d")
        teams_playing = mlb_client.teams_playing_today(today_str)
        probable_pitchers = mlb_client.probable_pitchers_today(today_str)
        opponents = mlb_client.game_opponents_today(today_str)

        IL_SLOTS = {"IL", "IL+", "DL", "DL+"}
        BENCH_SLOTS = {"BN"}

        changes = []
        active_players = []
        bench_players = []

        for player in roster:
            slot = formatters._player_selected_position(player).upper()
            if slot in IL_SLOTS:
                continue
            if slot in BENCH_SLOTS:
                bench_players.append(player)
            elif slot not in ("", "NA"):
                active_players.append(player)

        used_bench = set()
        for active_p in active_players:
            active_team = mlb_client.normalize_team_abbr(formatters._player_team(active_p))
            active_slot = formatters._player_selected_position(active_p)

            if active_team and active_team not in teams_playing:
                for bench_p in bench_players:
                    bp_id = formatters._player_id(bench_p)
                    if bp_id in used_bench:
                        continue
                    bench_team = mlb_client.normalize_team_abbr(formatters._player_team(bench_p))
                    if bench_team and bench_team in teams_playing:
                        bench_positions = formatters._player_position(bench_p).upper().split(",")
                        if active_slot.upper() in bench_positions or "UTIL" in bench_positions:
                            changes.append({
                                "active": formatters._player_name(active_p),
                                "active_id": formatters._player_id(active_p),
                                "bench": formatters._player_name(bench_p),
                                "bench_id": bp_id,
                                "slot": active_slot,
                            })
                            used_bench.add(bp_id)
                            break

        if not changes:
            print("No automatic swaps needed — lineup looks good.")
            return

        # Preview
        for c in changes:
            print(f"  {c['bench']} → {c['slot']}  (replaces {c['active']} → BN)")

        if not args.confirm:
            print(f"\n{len(changes)} swap(s) suggested. Add --confirm to execute.")
            return

        # Execute: build the full modified lineup
        modified = []
        swap_map = {}  # active_id -> bench change info
        for c in changes:
            swap_map[c["active_id"]] = c

        for c in changes:
            modified.append({"player_id": c["bench_id"], "selected_position": c["slot"]})
            modified.append({"player_id": c["active_id"], "selected_position": "BN"})

        try:
            tm.change_positions(today, modified)
            print(f"Executed {len(changes)} swap(s) successfully.")
        except Exception as e:
            print(f"Error executing swaps: {e}", file=sys.stderr)
            sys.exit(1)
        return

    # Manual swap: --player and --to
    if not args.player or not args.to:
        print("Error: --player and --to are required (or use --auto).", file=sys.stderr)
        sys.exit(1)

    player = _resolve_player_on_roster(roster, args.player)
    name = formatters._player_name(player)
    pid = formatters._player_id(player)
    current_slot = formatters._player_selected_position(player)
    target_slot = args.to.upper()

    details = {
        "player": name,
        "player_id": pid,
        "current_slot": current_slot,
        "new_slot": target_slot,
    }

    if not args.confirm:
        print(formatters.format_preview("Swap Position", details, fmt=args.format))
        return

    try:
        tm.change_positions(today, [{"player_id": pid, "selected_position": target_slot}])
        print(f"Moved {name} to {target_slot}.")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_move_to_il(args):
    """Move an injured player to an IL slot."""
    config = yahoo_api.load_config()
    league, team_key, team_name = _get_league_and_team(args, config)
    tm = yahoo_api.get_team(league, team_key)
    today = date.today()

    roster = tm.roster(day=today)
    player = _resolve_player_on_roster(roster, args.player)
    name = formatters._player_name(player)
    pid = formatters._player_id(player)
    current_slot = formatters._player_selected_position(player)
    status = formatters._player_status(player)

    details = {
        "player": name,
        "player_id": pid,
        "current_slot": current_slot,
        "new_slot": "IL",
        "status": status,
    }

    if not args.confirm:
        print(formatters.format_preview("Move to IL", details, fmt=args.format))
        return

    try:
        tm.change_positions(today, [{"player_id": pid, "selected_position": "IL"}])
        print(f"Moved {name} to IL.")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_add(args):
    """Add a free agent to the roster."""
    config = yahoo_api.load_config()
    league, team_key, team_name = _get_league_and_team(args, config)
    tm = yahoo_api.get_team(league, team_key)

    player = _resolve_free_agent(league, args.player)
    name = formatters._player_name(player)
    pid = formatters._player_id(player)

    details = {
        "action": "Add free agent",
        "player": name,
        "player_id": pid,
    }

    if not args.confirm:
        print(formatters.format_preview("Add Player", details, fmt=args.format))
        return

    try:
        tm.add_player(pid)
        print(f"Added {name} to your roster.")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_drop(args):
    """Drop a player from the roster."""
    config = yahoo_api.load_config()
    league, team_key, team_name = _get_league_and_team(args, config)
    tm = yahoo_api.get_team(league, team_key)

    roster = tm.roster()
    player = _resolve_player_on_roster(roster, args.player)
    name = formatters._player_name(player)
    pid = formatters._player_id(player)

    details = {
        "action": "Drop player",
        "player": name,
        "player_id": pid,
    }

    if not args.confirm:
        print(formatters.format_preview("Drop Player", details, fmt=args.format))
        return

    try:
        tm.drop_player(pid)
        print(f"Dropped {name} from your roster.")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_add_drop(args):
    """Add a free agent and drop a roster player in one transaction."""
    config = yahoo_api.load_config()
    league, team_key, team_name = _get_league_and_team(args, config)
    tm = yahoo_api.get_team(league, team_key)

    add_player = _resolve_free_agent(league, args.add)
    add_name = formatters._player_name(add_player)
    add_pid = formatters._player_id(add_player)

    roster = tm.roster()
    drop_player = _resolve_player_on_roster(roster, args.drop)
    drop_name = formatters._player_name(drop_player)
    drop_pid = formatters._player_id(drop_player)

    details = {
        "add_player": add_name,
        "add_player_id": add_pid,
        "drop_player": drop_name,
        "drop_player_id": drop_pid,
    }

    if not args.confirm:
        print(formatters.format_preview("Add/Drop", details, fmt=args.format))
        return

    try:
        tm.add_and_drop_players(add_pid, drop_pid)
        print(f"Added {add_name}, dropped {drop_name}.")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_claim(args):
    """Submit a waiver claim."""
    config = yahoo_api.load_config()
    league, team_key, team_name = _get_league_and_team(args, config)
    tm = yahoo_api.get_team(league, team_key)

    claim_player = _resolve_free_agent(league, args.player)
    claim_name = formatters._player_name(claim_player)
    claim_pid = formatters._player_id(claim_player)

    details = {
        "action": "Waiver claim",
        "player": claim_name,
        "player_id": claim_pid,
    }
    if args.faab is not None:
        details["faab_bid"] = args.faab

    drop_pid = None
    if args.drop:
        roster = tm.roster()
        drop_player = _resolve_player_on_roster(roster, args.drop)
        drop_name = formatters._player_name(drop_player)
        drop_pid = formatters._player_id(drop_player)
        details["drop_player"] = drop_name
        details["drop_player_id"] = drop_pid

    if not args.confirm:
        print(formatters.format_preview("Waiver Claim", details, fmt=args.format))
        return

    try:
        if drop_pid:
            tm.claim_and_drop_players(claim_pid, drop_pid, faab=args.faab)
            print(f"Waiver claim submitted: {claim_name} (dropping {drop_name}).")
        else:
            tm.claim_player(claim_pid, faab=args.faab)
            print(f"Waiver claim submitted: {claim_name}.")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Yahoo Fantasy Baseball — roster management, optimization, and more"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # auth
    subparsers.add_parser("auth", help="One-time Yahoo OAuth setup")

    # config
    config_parser = subparsers.add_parser("config", help="Set default league/team/season")
    config_parser.add_argument("--league", help="Default league ID")
    config_parser.add_argument("--team", help="Default team ID")
    config_parser.add_argument("--season", type=int, help="Default season year")

    # leagues
    leagues_parser = subparsers.add_parser("leagues", help="List your fantasy baseball leagues")
    leagues_parser.add_argument("--season", type=int, help="Season year (default: current)")
    leagues_parser.add_argument(
        "--format", choices=["text", "json", "discord"], default="text",
        help="Output format (default: text)"
    )

    # teams
    teams_parser = subparsers.add_parser("teams", help="List all teams in the league")
    teams_parser.add_argument("--league", help="League ID (or use config default)")
    teams_parser.add_argument("--season", type=int, help="Season year")
    teams_parser.add_argument(
        "--format", choices=["text", "json", "discord"], default="text",
        help="Output format (default: text)"
    )

    # Common args for most data commands
    def _add_common_args(p, with_team=True):
        p.add_argument("--league", help="League ID (or use config default)")
        if with_team:
            p.add_argument("--team", help="Team ID (or use config default)")
        p.add_argument("--season", type=int, help="Season year")
        p.add_argument(
            "--format", choices=["text", "json", "discord"], default="text",
            help="Output format (default: text)"
        )

    # roster
    roster_parser = subparsers.add_parser("roster", help="Current roster with stats")
    _add_common_args(roster_parser)
    roster_parser.add_argument("--date", help="Date for roster (YYYY-MM-DD)")

    # lineup
    lineup_parser = subparsers.add_parser("lineup", help="Roster with scoring categories for start/sit analysis")
    _add_common_args(lineup_parser)
    lineup_parser.add_argument("--week", type=int, help="Scoring week number")

    # standings
    standings_parser = subparsers.add_parser("standings", help="League standings")
    _add_common_args(standings_parser, with_team=False)

    # matchup
    matchup_parser = subparsers.add_parser("matchup", help="Your matchup details")
    _add_common_args(matchup_parser)
    matchup_parser.add_argument("--week", type=int, help="Specific week number")

    # scoreboard
    scoreboard_parser = subparsers.add_parser("scoreboard", help="All league matchups for a week")
    _add_common_args(scoreboard_parser, with_team=False)
    scoreboard_parser.add_argument("--week", type=int, help="Specific week number")

    # players
    players_parser = subparsers.add_parser("players", help="Search/browse available players")
    _add_common_args(players_parser, with_team=False)
    players_parser.add_argument("--search", help="Filter by player name")
    players_parser.add_argument("--position", help="Filter by position (e.g., SP, OF, SS)")
    players_parser.add_argument("--status", help="Player status: FA (free agents, default), A (available=FA+W), T (taken), W (waivers), ALL (every player)")
    players_parser.add_argument("--sort", help="Sort order: OR (overall rank), AR (actual rank), PTS (points), NAME, or stat abbrev (HR, ERA, SB, etc.)")
    players_parser.add_argument("--sort-type", help="Sort period: season, lastweek, lastmonth")
    players_parser.add_argument("--count", type=int, help="Max players to show (default: 25)")
    players_parser.add_argument("--start", type=int, help="Start offset for pagination")
    players_parser.add_argument("--stat-season", type=int, help="Season year for stats (auto-detects if omitted)")

    # draft
    draft_parser = subparsers.add_parser("draft", help="Draft results")
    _add_common_args(draft_parser)

    # transactions
    txn_parser = subparsers.add_parser("transactions", help="Recent league transactions")
    _add_common_args(txn_parser, with_team=False)
    txn_parser.add_argument("--type", help="Filter by type (e.g., add,drop,trade)")

    # injuries
    injuries_parser = subparsers.add_parser("injuries", help="Injured players on roster")
    _add_common_args(injuries_parser)

    # today (Phase 2)
    today_parser = subparsers.add_parser("today", help="Daily roster status with MLB schedule")
    _add_common_args(today_parser)

    # optimize (Phase 3)
    optimize_parser = subparsers.add_parser("optimize", help="Roster optimization suggestions")
    _add_common_args(optimize_parser)

    # swap (Phase 4)
    swap_parser = subparsers.add_parser("swap", help="Change lineup positions")
    _add_common_args(swap_parser)
    swap_parser.add_argument("--player", help="Player name to move")
    swap_parser.add_argument("--to", help="Target position slot (e.g., BN, SP, OF)")
    swap_parser.add_argument("--auto", action="store_true", help="Auto-execute optimize suggestions")
    swap_parser.add_argument("--confirm", action="store_true", help="Execute the change (without this, preview only)")

    # move-to-il (Phase 4)
    il_parser = subparsers.add_parser("move-to-il", help="Move injured player to IL slot")
    _add_common_args(il_parser)
    il_parser.add_argument("--player", required=True, help="Player name to move to IL")
    il_parser.add_argument("--confirm", action="store_true", help="Execute the change")

    # add (Phase 4)
    add_parser = subparsers.add_parser("add", help="Add a free agent")
    _add_common_args(add_parser)
    add_parser.add_argument("--player", required=True, help="Player name to add")
    add_parser.add_argument("--confirm", action="store_true", help="Execute the change")

    # drop (Phase 4)
    drop_parser = subparsers.add_parser("drop", help="Drop a player")
    _add_common_args(drop_parser)
    drop_parser.add_argument("--player", required=True, help="Player name to drop")
    drop_parser.add_argument("--confirm", action="store_true", help="Execute the change")

    # add-drop (Phase 4)
    add_drop_parser = subparsers.add_parser("add-drop", help="Add one player, drop another")
    _add_common_args(add_drop_parser)
    add_drop_parser.add_argument("--add", required=True, help="Player name to add")
    add_drop_parser.add_argument("--drop", required=True, help="Player name to drop")
    add_drop_parser.add_argument("--confirm", action="store_true", help="Execute the change")

    # claim (Phase 4)
    claim_parser = subparsers.add_parser("claim", help="Submit a waiver claim")
    _add_common_args(claim_parser)
    claim_parser.add_argument("--player", required=True, help="Player name to claim")
    claim_parser.add_argument("--drop", help="Player name to drop (optional)")
    claim_parser.add_argument("--faab", type=int, help="FAAB bid amount")
    claim_parser.add_argument("--confirm", action="store_true", help="Execute the change")

    args = parser.parse_args()

    commands = {
        "auth": cmd_auth,
        "config": cmd_config,
        "leagues": cmd_leagues,
        "teams": cmd_teams,
        "roster": cmd_roster,
        "lineup": cmd_lineup,
        "standings": cmd_standings,
        "matchup": cmd_matchup,
        "scoreboard": cmd_scoreboard,
        "players": cmd_players,
        "draft": cmd_draft,
        "transactions": cmd_transactions,
        "injuries": cmd_injuries,
        "today": cmd_today,
        "optimize": cmd_optimize,
        "swap": cmd_swap,
        "move-to-il": cmd_move_to_il,
        "add": cmd_add,
        "drop": cmd_drop,
        "add-drop": cmd_add_drop,
        "claim": cmd_claim,
    }

    handler = commands.get(args.command)
    if handler:
        handler(args)


if __name__ == "__main__":
    main()
