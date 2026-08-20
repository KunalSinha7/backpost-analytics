"""Parser retention guarantees for the StatsBomb row models.

`extra="allow"` lives on `_StatsBombRow` so every row type keeps the feed columns
it does not declare. Without it, unmodelled columns are dropped at parse time and
are unrecoverable from the DB afterwards.
"""

import math

from app.utils.statsbomb import (
    StatsBombCompetitionRow,
    StatsBombEventRow,
    StatsBombFrameRow,
    StatsBombLineupPlayerRow,
    StatsBombMatchRow,
)

# The nine `sb.matches()` id columns that `StatsBombMatchRow` does not declare.
MATCH_ENTITY_ID_FIELDS = (
    "home_team_id",
    "away_team_id",
    "referee_id",
    "stadium_id",
    "home_manager_id",
    "away_manager_id",
    "competition_stage_id",
    "home_team_country_id",
    "away_team_country_id",
)


def _match_payload() -> dict:
    """A `sb.matches()` row: declared fields plus the ids the model omits."""
    return {
        "match_id": 7576,
        "match_date": "2020-07-19",
        "kick_off": "22:00:00.000",
        "home_team": "Marseille",
        "away_team": "Paris Saint-Germain",
        "home_score": 1,
        "away_score": 0,
        "stadium": "Stade Vélodrome",
        "referee": "A. Referee",
        "match_week": 38,
        "competition_stage": "Regular Season",
        "home_team_id": 220,
        "away_team_id": 217,
        "referee_id": 1234,
        "stadium_id": 4567,
        "home_manager_id": 89,
        "away_manager_id": 90,
        "competition_stage_id": 1,
        "home_team_country_id": 78,
        "away_team_country_id": 78,
    }


def test_match_row_retains_the_nine_entity_ids() -> None:
    row = StatsBombMatchRow.model_validate(_match_payload())

    for field in MATCH_ENTITY_ID_FIELDS:
        assert hasattr(row, field), f"{field} was dropped at parse time"

    assert row.home_team_id == 220  # type: ignore[attr-defined]
    assert row.away_team_id == 217  # type: ignore[attr-defined]
    assert row.competition_stage_id == 1  # type: ignore[attr-defined]


def test_match_row_entity_ids_survive_model_dump() -> None:
    """The backfill reads these out of a dump, not off the attribute."""
    dumped = StatsBombMatchRow.model_validate(_match_payload()).model_dump()

    for field in MATCH_ENTITY_ID_FIELDS:
        assert field in dumped, f"{field} missing from model_dump()"
    assert dumped["away_team_country_id"] == 78


def test_match_row_declared_fields_are_unaffected() -> None:
    """Retaining extras must not disturb the fields ingest already reads."""
    row = StatsBombMatchRow.model_validate(_match_payload())

    assert row.match_id == 7576
    assert row.home_team == "Marseille"
    assert row.away_team == "Paris Saint-Germain"
    assert row.home_score == 1
    assert row.away_score == 0
    assert row.competition_stage == "Regular Season"


def test_competition_row_retains_undeclared_columns() -> None:
    row = StatsBombCompetitionRow.model_validate(
        {
            "competition_id": 11,
            "season_id": 90,
            "competition_name": "La Liga",
            "some_future_column": "kept",
        }
    )

    assert row.competition_id == 11
    assert row.competition_name == "La Liga"
    assert row.some_future_column == "kept"  # type: ignore[attr-defined]


def test_lineup_row_retains_cards_and_position_detail() -> None:
    """`positions[]` and `cards[]` are unrecoverable from the DB once dropped."""
    positions = [
        {
            "position_id": 1,
            "position": "Goalkeeper",
            "from": "00:00",
            "to": None,
            "from_period": 1,
            "to_period": None,
            "start_reason": "Starting XI",
            "end_reason": "Final Whistle",
        }
    ]
    cards = [{"time": "63:20", "card_type": "Yellow Card", "reason": None, "period": 2}]

    row = StatsBombLineupPlayerRow.model_validate(
        {
            "player_id": 7626,
            "player_name": "Steve Mandanda",
            "player_nickname": None,
            "jersey_number": 30,
            "country": {"id": 78, "name": "France"},
            "positions": positions,
            "cards": cards,
        }
    )

    assert row.cards == cards  # type: ignore[attr-defined]
    assert row.positions == positions
    assert row.country == "France"
    assert row.is_starter() is True


def test_event_row_still_retains_extras() -> None:
    """`raw_event` is `model_dump()` of this row — its contents must not shrink."""
    row = StatsBombEventRow.model_validate(
        {
            "id": "abc-123",
            "index": 4,
            "period": 1,
            "minute": 0,
            "second": 3,
            "type": {"id": 30, "name": "Pass"},
            "team": {"id": 220, "name": "Marseille"},
            "player": {"id": 7626, "name": "Steve Mandanda"},
            "team_id": 220,
            "player_id": 7626.0,
            "pass_recipient_id": 3501.0,
            "pass_end_location": [60.0, 40.0],
        }
    )
    dumped = row.model_dump()

    assert row.type == "Pass"
    assert row.team == "Marseille"
    assert dumped["team_id"] == 220
    assert dumped["pass_end_location"] == [60.0, 40.0]
    # Nullable id columns arrive from pandas as float64, so any SQL cast over
    # them must go through ::numeric::bigint rather than a bare ::int.
    assert dumped["player_id"] == 7626.0
    assert dumped["pass_recipient_id"] == 3501.0


def test_frame_row_still_retains_extras() -> None:
    row = StatsBombFrameRow.model_validate(
        {"id": "abc-123", "visible_area": [1.0, 2.0], "freeze_frame": [], "match_id": 7}
    )

    assert row.id == "abc-123"
    assert row.match_id == 7  # type: ignore[attr-defined]


def test_nan_cleaning_applies_to_retained_extras() -> None:
    """Retained columns go through `_clean_nan` like declared ones do."""
    payload = _match_payload() | {
        "referee_id": float("nan"),
        "stadium_id": float("nan"),
    }
    row = StatsBombMatchRow.model_validate(payload)

    for field in ("referee_id", "stadium_id"):
        value = getattr(row, field)
        assert value is None, f"{field} leaked a NaN instead of None"
        assert not (isinstance(value, float) and math.isnan(value))
