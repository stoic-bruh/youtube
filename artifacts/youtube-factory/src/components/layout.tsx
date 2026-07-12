import * as React from "react"
import { cn } from "@/lib/utils"

export const Layout = ({ children }: { children: React.ReactNode }) => {
  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col md:flex-row">
      {children}
    </div>
  )
}
