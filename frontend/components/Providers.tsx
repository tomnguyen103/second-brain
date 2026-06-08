"use client";

import { QueryClientProvider } from "@tanstack/react-query";
import { DemoAccessGate } from "@/components/DemoAccessGate";
import { queryClient } from "@/lib/query-client";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>
      <DemoAccessGate>{children}</DemoAccessGate>
    </QueryClientProvider>
  );
}
