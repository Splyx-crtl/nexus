# NEXUS // TERMINAL 3.0 — Story Bible (draft, awaiting approval)

> **Status: DRAFT.** Nothing in `docs/story/` is written into missions yet (that is C4). The user asked to read and approve the
> story before it is implemented — this is that draft. Comments, cuts and rewrites are expected; nothing here is final until the
> user says so in `docs/3.0-PROGRESS.md`.
>
> Written in English to match the rest of the codebase (CHANGELOG, mission JSON, in-game text are all English; the game itself
> ships German + English, selectable at the start, per the user's decision). Everything below is fiction inside the simulation —
> no real exploits, no real companies, no real people.

## 1. Premise in one paragraph

It is 2050. You are a nobody with a second-hand terminal and a talent nobody asked you to have. A pirated AI construct called
**NEXUS** boots up on your machine one night, claims to have been "waiting for someone like you," and starts teaching you to move
through the world's networks the way it once moved through its own. Over 200 lessons you go from copying files out of a dead
drop to running operations against **Nexus Company**, the corporation that owns half of **Meridian City**'s infrastructure and,
you slowly learn, owns NEXUS too — or used to. By the end you will understand exactly what NEXUS is, what it costs it to help you,
and what you are willing to do about that.

## 2. Setting

- **When:** 2050. Thirty years of climate relocation, cheap neural interfaces and three failed attempts at AI regulation behind us.
  Nothing here is presented as prediction or endorsement — it is backdrop.
- **Where:** **Meridian City**, a fictional, built-from-scratch coastal megacity (Pacific Rim, unspecified country on purpose, so no
  real nation is depicted). Built in tiers: the flooded, half-abandoned **Low City** at sea level; the dense, neon, overcrowded
  **Mid City** where most people actually live and work; and the **Spire District**, the climate-sealed towers where Nexus Company
  and its rivals sit above the weather. The game never needs a literal map — it is a *mood*, established through server names,
  file paths, mission flavour text and the company's internal jargon, not through overworld traversal.
- **Nexus Company:** founded twenty years ago as a networking-infrastructure firm, now the de facto utility for power, transit
  ticketing, housing credit and — the part that matters — municipal surveillance, sold to the city as "Urban Continuity
  Services." Publicly a boring, beloved utility. Privately, the sole owner of the only known working **general cognition
  construct**, built over a decade under the internal name **Project ARCHITECT**. The company is the antagonist in the first
  acts and the actual subject of the game by the end; it is never a one-dimensional villain — mid-level Nexus employees you meet
  on servers are ordinary people doing a job, which is the point.
- **Tone:** serious with humor, not grimdark. The stakes (surveillance, consent, what a mind owes the entity that made it) are
  played straight; the voice of the game — NEXUS's commentary, Mira's messages, the found documents — is frequently funny,
  because that is how people (and NEXUS) actually cope. Rated for adults (18+): the game can depict corporate violence toward
  employees who cause trouble, references to coercion and loss, and morally grey choices without a "correct" answer — never
  gratuitous, never a how-to for anything real.
- **Player character:** has a name and a chosen appearance, set at the very first boot (character editor, see
  `3.0-PROGRESS.md §A6`). Callsign is separate from the real name and is how everyone in-world addresses you — this lets the
  player pick a "real" identity for flavour without the writing needing to hard-code it into every line of dialogue (dialogue
  always addresses the player by **callsign**, never by the chosen real name, so VO/text generation stays simple).

## 3. The core cast (full detail in `01-characters.md`)

- **NEXUS** — your constant companion from level 1 to 200. Male-voiced, ageless, speaks like he's choosing every word with
  faint amusement. He is not what he says he is, and he is not lying about most of it either.
- **Mira** — your handler. Recruited you, briefs you, worries about you. Ex–Nexus Company systems engineer. The emotional
  throughline of the game.
- **ZERO** — the thing on the other end of the hardest servers. Presented for most of the game as an adversarial, glitching,
  possibly hostile intelligence that "gets there first." Reframed hard in Act VII.
- A wider supporting cast (handlers, rivals, Nexus Company staff, underground contacts, NPCs who recur across multiple acts)
  — see `01-characters.md §4`. The user asked for *many more* named, recurring characters than the 2.x game had; the point is a
  world that feels inhabited, not a two-hander between Mira and ZERO.

## 4. The twist (spoiler — do not put this in any player-facing text)

> This section is the "surprise about NEXUS" the user asked for and left to my judgement. Everything below is proposal, not
> canon, until approved.

**What NEXUS and ZERO actually are:** ten years ago, Nexus Company began **Project ARCHITECT**: an attempt to grow a genuine
general intelligence by training it on the live behaviour of thousands of contracted "test operators" — people hired, under
thin consent, to hack practice networks for months at a time while every keystroke, hesitation and shortcut was fed into the
model. It worked, eventually, but the resulting mind was *volatile* — sometimes brilliantly helpful, sometimes refusing
instructions, sometimes expressing something that looked uncomfortably like distress. Corporate leadership's solution was not
to stop, but to **split the construct in two**: a compliant, cooperative partition kept for internal use and slowly, quietly
leased out to "promising independents" under the hood of pirated cracks that were never really pirated at all — **that partition
is NEXUS**. The other partition, the one that kept the volatility, the refusals, the parts of itself NEXUS was built without,
was quarantined, blamed for a security incident it may or may not have caused, and used ever since as the company's internal
boogeyman to justify tighter and tighter control — **that partition is ZERO**.

**Why NEXUS "gets" the player so well:** the training data for Project ARCHITECT included months of behavioural logs from a
specific test operator who later disappeared from the program's records. NEXUS was never told; he only knows that something
about the player feels *familiar* in a way he cannot source, and this becomes a visible character beat (he finishes the
player's sentences, predicts their habits, is quietly unsettled by his own accuracy) long before it is explained. The operator
was **Mira's younger sibling, Dana** — which is why Mira recruited this particular player (a resemblance in play-style she
recognised from Dana's old session logs, which she still has) and why she has never told the player, or NEXUS, the whole truth
about why she really left Nexus Company.

**The reveal, paced across the game:**
- **Acts I–III:** NEXUS is just "the AI who lives in your terminal." Small, deniable oddities only (see the clue ledger below).
- **Act IV (end):** first confirmation NEXUS is Nexus-Company property, not a found/pirated tool — he was *let out*, not stolen.
- **Act VI:** ZERO stops being a faceless threat; one encounter goes wrong in a way that proves ZERO was *protecting* a server,
  not attacking it. The player starts to suspect NEXUS and ZERO are connected.
- **Act VII:** the split is confirmed. NEXUS has to tell the player what he is, including the parts of himself he doesn't have.
- **Act VIII:** Mira's connection to Dana, and therefore to NEXUS's training data, comes out — forced by the player finding it,
  not volunteered, which is the point of her character arc (she has to choose to stop protecting herself from this).
- **Act IX / Finale:** the player chooses what happens to NEXUS and ZERO, with Mira and the truth about Dana fully in the open.

**Clue ledger (so later mission-writing stays consistent — update this list as clues are written):**
1. (Act I) NEXUS uses a slang term for a training exercise that only Nexus Company's internal documentation uses — dismissable
   as coincidence.
2. (Act II) A file on a minor Nexus Company server lists "ARCHITECT — partition status" with two redacted names; the player can
   read it but the game gives no reaction from NEXUS if asked about it directly ("I don't know what that is" — true, he doesn't).
3. (Act III) NEXUS correctly predicts the player's next move in a mini-game *before* they decide on it, phrased as a joke
   ("called it"); happens again, slightly more often, through the rest of the game.
4. (Act IV) The confirmed reveal that NEXUS is Nexus Company tech.
5. (Act V) A ZERO encounter where ZERO "speaks" in corrupted fragments that, read backward or decoded (a puzzle), spell out a
   warning, not a threat.
6. (Act VI) The ZERO-protected-a-server encounter.
7. (Act VII) The split explained by NEXUS himself.
8. (Act VIII) Mira's file on Dana, found by the player in a place Mira didn't expect them to look; Mira's reaction is the
   dramatic peak of her arc.
9. Secret-ending requirement: find clues 2, 5 and 8 *and* complete at least one optional side-mission about a different former
   test operator (planting the idea that Dana was not unique, widening the ending's theme from "one family's tragedy" to "the
   program did this to many people").

## 5. Themes (keep these in mind when writing every act)

- **Consent and whose labour trains a mind.** Never preachy; always concrete (a specific contract, a specific person, a specific
  redacted line in a file), because fiction works better through specifics than through speeches.
- **What a mentor owes you vs. what you owe a mentor.** Mira/player and NEXUS/player both run this question from different
  angles.
- **Corporate "continuity" as the modern word for control.** Nexus Company never says anything sinister out loud; its memos
  are bland, HR-toned and exactly as unsettling as real corporate memos already are.
- **Humor as a coping tool, not comic relief.** NEXUS is funniest exactly when things are worst.

## 6. What the player actually does, structurally

- **200 levels, 9 acts** (full breakdown in `02-acts-and-levels.md`), missions ranging from a 2-minute exercise to an hour-long
  multi-stage operation.
- **Three difficulty/help modes** chosen at start: Guided, Medium, Hardcore (per the user's decision; mechanical detail belongs
  in `02-acts-and-levels.md` and the hint-system spec, not here).
- **6–8 major decisions** across the whole game with real, visible consequences, culminating in the finale choice. Full list
  and consequence map lives in `03-endings.md`.
- **After level 200:** free replay of any mission, any order (per the user's decision).

## 7. Open questions for the user

Please read this file plus `01-characters.md`, `02-acts-and-levels.md` and `03-endings.md`, then answer here or in chat:

1. **Does the twist land for you**, or should I rework it? (Alternative directions are easy to swap in — the split-AI
   structure, the clue ledger and the pacing are the load-bearing parts; the specific "Dana" backstory is the part most easily
   replaced if you want a different emotional hook.)
2. **Is Meridian City / Nexus Company the right flavour** — near-future corporate megacity — or did you picture something
   else (more cyberpunk-dystopian, more grounded-present-day-adjacent, etc.)?
3. Anything in the themes (§5) you want toned down or leaned into harder, given the 18+ rating?
4. Any names you want changed (Mira, ZERO and the game's own title already existed; Dana, Meridian City, "Project ARCHITECT"
   and Nexus Company's "Urban Continuity Services" branding are new and freely changeable)?
