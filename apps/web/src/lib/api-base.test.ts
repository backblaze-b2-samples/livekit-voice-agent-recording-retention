import { afterEach, describe, expect, it, vi } from "vitest";

// API_BASE is resolved once at module load from the environment, so each case
// re-imports the module under a fresh env.
describe("API_BASE resolution", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.resetModules();
  });

  it("uses an explicit NEXT_PUBLIC_API_URL when set", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.example.com");
    const { API_BASE } = await import("./api-client");
    expect(API_BASE).toBe("https://api.example.com");
  });

  it("defaults to the Compose api container's published port", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "");
    vi.stubEnv("NODE_ENV", "production");
    const { API_BASE } = await import("./api-client");
    expect(API_BASE).toBe("http://localhost:8000");
  });
});
