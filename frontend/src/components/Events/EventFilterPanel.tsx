import {
  keepPreviousData,
  useQuery,
  useSuspenseQuery,
} from "@tanstack/react-query"
import { X } from "lucide-react"
import { useEffect, useMemo, useState } from "react"
import type { EventPublic } from "@/client"
import { SoccerService } from "@/client"
import { Badge } from "@/components/ui/badge"
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Slider } from "@/components/ui/slider"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"

type SequenceMode = "off" | "index" | "possession"

function FilterPill({
  label,
  onRemove,
}: {
  label: string
  onRemove: () => void
}) {
  return (
    <Badge variant="secondary" className="gap-1 py-1 pl-2.5 pr-1">
      {label}
      <button
        type="button"
        onClick={onRemove}
        aria-label={`Remove ${label} filter`}
        className="rounded-full p-0.5 hover:bg-foreground/10"
      >
        <X className="size-3" />
      </button>
    </Badge>
  )
}

interface EventFilterPanelProps {
  matchId: string
  // Set on initial mount only (e.g. arriving from an Events table row click)
  // to open straight into that event's possession chain.
  initialPossession?: number
  onFilteredEventsChange: (events: EventPublic[]) => void
  onLoadingChange?: (isLoading: boolean) => void
  onTeamsChange?: (teams: string[]) => void
}

