import { Badge } from "@/components/ui/badge"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"

interface EventDataBadgeProps {
  hasEvents: boolean
  // Optional match coverage, shown on hover. Events are ingested per
  // competition/season in batches, so a partially-ingested edition would
  // otherwise look identical to a fully-ingested one.
  coverage?: { withEvents: number; total: number }
}

/**
 * Marks a row whose events have been ingested into *our* database.
 *
 * Deliberately distinct from the `360°` badge on the ingest page: that one
 * reads StatsBomb's upstream catalog and says what is *available to download*,
 * whereas this says what has actually been loaded and is queryable now.
 */
export function EventDataBadge({ hasEvents, coverage }: EventDataBadgeProps) {
  if (!hasEvents) return null

  const badge = (
    <Badge variant="secondary" className="text-xs">
      Events
    </Badge>
  )

  if (!coverage) return badge

  return (
    <Tooltip>
      {/* asChild would hand the ref to Badge, which is a plain span without
          forwardRef; the wrapper span keeps Radix's trigger ref valid. */}
      <TooltipTrigger asChild>
        <span className="inline-flex">{badge}</span>
      </TooltipTrigger>
      <TooltipContent>
        Event data — {coverage.withEvents} of {coverage.total} matches
      </TooltipContent>
    </Tooltip>
  )
}
