import { createFileRoute } from "@tanstack/react-router"
import { Suspense } from "react"

import { LineupTable } from "@/components/Lineups/LineupTable"
import { MatchSelector } from "@/components/Matches/MatchSelector"
import PendingTable from "@/components/Pending/PendingTable"

export const Route = createFileRoute("/_layout/soccer/lineups")({
  validateSearch: (search: Record<string, unknown>) => ({
    matchId: typeof search.matchId === "string" ? search.matchId : undefined,
  }),
  component: LineupsPage,
  head: () => ({ meta: [{ title: "Lineups - The Backpost" }] }),
})

function LineupsPage() {
  const { matchId } = Route.useSearch()
  const navigate = Route.useNavigate()

  const handleMatchSelect = (id: string) => {
    navigate({ search: { matchId: id } })
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Lineups</h1>
        <p className="text-muted-foreground">
          Starting lineups and squad details per match
        </p>
      </div>
      <Suspense fallback={<PendingTable />}>
        <MatchSelector onSelect={handleMatchSelect} defaultMatchId={matchId} />
      </Suspense>
      {matchId && (
        <Suspense fallback={<PendingTable />}>
          <LineupTable matchId={matchId} />
        </Suspense>
      )}
    </div>
  )
}
