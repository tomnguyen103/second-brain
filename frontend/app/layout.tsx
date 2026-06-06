import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { ThemeProvider } from "@/components/ThemeProvider";
import { Providers } from "@/components/Providers";
import { ConversationHistoryRail, ConversationSidebar } from "@/components/ConversationSidebar";

const geistSans = Geist({
  variable: "--font-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Second Brain",
  description: "A local-first personal AI workspace for cited chat, search, capture, and operations.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="flex h-full overflow-hidden bg-background text-foreground transition-colors duration-200">
        <ThemeProvider>
          <Providers>
            <a
              href="#main-content"
              className="sr-only fixed left-3 top-3 z-[100] rounded-lg bg-background px-3 py-2 text-sm font-semibold text-foreground shadow-lg ring-1 ring-border focus:not-sr-only"
            >
              Skip to content
            </a>
            <ConversationSidebar />
            <main
              id="main-content"
              className="flex h-full min-w-0 flex-1 flex-col overflow-hidden pt-14 md:pt-0"
            >
              {children}
            </main>
            <ConversationHistoryRail />
          </Providers>
        </ThemeProvider>
      </body>
    </html>
  );
}