export function EventFilterPanel({
  matchId,
  initialPossession,
  onFilteredEventsChange,
  onLoadingChange,
  onTeamsChange,
}: EventFilterPanelProps) {
  const [selectedTypes, setSelectedTypes] = useState<Set<string>>(new Set())
  const [teamFilter, setTeamFilter] = useState("all")
  const [playerFilter, setPlayerFilter] = useState("all")
  const [sequenceMode, setSequenceMode] = useState<SequenceMode>(
    initialPossession != null ? "possession" : "off",
  )
  const [indexRange, setIndexRange] = useState<[number, number] | null>(null)
  const [possessionFilter, setPossessionFilter] = useState(
    initialPossession != null ? String(initialPossession) : "all",
  )

  const { data: allEvents } = useSuspenseQuery({
    queryKey: ["events", matchId, "all"],
    queryFn: () => SoccerService.readEvents({ matchId, skip: 0, limit: 10000 }),
  })

  const types = useMemo(
    () => [...new Set(allEvents.data.map((e) => e.type_name))].sort(),
    [allEvents.data],
  )
  const teams = useMemo(
    () => [...new Set(allEvents.data.map((e) => e.team))].sort(),
    [allEvents.data],
  )

  // Reported up so team colors/mirroring can be keyed off the match's full
  // roster instead of whichever teams survive the current filter — without
  // this, isolating one team (or filtering to a subset with no events for
  // the other) reshuffles that team's color and mirrored attacking side.
  useEffect(() => {
    onTeamsChange?.(teams)
  }, [teams, onTeamsChange])
  const players = useMemo(
    () =>
      [
        ...new Set(
          allEvents.data
            .map((e) => e.player)
            .filter((p): p is string => p != null),
        ),
      ].sort(),
    [allEvents.data],
  )
  const possessions = useMemo(() => {
    const map = new Map<number, string>()
    for (const e of allEvents.data) {
      if (e.possession != null && !map.has(e.possession)) {
        map.set(e.possession, e.possession_team_name ?? "Unknown")
      }
    }
    return [...map.entries()].sort((a, b) => a[0] - b[0])
  }, [allEvents.data])

  const [minIndex, maxIndex] = useMemo(() => {
    if (allEvents.data.length === 0) return [0, 0]
    const indices = allEvents.data.map((e) => e.index)
    return [Math.min(...indices), Math.max(...indices)]
  }, [allEvents.data])

  useEffect(() => {
    setIndexRange([minIndex, maxIndex])
  }, [minIndex, maxIndex])

  const [rangeStart, rangeEnd] = indexRange ?? [minIndex, maxIndex]

  const { data: displayEvents, isFetching: isFetchingDisplayEvents } = useQuery(
    {
      queryKey: [
        "events",
        matchId,
        "display",
        sequenceMode,
        teamFilter,
        playerFilter,
        possessionFilter,
        rangeStart,
        rangeEnd,
      ],
      queryFn: () =>
        sequenceMode === "index"
          ? SoccerService.readEvents({
              matchId,
              skip: rangeStart - 1,
              limit: rangeEnd - rangeStart + 1,
            })
          : SoccerService.readEvents({
              matchId,
              skip: 0,
              limit: 10000,
              team: teamFilter === "all" ? undefined : teamFilter,
              player: playerFilter === "all" ? undefined : playerFilter,
              possession:
                sequenceMode === "possession" && possessionFilter !== "all"
                  ? Number(possessionFilter)
                  : undefined,
            }),
      enabled: sequenceMode !== "index" || rangeEnd >= rangeStart,
      // Keep showing the previous filter's markers while the new query is
      // in flight instead of resetting to an empty pitch on every filter
      // change (react-query clears `data` on queryKey change by default).
      placeholderData: keepPreviousData,
    },
  )

  const filteredEvents = useMemo(() => {
    const base = displayEvents?.data ?? []

    return base.filter((e) => {
      if (selectedTypes.size > 0 && !selectedTypes.has(e.type_name))
        return false
      // team/player aren't sent to the backend in index-range mode
      // (skip/limit there is an absolute offset into match order, which
      // combining with other WHERE filters would invalidate), so apply
      // them client-side for that mode only.
      if (sequenceMode === "index") {
        if (teamFilter !== "all" && e.team !== teamFilter) return false
        if (playerFilter !== "all" && e.player !== playerFilter) return false
      }
      return true
    })
  }, [displayEvents, selectedTypes, sequenceMode, teamFilter, playerFilter])

  useEffect(() => {
    onFilteredEventsChange(filteredEvents)
  }, [filteredEvents, onFilteredEventsChange])

  useEffect(() => {
    onLoadingChange?.(isFetchingDisplayEvents)
  }, [isFetchingDisplayEvents, onLoadingChange])

  const toggleType = (type: string) => {
    setSelectedTypes((prev) => {
      const next = new Set(prev)
      if (next.has(type)) {
        next.delete(type)
      } else {
        next.add(type)
      }
      return next
    })
  }

  const hasActiveFilters =
    selectedTypes.size > 0 ||
    teamFilter !== "all" ||
    playerFilter !== "all" ||
    sequenceMode !== "off"

  const clearSequence = () => {
    setSequenceMode("off")
    setPossessionFilter("all")
    setIndexRange([minIndex, maxIndex])
  }

  const clearFilters = () => {
    setSelectedTypes(new Set())
    setTeamFilter("all")
    setPlayerFilter("all")
    clearSequence()
  }

  const sequencePillLabel =
    sequenceMode === "index"
      ? `Index ${rangeStart}–${rangeEnd}`
      : sequenceMode === "possession"
        ? possessionFilter === "all"
          ? "Possession chain"
          : `Possession #${possessionFilter} — ${
              possessions.find(
                ([id]) => String(id) === possessionFilter,
              )?.[1] ?? "Unknown"
            }`
        : null

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap gap-3 items-center">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button
              type="button"
              className="flex h-8 w-44 items-center justify-between rounded-md border bg-transparent px-3 text-sm shadow-xs"
            >
              <span className="truncate">
                {selectedTypes.size === 0
                  ? "All types"
                  : `${selectedTypes.size} type${selectedTypes.size > 1 ? "s" : ""}`}
              </span>
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent className="max-h-72 overflow-y-auto">
            {types.map((t) => (
              <DropdownMenuCheckboxItem
                key={t}
                checked={selectedTypes.has(t)}
                onCheckedChange={() => toggleType(t)}
                onSelect={(e) => e.preventDefault()}
              >
                {t}
              </DropdownMenuCheckboxItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>

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

        <Select value={playerFilter} onValueChange={setPlayerFilter}>
          <SelectTrigger className="w-44 h-8 text-sm">
            <SelectValue placeholder="Player" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All players</SelectItem>
            {players.map((p) => (
              <SelectItem key={p} value={p}>
                {p}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        {hasActiveFilters && (
          <button
            type="button"
            onClick={clearFilters}
            className="text-xs text-muted-foreground hover:text-foreground underline"
          >
            Clear filters
          </button>
        )}
      </div>

      {hasActiveFilters && (
        <div className="flex flex-wrap items-center gap-1.5">
          {[...selectedTypes].map((type) => (
            <FilterPill
              key={type}
              label={type}
              onRemove={() => toggleType(type)}
            />
          ))}
          {teamFilter !== "all" && (
            <FilterPill
              label={teamFilter}
              onRemove={() => setTeamFilter("all")}
            />
          )}
          {playerFilter !== "all" && (
            <FilterPill
              label={playerFilter}
              onRemove={() => setPlayerFilter("all")}
            />
          )}
          {sequencePillLabel && (
            <FilterPill label={sequencePillLabel} onRemove={clearSequence} />
          )}
        </div>
      )}

      <div className="flex flex-col gap-3">
        <Tabs
          value={sequenceMode}
          onValueChange={(v) => setSequenceMode(v as SequenceMode)}
        >
          <TabsList>
            <TabsTrigger value="off">No sequence</TabsTrigger>
            <TabsTrigger value="index">Index range</TabsTrigger>
            <TabsTrigger value="possession">Possession chain</TabsTrigger>
          </TabsList>
        </Tabs>

        {sequenceMode === "index" && (
          <div className="flex items-center gap-3 max-w-md">
            <span className="font-mono text-xs text-muted-foreground w-8">
              {rangeStart}
            </span>
            <Slider
              min={minIndex}
              max={maxIndex}
              step={1}
              value={[rangeStart, rangeEnd]}
              onValueChange={(v) => setIndexRange([v[0], v[1]])}
              className="flex-1"
            />
            <span className="font-mono text-xs text-muted-foreground w-8">
              {rangeEnd}
            </span>
          </div>
        )}

        {sequenceMode === "possession" && (
          <Select value={possessionFilter} onValueChange={setPossessionFilter}>
            <SelectTrigger className="w-64 h-8 text-sm">
              <SelectValue placeholder="Possession" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All possessions</SelectItem>
              {possessions.map(([possession, teamName]) => (
                <SelectItem key={possession} value={String(possession)}>
                  #{possession} — {teamName}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
      </div>
    </div>
  )
}
