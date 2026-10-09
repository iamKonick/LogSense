let apiKey = sessionStorage.getItem("logsense-key") || "";
export async function api(path, options = {}) {
  const headers = {
    ...options.headers,
    "X-API-Key": apiKey,
    ...(options.body instanceof FormData
      ? {}
      : { "Content-Type": "application/json" }),
  };
  const response = await fetch("/api" + path, { ...options, headers });
  const data = await response
    .json()
    .catch(() => ({ detail: "Unable to read server response" }));
  if (!response.ok) {
    if (response.status === 401)
      window.dispatchEvent(new Event("logsense-auth"));
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : "Please check the supplied fields",
    );
  }
  return data;
}

export function getApiKey() {
  return apiKey;
}
export function setApiKey(value) {
  apiKey = value;
  sessionStorage.setItem("logsense-key", value);
}
