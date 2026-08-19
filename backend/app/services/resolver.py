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

    The same payload can carry the same kind of id in different shapes —
    `team_id: 142` (int) beside `player_id: 3348.0` (float), because pandas
    widens any column containing a null to float64. Stored verbatim, "142" and
    "3348.0" would never match each other or a plain integer lookup.

    Integral numbers therefore become their plain integer string; anything
    non-numeric passes through unchanged, since other sources use uuids and
    opaque strings.
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

    Keyed on `(source_id, external_id)` and never on name, because feeds
    disagree about names: one calls team 147 "Olympique de Marseille", another
    calls it "Marseille". Keying on the id collapses them to one row.

    Every name variant seen is still recorded in `team_alias`, which is what
    lets a lookup by any spelling find the right team.
    """

    def __init__(
        self, session: Session, source_key: str = STATSBOMB_SOURCE_KEY
    ) -> None:
        self.session = session
        self.teams = TeamRepository(session)
        self.positions = PositionRepository(session)
        self.source = self._get_or_create_source(source_key)
        # Performance only, not correctness: autoflush already makes a pending
        # add() visible to the next select, so get-or-create cannot duplicate
        # without these. They save a round trip per lookup over ~1.4M lookups.
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

        Set `authoritative_name` when the caller's spelling should win over one
        already stored. Only the match feed does this; other feeds contribute
        aliases and may create a team never seen before, but never rename one.
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
        """Get-or-create the season-independent competition.

        The source's competition id stays the same across seasons, so this
        returns one row for La Liga rather than one per La Liga season.
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

    def resolve_player(
        self, external_id: Any, name: str | None = None
    ) -> Player | None:
        """Get-or-create a player, keyed on the source's id.

        Events are ingested before lineups, so this must be able to create a
        player the lineup feed has not introduced yet.
        """
        key = normalize_external_id(external_id)
        if key is None:
            return None
        player = self._player_cache.get(key)
        if player is None:
            player = self.session.exec(
                select(Player).where(
                    Player.source_id == self.source.id, Player.external_id == key
                )
            ).first()
        if player is None:
            # Fall back to the legacy unique key so a player already created by
            # another feed is reused rather than duplicated.
            player = self.session.exec(
                select(Player).where(Player.statsbomb_id == int(key))
            ).first()
        if player is None:
            player = Player(
                statsbomb_id=int(key),
                name=name or key,
                source_id=self.source.id,
                external_id=key,
            )
            self.session.add(player)
            self.session.flush()
        else:
            self.attach_player_source(player)
        self._player_cache[key] = player
        return player

    def attach_player_source(self, player: Player) -> None:
        """Fill in the source/external id on a player that predates them."""
        if player.source_id is None:
            player.source_id = self.source.id
        if player.external_id is None:
            player.external_id = normalize_external_id(player.statsbomb_id)

    @property
    def source_id(self) -> uuid.UUID:
        return self.source.id
