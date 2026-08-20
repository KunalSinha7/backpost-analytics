import { keepPreviousData, useQuery } from "@tanstack/react-query"
import { Loader2 } from "lucide-react"
import { SoccerService } from "@/client"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

const ALL = "all"

export interface MatchHierarchySelection {
  competitionSeasonId: string | undefined
  teamName: string | undefined
  matchId: string | undefined
}

interface MatchHierarchyFilterProps extends MatchHierarchySelection {
  // Consumers only need to say where the search params should land (e.g.
  // navigate); the cascade rule below — narrowing a higher level clears the
  // levels beneath it — is owned here so it isn't reimplemented per page.
  onChange: (next: MatchHierarchySelection) => void
}

export function MatchHierarchyFilter({
  competitionSeasonId,
  teamName,
  matchId,
  onChange,
}: MatchHierarchyFilterProps) {
  // keepPreviousData on every level here — without it, narrowing the
  // competition/team dropdown would blank the row while its query refetches,
  // which reads as the whole filter resetting rather than narrowing.
  const { data: compsData } = useQuery({
    queryKey: ["competitions", "hasEvents"],
    queryFn: () =>
      SoccerService.readCompetitions({ skip: 0, limit: 500, hasEvents: true }),
    placeholderData: keepPreviousData,
  })

  const { data: teamsData, isFetching: isFetchingTeams } = useQuery({
    queryKey: ["match-teams", competitionSeasonId],
    queryFn: () =>
      SoccerService.readMatchTeams({ competitionSeasonId, hasEvents: true }),
    placeholderData: keepPreviousData,
  })

  const { data: matchesData, isFetching: isFetchingMatches } = useQuery({
    queryKey: ["matches", "with-events", competitionSeasonId, teamName],
    queryFn: () =>
      SoccerService.readMatches({
        skip: 0,
        limit: 500,
        hasEvents: true,
        competitionSeasonId,
        teamName,
      }),
    placeholderData: keepPreviousData,
  })

  const sortedComps = [...(compsData?.data ?? [])].sort((a, b) =>
    a.competition_name.localeCompare(b.competition_name),
  )
  const teams = teamsData?.data ?? []
  const matches = matchesData?.data ?? []

  const handleCompetitionChange = (value: string) => {
    onChange({
      competitionSeasonId: value === ALL ? undefined : value,
      teamName: undefined,
      matchId: undefined,
    })
  }

  const handleTeamChange = (value: string) => {
    onChange({
      competitionSeasonId,
      teamName: value === ALL ? undefined : value,
      matchId: undefined,
    })
  }

  const handleMatchChange = (value: string) => {
    onChange({ competitionSeasonId, teamName, matchId: value })
  }

  return (
    <div className="flex flex-wrap items-center gap-3">
      <Select
        value={competitionSeasonId ?? ALL}
        onValueChange={handleCompetitionChange}
      >
        <SelectTrigger className="w-64">
          <SelectValue placeholder="All competitions" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={ALL}>All competitions</SelectItem>
          {sortedComps.map((comp) => (
            <SelectItem key={comp.id} value={comp.id}>
              {comp.competition_name} — {comp.season_name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Select value={teamName ?? ALL} onValueChange={handleTeamChange}>
        <SelectTrigger className="w-56">
          <SelectValue placeholder="All teams" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={ALL}>All teams</SelectItem>
          {teams.map((team) => (
            <SelectItem key={team} value={team}>
              {team}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      {matches.length === 0 && !isFetchingMatches ? (
        <p className="text-sm text-muted-foreground">
          No matches with events match these filters.
        </p>
      ) : (
        <Select value={matchId ?? ""} onValueChange={handleMatchChange}>
          <SelectTrigger className="w-full max-w-md">
            <SelectValue placeholder="Select a match…" />
          </SelectTrigger>
          <SelectContent>
            {matches.map((match) => (
              <SelectItem key={match.id} value={match.id}>
                {match.home_team} vs {match.away_team}{" "}
                <span className="text-muted-foreground">
                  ({match.match_date})
                </span>
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      )}

      {(isFetchingTeams || isFetchingMatches) && (
        <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
      )}
    </div>
  )
}
