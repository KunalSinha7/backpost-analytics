import { useSuspenseQuery } from "@tanstack/react-query"
import { useNavigate } from "@tanstack/react-router"
import type { ColumnDef } from "@tanstack/react-table"
import { useState } from "react"
import { useTablePageSize } from "@/hooks/useTablePageSize"
import type { CompetitionPublic } from "@/client"
import { SoccerService } from "@/client"
import { DataTable } from "@/components/Common/DataTable"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

export function CompetitionTable() {
  const { data } = useSuspenseQuery({
    queryKey: ["competitions"],
    queryFn: () => SoccerService.readCompetitions({ skip: 0, limit: 500 }),
  })

  const navigate = useNavigate()
  const [countryFilter, setCountryFilter] = useState("all")
  const [genderFilter, setGenderFilter] = useState("all")
  const [page, setPage] = useState(0)
  const [pageSize, setPageSize] = useTablePageSize()

  if (data.count === 0) return null

  const countries = [...new Set(data.data.map((c) => c.country_name))].sort()
  const genders = [
    ...new Set(data.data.map((c) => c.competition_gender)),
  ].sort()

  const filtered = data.data.filter(
    (c) =>
      (countryFilter === "all" || c.country_name === countryFilter) &&
      (genderFilter === "all" || c.competition_gender === genderFilter),
  )
  const pageData = filtered.slice(page * pageSize, (page + 1) * pageSize)

  const columns: ColumnDef<CompetitionPublic>[] = [
    {
      accessorKey: "competition_name",
      header: "Competition",
      cell: ({ row }) => (
        <button
          type="button"
          onClick={() =>
            navigate({
              to: "/soccer/matches",
              search: { competitionId: row.original.id },
            })
          }
          className="font-medium text-left hover:underline hover:text-primary cursor-pointer"
        >
          {row.original.competition_name}
        </button>
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

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap gap-3 items-center">
        <Select
          value={countryFilter}
          onValueChange={(v) => {
            setCountryFilter(v)
            setPage(0)
          }}
        >
          <SelectTrigger className="w-44">
            <SelectValue placeholder="Country" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All countries</SelectItem>
            {countries.map((c) => (
              <SelectItem key={c} value={c}>
                {c}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select
          value={genderFilter}
          onValueChange={(v) => {
            setGenderFilter(v)
            setPage(0)
          }}
        >
          <SelectTrigger className="w-36">
            <SelectValue placeholder="Gender" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All genders</SelectItem>
            {genders.map((g) => (
              <SelectItem key={g} value={g} className="capitalize">
                {g}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      {filtered.length === 0 && data.count > 0 ? (
        <p className="text-sm text-muted-foreground">
          No competitions match the selected filters.
        </p>
      ) : (
        <DataTable
          columns={columns}
          data={pageData}
          serverPagination={{
            totalCount: filtered.length,
            page,
            pageSize,
            onPageChange: setPage,
            onPageSizeChange: (s) => {
              setPageSize(s)
              setPage(0)
            },
          }}
        />
      )}
    </div>
  )
}
