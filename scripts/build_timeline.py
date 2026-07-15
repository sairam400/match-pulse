"""
Fetch a StatsBomb open-data match and compress it into a compact timeline
JSON for The Match Pulse renderer.

Usage:
    python build_timeline.py --match-id 3869685 --out ../site/data/3869685.json
    python build_timeline.py --list-finals        # helper to find match ids
"""
import argparse
import json
import math
import os
import urllib.request

RAW = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"
CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "raw")

# Approximate broadcast-style team colors. StatsBomb doesn't ship kit colors,
# and several national teams share near-identical blues (e.g. Argentina vs
# France), which would collapse the tug-of-war blend into mud. Where a
# match's two sides are too close in hue, override with a value tuned for
# contrast rather than literal kit accuracy.
TEAM_COLORS = {
    "Argentina": "#5DC9F1",
    "France": "#FF4757",
    "Croatia": "#EE3355",
    "Morocco": "#C8102E",
    "England": "#FFFFFF",
    "Brazil": "#FFD200",
    "Spain": "#FF4646",
    "Germany": "#FFFFFF",
    "Portugal": "#C8102E",
    "Netherlands": "#FF6600",
}
DEFAULT_COLORS = ["#5DC9F1", "#FFD200"]

BOX_X_MIN = 102.0
BOX_Y_MIN = 18.0
BOX_Y_MAX = 62.0

W_XG = 4.0
W_SHOT = 1.0
W_BOX = 0.4
EMA_HALFLIFE_MIN = 3.0
MOMENTUM_K = 1.4
INTENSITY_K = 2.4


def fetch(path):
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_path = os.path.join(CACHE_DIR, path.replace("/", "_"))
    if os.path.exists(cache_path):
        with open(cache_path, encoding="utf-8") as f:
            return json.load(f)
    url = f"{RAW}/{path}"
    with urllib.request.urlopen(url) as resp:
        data = json.load(resp)
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(data, f)
    return data


def find_match(match_id):
    competitions = fetch("competitions.json")
    for comp in competitions:
        cid, sid = comp["competition_id"], comp["season_id"]
        try:
            matches = fetch(f"matches/{cid}/{sid}.json")
        except Exception:
            continue
        for m in matches:
            if m["match_id"] == match_id:
                return m
    raise SystemExit(f"match_id {match_id} not found in any competition/season")


def team_color(name, other_name, used):
    c = TEAM_COLORS.get(name)
    if c is None:
        c = DEFAULT_COLORS[0] if not used else DEFAULT_COLORS[1]
    return c


def in_box(loc):
    if not loc:
        return False
    x, y = loc[0], loc[1]
    return x >= BOX_X_MIN and BOX_Y_MIN <= y <= BOX_Y_MAX


# StatsBomb's `minute` field resets to each period's nominal kickoff minute
# and counts that period's own elapsed time on top of it — it is NOT a
# cumulative match clock. So minute 47 in period 1 (first-half stoppage) and
# minute 47 (never happens, but e.g. minute 50) in period 2 (a few minutes
# into the second half) are different real moments sharing one label. Bucket
# indices and animation pacing need a true continuous clock instead.
NOMINAL_START = {1: 0, 2: 45, 3: 90, 4: 105, 5: 120}
CLOCK_CAP = {1: 45, 2: 90, 3: 105, 4: 120}


def clock_label(period, minute):
    cap = CLOCK_CAP.get(period)
    if cap is None or minute <= cap:
        return f"{minute}'"
    return f"{cap}+{minute - cap}'"


