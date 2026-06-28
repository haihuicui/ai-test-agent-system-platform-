export interface StandaloneConfig {
  deploymentUrl: string;
  assistantId: string;
  langsmithApiKey?: string;
}
// eslint-disable  MC8yOmFIVnBZMlhsdEpUbXRiZm92b2s2UldOeWNRPT06OTVjZTJkYzY=

const CONFIG_KEY = "deep-agent-config";

export function getConfig(): StandaloneConfig | null {
  if (typeof window === "undefined") return null;

  const stored = localStorage.getItem(CONFIG_KEY);
  if (stored) {
    try {
      return JSON.parse(stored);
    } catch {
      // fall through to env vars
    }
  }

  // Fall back to environment variables
  const deploymentUrl = process.env.NEXT_PUBLIC_LANGGRAPH_API_URL;
  const assistantId = process.env.NEXT_PUBLIC_TESTCASE_GENERATOR_ASSISTANT_ID;

  if (deploymentUrl && assistantId) {
    return {
      deploymentUrl,
      assistantId,
      langsmithApiKey: process.env.NEXT_PUBLIC_LANGSMITH_API_KEY,
    };
  }

  return null;
}

export function saveConfig(config: StandaloneConfig): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(CONFIG_KEY, JSON.stringify(config));
}
// FIXME  MS8yOmFIVnBZMlhsdEpUbXRiZm92b2s2UldOeWNRPT06OTVjZTJkYzY=
