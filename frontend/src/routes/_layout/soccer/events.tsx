import { createFileRoute } from "@tanstack/react-router"
import { Suspense } from "react"

import { EventTable } from "@/components/Events/EventTable"
import { MatchHierarchyFilter } from "@/components/Matches/MatchHierarchyFilter"
import PendingTable from "@/components/Pending/PendingTable"

export const Route = createFileRoute("/_layout/soccer/events")({
  validateSearch: (search: Record<string, unknown>) => ({
    competitionId:
      typeof search.competitionId === "string"
        ? search.competitionId
        : undefined,
    teamName: typeof search.teamName === "string" ? search.teamName : undefined,
    matchId: typeof search.matchId === "string" ? search.matchId : undefined,
  }),
  component: EventsPage,
  head: () => ({ meta: [{ title: "Events - The Backpost" }] }),
})

function EventsPage() {
  const { competitionId, teamName, matchId } = Route.useSearch()
  const navigate = Route.useNavigate()

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Events</h1>
        <p className="text-muted-foreground">
          Match events — passes, shots, and more
        </p>
      </div>
      <MatchHierarchyFilter
        competitionId={competitionId}
        teamName={teamName}
        matchId={matchId}
        onChange={(next) => navigate({ search: next })}
      />
      {matchId && (
        <Suspense fallback={<PendingTable />}>
          <EventTable matchId={matchId} />
        </Suspense>
      )}
    </div>
  )
}
