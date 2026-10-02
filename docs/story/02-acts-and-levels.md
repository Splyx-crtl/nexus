# The 200-level curriculum (draft, awaiting approval — see `00-bible.md`)

## 1. How "something new every level" actually works

Levels 1–~20 are where most *new commands* unlock (the engine already supports this: every `@command(...)` in
`nexus/shell/commands/*.py` carries a `level=` and a `lesson=` shown once on unlock — see `3.0-PROGRESS.md §B`). Beyond that,
200 straight levels of brand-new commands would be neither realistic (real shells have a few hundred commands total, most
people use thirty of them daily) nor fun. From Act III onward, "new every level" means one of:

- a **new technique** with tools you already have (a pipe chain, a flag you haven't needed yet, a scripting idiom),
- a **new tool window** unlocking (B10: brute-force module, hash lab, packet analyser, decryption workbench, network map),
- a **new mechanic** (a specialisation path, the base, living-economy pricing — B8/F2 of the progress file),
- or a **story beat** that recontextualises something already learned.

**Open question for the user:** please confirm this reading of "learn something new every level" before C4 starts, since it
changes what "new" means for roughly 180 of the 200 levels.

## 2. Difficulty / help modes (chosen at first boot, per the user's decision)

| Mode | Hints | Explanations |
|---|---|---|
| **Guided** | Every new command explained in full before first use; tiered hints always on | Lexicon entries auto-opened on unlock |
| **Medium** | Short unlock notice; tiered hints available on request (`hint`) | Lexicon available, not pushed |
| **Hardcore** | No unlock notices, no hints, no lexicon | None — real tool behaviour only |

Mode only changes *help*, never mission content, difficulty of puzzles, or available commands — so missions do not need to be
written three times. (Ties to `3.0-PROGRESS.md §C6`, not yet built.)

## 3. The nine acts

Total: 200 levels, sized to the amount of real material each act teaches (not an even split).

| Act | Levels | Rank earned | Working title | What's taught | Engine status |
|---|---|---|---|---|---|
| I | 1–20 | SCRIPT KIDDIE → **TRACER** | **Awakening** | bash fundamentals: `ls cd pwd cat find grep` etc., reading a filesystem, first NEXUS contact | ✅ built (B3) |
| II | 21–45 | **TRACER** → **NETRUNNER** | **Traces** | search/filter mastery, permissions, pipes/redirection, first choices, Reyes introduced | ✅ built (B3) |
| III | 46–70 | **NETRUNNER** → **CRYPTOSMITH** | **The Network** | `ping dig whois curl nmap-equivalent reconnaissance`, first real Nexus Company server, Oduya introduced | ✅ built (B4) |
| IV | 71–95 | **CRYPTOSMITH** → **GHOST** | **The Keys** | hashes/encoding, the Brute-Force module and Hash Lab (B10, not yet built), Priya Shah introduced, Act finale: **NEXUS confirmed as Nexus Company tech** | ⚠️ needs B5 + B10 |
| V | 96–120 | **GHOST** → **ENGINEER** | **Windows** | PowerShell/cmd, Windows privilege model, office/admin targets, Kade Voss introduced as active hunter | ✅ built (B6) |
| VI | 121–145 | **ENGINEER** → **SENTINEL** | **Rights & Automation** | scripting (bash functions/loops already work; `.ps1`/batch scripting is B8, not yet built), specialisation choice (B8/F2) | ⚠️ needs B8 |
| VII | 146–165 | **SENTINEL** (role reversal act) | **Defense** | *playing defense* — reading logs, writing firewall-style rules, catching an intrusion; the ZERO-reframe and the full split reveal | ⚠️ needs new "defender" mission shape (design only, no new engine work expected) |
| VIII | 166–185 | **SENTINEL** → **ARCHITECT** | **Automation** | chained scripts, endless-ops-style procedural missions (F2), Mira's reveal about Dana | ⚠️ needs F2 (endless ops) |
| IX | 186–200 | **ARCHITECT** → **NEXUS** | **The Architect** | everything combined, 6–8th major decision, finale, multiple endings | no new engine work expected — content only |

The rank **ARCHITECT** (Act VIII) deliberately echoes "Project ARCHITECT" (the twist, revealed in Act VII) — the player is
*becoming* what the company tried to build, on their own terms. The final rank, **NEXUS**, is the same word as the
companion's name on purpose: the capstone payoff of the whole game.

## 4. Mission-size rhythm (per the user's decision: small to large, mixed)

Within each act, roughly every 10 levels:

- **5× Mini** (1–3 min): a single technique, often procedurally varied so it can be replayed without feeling stale.
- **3× Standard** (5–10 min): combine 2–3 techniques, usually where a side character or found document advances.
- **1× Story** (15–30 min): a scene with dialogue, a choice, or a clue-ledger beat.
- **1× Milestone** (30–60 min): act-ending or mid-act set-piece; where command unlocks, tool windows and rank-ups land.

Each act therefore ends on a Milestone mission. Act endings (IV, VII, IX) also carry a named story beat from the clue ledger
in `00-bible.md §4`.

## 5. XP curve and level pacing (engineering default, not a creative decision — tune later via playtesting, G1)

Proposed formula (v3 schema, replaces the 2.x `xp_for_level` in `nexus/config.py`, which stays untouched for the shipped
2.x game): `xp_for_level(level) = 80 + 15 * level`. Early levels come in a few missions each; by Act VI–IX a level represents
several real missions, matching "Mini/Standard missions get you through early acts fast, Milestones carry the late game."
Exact numbers are easy to retune once real missions exist and the solver-bot (C2) can simulate full playthroughs.

## 6. Open questions for the user

1. Confirm or correct the act titles, rank names and the Act VII "role reversal" idea (player briefly defends instead of
   attacks — a structural idea, not yet written as missions).
2. Confirm the reading of "something new every level" in §1.
3. Is it acceptable that Acts IV, VI and VIII need engine work (B5, B8, B10, F2) finished before their *content* can be
   written, or should mission-writing (C4) start with Acts I–III and V (already fully supported) while that other work
   happens in parallel?
