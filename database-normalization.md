# DB Normalization & Multi-Source Ingest — Plan v1

Status: **AGREED — reviewed, decisions resolved. No code written yet; Phase 0 ready to start.**
Date: 2026-08-06
Scope: `backend/app/models`, `repositories`, `services`, `utils/statsbomb.py`, Alembic; API response shapes held stable.

All evidence in §1 is measured against the live dev database, not inferred. §5 records the resolved decisions; §6 records an independent architect review whose every factual claim was re-verified before being accepted.

**Read first if you are picking this up:** §6 blockers (B0–B3) — one of them is a corrected error in an earlier revision of this document, and two of them will break a migration if missed.

---

## 1. Evidence: what's actually wrong

Measured against the live dev DB (80 competitions / 3,961 matches / 376,362 events / 3,745 lineups / 1,583 players).

### 1.1 `competition` violates 2NF (the one you named)

The table's real key is the composite `(statsbomb_id, season_id)` — i.e. tournament × season, where `statsbomb_id` holds StatsBomb's `competition_id`. But these columns depend on `statsbomb_id` **alone**, i.e. on part of the key:

`country_name`, `competition_name`, `competition_gender`, `competition_youth`, `competition_international`

That is the textbook partial-dependency / 2NF violation. And `season_name` depends only on `season_id`.

```
distinct competition ids : 24
competition rows         : 80   →  La Liga stored 18×, Champions League 18×, World Cup 8×
```

Update anomaly today: renaming a competition or fixing its country means touching up to 18 rows, and nothing in the schema stops them from disagreeing.

### 1.2 Team is not an entity — and it has already drifted

"Team" exists only as free text, in five places with no constraint tying them together:

| Column | Type |
|---|---|
| `soccer_match.home_team` / `away_team` | `varchar(255)` |
| `lineup.team_name` | `varchar(255)` |
| `event.team` | `varchar(255)` |
| `event.possession_team_name` | `varchar(255)` |

353 distinct team strings across 7,922 occurrences in `soccer_match` alone.

**This has already produced a real bug.** StatsBomb's *match* feed and its *event/lineup* feeds disagree on one name:

```
raw_event->>'team_id' = 147   →   event.team    = "Marseille"
                                  match teams   = "Olympique de Marseille"
```

**1,920 events cannot be joined to their own match's team.** Every string-keyed team query is silently wrong for those rows. This is not hypothetical and it is not fixable by cleaning data once — the two feeds will keep disagreeing.

Team-level attributes are also repeated per match rather than stored once: `home_team_gender`, `away_team_gender`, `home_team_country_name`, `away_team_country_name`.

### 1.3 Player identity is split three ways with no FK

| Location | Form | FK? |
|---|---|---|
| `player.statsbomb_id` | `int` | — |
| `lineup.statsbomb_player_id` | `int` | **no FK** to `player` |
| `event.player` | `varchar(255)` name | **no FK** |
| `event.pass_recipient` | `varchar(255)` name | **no FK** |

Your stated goal — *season stats for one player* — currently requires:

```
event.player  ={string}=  lineup.player_name
lineup.statsbomb_player_id  =  player.statsbomb_id
lineup.match_id  →  soccer_match  →  competition.season_id
```

A 4-hop, string-mediated join across 376k unindexed rows. It happens to return correct results on today's sample (0 ambiguous names, 0 unmatched `event.player`) — but that is a property of this dataset, not a guarantee the schema provides. The Marseille case shows exactly how that luck runs out.

### 1.4 No source provenance — multi-source is structurally excluded

Every external key is literally named `statsbomb_id`, and `player.statsbomb_id` / `soccer_match.statsbomb_id` are `UNIQUE`. There is no way to express "Opta player 99123" or "StatsBomb 5503 and Opta 99123 are the same person". Adding a second source today would require altering unique constraints on every table.

`statsbombpy` is also imported **inside service methods** (`CompetitionService.ingest`, `MatchService.ingest`, `EventService.ingest_for_competition`, `LineupService`, `Frame360Service`), so the vendor is welded into the service layer with no seam to swap.

### 1.5 We are discarding the keys we need — at the parser

`sb.matches()` returns all of these and `StatsBombMatchRow` declares none of them:

```
home_team_id, away_team_id, home_team_country_id, away_team_country_id,
competition_stage_id, stadium_id, referee_id, home_manager_id, away_manager_id
```

Likewise `StatsBombEventRow.extract_name` collapses `{"id":…, "name":…}` → `name`, dropping the id.

**Mitigating find:** because `Event.raw_event` stores `model_dump()` of an `extra="allow"` model, statsbombpy's flattened `*_id` columns survived anyway:

```
raw_event->>'team_id'            : 376,362 / 376,362                    (100%)
raw_event->>'possession_team_id' : 376,362 / 376,362                    (100%)
raw_event->>'player_id'          : 374,954  = every non-null player     (100%)
raw_event->>'pass_recipient_id'  : 104,090  = every non-null recipient  (100%)
```

**Consequence: the entire event backfill is a pure in-database operation. No re-fetch, no re-ingest of 376k rows.**

##### ⚠️ BLOCKER — the ids are float strings; a naive `::int` cast throws

`raw_event` is Postgres `json` (not `jsonb`), and pandas coerced every *nullable* id column to `float64` before `model_dump()`:

```sql
raw_event->>'player_id'  →  "7626.0"     -- ::int  ERRORS
                            ::numeric::bigint  →  7626   -- correct
```

Affected: `player_id`, `pass_recipient_id`, `substitution_replacement_id` (all nullable → floats).
Clean: `team_id`, `possession_team_id` (never null → stayed int).

**Required cast: `(raw_event->>'player_id')::numeric::bigint`.** Assert post-backfill `count(player_id) = 374,954`.

