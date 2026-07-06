import { createFileRoute, Outlet } from "@tanstack/react-router"

export const Route = createFileRoute("/_layout/soccer")({
  component: SoccerLayout,
})

function SoccerLayout() {
  return <Outlet />
}
