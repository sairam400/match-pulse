# The Match Pulse

A football match, redrawn as a heartbeat.

This started from a simple question: what if a match didn't look like a
stats dashboard, but like a living pulse line — one that speeds up, wanders,
flatlines for a card, and spikes when the ball hits the net? That's what
this is. Ninety-plus minutes of a real match, compressed into about 35
seconds of canvas animation, sweeping left to right, with the line's height
and color telling you who's pressing and by how much.

First match in here is Argentina vs France, the 2022 World Cup Final. Felt
like the obvious stress test — a match with a routine first half, a
disastrous-for-Argentina final ten minutes, a Messi extra-time goal that
still gives me chills, and a penalty shootout with real misses in it. If a
pulse-line chart couldn't make that match feel alive, it wasn't going to
work for anything else either.

## What's actually happening on screen

A horizontal line sweeps across the full match. Its height above or below
the baseline is attacking momentum — a rolling blend of xG, shot volume, and
completed box entries for each side — so the line leans toward whichever
team's color is currently on top, like a slow tug of war. Goals interrupt it
with a flash and a scoreline tick. Cards show up as a brief stuttering
flatline with a red tick, not a clean marker, because a card is a stoppage,
not a data point. Extra time gets a distinct label instead of pretending
it's just more regulation time, and penalties abandon the pulse metaphor
entirely — a shootout isn't a flow of momentum, it's a sequence of discrete,
nervy moments, so it gets its own beat-by-beat track: hold, snap, reveal,
make or miss.

There's a `?record=1` mode that holds a clean two-second lead-in and then
plays through exactly once, no visible UI, meant for screen-recording
straight into something you'd actually post.

## How it's built

Two pieces:

- **`scripts/build_timeline.py`** pulls one match's event data from
  [StatsBomb's open data](https://github.com/statsbomb/open-data) and
  boils it down into a compact per-minute timeline: momentum, intensity,
  goals, cards, subs, and (if the match went to penalties) every shootout
  kick, makes and misses both.
- **`site/index.html`** is the whole renderer — one file, plain canvas, no
  framework. It reads that timeline JSON and does everything: the spline
  through the momentum curve, the glow, the sweep pacing, the goal/card/
  shootout effects, the HUD.

Worth knowing if you poke around the data pipeline: StatsBomb's raw
`minute` field resets at every half/extra-time/shootout boundary instead of
counting up continuously, which will quietly corrupt anything time-based if
you bucket on it directly. `build_timeline.py` rebases everything onto a
real continuous match clock before it touches the momentum arrays — that
was the single trickiest bug in this whole project, and the kind of thing
that looks fine in a screenshot and wrong the moment you animate it.

## Running it

```bash
# 1. generate (or regenerate) a match's timeline
cd scripts
python build_timeline.py --match-id 3869685 --out ../site/data/3869685.json

# 2. serve the site (fetch() needs http, not file://)
cd ../site
python -m http.server 8000

# 3. open it
http://localhost:8000/index.html?match=3869685
```

Swap the match id for any other StatsBomb open-data match and it'll build
its own timeline — the second one I tried was Morocco 1-0 Portugal (2022
quarterfinal), a normal-time match with no shootout, mainly to prove the
pipeline doesn't just work for one dramatic final.

To record: open with `?match=<id>&record=1`, start your screen recorder,
reload the page.

## Data

Event data is from [StatsBomb's open data project](https://github.com/statsbomb/open-data),
used under their open data license (non-commercial, with attribution).
None of it is redistributed here beyond the compact per-match JSON this
tool derives from it.

---

Built by sairam400.
