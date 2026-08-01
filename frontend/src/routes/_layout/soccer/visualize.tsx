import { createFileRoute } from "@tanstack/react-router"
import { Loader2 } from "lucide-react"
import { Suspense, useMemo, useState } from "react"

import type { EventPublic } from "@/client"
import { EventFilterPanel } from "@/components/Events/EventFilterPanel"
import { MatchSelector } from "@/components/Matches/MatchSelector"
import PendingTable from "@/components/Pending/PendingTable"
import { PitchEventLayer } from "@/components/Pitch/PitchEventLayer"
import { PitchSvg } from "@/components/Pitch/PitchSvg"

function parsePossession(value: unknown): number | undefined {
  const n = typeof value === "string" ? Number(value) : value
  return typeof n === "number" && Number.isFinite(n) ? n : undefined
}

export const Route = createFileRoute("/_layout/soccer/visualize")({
  validateSearch: (search: Record<string, unknown>) => ({
    matchId: typeof search.matchId === "string" ? search.matchId : undefined,
    // Set when arriving from an Events table row click, to jump straight to
    // that event's possession chain instead of the default unfiltered view.
    possession: parsePossession(search.possession),
  }),
  component: VisualizePage,
  head: () => ({ meta: [{ title: "Visualize - The Backpost" }] }),
})

const TEAM_COLORS = ["#2563eb", "#dc2626", "#16a34a", "#d97706"]

function VisualizePage() {
  const { matchId, possession } = Route.useSearch()
  const navigate = Route.useNavigate()
  const [filteredEvents, setFilteredEvents] = useState<EventPublic[]>([])
  const [isLoadingEvents, setIsLoadingEvents] = useState(false)
  const [matchTeams, setMatchTeams] = useState<string[]>([])

  // Keyed off the match's full team roster (both teams, however filters are
  // set) rather than filteredEvents — otherwise isolating one team reshuffles
  // its color, and PitchEventLayer's mirroring (which follows this same
  // team order) would flip that team's attacking side too.
  const colorByTeam = useMemo(() => {
    return Object.fromEntries(
      matchTeams.map((t, i) => [t, TEAM_COLORS[i % TEAM_COLORS.length]]),
    )
  }, [matchTeams])

  // Some events (Starting XI, Half Start, substitutions, etc.) carry no
  // pitch coordinates, so a selection can be non-empty yet have nothing
  // plottable — most visibly the first "possession" of a match, which is
  // often just kickoff/lineup events. Surface that explicitly rather than
  // leaving an unexplained blank pitch.
  const hasPlottableEvents = filteredEvents.some(
    (e) => e.location_x != null && e.location_y != null,
  )

  const handleMatchSelect = (id: string) => {
    navigate({ search: { matchId: id, possession: undefined } })
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Visualize</h1>
        <p className="text-muted-foreground">Plot match events on the pitch</p>
      </div>
      <Suspense fallback={<PendingTable />}>
        <MatchSelector onSelect={handleMatchSelect} defaultMatchId={matchId} />
      </Suspense>
      {matchId && (
        <Suspense fallback={<PendingTable />}>
          <EventFilterPanel
            matchId={matchId}
            initialPossession={possession}
            onFilteredEventsChange={setFilteredEvents}
            onLoadingChange={setIsLoadingEvents}
            onTeamsChange={setMatchTeams}
          />
          {matchTeams.length > 0 && (
            <div className="flex flex-wrap items-center gap-4">
              {matchTeams.map((team) => {
                const color = colorByTeam[team]
                return (
                  <div key={team} className="flex items-center gap-2 text-sm">
                    <span
                      className="size-3 shrink-0 rounded-full"
                      style={{ backgroundColor: color }}
                    />
                    <span>{team}</span>
                  </div>
                )
              })}
            </div>
          )}
          <div className="relative">
            <PitchSvg>
              <PitchEventLayer
                events={filteredEvents}
                colorByTeam={colorByTeam}
              />
            </PitchSvg>
            {isLoadingEvents && (
              <output
                aria-label="Loading events"
                className="absolute inset-0 flex items-center justify-center rounded-lg bg-background/40 backdrop-blur-[1px]"
              >
                <Loader2 className="h-8 w-8 animate-spin text-foreground" />
              </output>
            )}
            {!isLoadingEvents && !hasPlottableEvents && (
              <div className="absolute inset-0 flex items-center justify-center rounded-lg bg-background/40">
                <p className="max-w-xs text-center text-sm text-muted-foreground">
                  {filteredEvents.length === 0
                    ? "No events match the current filters."
                    : "These events have no pitch location to plot (e.g. lineup or kickoff events)."}
                </p>
              </div>
            )}
          </div>
        </Suspense>
      )}
    </div>
  )
}
