import { Link as RouterLink, useRouterState } from "@tanstack/react-router"
import {
  Calendar,
  Download,
  Home,
  ListOrdered,
  Trophy,
  Users,
  Zap,
} from "lucide-react"
import { SidebarAppearance } from "@/components/Common/Appearance"
import { Logo } from "@/components/Common/Logo"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar"
import useAuth from "@/hooks/useAuth"
import { User } from "./User"

type NavItem = { icon: React.ElementType; title: string; path: string }

const mainItems: NavItem[] = [{ icon: Home, title: "Dashboard", path: "/" }]

const soccerItems: NavItem[] = [
  { icon: Trophy, title: "Competitions", path: "/soccer" },
  { icon: Calendar, title: "Matches", path: "/soccer/matches" },
  { icon: Zap, title: "Events", path: "/soccer/events" },
  { icon: ListOrdered, title: "Lineups", path: "/soccer/lineups" },
]

const ingestItem: NavItem = {
  icon: Download,
  title: "Ingest",
  path: "/soccer/ingest",
}

function NavGroup({ label, items }: { label?: string; items: NavItem[] }) {
  const { isMobile, setOpenMobile } = useSidebar()
  const currentPath = useRouterState({ select: (s) => s.location.pathname })

  return (
    <SidebarGroup>
      {label && <SidebarGroupLabel>{label}</SidebarGroupLabel>}
      <SidebarGroupContent>
        <SidebarMenu>
          {items.map((item) => (
            <SidebarMenuItem key={item.title}>
              <SidebarMenuButton
                tooltip={item.title}
                isActive={currentPath === item.path}
                asChild
              >
                <RouterLink
                  to={item.path}
                  onClick={() => isMobile && setOpenMobile(false)}
                >
                  <item.icon />
                  <span>{item.title}</span>
                </RouterLink>
              </SidebarMenuButton>
            </SidebarMenuItem>
          ))}
        </SidebarMenu>
      </SidebarGroupContent>
    </SidebarGroup>
  )
}

export function AppSidebar() {
  const { user: currentUser } = useAuth()

  const topItems = currentUser?.is_superuser
    ? [...mainItems, { icon: Users, title: "Admin", path: "/admin" }]
    : mainItems

  const bottomSoccerItems = currentUser?.is_superuser
    ? [...soccerItems, ingestItem]
    : soccerItems

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader className="px-4 py-6 group-data-[collapsible=icon]:px-0 group-data-[collapsible=icon]:items-center">
        <Logo variant="responsive" />
      </SidebarHeader>
      <SidebarContent>
        <NavGroup items={topItems} />
        <NavGroup label="Soccer" items={bottomSoccerItems} />
      </SidebarContent>
      <SidebarFooter>
        <SidebarAppearance />
        <User user={currentUser} />
      </SidebarFooter>
    </Sidebar>
  )
}

export default AppSidebar
