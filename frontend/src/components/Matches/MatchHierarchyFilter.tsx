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

interface MatchHierarchyFilterProps {
  competitionId?: string
  teamName?: string
  matchId?: string
  onCompetitionChange: (competitionId: string | undefined) => void
  onTeamChange: (teamName: string | undefined) => void
  onMatchChange: (matchId: string) => void
}

export function MatchHierarchyFilter({
  competitionId,
  teamName,
  matchId,
  onCompetitionChange,
  onTeamChange,
  onMatchChange,
}: MatchHierarchyFilterProps) {
  // keepPreviousData on every level here — without it, narrowing the
  // competition/team dropdown would blank the row while its query refetches,
  // which reads as the whole filter resetting rather than narrowing.
  const { data: compsData } = useQuery({
    queryKey: ["competitions", "hasMatches"],
    queryFn: () =>
      SoccerService.readCompetitions({ skip: 0, limit: 500, hasMatches: true }),
    placeholderData: keepPreviousData,
  })

  const { data: teamsData, isFetching: isFetchingTeams } = useQuery({
    queryKey: ["match-teams", competitionId],
    queryFn: () =>
      SoccerService.readMatchTeams({ competitionId, hasEvents: true }),
    placeholderData: keepPreviousData,
  })

  const { data: matchesData, isFetching: isFetchingMatches } = useQuery({
    queryKey: ["matches", "with-events", competitionId, teamName],
    queryFn: () =>
      SoccerService.readMatches({
        skip: 0,
        limit: 500,
        hasEvents: true,
        competitionId,
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
    // Resetting the team here (instead of a separate onTeamChange call) matters:
    // two independent navigate() calls in the same tick would each close over
    // the pre-update search state, so the second call clobbers the first.
    onCompetitionChange(value === ALL ? undefined : value)
  }

  const handleTeamChange = (value: string) => {
    onTeamChange(value === ALL ? undefined : value)
  }

  return (
    <div className="flex flex-wrap items-center gap-3">
      <Select
        value={competitionId ?? ALL}
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
        <Select value={matchId ?? ""} onValueChange={onMatchChange}>
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
