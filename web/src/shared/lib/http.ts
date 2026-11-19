const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

export const http = {
  post: async <T>(path: string, body: unknown): Promise<T> => {
    const res = await fetch(`${BASE_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ error: res.statusText })) as { error: string };
      throw new Error(err.error ?? res.statusText);
    }
    return res.json() as Promise<T>;
  },

  stream: async (path: string, body: unknown): Promise<Response> => {
    const res = await fetch(`${BASE_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    return res;
  },
};
