const ENV_KEY = "FN_API_KEY";
const BASE_URL_ENV_KEY = "FN_API_BASE_URL";
const DEFAULT_BASE_URL = "https://m.riskbird.com/prod-qbb-api";

export const BASE_URL = (process.env[BASE_URL_ENV_KEY] || DEFAULT_BASE_URL).trim().replace(/\/$/, "");

export async function getApiKey() {
  const key = (process.env[ENV_KEY] || "").trim();
  if (key && key !== "YOUR_API_KEY") return key;
  return "";
}
