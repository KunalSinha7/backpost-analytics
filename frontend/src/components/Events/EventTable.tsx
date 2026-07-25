import { useSuspenseQuery } from "@tanstack/react-query"
import type { ColumnDef } from "@tanstack/react-table"
import { useState } from "react"
import type { EventPublic } from "@/client"
import { SoccerService } from "@/client"
import { DataTable } from "@/components/Common/DataTable"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

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

  const [typeFilter, setTypeFilter] = useState("all")
  const [teamFilter, setTeamFilter] = useState("all")
  const [periodFilter, setPeriodFilter] = useState("all")

  const types = [...new Set(data.data.map((e) => e.type_name))].sort()
  const teams = [...new Set(data.data.map((e) => e.team))].sort()
  const periods = [...new Set(data.data.map((e) => String(e.period)))].sort()

  const filtered = data.data.filter(
    (e) =>
      (typeFilter === "all" || e.type_name === typeFilter) &&
      (teamFilter === "all" || e.team === teamFilter) &&
      (periodFilter === "all" || String(e.period) === periodFilter),
  )

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap gap-3 items-center">
        <Select value={typeFilter} onValueChange={setTypeFilter}>
          <SelectTrigger className="w-44 h-8 text-sm">
            <SelectValue placeholder="Event type" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All types</SelectItem>
            {types.map((t) => (
              <SelectItem key={t} value={t}>
                {t}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select value={teamFilter} onValueChange={setTeamFilter}>
          <SelectTrigger className="w-40 h-8 text-sm">
            <SelectValue placeholder="Team" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Both teams</SelectItem>
            {teams.map((t) => (
              <SelectItem key={t} value={t}>
                {t}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select value={periodFilter} onValueChange={setPeriodFilter}>
          <SelectTrigger className="w-32 h-8 text-sm">
            <SelectValue placeholder="Period" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All periods</SelectItem>
            {periods.map((p) => (
              <SelectItem key={p} value={p}>
                Period {p}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        {(typeFilter !== "all" ||
          teamFilter !== "all" ||
          periodFilter !== "all") && (
          <button
            type="button"
            onClick={() => {
              setTypeFilter("all")
              setTeamFilter("all")
              setPeriodFilter("all")
            }}
            className="text-xs text-muted-foreground hover:text-foreground underline"
          >
            Clear filters
          </button>
        )}
      </div>

      <p className="text-sm text-muted-foreground">
        {filtered.length.toLocaleString()} of {data.count.toLocaleString()}{" "}
        events
      </p>
      <DataTable columns={columns} data={filtered} pageSize={50} />
    </div>
  )
}
