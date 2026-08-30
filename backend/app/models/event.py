import uuid

from sqlalchemy import JSON, Index
from sqlmodel import Field, SQLModel


class EventBase(SQLModel):
    statsbomb_id: str = Field(max_length=36, index=True, unique=True)
    match_id: uuid.UUID = Field(foreign_key="soccer_match.id")
    index: int
    period: int
    timestamp: str | None = Field(default=None, max_length=20)
    minute: int
    second: int
    type_name: str = Field(max_length=100)
    possession: int | None = None
    play_pattern_name: str | None = Field(default=None, max_length=100)
    location_x: float | None = None
    location_y: float | None = None
    end_location_x: float | None = None
    end_location_y: float | None = None
    duration: float | None = None
    under_pressure: bool | None = None
    off_camera: bool | None = None
    out: bool | None = None


class Event(EventBase, table=True):
    # Composite rather than a plain index=True on match_id: every read of this
    # table is "the events of one match, in index order", so the second column
    # serves the ORDER BY as well as the lookup. A leading-column-only index
    # would be redundant with this one.
    __table_args__ = (Index("ix_event_match_id_index", "match_id", "index"),)
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    # jsonb, not the json this column started as (see the 20260822 migration
    # for the conversion rationale) — needed for ->> extraction on the backfill
    # below and for issue #31's jsonb_array_elements_text on related_events.
    raw_event: dict = Field(default_factory=dict, sa_type=JSON)
    # Not index=True: these are the leading columns of composite indexes
    # declared in the migrations, which single-column indexes would duplicate.
    #
    # player_id and pass_recipient_id are nullable because some events (Half
    # Start, Half End and similar) genuinely have no player.
    team_id: uuid.UUID = Field(foreign_key="team.id")
    possession_team_id: uuid.UUID = Field(foreign_key="team.id")
    player_id: uuid.UUID | None = Field(default=None, foreign_key="player.id")
    pass_recipient_id: uuid.UUID | None = Field(default=None, foreign_key="player.id")
    position_id: uuid.UUID | None = Field(default=None, foreign_key="position.id")
    substitution_replacement_id: uuid.UUID | None = Field(
        default=None, foreign_key="player.id"
    )
    # Self-FKs carrying assist attribution, sourced from `raw_event`'s
    # `shot_key_pass_id` / `pass_assisted_shot_id`. Not indexed: nothing
    # queries "which shots did this pass key" (the reverse direction) yet, and
    # the forward lookup is a single-row fetch by this column's own value.
    #
    # ondelete="SET NULL" rather than the app's usual unset (= RESTRICT): these
    # are the first self-referencing FKs on this table, and a plain bulk
    # `DELETE FROM event` — which the test suite's teardown does — errors on a
    # self-referencing RESTRICT constraint once any row in the batch is
    # pointed to by another row in the same batch, since Postgres checks "is
    # this id still referenced" before the whole statement finishes deleting
    # its referrers. SET NULL sidesteps that and is also the right read:
    # "assist attribution unknown" once the source event is gone, not "this
    # deletion is illegal".
    key_pass_event_id: uuid.UUID | None = Field(
        default=None, foreign_key="event.id", ondelete="SET NULL"
    )
    assisted_shot_event_id: uuid.UUID | None = Field(
        default=None, foreign_key="event.id", ondelete="SET NULL"
    )

    # --- Metric/qualifier columns promoted from raw_event (issue #33) -------
    # Plain columns, deliberately no lookup tables: these are 3-8 distinct
    # values apiece, and a join on a 376k-row hot path costs more than the
    # storage saves (same call the plan makes for type_name/play_pattern_name).
    # Stored but not (yet) exposed on EventPublic/the API — see the PR
    # description for why, and add them there once field presence is
    # confirmed against the real dataset.

    # Headline metric: expected goals. 2,536 shots, 100% coverage, mean ~0.115.
    shot_statsbomb_xg: float | None = None
    pass_length: float | None = None
    pass_angle: float | None = None

    # Disciplinary cards.
    foul_committed_card: str | None = Field(default=None, max_length=50)
    bad_behaviour_card: str | None = Field(default=None, max_length=50)

    # Qualifiers: low-cardinality outcome/type/technique strings.
    pass_height: str | None = Field(default=None, max_length=50)
    pass_body_part: str | None = Field(default=None, max_length=50)
    pass_outcome: str | None = Field(default=None, max_length=50)
    pass_type: str | None = Field(default=None, max_length=50)
    pass_technique: str | None = Field(default=None, max_length=50)
    shot_outcome: str | None = Field(default=None, max_length=50)
    shot_body_part: str | None = Field(default=None, max_length=50)
    shot_technique: str | None = Field(default=None, max_length=50)
    shot_type: str | None = Field(default=None, max_length=50)
    duel_type: str | None = Field(default=None, max_length=50)
    duel_outcome: str | None = Field(default=None, max_length=50)
    dribble_outcome: str | None = Field(default=None, max_length=50)
    ball_receipt_outcome: str | None = Field(default=None, max_length=50)
    interception_outcome: str | None = Field(default=None, max_length=50)
    goalkeeper_type: str | None = Field(default=None, max_length=50)
    goalkeeper_outcome: str | None = Field(default=None, max_length=50)
    goalkeeper_position: str | None = Field(default=None, max_length=50)
    goalkeeper_technique: str | None = Field(default=None, max_length=50)
    goalkeeper_body_part: str | None = Field(default=None, max_length=50)

    # Boolean qualifiers.
    counterpress: bool | None = None
    pass_cross: bool | None = None
    pass_switch: bool | None = None
    pass_through_ball: bool | None = None
    pass_goal_assist: bool | None = None
    pass_shot_assist: bool | None = None
    pass_cut_back: bool | None = None
    pass_deflected: bool | None = None
    pass_no_touch: bool | None = None
    pass_miscommunication: bool | None = None
    shot_first_time: bool | None = None
    shot_one_on_one: bool | None = None
    shot_open_goal: bool | None = None
    shot_deflected: bool | None = None
    shot_redirect: bool | None = None
    shot_saved_off_target: bool | None = None
    shot_saved_to_post: bool | None = None
    shot_follows_dribble: bool | None = None
    dribble_nutmeg: bool | None = None
    dribble_overrun: bool | None = None
    dribble_no_touch: bool | None = None
    foul_committed_advantage: bool | None = None
    foul_committed_penalty: bool | None = None
    foul_won_advantage: bool | None = None
    foul_won_defensive: bool | None = None
    foul_won_penalty: bool | None = None


class EventPublic(EventBase):
    # Names are resolved by the service from an id -> name map, not by ORM
    # relationships, which would be four lazy loads per row on a large page.
    id: uuid.UUID
    team: str = Field(max_length=255)
    player: str | None = Field(default=None, max_length=255)
    pass_recipient: str | None = Field(default=None, max_length=255)
    possession_team_name: str | None = Field(default=None, max_length=255)

    @classmethod
    def from_row(
        cls,
        event: "Event",
        names: "dict[uuid.UUID, str]",
    ) -> "EventPublic":
        return cls(
            **event.model_dump(
                exclude={
                    "raw_event",
                    "team_id",
                    "possession_team_id",
                    "player_id",
                    "pass_recipient_id",
                    "position_id",
                    "substitution_replacement_id",
                    "key_pass_event_id",
                    "assisted_shot_event_id",
                }
            ),
            team=names.get(event.team_id, ""),
            player=names.get(event.player_id) if event.player_id else None,
            pass_recipient=(
                names.get(event.pass_recipient_id) if event.pass_recipient_id else None
            ),
            possession_team_name=(
                names.get(event.possession_team_id)
                if event.possession_team_id
                else None
            ),
        )


class EventsPublic(SQLModel):
    data: list[EventPublic]
    count: int
