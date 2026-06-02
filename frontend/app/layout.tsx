import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { ThemeProvider } from "@/components/ThemeProvider";
import { Providers } from "@/components/Providers";
import { ConversationSidebar } from "@/components/ConversationSidebar";

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
  description: "Your personal AI knowledge assistant",
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
      <body className="h-full flex bg-background text-foreground transition-colors duration-200">
        <ThemeProvider>
          <Providers>
            <ConversationSidebar />
            <main className="flex-1 flex flex-col overflow-hidden min-w-0">{children}</main>
          </Providers>
        </ThemeProvider>
      </body>
    </html>
  );
}
