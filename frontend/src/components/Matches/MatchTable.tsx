import { useSuspenseQuery } from "@tanstack/react-query"
import { useNavigate } from "@tanstack/react-router"
import type { ColumnDef } from "@tanstack/react-table"
import { useState } from "react"
import type { SoccerMatchPublic } from "@/client"
import { SoccerService } from "@/client"
import { DataTable } from "@/components/Common/DataTable"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

interface MatchTableProps {
  initialCompetitionId?: string
}

export function MatchTable({ initialCompetitionId }: MatchTableProps) {
  const navigate = useNavigate()
  const [competitionFilter, setCompetitionFilter] = useState(
    initialCompetitionId ?? "all",
  )
  const [teamSearch, setTeamSearch] = useState("")

  const { data } = useSuspenseQuery({
    queryKey: ["matches"],
    queryFn: () => SoccerService.readMatches({ skip: 0, limit: 500 }),
  })
  const { data: compsData } = useSuspenseQuery({
    queryKey: ["competitions"],
    queryFn: () => SoccerService.readCompetitions({ skip: 0, limit: 500 }),
  })

  const filtered = data.data.filter((m) => {
    const matchesComp =
      competitionFilter === "all" || m.competition_id === competitionFilter
    const searchLower = teamSearch.toLowerCase()
    const matchesTeam =
      teamSearch === "" ||
      m.home_team.toLowerCase().includes(searchLower) ||
      m.away_team.toLowerCase().includes(searchLower)
    return matchesComp && matchesTeam
  })

  const sortedComps = [...(compsData.data ?? [])].sort((a, b) =>
    a.competition_name.localeCompare(b.competition_name),
  )

  const columns: ColumnDef<SoccerMatchPublic>[] = [
    {
      accessorKey: "match_week",
      header: "Wk",
      cell: ({ row }) => (
        <span className="font-mono text-xs text-muted-foreground">
          {row.original.match_week ?? "—"}
        </span>
      ),
    },
    { accessorKey: "match_date", header: "Date" },
    {
      accessorKey: "competition_stage_name",
      header: "Stage",
      cell: ({ row }) => (
        <span className="text-muted-foreground text-xs">
          {row.original.competition_stage_name ?? "—"}
        </span>
      ),
    },
    {
      id: "fixture",
      header: "Fixture",
      cell: ({ row }) => (
        <button
          type="button"
          onClick={() =>
            navigate({
              to: "/soccer/events",
              search: { matchId: row.original.id },
            })
          }
          className="font-medium text-left hover:underline hover:text-primary cursor-pointer"
        >
          {row.original.home_team}{" "}
          <span className="text-muted-foreground font-normal">vs</span>{" "}
          {row.original.away_team}
        </button>
      ),
    },
    {
      id: "score",
      header: "Score",
      cell: ({ row }) => {
        const { home_score, away_score } = row.original
        if (home_score == null || away_score == null) return "—"
        return (
          <span className="font-mono font-medium">
            {home_score} – {away_score}
          </span>
        )
      },
    },
    {
      id: "managers",
      header: "Managers",
      cell: ({ row }) => {
        const home = row.original.home_manager_name
        const away = row.original.away_manager_name
        if (!home && !away)
          return <span className="text-muted-foreground">—</span>
        return (
          <span className="text-xs text-muted-foreground">
            {home ?? "—"} / {away ?? "—"}
          </span>
        )
      },
    },
    {
      accessorKey: "stadium",
      header: "Stadium",
      cell: ({ row }) => (
        <span className="text-muted-foreground">
          {row.original.stadium ?? "—"}
        </span>
      ),
    },
  ]

  if (data.count === 0) return null

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap gap-3 items-center">
        <Select value={competitionFilter} onValueChange={setCompetitionFilter}>
          <SelectTrigger className="w-56">
            <SelectValue placeholder="All competitions" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All competitions</SelectItem>
            {sortedComps.map((comp) => (
              <SelectItem key={comp.id} value={comp.id}>
                {comp.competition_name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Input
          placeholder="Search team…"
          value={teamSearch}
          onChange={(e) => setTeamSearch(e.target.value)}
          className="w-48"
        />
        <span className="text-sm text-muted-foreground ml-auto">
          {filtered.length} matches
        </span>
      </div>
      <DataTable columns={columns} data={filtered} />
    </div>
  )
}
