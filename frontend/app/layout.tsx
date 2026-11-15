import type { Metadata } from "next";
import "@fontsource-variable/ibm-plex-sans/wght.css";
import "@fontsource/ibm-plex-mono/latin-400.css";
import "./globals.css";
import { Shell } from "./components";
export const metadata: Metadata = {
  title: "Dispatch — Engineering, orchestrated",
  description:
    "Run engineering workflows with adaptive agents and deterministic verification gates.",
};
export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Shell>{children}</Shell>
      </body>
    </html>
  );
}
