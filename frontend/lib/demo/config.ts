export const STATIC_DEMO_MODE =
  process.env.NEXT_PUBLIC_SECOND_BRAIN_DEMO_MODE === "static";

export const DEMO_ACCESS_HASH =
  process.env.NEXT_PUBLIC_DEMO_ACCESS_HASH?.trim().toLowerCase() ?? "";

export const DEMO_ACCESS_STORAGE_KEY = "second-brain.static-demo-access";

export const DEMO_ACCESS_ENABLED = STATIC_DEMO_MODE && DEMO_ACCESS_HASH.length > 0;
