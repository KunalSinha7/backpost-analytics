import logging
import uuid
from typing import Any

from sqlmodel import Session, select

from app.models.competition import Competition, Season
from app.models.competition_stage import CompetitionStage
from app.models.data_source import DataSource
from app.models.manager import Manager
from app.models.player import Player
from app.models.position import Position
from app.models.referee import Referee
from app.models.stadium import Stadium
from app.models.team import Team, TeamAlias
from app.repositories.competition_stage import CompetitionStageRepository
from app.repositories.manager import ManagerRepository
from app.repositories.position import PositionRepository
from app.repositories.referee import RefereeRepository
from app.repositories.stadium import StadiumRepository
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
        self.referees = RefereeRepository(session)
        self.stadiums = StadiumRepository(session)
        self.managers = ManagerRepository(session)
        self.competition_stages = CompetitionStageRepository(session)
        self.source = self._get_or_create_source(source_key)
        # Performance only, not correctness: autoflush already makes a pending
        # add() visible to the next select, so get-or-create cannot duplicate
        # without these. They save a round trip per lookup over ~1.4M lookups.
        self._team_cache: dict[str, Team] = {}
        self._player_cache: dict[str, Player] = {}
        self._position_cache: dict[str, Position] = {}
        self._competition_cache: dict[str, Competition] = {}
        self._season_cache: dict[str, Season] = {}
        self._referee_cache: dict[str, Referee] = {}
        self._stadium_cache: dict[str, Stadium] = {}
        self._manager_cache: dict[str, Manager] = {}
        self._competition_stage_cache: dict[str, CompetitionStage] = {}

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

    def resolve_referee(self, external_id: Any, name: str | None) -> Referee | None:
        """Get-or-create a referee, keyed on the source's id.

        Deferred entity (issue #30): promoted from `soccer_match.referee` free
        text with the same `(source_id, external_id)` identity as team/position.
        """
        key = normalize_external_id(external_id)
        if key is None:
            return None
        referee = self._referee_cache.get(key)
        if referee is None:
            referee = self.referees.get_by_external(self.source.id, key)
        if referee is None:
            referee = Referee(
                source_id=self.source.id, external_id=key, name=name or key
            )
            self.referees.add(referee)
            self.session.flush()
        self._referee_cache[key] = referee
        return referee

    def resolve_stadium(self, external_id: Any, name: str | None) -> Stadium | None:
        """Get-or-create a stadium, keyed on the source's id.

        Deferred entity (issue #30): promoted from `soccer_match.stadium` free
        text with the same `(source_id, external_id)` identity as team/position.
        """
        key = normalize_external_id(external_id)
        if key is None:
            return None
        stadium = self._stadium_cache.get(key)
        if stadium is None:
            stadium = self.stadiums.get_by_external(self.source.id, key)
        if stadium is None:
            stadium = Stadium(
                source_id=self.source.id, external_id=key, name=name or key
            )
            self.stadiums.add(stadium)
            self.session.flush()
        self._stadium_cache[key] = stadium
        return stadium

    def resolve_manager(self, external_id: Any, name: str | None) -> Manager | None:
        """Get-or-create a manager, keyed on the source's id.

        Shared by both `home_manager_id` and `away_manager_id` — there is no
        separate home/away manager entity. Deferred entity (issue #30):
        promoted from `soccer_match.home_manager_name` /
        `away_manager_name` free text with the same `(source_id, external_id)`
        identity as team/position.
        """
        key = normalize_external_id(external_id)
        if key is None:
            return None
        manager = self._manager_cache.get(key)
        if manager is None:
            manager = self.managers.get_by_external(self.source.id, key)
        if manager is None:
            manager = Manager(
                source_id=self.source.id, external_id=key, name=name or key
            )
            self.managers.add(manager)
            self.session.flush()
        self._manager_cache[key] = manager
        return manager

    def resolve_competition_stage(
        self, external_id: Any, name: str | None
    ) -> CompetitionStage | None:
        """Get-or-create a competition stage, keyed on the source's id.

        Deferred entity (issue #30): promoted from
        `soccer_match.competition_stage_name` free text with the same
        `(source_id, external_id)` identity as team/position.
        """
        key = normalize_external_id(external_id)
        if key is None:
            return None
        stage = self._competition_stage_cache.get(key)
        if stage is None:
            stage = self.competition_stages.get_by_external(self.source.id, key)
        if stage is None:
            stage = CompetitionStage(
                source_id=self.source.id, external_id=key, name=name or key
            )
            self.competition_stages.add(stage)
            self.session.flush()
        self._competition_stage_cache[key] = stage
        return stage

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
