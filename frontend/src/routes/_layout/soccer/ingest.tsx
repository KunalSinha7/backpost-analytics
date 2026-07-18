import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { useState } from "react"

import { SoccerService } from "@/client"
import { Badge } from "@/components/ui/badge"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { LoadingButton } from "@/components/ui/loading-button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

export const Route = createFileRoute("/_layout/soccer/ingest")({
  component: IngestPage,
  head: () => ({ meta: [{ title: "Ingest - StatsBomb Analytics" }] }),
})

function IngestPage() {
  const queryClient = useQueryClient()
  const [selectedKey, setSelectedKey] = useState<string>("")
  const [statusMsg, setStatusMsg] = useState<string | null>(null)

  const { data: available = [], isLoading: loadingAvailable } = useQuery({
    queryKey: ["competitions", "available"],
    queryFn: () => SoccerService.getAvailableCompetitions(),
  })

  const selected = available.find(
    (c) => `${c.competition_id}:${c.season_id}` === selectedKey,
  )

  const ingestAll = useMutation({
    mutationFn: () => SoccerService.ingestSoccerData(),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["competitions"] })
      queryClient.invalidateQueries({ queryKey: ["matches"] })
      setStatusMsg(
        `Imported ${data.imported_competitions} competitions and ${data.imported_matches} matches.`,
      )
    },
  })

  const ingestEvents = useMutation({
    mutationFn: () =>
      SoccerService.ingestEvents({
        competitionStatsbombId: selected!.competition_id,
        seasonId: selected!.season_id,
      }),
    onSuccess: () => {
      setStatusMsg(
        `Event ingestion started for ${selected!.competition_name} ${selected!.season_name}.`,
      )
    },
  })

  const groupedByCompetition = available.reduce<
    Record<string, typeof available>
  >((acc, c) => {
    const key = c.competition_name
    acc[key] = acc[key] ?? []
    acc[key].push(c)
    return acc
  }, {})

  return (
    <div className="flex flex-col gap-6 max-w-2xl">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Ingest</h1>
        <p className="text-muted-foreground">
          Import StatsBomb open data into the database
        </p>
      </div>

      {statusMsg && (
        <p className="text-sm text-muted-foreground border rounded-md px-4 py-3">
          {statusMsg}
        </p>
      )}

      {/* Step 1 */}
      <Card>
        <CardHeader>
          <CardTitle>Competitions &amp; Matches</CardTitle>
          <CardDescription>
            Imports the full StatsBomb open data catalog of competitions and
            their matches. Safe to run repeatedly — skips already-ingested rows.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <LoadingButton
            loading={ingestAll.isPending}
            onClick={() => ingestAll.mutate()}
          >
            {ingestAll.isPending ? "Importing…" : "Ingest All"}
          </LoadingButton>
        </CardContent>
      </Card>

      {/* Step 2 */}
      <Card>
        <CardHeader>
          <CardTitle>Events, Lineups &amp; 360 Frames</CardTitle>
          <CardDescription>
            Imports detailed match data for a single competition and season.
            Competitions &amp; Matches must be ingested first.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <Select
            value={selectedKey}
            onValueChange={setSelectedKey}
            disabled={loadingAvailable}
          >
            <SelectTrigger className="w-full">
              <SelectValue
                placeholder={
                  loadingAvailable
                    ? "Loading…"
                    : "Select a competition / season"
                }
              />
            </SelectTrigger>
            <SelectContent>
              {Object.entries(groupedByCompetition)
                .sort(([a], [b]) => a.localeCompare(b))
                .map(([competitionName, seasons]) =>
                  seasons
                    .sort((a, b) => b.season_name.localeCompare(a.season_name))
                    .map((c) => (
                      <SelectItem
                        key={`${c.competition_id}:${c.season_id}`}
                        value={`${c.competition_id}:${c.season_id}`}
                      >
                        <span className="flex items-center gap-2">
                          {competitionName} — {c.season_name}
                          {c.has_360 && (
                            <Badge variant="secondary" className="text-xs">
                              360°
                            </Badge>
                          )}
                        </span>
                      </SelectItem>
                    )),
                )}
            </SelectContent>
          </Select>

          <LoadingButton
            loading={ingestEvents.isPending}
            disabled={!selected || ingestEvents.isPending}
            onClick={() => ingestEvents.mutate()}
          >
            {ingestEvents.isPending ? "Ingesting…" : "Ingest"}
          </LoadingButton>
        </CardContent>
      </Card>
    </div>
  )
}
