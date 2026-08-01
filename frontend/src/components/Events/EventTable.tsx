import { useSuspenseQuery } from "@tanstack/react-query"
import { useNavigate } from "@tanstack/react-router"
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
import { useTablePageSize } from "@/hooks/useTablePageSize"

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
  const navigate = useNavigate()
  const [typeFilter, setTypeFilter] = useState("all")
  const [teamFilter, setTeamFilter] = useState("all")
  const [periodFilter, setPeriodFilter] = useState("all")
  const [page, setPage] = useState(0)
  const [pageSize, setPageSize] = useTablePageSize()

  const { data } = useSuspenseQuery({
    queryKey: [
      "events",
      matchId,
      typeFilter,
      teamFilter,
      periodFilter,
      page,
      pageSize,
    ],
    queryFn: () =>
      SoccerService.readEvents({
        matchId,
        skip: page * pageSize,
        limit: pageSize,
        typeName: typeFilter === "all" ? undefined : typeFilter,
        team: teamFilter === "all" ? undefined : teamFilter,
        period: periodFilter === "all" ? undefined : Number(periodFilter),
      }),
  })

  const { data: allEvents } = useSuspenseQuery({
    queryKey: ["events", matchId, "all"],
    queryFn: () => SoccerService.readEvents({ matchId, skip: 0, limit: 10000 }),
  })

  const types = [...new Set(allEvents.data.map((e) => e.type_name))].sort()
  const teams = [...new Set(allEvents.data.map((e) => e.team))].sort()
  const periods = [
    ...new Set(allEvents.data.map((e) => String(e.period))),
  ].sort()

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap gap-3 items-center">
        <Select
          value={typeFilter}
          onValueChange={(v) => {
            setTypeFilter(v)
            setPage(0)
          }}
        >
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

        <Select
          value={teamFilter}
          onValueChange={(v) => {
            setTeamFilter(v)
            setPage(0)
          }}
        >
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

        <Select
          value={periodFilter}
          onValueChange={(v) => {
            setPeriodFilter(v)
            setPage(0)
          }}
        >
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
              setPage(0)
            }}
            className="text-xs text-muted-foreground hover:text-foreground underline"
          >
            Clear filters
          </button>
        )}
      </div>

      <DataTable
        columns={columns}
        data={data.data}
        onRowClick={(event) =>
          navigate({
            to: "/soccer/visualize",
            search: {
              matchId,
              possession: event.possession ?? undefined,
            },
          })
        }
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
