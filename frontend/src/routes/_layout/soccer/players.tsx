import { createFileRoute } from "@tanstack/react-router"
import { Suspense } from "react"
import PendingTable from "@/components/Pending/PendingTable"
import { PlayerTable } from "@/components/Players/PlayerTable"

export const Route = createFileRoute("/_layout/soccer/players")({
  component: PlayersPage,
  head: () => ({ meta: [{ title: "Players - The Backpost" }] }),
})

function PlayersPage() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Players</h1>
        <p className="text-muted-foreground">
          Browse players from all competitions
        </p>
      </div>
      <Suspense fallback={<PendingTable />}>
        <PlayerTable />
      </Suspense>
    </div>
  )
}
