// eslint-disable  MC8yOmFIVnBZMlhsdEpUbXRiZm92b2s2TWtzemJ3PT06ZDNkOGVhMWI=

import { useAppState } from './useAppState';

export const useSettings = () => {
  const { llmSettings, updateLLMSettings } = useAppState();

  return {
    settings: llmSettings,
    updateSettings: updateLLMSettings,
  };
};
// NOTE  MS8yOmFIVnBZMlhsdEpUbXRiZm92b2s2TWtzemJ3PT06ZDNkOGVhMWI=
