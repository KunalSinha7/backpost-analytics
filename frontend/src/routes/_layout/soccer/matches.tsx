import { createFileRoute } from "@tanstack/react-router"
import { Suspense } from "react"
import { MatchTable } from "@/components/Matches/MatchTable"
import PendingTable from "@/components/Pending/PendingTable"

export const Route = createFileRoute("/_layout/soccer/matches")({
  validateSearch: (search: Record<string, unknown>) => ({
    competitionSeasonId:
      typeof search.competitionSeasonId === "string"
        ? search.competitionSeasonId
        : undefined,
  }),
  component: MatchesPage,
  head: () => ({ meta: [{ title: "Matches - The Backpost" }] }),
})

function MatchesPage() {
  const { competitionSeasonId } = Route.useSearch()
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Matches</h1>
        <p className="text-muted-foreground">Browse matches by competition</p>
      </div>
      <Suspense fallback={<PendingTable />}>
        <MatchTable initialCompetitionSeasonId={competitionSeasonId} />
      </Suspense>
    </div>
  )
}
