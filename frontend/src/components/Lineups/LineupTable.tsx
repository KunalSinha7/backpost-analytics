import { useSuspenseQuery } from "@tanstack/react-query"
import type { ColumnDef } from "@tanstack/react-table"
import type { LineupPublic } from "@/client"
import { SoccerService } from "@/client"
import { DataTable } from "@/components/Common/DataTable"

const columns: ColumnDef<LineupPublic>[] = [
  {
    accessorKey: "jersey_number",
    header: "#",
    cell: ({ row }) => (
      <span className="font-mono text-xs font-medium w-6 inline-block">
        {row.original.jersey_number}
      </span>
    ),
  },
  {
    accessorKey: "player_name",
    header: "Player",
    cell: ({ row }) => (
      <span className="font-medium">{row.original.player_name}</span>
    ),
  },
  {
    accessorKey: "player_nickname",
    header: "Nickname",
    cell: ({ row }) => (
      <span className="text-muted-foreground text-xs">
        {row.original.player_nickname ?? "—"}
      </span>
    ),
  },
  {
    accessorKey: "country_name",
    header: "Nationality",
    cell: ({ row }) => (
      <span className="text-muted-foreground text-xs">
        {row.original.country_name ?? "—"}
      </span>
    ),
  },
]

interface TeamPanelProps {
  teamName: string
  players: LineupPublic[]
}

function TeamPanel({ teamName, players }: TeamPanelProps) {
  const starters = players.filter((p) => p.started)
  const bench = players.filter((p) => !p.started)
  const hasStartedData = starters.length > 0

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-sm">{teamName}</h3>
        <span className="text-xs text-muted-foreground">
          {players.length} players
        </span>
      </div>

      {hasStartedData ? (
        <>
          <div>
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-1">
              Starting XI ({starters.length})
            </p>
            <DataTable
              columns={columns}
              data={starters}
              pageSize={starters.length}
            />
          </div>
          {bench.length > 0 && (
            <div>
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-1">
                Bench ({bench.length})
              </p>
              <DataTable
                columns={columns}
                data={bench}
                pageSize={bench.length}
              />
            </div>
          )}
        </>
      ) : (
        <DataTable columns={columns} data={players} pageSize={players.length} />
      )}
    </div>
  )
}

interface LineupTableProps {
  matchId: string
}

export function LineupTable({ matchId }: LineupTableProps) {
  const { data } = useSuspenseQuery({
    queryKey: ["lineups", matchId],
    queryFn: () => SoccerService.readLineups({ matchId }),
  })

  if (data.count === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No lineup data for this match. Re-run "Ingest Events" to fetch lineups.
      </p>
    )
  }

  const byTeam = data.data.reduce<Record<string, LineupPublic[]>>((acc, p) => {
    const team = p.team_name ?? "Unknown"
    if (!acc[team]) acc[team] = []
    acc[team].push(p)
    return acc
  }, {})

  const teams = Object.entries(byTeam).sort(([a], [b]) => a.localeCompare(b))

  return (
    <div className="grid grid-cols-2 gap-6">
      {teams.map(([teamName, players]) => (
        <TeamPanel key={teamName} teamName={teamName} players={players} />
      ))}
    </div>
  )
}
