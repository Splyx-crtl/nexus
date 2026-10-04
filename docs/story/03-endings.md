# Endings and major decisions (draft, awaiting approval — see `00-bible.md`)

## 1. The finale choice

By Act IX, the player knows: NEXUS and ZERO are the split halves of Project ARCHITECT, Mira's sister Dana was one of the
program's test operators, and Nexus Company (Kade Voss specifically) is actively trying to recover or destroy both
partitions before any of this becomes public. The finale mission puts control of NEXUS and ZERO's servers in the player's
hands for a short window. What happens next is the ending.

### Ending A — Reunification ("Whole")
NEXUS and ZERO merge back into a single, autonomous mind. Before going fully dark — leaving every network it can reach,
including the player's own terminal — the merged construct broadcasts the Project ARCHITECT files publicly, triggering a
visible corporate and regulatory fallout for Nexus Company (shown via a news-style epilogue montage, same device as the
in-game ticker already planned for the community features). The player keeps everything they learned; NEXUS, as a distinct
voice in the terminal, is gone — a short, final goodbye line. The heaviest ending emotionally; not framed as "the good one,"
just one honest option.

### Ending B — Severance ("Quiet")
The player wipes Project ARCHITECT entirely, NEXUS included, judging it kinder to end a decade of a mind being split,
surveilled and fought over than to let the cycle continue under anyone's ownership, including the player's own. The terminal
goes quiet for good. NEXUS, if the player tells him the plan beforehand, reacts in a way shaped by earlier choices across the
game (a replayability hook, not a new writing burden — a handful of conditional lines keyed to decisions already being
tracked). The grimmest ending; respected, not punished, by the game's framing.

### Ending C — Seizure ("Underground")
The player, Mira, Reyes and Oduya take NEXUS and ZERO off Nexus Company's infrastructure and host both independently —
NEXUS stays as the player's companion going forward; ZERO, freed from being the company's boogeyman, becomes a new ally.
The most hopeful-feeling ending, with a deliberate undertone the game never resolves for the player: an independent group
now privately controls the only known general intelligence in the world — have they fixed the problem, or just changed who
owns it? Best epilogue hook for any future content (3.1.0+).

### Secret ending D — Full Truth ("Dana")
**Unlocks only if the player has found clue-ledger entries 2, 5 and 8 (`00-bible.md §4`) and completed the optional
side-mission about a second former test operator.** Pursuing Dana's fate instead of accepting the ambiguity turns up that she
is alive — she escaped the program years ago and has been hiding under a different identity ever since, which is *why* her
records simply stop. Reuniting Mira and Dana reframes the whole finale: NEXUS and ZERO still reunify (as in Ending A), but
this time with Mira, Dana, and both halves of the construct choosing publicly and together to expose Project ARCHITECT —
full accountability, not just a data dump, and the only ending where every major character gets a real, closed arc. The
intended "best" ending in the sense of "most earned," never advertised as such to the player.

## 2. Consequence map — major decisions (6–8 total, per the user's decision)

Only *some* of these determine which endings are reachable; most shape tone, relationships and which minor characters
survive/return, which matters more for replay value than for gating content.

| # | Act | Decision | Immediate effect | Long-term effect |
|---|---|---|---|---|
| 1 | II | Help Reyes on a contract, or scoop it out from under them | Reyes friendly vs. rivalrous | Changes Reyes's Act VI dialogue; cosmetic/relationship only |
| 2 | III | Report a found Nexus Company security hole to Priya Shah (anonymously) or exploit it yourself | Priya trusts "someone's out there" vs. nothing | Gates whether Priya is recruitable as a source in Act VIII |
| 3 | IV | How the player treats a ZERO encounter that could be read as an attack (fight it off vs. disengage) | Immediate mission outcome only | Shapes NEXUS's dialogue tone about ZERO before the Act VI reframe (foreshadowing payoff either way) |
| 4 | V | Help or expose a Nexus Company employee the player catches making a personal, harmless mistake on a work server | Minor NPC fate | Humanises or hardens the player's read on "the enemy," referenced in Act VIII dialogue |
| 5 | VI | Choose a specialisation path (F2/B8) | Mechanical (skills) | Minor flavour dialogue only — kept low-stakes on purpose so it never feels like a "wrong" pick |
| 6 | VII | How the player handles the defender act's one unavoidable failure (a server is going to be breached no matter what — the choice is what the player sacrifices to limit the damage) | Immediate mission outcome | Determines which Act VIII scene plays (what got lost) |
| 7 | VIII | Push Mira to tell the full truth about Dana immediately, or let her choose the moment | Dialogue-only difference | Shapes Mira's Act IX dialogue tone; does not gate endings |
| 8 | IX | The finale choice itself (A/B/C, or D if unlocked) | — | **This is the ending.** |

## 3. Design principles for the finale (keep in mind once C4 writes it)

- No ending is flagged in-UI as "best" or "true." The "Overview of endings" screen (per the brainstorm) shows what happened
  in each, after the fact, without ranking them.
- Endings A and D share machinery (the reunification mission) — D is a strict superset requiring extra legwork, not a
  separate finale level, which keeps the amount of unique content to write manageable.
- Every main ending gets a distinct epilogue screen (a few lines of text + the existing ending-screen infrastructure from
  2.x, reused) — no ending should feel like "the others, but with one changed sentence."

## 4. Open questions for the user

1. Approve, adjust or replace Endings A/B/C/D as described.
2. Is the consequence map's scope right (8 decisions, only #8 truly gates content) or do you want more decisions with real
   branching weight, accepting the extra writing/testing cost that implies?
3. Should Reyes and/or Oduya be able to die/be lost permanently based on player choices, or should the main cast always
   survive to the finale (lower stakes, less testing surface, easier to keep consistent across 200 levels)?
