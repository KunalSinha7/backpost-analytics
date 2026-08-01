import type { ReactNode } from "react"
import { cn } from "@/lib/utils"

// StatsBomb pitch coordinate system: 120 (length) x 80 (width) yards.
const LENGTH = 120
const WIDTH = 80
const CENTER_X = LENGTH / 2
const CENTER_Y = WIDTH / 2
const CENTER_CIRCLE_RADIUS = 9.15
const CENTER_SPOT_RADIUS = 0.4

const PENALTY_AREA_LENGTH = 18
const PENALTY_AREA_WIDTH = 44
const PENALTY_AREA_Y = (WIDTH - PENALTY_AREA_WIDTH) / 2

const SIX_YARD_LENGTH = 6
const SIX_YARD_WIDTH = 20
const SIX_YARD_Y = (WIDTH - SIX_YARD_WIDTH) / 2

const PENALTY_SPOT_DISTANCE = 12
const PENALTY_SPOT_RADIUS = 0.4

const GOAL_WIDTH = 8
const GOAL_DEPTH = 2
const GOAL_Y = (WIDTH - GOAL_WIDTH) / 2

const CORNER_ARC_RADIUS = 1

interface PitchSvgProps {
  className?: string
  children?: ReactNode
}

/**
 * Renders a StatsBomb-coordinate soccer pitch (viewBox 0 0 120 80).
 * Children are rendered inside the same <svg>, so any child using
 * StatsBomb x/y coordinates lines up 1:1 with the pitch markings.
 */
export function PitchSvg({ className, children }: PitchSvgProps) {
  return (
    <svg
      viewBox={`0 0 ${LENGTH} ${WIDTH}`}
      preserveAspectRatio="xMidYMid meet"
      width="100%"
      role="img"
      aria-label="Soccer pitch"
      className={cn("h-auto w-full", className)}
    >
      <rect
        x={0}
        y={0}
        width={LENGTH}
        height={WIDTH}
        className="fill-emerald-800 dark:fill-emerald-950"
      />

      <g
        fill="none"
        className="stroke-white/60"
        strokeWidth={0.4}
        vectorEffect="non-scaling-stroke"
      >
        {/* Outer boundary */}
        <rect x={0} y={0} width={LENGTH} height={WIDTH} />

        {/* Halfway line */}
        <line x1={CENTER_X} y1={0} x2={CENTER_X} y2={WIDTH} />

        {/* Center circle + spot */}
        <circle cx={CENTER_X} cy={CENTER_Y} r={CENTER_CIRCLE_RADIUS} />
        <circle
          cx={CENTER_X}
          cy={CENTER_Y}
          r={CENTER_SPOT_RADIUS}
          className="fill-white/60"
        />

        {/* Left penalty area */}
        <rect
          x={0}
          y={PENALTY_AREA_Y}
          width={PENALTY_AREA_LENGTH}
          height={PENALTY_AREA_WIDTH}
        />
        {/* Right penalty area */}
        <rect
          x={LENGTH - PENALTY_AREA_LENGTH}
          y={PENALTY_AREA_Y}
          width={PENALTY_AREA_LENGTH}
          height={PENALTY_AREA_WIDTH}
        />

        {/* Left six-yard box */}
        <rect
          x={0}
          y={SIX_YARD_Y}
          width={SIX_YARD_LENGTH}
          height={SIX_YARD_WIDTH}
        />
        {/* Right six-yard box */}
        <rect
          x={LENGTH - SIX_YARD_LENGTH}
          y={SIX_YARD_Y}
          width={SIX_YARD_LENGTH}
          height={SIX_YARD_WIDTH}
        />

        {/* Penalty spots */}
        <circle
          cx={PENALTY_SPOT_DISTANCE}
          cy={CENTER_Y}
          r={PENALTY_SPOT_RADIUS}
          className="fill-white/60"
        />
        <circle
          cx={LENGTH - PENALTY_SPOT_DISTANCE}
          cy={CENTER_Y}
          r={PENALTY_SPOT_RADIUS}
          className="fill-white/60"
        />

        {/* Penalty arcs (the "D") */}
        <path
          d={`M ${PENALTY_AREA_LENGTH} ${CENTER_Y - 7.9} A ${CENTER_CIRCLE_RADIUS} ${CENTER_CIRCLE_RADIUS} 0 0 1 ${PENALTY_AREA_LENGTH} ${CENTER_Y + 7.9}`}
        />
        <path
          d={`M ${LENGTH - PENALTY_AREA_LENGTH} ${CENTER_Y - 7.9} A ${CENTER_CIRCLE_RADIUS} ${CENTER_CIRCLE_RADIUS} 0 0 0 ${LENGTH - PENALTY_AREA_LENGTH} ${CENTER_Y + 7.9}`}
        />

        {/* Goals (drawn just outside the boundary) */}
        <rect
          x={-GOAL_DEPTH}
          y={GOAL_Y}
          width={GOAL_DEPTH}
          height={GOAL_WIDTH}
        />
        <rect x={LENGTH} y={GOAL_Y} width={GOAL_DEPTH} height={GOAL_WIDTH} />

        {/* Corner arcs */}
        <path
          d={`M 0 ${CORNER_ARC_RADIUS} A ${CORNER_ARC_RADIUS} ${CORNER_ARC_RADIUS} 0 0 0 ${CORNER_ARC_RADIUS} 0`}
        />
        <path
          d={`M ${LENGTH - CORNER_ARC_RADIUS} 0 A ${CORNER_ARC_RADIUS} ${CORNER_ARC_RADIUS} 0 0 0 ${LENGTH} ${CORNER_ARC_RADIUS}`}
        />
        <path
          d={`M ${LENGTH} ${WIDTH - CORNER_ARC_RADIUS} A ${CORNER_ARC_RADIUS} ${CORNER_ARC_RADIUS} 0 0 0 ${LENGTH - CORNER_ARC_RADIUS} ${WIDTH}`}
        />
        <path
          d={`M ${CORNER_ARC_RADIUS} ${WIDTH} A ${CORNER_ARC_RADIUS} ${CORNER_ARC_RADIUS} 0 0 0 0 ${WIDTH - CORNER_ARC_RADIUS}`}
        />
      </g>

      {children}
    </svg>
  )
}
