class CompetitionNotFoundError(Exception):
    def __init__(self, statsbomb_id: int, season_id: int) -> None:
        super().__init__(
            f"Competition not found: statsbomb_id={statsbomb_id}, season_id={season_id}"
        )
        self.statsbomb_id = statsbomb_id
        self.season_id = season_id
