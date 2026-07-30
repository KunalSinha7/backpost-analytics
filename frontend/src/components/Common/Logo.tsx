import { Link } from "@tanstack/react-router"

import { useTheme } from "@/components/theme-provider"
import { cn } from "@/lib/utils"
import logo from "/assets/images/backpost-logo.svg"

interface LogoProps {
  variant?: "full" | "icon" | "responsive"
  className?: string
  asLink?: boolean
}

export function Logo({
  variant = "full",
  className,
  asLink = true,
}: LogoProps) {
  const { resolvedTheme } = useTheme()
  const isDark = resolvedTheme === "dark"

  const content =
    variant === "responsive" ? (
      <>
        <img
          src={logo}
          alt="The Backpost"
          className={cn(
            "h-[74px] w-auto group-data-[collapsible=icon]:hidden",
            isDark && "invert",
            className,
          )}
        />
        <img
          src={logo}
          alt="The Backpost"
          className={cn(
            "h-6 w-auto hidden group-data-[collapsible=icon]:block",
            isDark && "invert",
            className,
          )}
        />
      </>
    ) : (
      <img
        src={logo}
        alt="The Backpost"
        className={cn(
          variant === "full" ? "h-8 w-auto" : "h-6 w-auto",
          isDark && "invert",
          className,
        )}
      />
    )

  if (!asLink) {
    return content
  }

  return <Link to="/">{content}</Link>
}
