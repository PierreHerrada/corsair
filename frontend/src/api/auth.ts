const BASE = "/api/v1";

interface LoginResponse {
  access_token: string;
  token_type: string;
}

export async function login(password: string): Promise<LoginResponse> {
  const resp = await fetch(`${BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ password }),
  });
  if (!resp.ok) {
    const data = await resp.json().catch(() => ({}));
    throw new Error(data.detail || "Login failed");
  }
  return resp.json();
}
