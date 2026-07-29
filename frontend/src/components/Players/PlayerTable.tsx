import { useSuspenseQuery } from "@tanstack/react-query"
import type { ColumnDef } from "@tanstack/react-table"
import { Search } from "lucide-react"
import { useState } from "react"
import type { PlayerPublic } from "@/client"
import { SoccerService } from "@/client"
import { DataTable } from "@/components/Common/DataTable"
import { Input } from "@/components/ui/input"
import { useTablePageSize } from "@/hooks/useTablePageSize"

export function PlayerTable() {
  const [search, setSearch] = useState("")
  const [committedSearch, setCommittedSearch] = useState("")
  const [page, setPage] = useState(0)
  const [pageSize, setPageSize] = useTablePageSize()

  const commitSearch = () => {
    setCommittedSearch(search)
    setPage(0)
  }

  const { data } = useSuspenseQuery({
    queryKey: ["players", committedSearch, page, pageSize],
    queryFn: () =>
      SoccerService.readPlayers({
        skip: page * pageSize,
        limit: pageSize,
        nameSearch: committedSearch || undefined,
      }),
  })

  const columns: ColumnDef<PlayerPublic>[] = [
    {
      accessorKey: "name",
      header: "Name",
    },
    {
      accessorKey: "nationality",
      header: "Nationality",
      cell: ({ row }) => (
        <span className="text-muted-foreground">
          {row.original.nationality ?? "—"}
        </span>
      ),
    },
    {
      accessorKey: "match_count",
      header: "Matches",
      cell: ({ row }) => (
        <span className="font-mono text-xs">
          {row.original.match_count ?? 0}
        </span>
      ),
    },
  ]

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap gap-3 items-center">
        <div className="relative">
          <Input
            placeholder="Search player…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
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
          {data.count} players
        </span>
      </div>
      <DataTable
        columns={columns}
        data={data.data}
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
