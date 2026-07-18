import { useSuspenseQuery } from "@tanstack/react-query"
import { SoccerService } from "@/client"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

interface MatchSelectorProps {
  onSelect: (matchId: string) => void
}

export function MatchSelector({ onSelect }: MatchSelectorProps) {
  const { data } = useSuspenseQuery({
    queryKey: ["matches", "with-events"],
    queryFn: () =>
      SoccerService.readMatches({ skip: 0, limit: 500, hasEvents: true }),
  })

  if (data.count === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No matches with events yet. Use "Ingest Events" to load event data.
      </p>
    )
  }

  return (
    <Select onValueChange={onSelect}>
      <SelectTrigger className="w-full max-w-md">
        <SelectValue placeholder="Select a match…" />
      </SelectTrigger>
      <SelectContent>
        {data.data.map((match) => (
          <SelectItem key={match.id} value={match.id}>
            {match.home_team} vs {match.away_team}{" "}
            <span className="text-muted-foreground">({match.match_date})</span>
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
