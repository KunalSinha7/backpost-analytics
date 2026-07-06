import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Suspense } from "react"

import { SoccerService } from "@/client"
import { CompetitionTable } from "@/components/Competitions/CompetitionTable"
import PendingTable from "@/components/Pending/PendingTable"

export const Route = createFileRoute("/_layout/soccer/")({
  component: CompetitionsPage,
  head: () => ({ meta: [{ title: "Competitions - StatsBomb Analytics" }] }),
})

function CompetitionsContent() {
  useSuspenseQuery({
    queryKey: ["competitions"],
    queryFn: () => SoccerService.readCompetitions({ skip: 0, limit: 100 }),
  })
  return <CompetitionTable />
}

function CompetitionsPage() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Competitions</h1>
        <p className="text-muted-foreground">
          StatsBomb open data competitions
        </p>
      </div>
      <Suspense fallback={<PendingTable />}>
        <CompetitionsContent />
      </Suspense>
    </div>
  )
}
