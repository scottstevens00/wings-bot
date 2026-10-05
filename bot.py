"""
Have the Red Wings Been Eliminated Yet?
Sends "No. Magic number: N." (or "Yes.") to your phone every morning, ready to post.

Magic number = Wings losses + wins by the team they're chasing
(each one swings the gap by 2 points; Wings OT losses count as half).
"""
import json, math, os, sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
import requests

TEAM = "DET"
STATE_FILE = Path(__file__).parent / "state.json"
NHL = "https://api-web.nhle.com/v1"
ET = ZoneInfo("America/Detroit")
POST_HOUR = 8  # send the morning tweet at 8 AM ET, after every game has finished
DRY_RUN = os.getenv("DRY_RUN", "").lower() in ("1", "true", "yes")


def get(path):
    r = requests.get(f"{NHL}/{path}", timeout=20)
    r.raise_for_status()
    return r.json()


def load_state():
    return json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}


def save_state(state):
    if DRY_RUN:
        print("[DRY RUN] State not saved.")
        return
    STATE_FILE.write_text(json.dumps(state, indent=2) + "\n")


def last_completed_game(schedule):
    done = [g for g in schedule["games"]
            if g.get("gameType") == 2 and g.get("gameState") in ("OFF", "FINAL")]
    return done[-1] if done else None


def elimination_threshold(standings):
    """Points the Wings must stay above to keep a playoff path alive.
    Wings get in by finishing top 3 in the Atlantic OR as one of the top 2
    wild cards, so they're out only when BOTH paths are closed."""
    east = [t for t in standings if t["conferenceName"] == "Eastern"
            and t["teamAbbrev"]["default"] != TEAM]
    by_pts = lambda ts: sorted(ts, key=lambda t: t["points"], reverse=True)

    divisions = {}
    for t in east:
        divisions.setdefault(t["divisionName"], []).append(t)

    # Path 1: catch the 3rd-place Atlantic team
    atl3 = by_pts(divisions["Atlantic"])[2]["points"]

    # Path 2: catch the 2nd wild card (best non-top-3 teams across both divisions)
    top3 = {t["teamAbbrev"]["default"] for d in divisions.values() for t in by_pts(d)[:3]}
    wc_pool = by_pts([t for t in east if t["teamAbbrev"]["default"] not in top3])
    wc2 = wc_pool[1]["points"]

    return min(atl3, wc2)


def compose(standings, total_games):
    wings = next(t for t in standings if t["teamAbbrev"]["default"] == TEAM)
    clinch = wings.get("clinchIndicator", "")

    if clinch == "e":
        return "Yes.", 0
    if clinch in ("x", "y", "z", "p"):
        return "No. Somehow.", None

    remaining = total_games - wings["gamesPlayed"]
    max_pts = wings["points"] + 2 * remaining
    threshold = elimination_threshold(standings)
    magic = math.ceil((max_pts - threshold + 1) / 2)

    if magic <= 0:
        return "Yes.", 0
    return f"No. Magic number: {magic}.", magic


def post_tweet(text):
    """Send the tweet to your phone via ntfy (free). Tap 'Post on X' to post it."""
    if DRY_RUN:
        print(f"[DRY RUN] Would send: {text}")
        return
    from urllib.parse import quote
    intent = "https://x.com/intent/post?text=" + quote(text, safe="")
    r = requests.post(
        f"https://ntfy.sh/{os.environ['NTFY_TOPIC']}",
        data=text.encode("utf-8"),
        headers={
            "Title": "Wings tweet ready",
            "Actions": f"view, Post on X, {intent}, clear=true",
        },
        timeout=20,
    )
    r.raise_for_status()
    print(f"Sent to phone: {text}")


def game_date_et(game):
    utc = datetime.fromisoformat(game["startTimeUTC"].replace("Z", "+00:00"))
    return utc.astimezone(ET).date()


def result_line(game):
    home = game["homeTeam"]["abbrev"] == TEAM
    us, them = (game["homeTeam"], game["awayTeam"]) if home else (game["awayTeam"], game["homeTeam"])
    opp = them.get("placeName", {}).get("default", them["abbrev"])
    verb = "Won" if us["score"] > them["score"] else "Lost"
    extra = game.get("gameOutcome", {}).get("lastPeriodType", "REG")
    suffix = f" ({extra})" if extra in ("OT", "SO") else ""
    where = "vs." if home else "at"
    return f"{verb} {us['score']}-{them['score']}{suffix} {where} {opp}"


def main():
    state = load_state()
    now = datetime.now(ET)
    today = now.date()
    yesterday = today - timedelta(days=1)

    if now.hour < POST_HOUR:
        print("Too early. Waiting for the morning.")
        return
    if state.get("last_post_date") == str(today):
        print("Already sent today's tweet.")
        return

    schedule = get(f"club-schedule-season/{TEAM}/now")
    season = [g for g in schedule["games"] if g.get("gameType") == 2]
    if not season or not (game_date_et(season[0]) <= yesterday <= game_date_et(season[-1])):
        print("Outside the regular season.")
        return

    finals = [g for g in season if g.get("gameState") in ("OFF", "FINAL")]
    last_night = next((g for g in finals if game_date_et(g) == yesterday), None)

    standings = get("standings/now")["standings"]
    wings = next(t for t in standings if t["teamAbbrev"]["default"] == TEAM)
    if wings["gamesPlayed"] < len(finals):
        print("Standings haven't caught up yet. Trying again next run.")
        return

    headline, magic = compose(standings, len(season))
    detail = result_line(last_night) if last_night else "Didn't play last night."
    text = f"{headline}\n\n{detail}"

    post_tweet(text)
    state.update(last_post_date=str(today), last_tweet=text, magic_number=magic)
    save_state(state)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
