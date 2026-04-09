import { ConsoleShell } from "@/components/console-shell";
import type { ReactNode } from "react";

export default function ConsoleLayout({ children }: Readonly<{ children: ReactNode }>) {
  return <ConsoleShell>{children}</ConsoleShell>;
}
