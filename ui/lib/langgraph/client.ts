/**
 * 将 LangGraph deployment URL 规范化为绝对 URL。
 *
 * 本地开发在 .env.local 中把 NEXT_PUBLIC_LANGGRAPH_API_URL 设为 /langgraph，
 * 走 Next.js 同源代理以避免 CORS。但 @langchain/langgraph-sdk 的 Client
 * 内部用 `new URL(`${apiUrl}${path}`)` 构造请求地址，浏览器端要求 apiUrl
 * 必须是绝对 URL，否则抛出 "Failed to construct 'URL': Invalid URL"。
 */
export function resolveDeploymentUrl(deploymentUrl?: string): string {
  const url = deploymentUrl?.trim() || "http://127.0.0.1:2025";

  if (
    url.startsWith("http://") ||
    url.startsWith("https://") ||
    typeof window === "undefined"
  ) {
    return url;
  }

  if (url.startsWith("/")) {
    return `${window.location.origin}${url}`;
  }

  return url;
}
