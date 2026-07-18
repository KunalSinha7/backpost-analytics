class MatchNotFoundError(Exception):
    def __init__(self, statsbomb_id: int) -> None:
        super().__init__(f"Match not found: statsbomb_id={statsbomb_id}")
        self.statsbomb_id = statsbomb_id