Fold `ALTER TABLE event ALTER COLUMN raw_event TYPE jsonb` into the same migration — all 376k rows are being rewritten anyway, and [#31](https://github.com/KunalSinha7/backpost-analytics/issues/31) will need `jsonb_array_elements_text` on `related_events`.

##### Root cause is one line, and it is not Lineup-specific

`Event` and `Frame360` survived only because `StatsBombEventRow`/`StatsBombFrameRow` set `model_config = ConfigDict(extra="allow")`. `StatsBombMatchRow`, `StatsBombCompetitionRow` and `StatsBombLineupPlayerRow` do **not** — which is exactly why `sb.matches()`'s nine `*_id` columns are gone.

**Fix in Phase 0: move `extra="allow"` onto the `_StatsBombRow` base class, and add `raw` columns to `soccer_match` and `competition` as well as `lineup`.** Patching only `Lineup` leaves `soccer_match` in the state that caused this section.

### 1.6 Other fields discarded at the parser

Beyond the entity ids in §1.5, a full enumeration of `raw_event` keys and the `sb.lineups()` payload found substantial data dropped at parse time. **In scope for this plan** (decided 2026-08-06, §6/S1):

| Field | Coverage | Why it's in scope |
|---|---|---|
| `position` (24 distinct) | **374,954 events** — every player event | Entity reference, stored nowhere. Blocks "player X's numbers by position". |
| `lineup.positions[]` | every lineup row | Carries `position_id`, `from`/`to`, `from_period`/`to_period`, `start_reason`, `end_reason` per stint. **This is minutes played.** Current parser reads only `positions[0].start_reason` for `started` and discards the rest. |
| `lineup.cards[]` | every lineup row | Yellows/reds per player per match. Discarded entirely. |
| `substitution_replacement_id` | 770 events | An unplanned **player FK**. With `positions[].from/to`, completes minutes-played. |

Split into their own issues, out of scope here (see §6/S1 for the rule that decided this):

| Issue | Scope |
|---|---|
| [#31](https://github.com/KunalSinha7/backpost-analytics/issues/31) | Event graph: `related_events` (546,468 edges), `shot_key_pass_id`, `pass_assisted_shot_id` |
| [#32](https://github.com/KunalSinha7/backpost-analytics/issues/32) | Tactics/formations (485 events), shot freeze frames (~2,500 shots) |
| [#33](https://github.com/KunalSinha7/backpost-analytics/issues/33) | Metric columns: `shot_statsbomb_xg` (2,536 shots), `pass_length`/`pass_angle`, cards, low-cardinality qualifiers |

The dividing line: **`position` and `substitution_replacement_id` stay because they are entity FKs resolved by the same `EntityResolver` Phase 1 is already building.** Everything in #33 is a plain scalar with no entity to resolve and lives in `raw_event` indefinitely.

#### The recoverability asymmetry — and a trap to close

- **`Event` has `raw_event`**, so every event-side field above is backfillable with **zero re-fetch**.
- **`Lineup` has no raw column.** Its dropped `positions[]` and `cards[]` are **unrecoverable from the DB** and require re-running `sb.lineups()`.

That asymmetry is the whole reason the event backfill is cheap and the lineup one is not. **Phase 0 adds a `raw` JSON column to `Lineup`** so this trap cannot recur.

#### Confirmed: `sb.lineups()` exposes no team id

Flagged as a risk in v1, now verified. The feed returns columns `[player_id, player_name, player_nickname, jersey_number, country, cards, positions]` and the **teams are the returned dict's keys — names only**.

##### ⚠️ CORRECTED 2026-08-06 — the first proposed rule was wrong

An earlier revision of this section said `lineup.team_id` should "resolve against the parent match's two teams". **That is wrong and it fails on precisely the rows this plan exists to fix.** Scoping a name match to two candidates instead of 353 does not make it an id match — it just makes the failure quieter:

```
lineup.team_name matching NEITHER of its match's two teams:
  Marseille | Paris Saint-Germain | Olympique de Marseille | 20 rows
```

**Correct rule — resolve through the *event* feed, which shares the lineups feed's vocabulary, scoped to the same match:**

```
lineup.team_name --(same match_id)--> event.team --> (raw_event->>'team_id')::bigint
```

Verified against the live DB:

```
lineup rows                            : 3,745
resolved by the event-feed rule        : 3,745   (100%)
unresolved                             : 0
ambiguous (team_name → >1 team_id)     : 0
```

This works because the **lineups and events feeds agree with each other**; it is the *match* feed that carries the alias. So: never join lineup→match on name; join lineup→event on name (same vocabulary, safe) and take the id.

Do **not** use the player-mediated path (`(match_id, statsbomb_player_id)` → event `player_id` → `team_id`) as primary — 912 of 3,745 lineup rows are unused subs with no events. It is a valid cross-check only.

**Required in Phase 1:**
- Hard migration assertion: `lineup rows with NULL team_id after backfill = 0`
- The 20 Marseille rows as the named regression fixture
- A **negative** test asserting the two-team name-match rule fails, so it can't be reintroduced

**Standing constraint this creates:** lineups can only be ingested for matches that already have events. That holds today only because `api/routes/event.py` runs events → lineups → frames in that order. Phase 0 must make that ordering explicit rather than incidental.

### 1.7 Considered and rejected

- **Lookup tables for `event.type_name` / `play_pattern_name` / `competition_stage_name`.** ~40 distinct values × 376k rows. Storage saving is ~6 MB; cost is a join on every event query and churn across the whole read path. This is the over-normalization trap. **Not doing it.** Recorded here so it doesn't get re-litigated.
- **`referee` / `stadium` / manager as entities.** IDs are available, but there is no analytics use case today. Deferred; the `external_id` convention below means they can be added later without reworking anything.

---

## 2. Target model

Three ideas, in dependency order.

### 2.1 Split `competition` into `competition` × `season` → edition

**DECIDED 2026-08-06.** Naming follows StatsBomb's vocabulary, which is also the correct domain vocabulary.

```
competition               -- TIMELESS: La Liga, Champions League, FIFA World Cup
  id            UUID pk
  name
  country_name
  gender
  is_youth
  is_international

season
  id            UUID pk
  name          "2018/2019"
  start_year    int
  end_year      int

competition_season        -- the EDITION
  id                UUID pk
  competition_id    FK → competition
  season_id         FK → season
  UNIQUE(competition_id, season_id)
```

Rationale — an earlier draft proposed `league` + `season` + `competition`(=edition) to avoid rename churn. **Overruled**, for two reasons:

1. **`league` is factually wrong.** The data contains FIFA World Cup, Copa del Rey, and Champions League — a tournament, a domestic cup, and a continental cup. None are leagues. "Competition" is the correct generic term.
2. **StatsBomb-consistent and source-neutral coincide here.** `competition_id=11` is La Liga across all 18 seasons — StatsBomb's "competition" is the timeless entity, exactly inverted from how our current table uses the name. Opta and Wyscout use "competition" the same way, so this is domain vocabulary, not vendor jargon. The ingest adapter reads 1:1 against StatsBomb docs.

StatsBomb has no name for the edition; `competition_season` is the common convention.

**Rename churn (measured):** `soccer_match.competition_id` → `competition_season_id`; frontend search param `competitionId` → `competitionSeasonId`. 44 backend refs, 29 hand-written frontend refs, 12 generated-client refs. Mechanical and compiler-caught, but it is real and lands in Phase 2.

Feed-availability columns (`match_updated`, `match_available`, `match_updated_360`, `match_available_360`) are *StatsBomb feed metadata*, not domain facts. They move onto the source-link row (§2.3), not onto `competition_season`.

### 2.2 Team, Player and Position as real entities

```
team                                     player   (already exists — gains source cols)
  id             UUID pk                   id, name, nickname, nationality
  name           canonical
  gender
  country_name
  is_national_team
```

Plus a third entity, from §1.6:

```
position                  -- 24 values: Goalkeeper, Right Back, Right Center Forward, ...
  id             UUID pk
  external_id    "1", "22", ...     (StatsBomb position_id)
  name
```

FKs added (all nullable during expand, `NOT NULL` after contract where applicable):

| Table | New column |
|---|---|
| `soccer_match` | `home_team_id`, `away_team_id` → `team` |
| `lineup` | `team_id` → `team`, `player_id` → `player` |
| `event` | `team_id`, `possession_team_id` → `team` |
| `event` | `player_id`, `pass_recipient_id` → `player` |
| `event` | `position_id` → `position` |
| `event` | `substitution_replacement_id` → `player` |
| `frame360` | `event_id` → `event` (replaces soft `event_statsbomb_id`) |

**`lineup_position` — the minutes-played table (§1.6).** `lineup.positions[]` is a repeating group inside a column, which is a 1NF violation and the reason per-90 stats are impossible today. It becomes its own table:

```
lineup_position
  id            UUID pk
  lineup_id     FK → lineup
  position_id   FK → position
  from_period   int      to_period   int | null
  from_time     varchar  to_time     varchar | null
  start_reason  varchar  end_reason  varchar | null
```

`lineup.started` stays as a derived convenience column (it is read by `LineupTable`), now computed from the first stint's `start_reason` rather than parsed ad hoc.

**Scalar metric columns** (`shot_statsbomb_xg`, `pass_length`/`pass_angle`, cards, qualifiers) are **not** in this plan — split to [#33](https://github.com/KunalSinha7/backpost-analytics/issues/33) per §6/S1. `lineup.cards[]` stays in scope (it is not in `raw_event`) as either a `lineup_card` table or a JSON column — **decide during Phase 3**, low stakes either way.

Indexes required for the season-stats goal:
```sql
CREATE INDEX ix_event_player_match   ON event (player_id, match_id);
CREATE INDEX ix_event_team_match     ON event (team_id, match_id);
CREATE INDEX ix_match_comp_season    ON soccer_match (competition_season_id);
```

Which makes the target query a plain 3-join:

```sql
SELECT e.type_name, count(*)
FROM event e
JOIN soccer_match      m  ON m.id  = e.match_id
JOIN competition_season cs ON cs.id = m.competition_season_id
WHERE e.player_id = :player_id AND cs.season_id = :season_id
GROUP BY 1;
```

> **Not** creating `player_season_team` / squad-membership. StatsBomb open data has no transfer windows; that table would be derived from lineups and is speculative until something needs it.

### 2.3 Source provenance — minimum viable, non-speculative

```
data_source
  id     UUID pk
  key    'statsbomb'  UNIQUE
  name
```

On every ingested entity, replace `statsbomb_id` with:

```
  source_id    FK → data_source
  external_id  varchar(64)          -- varchar: sources use ints, uuids, and strings
  UNIQUE(source_id, external_id)
```

That is the whole change. **Deliberately NOT building a cross-source crosswalk table now** — with exactly one source it is unused abstraction. When a second source lands, adding a nullable `canonical_team_id` self-FK (or a merge table) is an additive migration that does not disturb this shape.

### 2.4 Ingest: provider port

```
app/ingest/
  base.py        Protocol SourceProvider:
                   fetch_competitions() -> Iterable[SourceCompetition]
                   fetch_matches(edition) -> Iterable[SourceMatch]
                   fetch_events(match) -> Iterable[SourceEvent]
                   fetch_lineups(match) -> Iterable[SourceLineupEntry]
  dto.py         source-neutral DTOs (external_id + name for every entity ref)
  statsbomb.py   StatsBombProvider — existing utils/statsbomb.py logic moves here,
                 extended to keep the *_id columns it currently discards
  resolver.py    EntityResolver.resolve_team(source, external_id, name) -> Team
                                .resolve_player(...) etc.  Get-or-create, keyed on
                                (source_id, external_id) — NEVER on name.
```

Services depend on the `SourceProvider` Protocol; `statsbombpy` is imported only in `statsbomb.py`. The resolver keying on ID rather than name is precisely what makes the Marseille case impossible to reintroduce.

Add an architecture rule to `tests/test_architecture.py`:
```python
def test_only_ingest_adapter_imports_statsbombpy(...)  # app.services must not import statsbombpy
```

---

## 3. Migration strategy — expand / backfill / contract

Non-negotiable constraint: **no functionality breaks at any commit.** Every phase is independently shippable and independently revertible.

Per phase:
1. **Expand** — Alembic adds new tables + **nullable** FK columns beside the existing string columns. Nothing reads them. Zero behavior change.
2. **Backfill** — data migration populates entities and FKs. Old and new columns coexist and are cross-checkable.
3. **Cut over** — repositories/services switch to FKs. `*Public` schemas keep emitting the same string fields (now resolved via relationship), so **the OpenAPI contract and the frontend do not change.**
4. **Contract** — a later migration sets `NOT NULL` and drops the string columns.

### Key decision: the strings leave the *tables*, not the *API*

**DECIDED 2026-08-06: fully normalize — the denormalized name columns are dropped, not kept as a read cache.**

`SoccerMatchPublic` keeps emitting `home_team: str` / `away_team: str`; the new `home_team_id` is **added** alongside. Result: existing frontend code (`MatchTable`, `MatchHierarchyFilter`, `MatchSelector`, `EventFilterPanel`, `PitchEventLayer`, `LineupTable` — 6 hand-written files) compiles and behaves identically; new ID-based features opt in.

This is safe here because of a property of this codebase specifically: **no `*Public` schema traverses a SQLModel `Relationship`.** The only two relationships that exist (`Competition.matches`, `SoccerMatch.competition`) are never serialized — every repository builds an explicit `select()`. So the N+1 hazard that normally pressures teams into keeping denormalized copies does not apply.

The pattern is what `CompetitionRepository.list_all` already uses for `match_count` — join and select a labeled column:

```python
home = aliased(Team); away = aliased(Team)
select(SoccerMatch, home.name.label("home_team"), away.name.label("away_team"))
    .join(home, col(SoccerMatch.home_team_id) == home.id)
    .join(away, col(SoccerMatch.away_team_id) == away.id)
```

One query, no lazy loads. Keeping denormalized copies would re-open exactly the drift that produced the Marseille bug (§1.2), so they go.

### Backfill sources per entity

| Entity | Source of truth for backfill | Re-fetch needed? |
|---|---|---|
| `event.team_id`, `possession_team_id`, `player_id`, `pass_recipient_id` | `raw_event` JSON — **100% coverage, verified** | **No** — pure SQL/Python over the existing table |
| `soccer_match.home/away_team_id` | 94 of 3,961 matches derivable from their events; the rest need `sb.matches()` | Yes, but cheap: 80 cached calls, idempotent |
| `lineup.player_id` | `lineup.statsbomb_player_id` → `player.statsbomb_id` | No |
| `event.position_id`, `substitution_replacement_id` | `raw_event` JSON — 100% of player events | No |
| `lineup.team_id` | **`sb.lineups()` has no team id (§1.6).** `lineup.team_name` →(same match)→ `event.team` → `raw_event->>'team_id'`. Verified 3,745/3,745, 0 ambiguous. **Never against the match's teams** — that fails on the 20 Marseille rows | No |
| `lineup_position`, `lineup.cards` | **Not in the DB at all** — `Lineup` has no raw column | **Yes** — re-run `sb.lineups()` for all 3,745 lineup rows |
| `competition` / `season` / `competition_season` | derived from existing `competition` rows | No |

The Marseille pair is the acceptance test for the backfill: after it runs, `Olympique de Marseille` and `Marseille` must resolve to **one** `team` row, and all 1,920 orphaned events must join.

---

## 4. Phasing

Ordered so the capability you actually asked for (§1.3, season stats) lands early, and each phase is one PR.

**DECIDED 2026-08-06.** Two changes from the first draft, both explained below the table.

| Phase | Delivers | Risk | Key gate |
|---|---|---|---|
| **0. Foundations** | **Golden-response + `openapi.json` snapshot harness** (§7.1 — must land while the baseline is still trivially correct). `data_source` table. **`extra="allow"` on `_StatsBombRow` + `raw` columns on `lineup`/`soccer_match`/`competition`** (§1.5). **Re-fetch `sb.lineups()` for the 94 event-matches** — the only network-bound step in the plan. **`ix_event_match_id_index`** (§6/H2). **Fix `model_validate` relationship loss** (§6/B2). **No entity changes, and no `app/ingest/` package — see the note below.** | Low | Snapshots captured and committed; `openapi.json` unchanged; `model_validate` fix has a **failing test first**; `alembic downgrade` rehearsed; `/competitions` p95 improves |
| **1. Identity** | `team` + `player` + `position` entities; **`team_alias`** (§6/M5); `EntityResolver`; FKs on `soccer_match`/`lineup`/`event`; one backfill pass. Additive `home_team_id`/`away_team_id` on `SoccerMatchPublic` + optional `team_id` filter params (§6/H4). **Fixes the Marseille bug.** | Medium — touches 376k rows | Marseille resolves to 1 team; all 1,920 orphaned events join; **`lineup.team_id` NULL count = 0**; distinct team count = 353; responses identical **except the enumerated drift set = {team 147}** |
| **2. Competition split** | `competition` / `season` / `competition_season`; `competition_id` → `competition_season_id` rename churn. **In-place `ALTER` only — never DELETE/re-INSERT `competition`** (§6/B3) | Medium — 85 refs across stack | `/competitions` response unchanged; pre-flight FD assertions (§6) pass; `soccer_match` row count unchanged |
| **3. Season stats** | `lineup_position` (minutes played); indexes from §2.2; `/players/{id}/stats?season_id=` endpoint | Low | **Per-90 for a known player matches a hand-computed value** — not just raw counts |
| **4. Contract** | Drop the redundant name columns; `NOT NULL` the FKs. **The `statsbomb_id` → `external_id` rename is CUT from this plan** (§6/H1) | Low-medium | Full test suite + `openapi.json` diff + manual UI pass |

**Change 1 — Team and Player merged into one "Identity" phase.** The first draft split them for reviewability. But they share a single backfill pass over the same 376k-row table reading the same JSON blob; splitting means scanning `event` twice and running expand/backfill/cutover twice over the same files. They are structurally symmetric (same resolver, same pattern), so reviewing together is cheaper than reviewing twice.

> #### ⚠️ CORRECTED 2026-08-06 — the provider port does NOT belong in Phase 0
>
> "Change 2" below was the pre-review position and **§6/M1 overrides it**. M1 was marked applied but was only half-applied: the `EntityResolver` moved to Phase 1 as intended, while the Phase 0 row and §7.3 kept the Protocol/DTOs. That contradiction is resolved here in M1's favour.
>
> **Phase 0 does not create `app/ingest/`.** Designing source-neutral DTOs before the `team`/`player`/`position` shapes exist means guessing at their fields and rewriting them in Phase 1. What Phase 0 *does* take from this area is the one-line `extra="allow"` fix on `_StatsBombRow` (§1.5), which needs no package and no Protocol.
>
> The arch rule moves with the port. Writing it at Phase 0 would commit a **permanently red** test — the port that makes it pass is Phase 4 — and per §6/M2 it may not even detect the violations, since all six statsbombpy imports are function-local. Phase 0 answers that question as a written finding instead (see §7.3 Lane C).

**Change 2 (SUPERSEDED — see the correction above) — provider port moved from Phase 4 to Phase 0.** Backfill code is one-shot and disposable, so StatsBomb-specific backfill is fine at any point. But **ingest** code is not: Phases 1–2 must modify `StatsBombMatchRow`/`StatsBombEventRow` to stop discarding the `*_id` columns (§1.5), and a late Phase 4 would then move those same files behind the port — touching ingest twice. Porting first means touching it once, and every later phase adds its parsing inside the adapter where it belongs.

Phase 4 is deliberately last and separable — it is the only phase that is hard to revert, and nothing depends on it.

### Verification per phase

- Row-count parity before/after every backfill
- Golden-response diff: capture `/api/v1/{competitions,matches,events,lineups,players}` JSON before, assert identical after cut-over
- Existing 121 backend tests green; `prek run --all-files` clean
- New repository tests per entity, including the Marseille-style duplicate-name case as a **regression test**

---

## 5. Decisions — resolved 2026-08-06

| # | Question | Resolution |
|---|---|---|
| 1 | Naming | **`competition` (timeless) / `season` / `competition_season` (edition)** — StatsBomb-consistent and domain-correct. Earlier `league` proposal overruled: `league` is wrong for World Cup / Copa del Rey / Champions League. See §2.1. |
| 2 | Phase order | **Provider port first (Phase 0); Team+Player merged into one Identity phase.** See §4. |
| 3 | Referee / stadium / manager / competition_stage entities | **Deferred**, tracked in [#30](https://github.com/KunalSinha7/backpost-analytics/issues/30). Issue also records the *rejected* event-type lookup tables so that call isn't mistaken for an oversight. |
| 4 | Keep denormalized name columns as a read cache? | **No — fully normalize.** Safe here because no `*Public` schema traverses a `Relationship`; all repos build explicit selects, so there is no N+1 to dodge. See §3. |

| 5 | Scope of the fields discarded at the parser (§1.6) | **In scope:** `position`, `substitution_replacement_id` (entity FKs), `lineup.positions[]` → `lineup_position`, `lineup.cards[]`, plus `raw` columns in Phase 0. **Split out:** [#31](https://github.com/KunalSinha7/backpost-analytics/issues/31), [#32](https://github.com/KunalSinha7/backpost-analytics/issues/32), [#33](https://github.com/KunalSinha7/backpost-analytics/issues/33). Rule and rationale in §6/S1. |

### Standing rule

> **Do now what only a re-fetch can recover. Defer what `raw_event` already preserves.**

This is what put `lineup.positions[]`/`cards[]` in scope (nothing preserves them) and moved xG, pass geometry, and qualifiers out (`raw_event` holds them indefinitely). Apply it to any future "should we also extract X?" question.

### Tracking issues

| Issue | Scope |
|---|---|
| [#30](https://github.com/KunalSinha7/backpost-analytics/issues/30) | Deferred entities: referee, stadium, manager, competition_stage. Also records the rejected event-type lookup tables. |
| [#31](https://github.com/KunalSinha7/backpost-analytics/issues/31) | Event graph: `related_events` (546,468 edges), `shot_key_pass_id`, `pass_assisted_shot_id`. |
| [#32](https://github.com/KunalSinha7/backpost-analytics/issues/32) | Tactics/formations (485 events) and shot freeze frames (~2,500 shots). |
| [#33](https://github.com/KunalSinha7/backpost-analytics/issues/33) | Metric columns: xG, pass geometry, cards, low-cardinality qualifiers. |

### Still open

- Minor, decide during Phase 3: `lineup.cards[]` as a `lineup_card` table vs a JSON column (§2.2).

**Nothing blocking. Phase 0 is ready to start — see §7 for the verification harness (which must land first) and the parallel-lane breakdown.**

---

## 6. Architect review — findings (2026-08-06)

Independent adversarial review. **Every factual claim below was re-verified against the live DB before being recorded here.**

### Blockers — must be resolved before code

| # | Finding | Status |
|---|---|---|
| **B0** | The `lineup.team_id` rule written in an earlier revision of §1.6 was **wrong** — fails on 20 Marseille rows. | ✅ **Fixed** in §1.6; corrected rule verified 3,745/3,745, 0 ambiguous |
| **B1** | `raw_event` ids are **float strings** (`"7626.0"`); `::int` throws. Needs `::numeric::bigint`. | ✅ **Recorded** in §1.5 |
| **B2** | ~~`model_validate` **drops** `Relationship` attrs, so Phase 2 returns `None` silently.~~ **The failure mode was wrong — see the correction below.** The real defect is a live N+1. | ✅ **Fixed in Phase 0**: repositories return the attached ORM row |

> #### B2 CORRECTED 2026-08-07 — measured, not inferred
>
> The review's stated mechanism was wrong. `Competition.model_validate(row)` does **not** drop the relationship; it **eagerly walks** it. Probe against the live DB:
>
> ```
> queries during model_validate : 1 | hitting soccer_match: 1
> copy session-attached         : False
> copy is original (identity)   : False
> copy.matches length           : 34      ← populated, not dropped
> ```
>
> Only the **detachment** half of B2 held. The consequence is therefore not a silent `None` in a future phase — it is a **hidden N+1 in production today**: one extra query per row on `/competitions` and `/players`, plus full hydration of every `SoccerMatch` for a column no caller reads. At `limit=100` that is 100 extra queries; a single Ligue 1 season is 377 matches hydrated per row.
>
> The fix (return the session-attached ORM row) is unchanged and correct. Its value is higher than the plan claimed: it repairs a live performance bug rather than pre-empting a future one.
>
> **Method note:** this is the second claim in the review chain to need correction against reality (the first being the `lineup.team_id` rule in §1.6). Both were plausible and both were wrong in their specifics. Treat remaining unverified review items — **M3** especially — as hypotheses until probed.
| **B3** | `Competition.matches` has `cascade_delete=True`. If Phase 2 recreates `competition` rows rather than altering in place, **3,961 matches and 376k events are deleted**. | ⬜ **Rule added** to Phase 2: in-place `ALTER` only; assert `soccer_match` row count inside the migration |

### High

- **H1 — Cut the `statsbomb_id` rename from this plan.** It is in the `required` list of 5 public schemas and is a **rendered UI column** (`PlayerTable.tsx:57`), plus `competition_statsbomb_id` is a public query param. That is a breaking OpenAPI change delivering **zero capability** — `source_id`/`external_id` can coexist with `statsbomb_id` indefinitely. Do it when a second source actually lands. ✅ **Cut** from Phase 4.
- **H2 — `event.match_id` has no index.** Verified: `event` has only `event_pkey` and `ix_event_statsbomb_id`. This is the primary read path (`read_events` defaults `limit=10000`) *and* backs both `_events_exist_clause` EXISTS subqueries, so `/competitions?has_events=true` seq-scans 376k rows. ✅ **Moved to Phase 0** as `ix_event_match_id_index (match_id, "index")`.

  **Measured 2026-08-07 — and that index alone was NOT enough.** With only the event index, `/competitions?has_events=true` still took **14,136 ms**: the planner did use it, then seq-scanned `soccer_match` once per competition because the correlating column was unindexed. `ix_soccer_match_competition_id` was the missing half:

  ```
  event index only                : 14,136 ms
  + ix_soccer_match_competition_id:      5.5 ms     ← 2,560×
  ```

  Both now ship in Phase 0 (revisions `87e65e37d56a` and `87e2e9cbdd6e`). The plan had `soccer_match.competition_id` slated for Phase 3; it is a pure perf win with no schema semantics, so there was no reason to wait.

  **Lesson to carry into later phases:** an index the planner *uses* is not the same as an index that makes the query *fast*. `EXPLAIN` proudly showed `Index Only Scan using ix_event_match_id_index` while the statement took 14 seconds. **Verify perf gates by timing, not by grepping the plan for an index name.**
- **H3 — "byte-identical responses" is unachievable as a gate.** `read_events(team=...)` filters *event*-feed vocabulary while the dropdown is populated from *match*-feed vocabulary — **already broken for Marseille**; fixing it necessarily changes the response. ✅ **Gate restated** as "identical except the enumerated drift set = {team 147}". Also adds: assert distinct team count == 353 after the `sb.matches()` backfill, and set the tie-break explicitly — **match-feed name wins** (it is what the API emits today).
- **H4 — Phase 1 ships nothing visible.** ✅ Added *additive* `home_team_id`/`away_team_id` to `SoccerMatchPublic` and optional `team_id` filter params. No frontend change required; the phase becomes demonstrable.

### Medium

- **M1 — `EntityResolver` must move to Phase 1, not Phase 4.** Phases 1–2 cannot avoid StatsBomb-specific ingest code (ingest has to populate the new FKs or the backfill decays). ✅ Applied. The `SourceProvider` Protocol/DTOs stay at Phase 4 — that's a `git mv`, not a rewrite. **Explicitly do not port fully first**: designing source-neutral DTOs before the entity shapes settle means rewriting them in Phase 1.
- **M2 — The proposed arch rule may be vacuous.** All five `from statsbombpy import sb` are **function-local**. Verify pytestarch descends into function bodies — otherwise the test is green on day one while every violation persists. ⬜ **Write the test red first.** Also widen its scope: `api/routes/competition.py` imports statsbombpy **inside a route handler** and makes a synchronous vendor HTTP call in the request path.
- **M3 — Resolver will duplicate within a run.** `select` → miss → `add()` without flush re-misses on the next event, and `EventService` commits per match. ⬜ Contract: in-session dict cache on `(source_id, external_id)` + DB `UNIQUE` + `INSERT … ON CONFLICT DO NOTHING RETURNING id`.
- **M4 — Missing constraints** (verified `lineup_dupes = 0`, all safe to add): `UNIQUE(lineup.match_id, player_id)` — today idempotency rests solely on `has_lineups_for_match`, so a half-failed lineup ingest is **permanently stuck and silently skipped**, which matters more now that Phase 0 re-fetches lineups. Plus `UNIQUE(team.source_id, external_id)`, `UNIQUE(player.source_id, external_id)`, `UNIQUE(frame360.event_id)`. Also: `MatchService.ingest` only ever **inserts**, so the team-id backfill cannot be "just re-run ingest" — it needs a dedicated update path.
- **M5 — Add `team_alias(team_id, source_id, name)` in Phase 1.** The team merge is itself irreversible: collapsing `{"Marseille", "Olympique de Marseille"}` destroys per-feed provenance that only the string columns preserve today. Populated as a by-product of the resolver, it makes the merge auditable and Phase 4 genuinely reversible. ✅ Added to Phase 1.

### Serialization — the "strings via relationship" plan needs surgery

`EventPublic(EventBase)` and `Event(EventBase, table=True)` **share `EventBase`** — `team: str` cannot be kept on one and dropped from the other; it is one class. `EventPublic` must be split off `EventBase` and redeclare the name fields, with `@property` accessors on `Event` so `EventPublic.model_validate(e)` keeps working. Same for `SoccerMatchBase`, `LineupBase`, `CompetitionBase`.

**Do not use ORM relationships on the events path.** `read_events` defaults to `limit=10000`; have `EventRepository.list_by_match` load the match's teams/players in one extra query and map ids→names in the service. Use `selectinload` only for `/matches` (limit 100). Also **diff `openapi.json` per phase** — field renames and `required`-list changes don't show up in a response-body diff.

### Cuts — newly identified as speculative

- `season.start_year` / `end_year` — undefined for single-year seasons ("1958" World Cup) and unused. Drop or make nullable with a documented parse rule.
- `team.is_national_team` — **not derivable from any StatsBomb field**; null or wrong on day one. Drop.
- `team.gender` / `country_name` — **must be nullable**; teams first seen via the event feed have no gender/country source.

### Phase 2 pre-flight assertions (verified clean today — record so a future ingest can't silently break them)

```
competition attr conflicts (statsbomb_id → name/country/gender/youth/intl) : 0
season_id → season_name conflicts                                          : 0
season_name → multiple season_id                                           : 0
```

The split is **lossless on today's data**. Assert all three in the Phase 2 migration.

### S1 — Scope of the §1.6 "extract as columns" bucket — RESOLVED 2026-08-06

The reviewer argued the whole bucket was scope creep, under this organizing principle — which is adopted as a **standing rule for this plan**:

> **Do now what only a re-fetch can recover. Defer what `raw_event` already preserves.**

**Resolution — split by role, not by convenience:**

| Kept in Phase 1 | Moved to [#33](https://github.com/KunalSinha7/backpost-analytics/issues/33) |
|---|---|
| `position` (24 values, 374,954 events) | `shot_statsbomb_xg` |
| `substitution_replacement_id` (770) | `pass_length`, `pass_angle` |
| | cards (`foul_committed_card`, `bad_behaviour_card`) |
| | all low-cardinality qualifiers |

Rationale: `position` and `substitution_replacement_id` are **entity FKs on the identity path** — they resolve to `position` and `player` rows via the same `EntityResolver` being built in Phase 1, so deferring them means building the resolver twice. Everything in the right column is a plain scalar with no entity to resolve, sits in `raw_event` indefinitely, and would only inflate the plan's largest phase.

`lineup.positions[]` and `lineup.cards[]` remain in scope regardless — they are the one thing `raw_event` does **not** preserve (§1.6), which is precisely what the standing rule flags as urgent.

### Stale finding — disregard

The reviewer's naming verdict ("keep `competition` = edition, do not overrule") was formed against the **pre-2026-08-06 draft** and argues for the `league` naming that §2.1 has already replaced. Its two amendments still apply and are adopted:

- Rename StatsBomb-side identifiers: `competition_statsbomb_id` → `league_external_id` in repositories/services (they currently carry StatsBomb's *league* id under a "competition" name, and become outright lies after the split).
- **Do not name the ingest DTO `SourceCompetition`** — it will be read as the league. Use `SourceEdition`, with an adapter docstring stating the mapping explicitly.

---

## 7. Execution model — verification scaffolding and parallelism

### 7.1 The verification harness must land first

Every phase gate in §4 leans on *"responses identical except the enumerated drift set"* and *"diff `openapi.json` per phase"*. **No such harness exists in the repo** (verified: no snapshot/golden/openapi tooling under `backend/tests/`).

This cannot be retrofitted. Once Phase 1 lands there is no longer a clean baseline to snapshot, so it is a **Phase 0 deliverable, and the first one**:

- Capture golden responses for `/competitions`, `/matches`, `/matches/teams`, `/events`, `/lineups`, `/players` against the seeded dev dataset
- Capture `/api/v1/openapi.json` — field renames and `required`-list changes do **not** surface in a response-body diff (§6)
- Commit the snapshots; every later phase diffs against them and must explicitly justify any delta

Two Phase 0 items must also be **written red first**, because both are fixes for assumed-broken behaviour and a green-on-day-one test would prove nothing:

- The statsbombpy arch rule (§6/M2 — all five imports are function-local; confirm pytestarch descends into function bodies)
- The `model_validate` relationship-loss fix (§6/B2 — accepted from review, not yet reproduced)

Add one `alembic downgrade` rehearsal on Phase 0's own migration, where the stakes are lowest. Existing migrations do have real `downgrade()` bodies (not stubs), but nothing has exercised them.

### 7.1a ⚠️ Running the test suite DESTROYS the data every backfill reads

Discovered the hard way on 2026-08-06: `bash scripts/tests-start.sh` deleted all 376,362 events, 3,961 matches, 80 competitions and 3,745 lineups from the dev database.

**Mechanism.** `backend/tests/conftest.py` declares a **session-scoped, `autouse=True`** `db` fixture that calls `_wipe_soccer_data()` on both setup and teardown — unconditional `DELETE` against Event, Frame360, Lineup, SoccerMatch, Competition. And there is **no separate test database**: `.env` sets `POSTGRES_DB=app` and the tests bind `app.core.db.engine`, the same engine the dev server uses.

**Why this is a plan-level problem, not just an annoyance.** §1.5 says the Phase 1 event backfill is "a pure in-database operation, no re-fetch" — which is true, but only because the ids live in `event.raw_event`. **A test run deletes those rows.** So the sequence "write migration → run tests → run backfill" silently destroys the backfill's own input, and the backfill then succeeds against an empty table and reports zero rows updated. That is a false green.

**✅ FIXED 2026-08-07** — two layers, because either alone is defeatable:

1. **Isolation.** `scripts/tests-start.sh` exports `POSTGRES_DB=${POSTGRES_DB_TEST:-${POSTGRES_DB}_test}` before Python starts — the engine is built from settings at import time, so this needs no application change. The script creates the database if absent and brings it up with `alembic upgrade head`, so schema comes from migrations exactly as in production rather than from `create_all()`.
2. **A guard.** `conftest._assert_disposable_database()` refuses to run unless the connected database name ends in `_test`, and `_wipe_soccer_data` calls it first. Running `pytest` by hand against dev now raises immediately instead of deleting.

Verified end-to-end: dev DB held 1,365,934 events / 3,961 matches / 80 competitions **before and after** a full suite run; `app` and `app_test` exist side by side; the guard raises when pointed at `app`.

**Still required for Phase 1** (the data hazard is closed, the false-green one is not):

- Phase 1's gate must assert non-zero row counts *before* the backfill, not only after — otherwise an empty table passes every check and reports success.

### 7.2 The hard constraint on parallelism: Alembic serializes all schema work

Verified: the repo has a **single linear head** (`3cfb9503c5b7`), and `env.py` sets no `transaction_per_migration`, so each migration runs in one transaction.

Every generated revision hardcodes `down_revision = '<head at generation time>'`. **Two agents generating migrations concurrently both write the same `down_revision`, producing branched heads that `alembic upgrade head` refuses to run.** This is the single biggest failure mode for a parallel flow on this plan.

> **Rule: exactly one lane owns Alembic revisions at any time.** Other lanes must be migration-free, or hand their schema delta to the migration owner as a written spec rather than generating a revision themselves.

### 7.3 What actually parallelizes

**Phase 0 — genuinely parallel, 3 lanes + 1 serialized:**

| Lane | Scope | Files | Conflicts? |
|---|---|---|---|
| **A — Verification** | Golden + openapi harness (§7.1) | `backend/tests/**` only | None |
| **B — Repository fixes** | `model_validate` relationship loss (red first) | `repositories/competition.py`, `repositories/player.py` | None |
| **C — Parser trap** | `extra="allow"` onto `_StatsBombRow` (§1.5) + a written finding on whether pytestarch detects function-local imports (§6/M2). **No `app/ingest/` package, no Protocol, no committed arch rule** — see the correction in §4 | `utils/statsbomb.py`, new `tests/soccer/test_statsbomb_rows.py` | None |
| **D — Schema (SERIALIZED)** | `data_source`, `raw` columns, `extra="allow"`, `ix_event_match_id_index`, lineups re-fetch | `models/**`, `utils/statsbomb.py`, `alembic/versions/**` | **Owns all migrations** |

Lane D is one worker start-to-finish. A/B/C run concurrently against it. Lane A should finish first — the snapshots are the safety net for everything after.

**Post-Phase-1 — fully parallel, 3 lanes:**
[#31](https://github.com/KunalSinha7/backpost-analytics/issues/31), [#32](https://github.com/KunalSinha7/backpost-analytics/issues/32), [#33](https://github.com/KunalSinha7/backpost-analytics/issues/33) are independent of each other and of Phases 2–4. All three depend only on the `json` → `jsonb` conversion landing in Phase 1 (§1.5). Each is one PR, one lane, no shared files — the best parallel opportunity in the whole plan.

**Also parallel:** frontend work for the additive `team_id` params (§6/H4) once the API shape is agreed, against backend implementation.

### 7.4 What does NOT parallelize — and shouldn't be forced

**Phases 1 → 2 → 3 → 4 are strictly sequential.** Hard data dependency: `event.team_id` cannot be backfilled before `team` exists; the competition split cannot proceed before identity is stable.

**Within Phases 1–3, splitting is counterproductive.** Each is dominated by one hard thing — the backfill — which needs deep, whole-picture context: the float-cast trap (§1.5/B1), the event-feed lineup rule (§1.6/B0), the cascade hazard (§6/B3), and the canonical-name tie-break (§6/H3). Handing fragments of that to separate cold-start workers reintroduces exactly the class of bug the review caught. **Keep Phases 1–3 single-threaded.**

Honest assessment: the parallelism ceiling on this plan is roughly **3× on Phase 0 and 3× on the deferred issues, and 1× on the critical path**. The critical path is where nearly all the risk lives, and it is inherently serial.

### 7.5 Additions required for a multi-lane flow

1. **Migration ownership** (§7.2) — declare the owning lane before any phase starts.
2. **Lane scoping is file-scoped, not task-scoped** — see the table in §7.3. Two lanes must never hold the same file.
3. **Per-phase integration gate** — the §4 gates assume a single worker. With lanes, add an explicit merge point: all lanes green → integrate → *then* run the phase gate against the integrated result, never against a single lane's branch.
4. **Lane A is a prerequisite, not a peer** — no lane that can change an API response may merge before the snapshot harness exists.
