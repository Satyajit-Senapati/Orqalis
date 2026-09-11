import { afterEach, describe, expect, it, vi } from "vitest";
import { postRunCommand, readThemePreference } from "./Controls";

afterEach(() => vi.useRealTimers());

describe("run control requests", () => {
  it("preserves structured server error detail", async () => {
    const fetcher = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      void input;
      void init;
      return Promise.resolve(
        new Response(
          JSON.stringify({
            code: "invalid_transition",
            message: "The run cannot be cancelled from this state.",
          }),
          { status: 409, headers: { "Content-Type": "application/json" } },
        ),
      );
    });

    await expect(
      postRunCommand("run-1", "cancel", { fetcher }),
    ).rejects.toThrow(
      "The run cannot be cancelled from this state. · invalid_transition",
    );
  });

  it("sends an idempotent command with an abort signal", async () => {
    const fetcher = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      void input;
      void init;
      return Promise.resolve(new Response(null, { status: 204 }));
    });

    await postRunCommand("run-1", "pause", { fetcher });

    expect(fetcher).toHaveBeenCalledOnce();
    const [url, init] = fetcher.mock.calls[0];
    expect(url).toBe("/api/runs/run-1/pause");
    expect(init?.method).toBe("POST");
    expect(init?.signal).toBeInstanceOf(AbortSignal);
    expect(
      JSON.parse(String(init?.body)) as { idempotency_key: string },
    ).toEqual({ idempotency_key: expect.any(String) });
  });

  it("aborts a command that exceeds the 15 second limit", async () => {
    vi.useFakeTimers();
    const fetcher = vi.fn(
      (input: RequestInfo | URL, init?: RequestInit) =>
        new Promise<Response>((_resolve, reject) => {
          void input;
          const commandSignal = init?.signal as AbortSignal;
          commandSignal.addEventListener(
            "abort",
            () => reject(commandSignal.reason),
            {
              once: true,
            },
          );
        }),
    );

    const command = expect(
      postRunCommand("run-1", "resume", { fetcher }),
    ).rejects.toThrow("Orqalis did not respond within 15 seconds.");
    await vi.advanceTimersByTimeAsync(15_000);

    await command;
  });

  it("reports the configured command timeout", async () => {
    vi.useFakeTimers();
    const fetcher = vi.fn(
      (_input: RequestInfo | URL, init?: RequestInit) =>
        new Promise<Response>((_resolve, reject) => {
          const commandSignal = init?.signal as AbortSignal;
          commandSignal.addEventListener("abort", () => reject(commandSignal.reason), {
            once: true,
          });
        }),
    );

    const command = expect(
      postRunCommand("run-1", "resume", { fetcher, timeoutMs: 1_500 }),
    ).rejects.toThrow("Orqalis did not respond within 1.5 seconds.");
    await vi.advanceTimersByTimeAsync(1_500);

    await command;
  });
});

describe("theme preference", () => {
  it("accepts supported values and falls back from corrupt storage", () => {
    expect(readThemePreference({ getItem: () => "system" })).toBe("system");
    expect(readThemePreference({ getItem: () => "sepia" })).toBe("dark");
    expect(
      readThemePreference({
        getItem: () => {
          throw new Error("storage denied");
        },
      }),
    ).toBe("dark");
  });
});
