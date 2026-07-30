import { createFileRoute } from "@tanstack/react-router"
import { Suspense } from "react"

import { EventTable } from "@/components/Events/EventTable"
import { MatchSelector } from "@/components/Matches/MatchSelector"
import PendingTable from "@/components/Pending/PendingTable"

export const Route = createFileRoute("/_layout/soccer/events")({
  validateSearch: (search: Record<string, unknown>) => ({
    matchId: typeof search.matchId === "string" ? search.matchId : undefined,
  }),
  component: EventsPage,
  head: () => ({ meta: [{ title: "Events - The Backpost" }] }),
})

function EventsPage() {
  const { matchId } = Route.useSearch()
  const navigate = Route.useNavigate()

  const handleMatchSelect = (id: string) => {
    navigate({ search: { matchId: id } })
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Events</h1>
        <p className="text-muted-foreground">
          Match events — passes, shots, and more
        </p>
      </div>
      <Suspense fallback={<PendingTable />}>
        <MatchSelector onSelect={handleMatchSelect} defaultMatchId={matchId} />
      </Suspense>
      {matchId && (
        <Suspense fallback={<PendingTable />}>
          <EventTable matchId={matchId} />
        </Suspense>
      )}
    </div>
  )
}
