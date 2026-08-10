import logging
import uuid

from sqlmodel import Session, col, select

from app.models.lineup import Lineup
from app.models.match import SoccerMatch
from app.models.player import Player
from app.models.team import TeamAlias
from app.repositories.lineup import LineupRepository
from app.repositories.match import MatchRepository
from app.repositories.player import PlayerRepository
from app.services.resolver import EntityResolver
from app.utils.statsbomb import StatsBombLineupPlayerRow

logger = logging.getLogger(__name__)


class LineupService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.lineup_repo = LineupRepository(session)
        self.match_repo = MatchRepository(session)
        self.player_repo = PlayerRepository(session)
        self.resolver = EntityResolver(session)

    def list_by_match(
        self, match_id: uuid.UUID
    ) -> tuple[list[tuple[Lineup, str, Player]], int]:
        return self.lineup_repo.list_by_match(match_id)

    def _resolve_lineup_team(
        self, match: SoccerMatch, team_name: str
    ) -> uuid.UUID | None:
        """Map the lineup feed's team name onto one of the match's two teams.

        §1.6/B0 rejected comparing this name against the match's team *names*,
        because the feeds disagree: the lineup feed says "Marseille" where the
        match feed says "Olympique de Marseille". The rule it prescribed instead
        went through `event.team`, which no longer exists after Phase 4.

        `team_alias` supersedes both. The resolver records every spelling it has
        ever seen — including each team's canonical name — so this is an exact
        lookup rather than a name comparison, and scoping it to the match's own
        two teams stops a name shared across clubs from resolving to the wrong
        one.
        """
        return self.session.exec(
            select(TeamAlias.team_id).where(
                TeamAlias.name == team_name,
                col(TeamAlias.team_id).in_([match.home_team_id, match.away_team_id]),
            )
        ).first()

    def ingest_for_competition(
        self, competition_statsbomb_id: int, season_id: int
    ) -> int:
        from statsbombpy import sb  # type: ignore[import-untyped]

        matches = self.match_repo.list_for_competition(
            competition_statsbomb_id, season_id
        )
        total_imported = 0

        for match in matches:
            if self.lineup_repo.has_lineups_for_match(match.id):
                continue

            try:
                lineups = sb.lineups(match_id=match.statsbomb_id)
            except Exception:
                logger.warning(
                    "Could not fetch lineups for match %s", match.statsbomb_id
                )
                continue

            batch: list[Lineup] = []
            for team_name, players_df in lineups.items():
                team_id = self._resolve_lineup_team(match, team_name)
                if team_id is None:
                    logger.warning(
                        "Skipping lineup for match %s: team %r matches neither side",
                        match.statsbomb_id,
                        team_name,
                    )
                    continue

                for _, row in players_df.iterrows():
                    player_row = StatsBombLineupPlayerRow.model_validate(row.to_dict())
                    player = self.resolver.resolve_player(
                        player_row.player_id, player_row.player_name
                    )
                    if player is None:
                        continue
                    # Nickname and nationality live on `player` now, so the
                    # lineup feed's copies update the entity rather than being
                    # duplicated onto every appearance.
                    if player.nickname is None and player_row.player_nickname:
                        player.nickname = player_row.player_nickname
                    if player.nationality is None and player_row.country:
                        player.nationality = player_row.country

                    batch.append(
                        Lineup(
                            match_id=match.id,
                            team_id=team_id,
                            player_id=player.id,
                            statsbomb_player_id=player_row.player_id,
                            jersey_number=player_row.jersey_number,
                            started=player_row.is_starter(),
                            # positions[] and cards[] are dropped by the typed
                            # fields above and exist nowhere else, so capturing
                            # the payload here is the only thing standing
                            # between us and another re-fetch. positions[] in
                            # particular carries minutes played, which per-90
                            # season stats depend on.
                            raw=player_row.model_dump(),
                        )
                    )

            self.lineup_repo.add_batch(batch)
            self.session.commit()
            total_imported += len(batch)
            logger.info(
                "Lineups ingested: match_id=%s, players=%d",
                match.statsbomb_id,
                len(batch),
            )

        return total_imported
