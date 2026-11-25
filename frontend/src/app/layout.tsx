import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "TaskFlow — Next.js + FastAPI + PostgreSQL + Redis Demo",
  description: "Full-stack Kanban demo showcasing PostgreSQL ACID transactions and Redis caching, locking, and rate limiting.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}
