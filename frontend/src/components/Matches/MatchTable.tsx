import { useSuspenseQuery } from "@tanstack/react-query"
import { useNavigate } from "@tanstack/react-router"
import type { ColumnDef } from "@tanstack/react-table"
import { Search } from "lucide-react"
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
import { useTablePageSize } from "@/hooks/useTablePageSize"

interface MatchTableProps {
  initialCompetitionSeasonId?: string
}

export function MatchTable({ initialCompetitionSeasonId }: MatchTableProps) {
  const navigate = useNavigate()
  const [competitionFilter, setCompetitionFilter] = useState(
    initialCompetitionSeasonId ?? "all",
  )
  const [teamSearch, setTeamSearch] = useState("")
  const [committedTeamSearch, setCommittedTeamSearch] = useState("")
  const [page, setPage] = useState(0)
  const [pageSize, setPageSize] = useTablePageSize()

  const commitSearch = () => {
    setCommittedTeamSearch(teamSearch)
    setPage(0)
  }

  const { data } = useSuspenseQuery({
    queryKey: [
      "matches",
      competitionFilter,
      committedTeamSearch,
      page,
      pageSize,
    ],
    queryFn: () =>
      SoccerService.readMatches({
        skip: page * pageSize,
        limit: pageSize,
        competitionSeasonId:
          competitionFilter === "all" ? undefined : competitionFilter,
        teamName: committedTeamSearch || undefined,
      }),
  })

  // Only show competitions that have ingested matches in the dropdown
  const { data: compsData } = useSuspenseQuery({
    queryKey: ["competitions", "hasMatches"],
    queryFn: () =>
      SoccerService.readCompetitions({ skip: 0, limit: 500, hasMatches: true }),
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
        <span className="font-medium">
          {row.original.home_team}{" "}
          <span className="text-muted-foreground font-normal">vs</span>{" "}
          {row.original.away_team}
        </span>
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

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap gap-3 items-center">
        <Select
          value={competitionFilter}
          onValueChange={(v) => {
            setCompetitionFilter(v)
            setPage(0)
          }}
        >
          <SelectTrigger className="w-64">
            <SelectValue placeholder="All competitions" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All competitions</SelectItem>
            {sortedComps.map((comp) => (
              <SelectItem key={comp.id} value={comp.id}>
                {comp.competition_name} — {comp.season_name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <div className="relative">
          <Input
            placeholder="Search team…"
            value={teamSearch}
            onChange={(e) => setTeamSearch(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && commitSearch()}
            className="w-48 pr-8"
          />
          <button
            type="button"
            onClick={commitSearch}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
          >
            <Search className="h-4 w-4" />
          </button>
        </div>
        <span className="text-sm text-muted-foreground ml-auto">
          {data.count} matches
        </span>
      </div>
      <DataTable
        columns={columns}
        data={data.data}
        onRowClick={(match) => {
          if (!match.has_events) return
          navigate({
            to: "/soccer/visualize",
            search: {
              competitionSeasonId: match.competition_season_id,
              teamName: undefined,
              matchId: match.id,
              possession: undefined,
            },
          })
        }}
        serverPagination={{
          totalCount: data.count,
          page,
          pageSize,
          onPageChange: setPage,
          onPageSizeChange: (s) => {
            setPageSize(s)
            setPage(0)
          },
        }}
      />
    </div>
  )
}
