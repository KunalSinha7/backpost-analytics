import { Checkbox } from "@/components/ui/checkbox"

interface EventsOnlyFilterProps {
  checked: boolean
  onCheckedChange: (checked: boolean) => void
  // Distinct ids matter when two of these ever share a page: the <label>
  // targets one by id, and duplicates would send every click to the first.
  id?: string
}

/**
 * "Events only" toggle, paired with the `EventDataBadge` — the badge marks
 * which rows have ingested event data, this narrows the table to them.
 *
 * Callers own the filtering, because the two tables filter at different
 * layers: competitions are fetched whole and filtered in the client, while
 * matches are paginated server-side and must pass `hasEvents` to the query
 * so the row count stays truthful.
 */
export function EventsOnlyFilter({
  checked,
  onCheckedChange,
  id = "events-only",
}: EventsOnlyFilterProps) {
  return (
    <div className="flex items-center gap-2">
      <Checkbox
        id={id}
        checked={checked}
        onCheckedChange={(v) => onCheckedChange(v === true)}
      />
      <label
        htmlFor={id}
        className="text-sm text-muted-foreground cursor-pointer select-none"
      >
        Events only
      </label>
    </div>
  )
}
