import { useSuspenseQuery } from "@tanstack/react-query"
import type { ColumnDef } from "@tanstack/react-table"
import type { SoccerMatchPublic } from "@/client"
import { SoccerService } from "@/client"
import { DataTable } from "@/components/Common/DataTable"

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

export function MatchTable() {
  const { data } = useSuspenseQuery({
    queryKey: ["matches"],
    queryFn: () => SoccerService.readMatches({ skip: 0, limit: 500 }),
  })

  if (data.count === 0) return null

  return <DataTable columns={columns} data={data.data} />
}
