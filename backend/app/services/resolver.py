import logging
import uuid
from typing import Any

from sqlmodel import Session, select

from app.models.competition import Competition, Season
from app.models.data_source import DataSource
from app.models.player import Player
from app.models.position import Position
from app.models.team import Team, TeamAlias
from app.repositories.position import PositionRepository
from app.repositories.team import TeamRepository

logger = logging.getLogger(__name__)

STATSBOMB_SOURCE_KEY = "statsbomb"


def normalize_external_id(value: Any) -> str | None:
    """Canonicalise a source's entity id to the string form we store.

    Numeric ids arrive in inconsistent shapes from the same payload: a single
    flattened StatsBomb event carries `team_id: 142` (int) next to
    `player_id: 3348.0` (float), because pandas widens any column containing a
    null to float64. Left alone, "142" and "3348.0" would be stored as-is and
    the SQL backfill — which canonicalises via ::numeric::bigint::text — would
    match neither. That mismatch does not raise; it silently updates zero rows.

    So both sides agree on one rule: integral numerics become their plain
    integer string, and anything non-numeric is passed through unchanged (other
    sources use uuids and opaque strings).
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        number = float(text)
    except ValueError:
        return text
    if number.is_integer():
        return str(int(number))
    return text


class EntityResolver:
    """Get-or-create for the entities shared across feeds.

    Keyed on `(source_id, external_id)` and **never** on name. That is the
    whole point: StatsBomb's match feed calls team 147 "Olympique de Marseille"
    while its event feed calls it "Marseille", and keying on the id is what
    collapses them to one row instead of two. `UNIQUE(source_id, external_id)`
    backs the same invariant at the database level.

    Names are still recorded — every variant lands in `team_alias`, so the
    merge stays auditable and Phase 4 stays reversible.
    """

    def __init__(
        self, session: Session, source_key: str = STATSBOMB_SOURCE_KEY
    ) -> None:
        self.session = session
        self.teams = TeamRepository(session)
        self.positions = PositionRepository(session)
        self.source = self._get_or_create_source(source_key)
        # Purely a performance measure, not a correctness one. Session.autoflush
        # defaults to True, so a pending add() is already visible to the next
        # select and get-or-create cannot duplicate within a run (§6/M3, which
        # claimed otherwise and was disproved by probe). This just avoids a
        # round trip per lookup across ~1.4M resolutions.
        self._team_cache: dict[str, Team] = {}
        self._player_cache: dict[str, Player] = {}
        self._position_cache: dict[str, Position] = {}
        self._competition_cache: dict[str, Competition] = {}
        self._season_cache: dict[str, Season] = {}

    def _get_or_create_source(self, key: str) -> DataSource:
        source = self.session.exec(
            select(DataSource).where(DataSource.key == key)
        ).first()
        if source is None:
            source = DataSource(key=key, name=key.title())
            self.session.add(source)
            self.session.flush()
        return source

    def resolve_team(
        self,
        external_id: Any,
        name: str,
        *,
        authoritative_name: bool = False,
        gender: str | None = None,
        country_name: str | None = None,
    ) -> Team | None:
        """Get-or-create a team, recording `name` as an alias either way.

        `authoritative_name` encodes the §6/H3 tie-break: when two feeds
        disagree, the **match feed wins**, because its spelling is what the API
        emits today — so switching to FK-resolved names does not change any
        response. Event-feed names only fill in a team the match feed never
        mentioned.
        """
        key = normalize_external_id(external_id)
        if key is None:
            return None

        team = self._team_cache.get(key)
        if team is None:
            team = self.teams.get_by_external(self.source.id, key)
        if team is None:
            team = Team(
                source_id=self.source.id,
                external_id=key,
                name=name,
                gender=gender,
                country_name=country_name,
            )
            self.teams.add(team)
            self.session.flush()
        else:
            if authoritative_name and team.name != name:
                team.name = name
            # Only ever fill gaps: a team first seen through the event feed has
            # no gender/country, and the match feed is the only thing that
            # supplies them.
            if gender is not None and team.gender is None:
                team.gender = gender
            if country_name is not None and team.country_name is None:
                team.country_name = country_name

        self._team_cache[key] = team
        self._record_alias(team, name)
        return team

    def _record_alias(self, team: Team, name: str) -> None:
        if not name:
            return
        if self.teams.has_alias(team.id, self.source.id, name):
            return
        self.teams.add_alias(
            TeamAlias(team_id=team.id, source_id=self.source.id, name=name)
        )

    def resolve_position(self, external_id: Any, name: str) -> Position | None:
        key = normalize_external_id(external_id)
        if key is None:
            return None
        position = self._position_cache.get(key)
        if position is None:
            position = self.positions.get_by_external(self.source.id, key)
        if position is None:
            position = Position(source_id=self.source.id, external_id=key, name=name)
            self.positions.add(position)
            self.session.flush()
        self._position_cache[key] = position
        return position

    def resolve_competition(
        self,
        external_id: Any,
        name: str,
        *,
        country_name: str,
        gender: str,
        is_youth: bool = False,
        is_international: bool = False,
    ) -> Competition | None:
        """Get-or-create the TIMELESS competition (La Liga, not La Liga 18/19).

        Keyed on StatsBomb's `competition_id`, which is timeless by design —
        `11` is La Liga across all 18 seasons. Deduplicating on it is what
        collapses the 80 edition rows into 24 competitions and removes the 2NF
        violation in §1.1.
        """
        key = normalize_external_id(external_id)
        if key is None:
            return None
        competition = self._competition_cache.get(key)
        if competition is None:
            competition = self.session.exec(
                select(Competition).where(
                    Competition.source_id == self.source.id,
                    Competition.external_id == key,
                )
            ).first()
        if competition is None:
            competition = Competition(
                source_id=self.source.id,
                external_id=key,
                name=name,
                country_name=country_name,
                gender=gender,
                is_youth=is_youth,
                is_international=is_international,
            )
            self.session.add(competition)
            self.session.flush()
        self._competition_cache[key] = competition
        return competition

    def resolve_season(self, external_id: Any, name: str) -> Season | None:
        key = normalize_external_id(external_id)
        if key is None:
            return None
        season = self._season_cache.get(key)
        if season is None:
            season = self.session.exec(
                select(Season).where(
                    Season.source_id == self.source.id, Season.external_id == key
                )
            ).first()
        if season is None:
            season = Season(source_id=self.source.id, external_id=key, name=name)
            self.session.add(season)
            self.session.flush()
        self._season_cache[key] = season
        return season

    def attach_player_source(self, player: Player) -> None:
        """Stamp an existing player row with its source columns.

        Players are not get-or-create here: the table predates this phase and
        is populated from lineups, keyed on `statsbomb_id`. This backfills the
        provenance columns beside that id rather than re-identifying anyone —
        the rename of `statsbomb_id` itself was cut from the plan (§6/H1).
        """
        if player.source_id is None:
            player.source_id = self.source.id
        if player.external_id is None:
            player.external_id = normalize_external_id(player.statsbomb_id)

    @property
    def source_id(self) -> uuid.UUID:
        return self.source.id
