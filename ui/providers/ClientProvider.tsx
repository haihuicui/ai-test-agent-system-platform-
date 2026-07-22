"use client";

import { createContext, useContext, useMemo, ReactNode } from "react";
import { Client } from "@langchain/langgraph-sdk";
import { resolveDeploymentUrl } from "@/lib/langgraph/client";

interface ClientContextValue {
  client: Client;
}
// NOTE  MC8yOmFIVnBZMlhsdEpUbXRiZm92b2s2U0dSa1pnPT06NDIxNTM0YzQ=

const ClientContext = createContext<ClientContextValue | null>(null);

interface ClientProviderProps {
  children: ReactNode;
  deploymentUrl: string;
  apiKey: string;
}
// eslint-disable  MS8yOmFIVnBZMlhsdEpUbXRiZm92b2s2U0dSa1pnPT06NDIxNTM0YzQ=

export function ClientProvider({
  children,
  deploymentUrl,
  apiKey,
}: ClientProviderProps) {
  const client = useMemo(() => {
    return new Client({
      apiUrl: resolveDeploymentUrl(deploymentUrl),
      defaultHeaders: {
        "Content-Type": "application/json",
        "X-Api-Key": apiKey,
      },
    });
  }, [deploymentUrl, apiKey]);

  const value = useMemo(() => ({ client }), [client]);

  return (
    <ClientContext.Provider value={value}>{children}</ClientContext.Provider>
  );
}

export function useClient(): Client {
  const context = useContext(ClientContext);

  if (!context) {
    throw new Error("useClient must be used within a ClientProvider");
  }
  return context.client;
}
