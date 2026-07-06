class StatsBombFetchError(Exception):
    def __init__(self, match_id: int) -> None:
        super().__init__(
            f"Failed to fetch events from StatsBomb for match_id={match_id}"
        )
        self.match_id = match_id


class EventIngestError(Exception):
    def __init__(self, detail: str) -> None:
        super().__init__(detail)
