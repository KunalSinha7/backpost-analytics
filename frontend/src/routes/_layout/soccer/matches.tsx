import { createFileRoute } from "@tanstack/react-router"
import { Suspense } from "react"

import { MatchTable } from "@/components/Matches/MatchTable"
import PendingTable from "@/components/Pending/PendingTable"

export const Route = createFileRoute("/_layout/soccer/matches")({
  component: MatchesPage,
  head: () => ({ meta: [{ title: "Matches - StatsBomb Analytics" }] }),
})

function MatchesPage() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Matches</h1>
        <p className="text-muted-foreground">Browse matches by competition</p>
      </div>
      <Suspense fallback={<PendingTable />}>
        <MatchTable />
      </Suspense>
    </div>
  )
}
