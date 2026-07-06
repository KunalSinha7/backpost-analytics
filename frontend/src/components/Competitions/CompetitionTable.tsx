import { useSuspenseQuery } from "@tanstack/react-query"
import type { ColumnDef } from "@tanstack/react-table"
import type { CompetitionPublic } from "@/client"
import { SoccerService } from "@/client"
import { DataTable } from "@/components/Common/DataTable"

const columns: ColumnDef<CompetitionPublic>[] = [
  {
    accessorKey: "competition_name",
    header: "Competition",
    cell: ({ row }) => (
      <span className="font-medium">{row.original.competition_name}</span>
    ),
  },
  { accessorKey: "country_name", header: "Country" },
  { accessorKey: "season_name", header: "Season" },
  {
    accessorKey: "competition_gender",
    header: "Gender",
    cell: ({ row }) => (
      <span className="capitalize">{row.original.competition_gender}</span>
    ),
  },
  {
    accessorKey: "competition_youth",
    header: "Youth",
    cell: ({ row }) => (row.original.competition_youth ? "Yes" : "—"),
  },
  {
    accessorKey: "competition_international",
    header: "International",
    cell: ({ row }) => (row.original.competition_international ? "Yes" : "—"),
  },
]

export function CompetitionTable() {
  const { data } = useSuspenseQuery({
    queryKey: ["competitions"],
    queryFn: () => SoccerService.readCompetitions({ skip: 0, limit: 500 }),
  })

  if (data.count === 0) return null

  return <DataTable columns={columns} data={data.data} />
}
