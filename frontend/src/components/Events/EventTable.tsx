import { useSuspenseQuery } from "@tanstack/react-query"
import type { ColumnDef } from "@tanstack/react-table"
import type { EventPublic } from "@/client"
import { SoccerService } from "@/client"
import { DataTable } from "@/components/Common/DataTable"

function formatLocation(
  x: number | null | undefined,
  y: number | null | undefined,
): string {
  if (x == null || y == null) return "—"
  return `${x.toFixed(1)}, ${y.toFixed(1)}`
}

const columns: ColumnDef<EventPublic>[] = [
  {
    accessorKey: "index",
    header: "#",
    cell: ({ row }) => (
      <span className="font-mono text-xs text-muted-foreground">
        {row.original.index}
      </span>
    ),
  },
  {
    accessorKey: "period",
    header: "P",
    cell: ({ row }) => row.original.period,
  },
  {
    id: "time",
    header: "Time",
    cell: ({ row }) => (
      <span className="font-mono text-xs">
        {row.original.timestamp ??
          `${String(row.original.minute).padStart(2, "0")}:${String(row.original.second).padStart(2, "0")}`}
      </span>
    ),
  },
  {
    accessorKey: "possession",
    header: "Poss",
    cell: ({ row }) => (
      <span className="font-mono text-xs text-muted-foreground">
        {row.original.possession ?? "—"}
      </span>
    ),
  },
  {
    accessorKey: "play_pattern_name",
    header: "Pattern",
    cell: ({ row }) => (
      <span className="text-xs text-muted-foreground">
        {row.original.play_pattern_name ?? "—"}
      </span>
    ),
  },
  { accessorKey: "type_name", header: "Type" },
  { accessorKey: "team", header: "Team" },
  {
    accessorKey: "player",
    header: "Player",
    cell: ({ row }) => row.original.player ?? "—",
  },
  {
    id: "location",
    header: "Location",
    cell: ({ row }) => (
      <span className="font-mono text-xs">
        {formatLocation(row.original.location_x, row.original.location_y)}
      </span>
    ),
  },
  {
    accessorKey: "duration",
    header: "Dur",
    cell: ({ row }) => {
      const d = row.original.duration
      return (
        <span className="font-mono text-xs text-muted-foreground">
          {d != null ? d.toFixed(2) : "—"}
        </span>
      )
    },
  },
  {
    id: "flags",
    header: "Flags",
    cell: ({ row }) => {
      const flags = [
        row.original.under_pressure && "UP",
        row.original.off_camera && "OC",
        row.original.out && "Out",
      ].filter(Boolean)
      return flags.length ? (
        <span className="text-xs text-amber-600">{flags.join(" ")}</span>
      ) : null
    },
  },
]

interface EventTableProps {
  matchId: string
}

export function EventTable({ matchId }: EventTableProps) {
  const { data } = useSuspenseQuery({
    queryKey: ["events", matchId],
    queryFn: () => SoccerService.readEvents({ matchId, skip: 0, limit: 10000 }),
  })

  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm text-muted-foreground">
        {data.count.toLocaleString()} events
      </p>
      <DataTable columns={columns} data={data.data} />
    </div>
  )
}
