import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "FinDummy — AI Trading Agent",
  description: "Autonomous AI trading agent dashboard",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="antialiased">{children}</body>
    </html>
  );
}
