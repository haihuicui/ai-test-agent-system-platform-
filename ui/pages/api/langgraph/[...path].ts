import type { NextApiRequest, NextApiResponse } from "next";
import http from "http";

export const config = {
  api: {
    bodyParser: false,
  },
};

const UPSTREAM = (
  process.env.LANGGRAPH_INTERNAL_URL || "http://127.0.0.1:2026"
).replace(/\/$/, "");

const HOP_BY_HOP_HEADERS = new Set([
  "connection",
  "keep-alive",
  "transfer-encoding",
  "upgrade",
  "expect",
  "host",
  "proxy-connection",
  "te",
  "trailer",
]);

function buildUpstreamUrl(req: NextApiRequest): string {
  const segments = req.query.path;
  const upstreamPath = Array.isArray(segments)
    ? segments.join("/")
    : segments || "";
  const search = req.url?.includes("?") ? `?${req.url.split("?")[1]}` : "";
  return `${UPSTREAM}/${upstreamPath}${search}`;
}

function cleanHeaders(req: NextApiRequest): http.OutgoingHttpHeaders {
  const headers: http.OutgoingHttpHeaders = {};
  for (const [key, value] of Object.entries(req.headers)) {
    if (HOP_BY_HOP_HEADERS.has(key.toLowerCase())) continue;
    if (value !== undefined) headers[key] = value;
  }
  headers.host = new URL(UPSTREAM).host;
  return headers;
}

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
): Promise<void> {
  return new Promise((resolve) => {
    const proxyReq = http.request(
      buildUpstreamUrl(req),
      {
        method: req.method,
        headers: cleanHeaders(req),
      },
      (proxyRes) => {
        const statusCode = proxyRes.statusCode || 200;
        const headers: http.OutgoingHttpHeaders = {};
        for (const [key, value] of Object.entries(proxyRes.headers)) {
          if (HOP_BY_HOP_HEADERS.has(key.toLowerCase())) continue;
          if (value !== undefined) headers[key] = value;
        }
        res.writeHead(statusCode, headers);
        proxyRes.pipe(res);
        proxyRes.on("end", () => resolve());
      }
    );

    proxyReq.on("error", (err) => {
      console.error("[langgraph proxy] request error:", err);
      if (!res.headersSent) {
        res.status(500).json({ error: "proxy error", message: err.message });
      }
      resolve();
    });

    req.pipe(proxyReq);
  });
}
