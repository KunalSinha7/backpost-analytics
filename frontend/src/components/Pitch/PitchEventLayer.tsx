import type { EventPublic } from "@/client"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"

interface PitchEventLayerProps {
  events: EventPublic[]
  colorByTeam: Record<string, string>
}

const FALLBACK_COLOR = "var(--muted-foreground)"

// Must match PitchSvg's viewBox (StatsBomb pitch coordinate system).
const PITCH_LENGTH = 120
const PITCH_WIDTH = 80

function markerIdForTeam(team: string): string {
  return `pitch-arrow-${team.replace(/[^a-zA-Z0-9]/g, "-")}`
}

// StatsBomb locations are absolute pitch coordinates shared by both teams,
// so without this, both teams' shots/passes cluster near whichever goal is
// at the high-x end regardless of which way they're actually attacking.
// Rotating one team's points 180° around the pitch center makes the two
// teams read as attacking opposite ends, matching how shot maps are
// conventionally drawn. This is a fixed per-team flip, not per-half — a
// team's own second-half events (after they've switched ends) aren't
// re-flipped, since that needs tracking which goal each team attacked each
// period, not just team identity.
function mirrorPoint(x: number, y: number): [number, number] {
  return [PITCH_LENGTH - x, PITCH_WIDTH - y]
}

function hasEndLocation(
  event: EventPublic,
): event is EventPublic & { end_location_x: number; end_location_y: number } {
  return event.end_location_x != null && event.end_location_y != null
}

function radiusForType(typeName: string): number {
  switch (typeName) {
    case "Shot":
      return 1.3
    case "Pass":
      return 1.0
    default:
      return 0.7
  }
}

// Carries get a dashed line (ball moving under a player's own control),
// passes/shots get a solid line, so scanning a single player's full event
// history makes it obvious at a glance which arrows are which.
function dashArrayForType(typeName: string): string | undefined {
  return typeName === "Carry" ? "2.4 1.4" : undefined
}

function formatMinute(event: EventPublic): string {
  return `${event.minute}:${String(event.second).padStart(2, "0")}`
}

interface EventMarkerProps {
  event: EventPublic
  color: string
  mirror: boolean
}

function EventMarker({ event, color, mirror }: EventMarkerProps) {
  if (event.location_x == null || event.location_y == null) return null

  const [x, y] = mirror
    ? mirrorPoint(event.location_x, event.location_y)
    : [event.location_x, event.location_y]

  const radius = radiusForType(event.type_name)
  const isShot = event.type_name === "Shot"
  const isPass = event.type_name === "Pass"
  const rawEndLocation = hasEndLocation(event) ? event : null
  const endPoint = rawEndLocation
    ? mirror
      ? mirrorPoint(
          rawEndLocation.end_location_x,
          rawEndLocation.end_location_y,
        )
      : ([
          rawEndLocation.end_location_x,
          rawEndLocation.end_location_y,
        ] as const)
    : null
  const receiverPoint = isPass && event.pass_recipient ? endPoint : null

  return (
    <g>
      {/* Rendered outside the tooltip trigger: Radix positions the tooltip
          relative to the trigger's bounding box, and a long pass/carry
          arrow would otherwise stretch that box far past the origin dot,
          anchoring the tooltip somewhere along the line instead of above
          the marker being hovered. */}
      {endPoint && (
        <line
          x1={x}
          y1={y}
          x2={endPoint[0]}
          y2={endPoint[1]}
          stroke={color}
          strokeWidth={1.4}
          strokeDasharray={dashArrayForType(event.type_name)}
          strokeLinecap="round"
          vectorEffect="non-scaling-stroke"
          markerEnd={`url(#${markerIdForTeam(event.team)})`}
          opacity={0.95}
        />
      )}
      <Tooltip>
        <TooltipTrigger asChild>
          <g
            tabIndex={0}
            aria-label={`${event.type_name} by ${event.player ?? "unknown player"} at ${formatMinute(event)}`}
            className="cursor-pointer outline-none"
          >
            {isShot ? (
              <rect
                x={x - radius}
                y={y - radius}
                width={radius * 2}
                height={radius * 2}
                transform={`rotate(45 ${x} ${y})`}
                fill={color}
                stroke="white"
                strokeWidth={0.2}
                vectorEffect="non-scaling-stroke"
              />
            ) : (
              <circle
                cx={x}
                cy={y}
                r={radius}
                fill={color}
                stroke="white"
                strokeWidth={0.2}
                vectorEffect="non-scaling-stroke"
              />
            )}
          </g>
        </TooltipTrigger>
        <TooltipContent>
          <div className="flex flex-col gap-0.5">
            <span className="font-medium">
              {event.player ?? "Unknown player"}
            </span>
            <span className="text-muted-foreground">
              {event.type_name} · {formatMinute(event)}
            </span>
          </div>
        </TooltipContent>
      </Tooltip>
      {/* Receiver marker: a separate hoverable element (own Tooltip, own
          small hit target) at the pass's end location — a hollow ring
          reads as "landing spot" in contrast to the origin's solid dot. */}
      {receiverPoint && (
        <Tooltip>
          <TooltipTrigger asChild>
            <g
              tabIndex={0}
              aria-label={`Received by ${event.pass_recipient}`}
              className="cursor-pointer outline-none"
            >
              <circle
                cx={receiverPoint[0]}
                cy={receiverPoint[1]}
                r={0.9}
                fill="var(--background)"
                fillOpacity={0.4}
                stroke={color}
                strokeWidth={0.5}
                vectorEffect="non-scaling-stroke"
              />
            </g>
          </TooltipTrigger>
          <TooltipContent>
            <div className="flex flex-col gap-0.5">
              <span className="font-medium">{event.pass_recipient}</span>
              <span className="text-muted-foreground">
                Received pass · {formatMinute(event)}
              </span>
            </div>
          </TooltipContent>
        </Tooltip>
      )}
    </g>
  )
}

/**
 * Presentational overlay for a PitchSvg: renders a marker per event,
 * shaped/sized by event type, with a directional arrow when the event
 * has an end location. Must be rendered as a child of PitchSvg so
 * StatsBomb x/y coordinates line up with the pitch markings.
 *
 * When both teams are present, the second team (alphabetically, matching
 * how colorByTeam is built) is mirrored 180° so the two teams visually
 * attack opposite ends instead of overlapping around the same goal.
 */
export function PitchEventLayer({ events, colorByTeam }: PitchEventLayerProps) {
  const teams = Object.keys(colorByTeam)
  const mirroredTeam = teams.length >= 2 ? teams[1] : null

  return (
    <g>
      <defs>
        {teams.map((team) => (
          <marker
            key={team}
            id={markerIdForTeam(team)}
            viewBox="0 0 10 10"
            refX="8"
            refY="5"
            markerWidth={8}
            markerHeight={8}
            orient="auto-start-reverse"
          >
            <path d="M 0 0 L 10 5 L 0 10 z" fill={colorByTeam[team]} />
          </marker>
        ))}
      </defs>
      {events.map((event) => (
        <EventMarker
          key={event.id}
          event={event}
          color={colorByTeam[event.team] ?? FALLBACK_COLOR}
          mirror={event.team === mirroredTeam}
        />
      ))}
    </g>
  )
}
