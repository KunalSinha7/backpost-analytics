import { createFileRoute } from "@tanstack/react-router"
import { Suspense, useState } from "react"

import { EventTable } from "@/components/Events/EventTable"
import { MatchSelector } from "@/components/Matches/MatchSelector"
import PendingTable from "@/components/Pending/PendingTable"

export const Route = createFileRoute("/_layout/soccer/events")({
  component: EventsPage,
  head: () => ({ meta: [{ title: "Events - StatsBomb Analytics" }] }),
})

function EventsPage() {
  const [selectedMatchId, setSelectedMatchId] = useState<string | null>(null)

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Events</h1>
        <p className="text-muted-foreground">
          Match events — passes, shots, and more
        </p>
      </div>
      <MatchSelector onSelect={setSelectedMatchId} />
      {selectedMatchId && (
        <Suspense fallback={<PendingTable />}>
          <EventTable matchId={selectedMatchId} />
        </Suspense>
      )}
    </div>
  )
}
