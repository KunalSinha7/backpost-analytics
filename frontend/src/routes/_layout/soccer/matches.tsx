import { createFileRoute } from "@tanstack/react-router"
import { Suspense } from "react"
import { z } from "zod"

import { MatchTable } from "@/components/Matches/MatchTable"
import PendingTable from "@/components/Pending/PendingTable"

const matchesSearchSchema = z.object({
  competitionId: z.string().optional(),
})

export const Route = createFileRoute("/_layout/soccer/matches")({
  validateSearch: matchesSearchSchema,
  component: MatchesPage,
  head: () => ({ meta: [{ title: "Matches - StatsBomb Analytics" }] }),
})

function MatchesPage() {
  const { competitionId } = Route.useSearch()
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Matches</h1>
        <p className="text-muted-foreground">Browse matches by competition</p>
      </div>
      <Suspense fallback={<PendingTable />}>
        <MatchTable initialCompetitionId={competitionId} />
      </Suspense>
    </div>
  )
}