def build(match_id, out_path):
    match = find_match(match_id)
    home = match["home_team"]["home_team_name"]
    away = match["away_team"]["away_team_name"]
    events = fetch(f"events/{match_id}.json")

    periods_present = sorted(set(e["period"] for e in events))
    period_duration_s = {}
    for p in periods_present:
        pev = [e for e in events if e["period"] == p]
        period_duration_s[p] = max(
            (e["minute"] - NOMINAL_START[p]) * 60 + e["second"] for e in pev
        )
    period_offset_s = {}
    running = 0.0
    for p in periods_present:
        period_offset_s[p] = running
        running += period_duration_s[p]
    total_seconds = running
    duration = math.ceil(total_seconds / 60.0)

    def continuous_minute(e):
        p = e["period"]
        rel_s = (e["minute"] - NOMINAL_START[p]) * 60 + e["second"]
        return (period_offset_s[p] + rel_s) / 60.0

    def bucket(cm):
        return min(int(cm), duration - 1)

    raw = {
        "home": [0.0] * duration,
        "away": [0.0] * duration,
    }

    def side_of(team_name):
        if team_name == home:
            return "home"
        if team_name == away:
            return "away"
        return None

    goals = []
    cards = []
    subs = []
    shootout = []
    shootout_kick_no = {"home": 0, "away": 0}

    for e in events:
        etype = e["type"]["name"]
        minute = e["minute"]
        period = e["period"]
        cm = continuous_minute(e)
        b = bucket(cm)
        team_name = e.get("team", {}).get("name")
        side = side_of(team_name)

        if etype == "Shot" and side:
            shot = e["shot"]
            xg = shot.get("statsbomb_xg", 0.0) or 0.0
            raw[side][b] += W_XG * xg + W_SHOT
            is_goal = shot.get("outcome", {}).get("name") == "Goal"
            # Shootout goals don't count toward the match score (it stays
            # frozen at the AET scoreline) — tracked only in `shootout`.
            if is_goal and period != 5:
                goals.append({
                    "minute": minute, "second": e["second"],
                    "continuous_minute": round(cm, 3),
                    "clock_label": clock_label(period, minute),
                    "side": side,
                    "player": e.get("player", {}).get("name", ""),
                    "method": shot.get("type", {}).get("name", "Open Play"),
                    "period": period,
                })
            if period == 5:
                shootout_kick_no[side] += 1
                shootout.append({
                    "minute": minute, "second": e["second"],
                    "continuous_minute": round(cm, 3),
                    "side": side,
                    "player": e.get("player", {}).get("name", ""),
                    "outcome": "scored" if is_goal else "missed",
                    "kick_order": shootout_kick_no[side],
                })

        elif etype in ("Own Goal For",) and side:
            # side here is the team that gains the goal (benefits)
            goals.append({
                "minute": minute, "second": e["second"],
                "continuous_minute": round(cm, 3),
                "clock_label": clock_label(period, minute),
                "side": side,
                "player": e.get("player", {}).get("name", "Own Goal"),
                "method": "Own Goal", "period": period,
            })

        elif etype == "Pass" and side:
            end_loc = e.get("pass", {}).get("end_location")
            completed = "outcome" not in e.get("pass", {})
            if completed and in_box(end_loc):
                raw[side][b] += W_BOX

        elif etype == "Carry" and side:
            end_loc = e.get("carry", {}).get("end_location")
            if in_box(end_loc):
                raw[side][b] += W_BOX

        elif etype == "Foul Committed" and side:
            card = e.get("foul_committed", {}).get("card")
            if card:
                cards.append({
                    "minute": minute, "second": e["second"],
                    "continuous_minute": round(cm, 3),
                    "clock_label": clock_label(period, minute),
                    "side": side,
                    "player": e.get("player", {}).get("name", ""),
                    "card": card["name"], "period": period,
                })
        elif etype == "Bad Behaviour" and side:
            card = e.get("bad_behaviour", {}).get("card")
            if card:
                cards.append({
                    "minute": minute, "second": e["second"],
                    "continuous_minute": round(cm, 3),
                    "clock_label": clock_label(period, minute),
                    "side": side,
                    "player": e.get("player", {}).get("name", ""),
                    "card": card["name"], "period": period,
                })
        elif etype == "Substitution" and side:
            sub = e["substitution"]
            subs.append({
                "minute": minute, "second": e["second"],
                "continuous_minute": round(cm, 3),
                "clock_label": clock_label(period, minute),
                "side": side,
                "player_off": e.get("player", {}).get("name", ""),
                "player_on": sub.get("replacement", {}).get("name", ""),
                "period": period,
            })

    goals.sort(key=lambda g: g["continuous_minute"])
    cards.sort(key=lambda c: c["continuous_minute"])
    subs.sort(key=lambda s: s["continuous_minute"])
    shootout.sort(key=lambda s: s["continuous_minute"])

    home_score = away_score = 0
    for g in goals:
        if g["side"] == "home":
            home_score += 1
        else:
            away_score += 1
        g["score_after"] = {"home": home_score, "away": away_score}

    # Causal EMA smoothing so momentum reflects recent pressure only.
    alpha = 1 - 0.5 ** (1.0 / EMA_HALFLIFE_MIN)
    smooth = {"home": [0.0] * duration, "away": [0.0] * duration}
    for side in ("home", "away"):
        acc = 0.0
        for m in range(duration):
            acc = acc + alpha * (raw[side][m] - acc)
            smooth[side][m] = acc

    minutes = []
    for m in range(duration):
        h, a = smooth["home"][m], smooth["away"][m]
        momentum = math.tanh((h - a) / MOMENTUM_K)
        intensity = max(0.0, min(1.0, (h + a) / INTENSITY_K))
        minutes.append({
            "m": m,
            "momentum": round(momentum, 4),
            "intensity": round(intensity, 4),
        })

    periods = []
    for p in periods_present:
        start_min = period_offset_s[p] / 60.0
        end_min = (period_offset_s[p] + period_duration_s[p]) / 60.0
        periods.append({"period": p, "start": round(start_min, 2), "end": round(end_min, 2)})

    used = []
    home_color = team_color(home, away, used)
    used.append(home_color)
    away_color = team_color(away, home, used) if away != home else DEFAULT_COLORS[1]
    if away_color == home_color:
        away_color = DEFAULT_COLORS[1]

    penalties = None
    if shootout:
        ph = sum(1 for s in shootout if s["side"] == "home" and s["outcome"] == "scored")
        pa = sum(1 for s in shootout if s["side"] == "away" and s["outcome"] == "scored")
        penalties = {"home": ph, "away": pa}

    timeline = {
        "meta": {
            "match_id": match_id,
            "competition": match["competition"]["competition_name"],
            "season": match["season"]["season_name"],
            "stage": match["competition_stage"]["name"],
            "date": match["match_date"],
            "duration_minutes": duration,
            "home_team": {"name": home, "color": home_color},
            "away_team": {"name": away, "color": away_color},
            "final_score": {"home": match["home_score"], "away": match["away_score"]},
            "penalties": penalties,
            "periods": periods,
        },
        "minutes": minutes,
        "events": {
            "goals": goals,
            "cards": cards,
            "subs": subs,
            "shootout": shootout,
        },
    }

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(timeline, f, ensure_ascii=False, indent=1)

    print(f"wrote {out_path}")
    print(f"  {home} {match['home_score']}-{match['away_score']} {away}", end="")
    if penalties:
        print(f"  (pens {penalties['home']}-{penalties['away']})")
    else:
        print()
    print(f"  duration {duration} min, {len(goals)} goals, {len(cards)} cards, {len(subs)} subs, {len(shootout)} shootout kicks")
    raw_max = max(max(raw["home"]), max(raw["away"]))
    print(f"  raw pressure max={raw_max:.2f} (tune W_XG/W_SHOT/W_BOX/MOMENTUM_K/INTENSITY_K against this)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--match-id", type=int, required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    build(args.match_id, args.out)
