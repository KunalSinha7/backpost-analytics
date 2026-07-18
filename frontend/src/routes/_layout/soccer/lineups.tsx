import { createFileRoute } from "@tanstack/react-router"
import { Suspense, useState } from "react"

import { LineupTable } from "@/components/Lineups/LineupTable"
import { MatchSelector } from "@/components/Matches/MatchSelector"
import PendingTable from "@/components/Pending/PendingTable"

export const Route = createFileRoute("/_layout/soccer/lineups")({
  component: LineupsPage,
  head: () => ({ meta: [{ title: "Lineups - StatsBomb Analytics" }] }),
})

function LineupsPage() {
  const [selectedMatchId, setSelectedMatchId] = useState<string | null>(null)

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Lineups</h1>
        <p className="text-muted-foreground">
          Starting lineups and squad details per match
        </p>
      </div>
      <MatchSelector onSelect={setSelectedMatchId} />
      {selectedMatchId && (
        <Suspense fallback={<PendingTable />}>
          <LineupTable matchId={selectedMatchId} />
        </Suspense>
      )}
    </div>
  )
}
