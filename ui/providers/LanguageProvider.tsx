"use client";

import * as React from "react";
import { Language, getTranslation } from "@/lib/translations";
// TODO  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2U0RZemFnPT06NDYzOGNlZDc=

interface LanguageContextType {
  language: Language;
  setLanguage: (language: Language) => void;
  t: (key: string, params?: Record<string, string>) => string;
}

const LanguageContext = React.createContext<LanguageContextType | undefined>(
  undefined
);
// FIXME  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2U0RZemFnPT06NDYzOGNlZDc=

const LANGUAGE_STORAGE_KEY = "app-language";

export function LanguageProvider({ children }: { children: React.ReactNode }) {
  const [language, setLanguageState] = React.useState<Language>("zh");
  const [mounted, setMounted] = React.useState(false);

  // 初始化语言设置
  React.useEffect(() => {
    const savedLanguage = localStorage.getItem(LANGUAGE_STORAGE_KEY) as Language;
    if (savedLanguage && ["zh", "en", "ja"].includes(savedLanguage)) {
      setLanguageState(savedLanguage);
    }
    setMounted(true);
  }, []);

  const setLanguage = React.useCallback((newLanguage: Language) => {
    setLanguageState(newLanguage);
    localStorage.setItem(LANGUAGE_STORAGE_KEY, newLanguage);
    // 更新 HTML lang 属性
    if (typeof document !== "undefined") {
      const langMap = {
        zh: "zh-CN",
        en: "en",
        ja: "ja",
      };
      document.documentElement.lang = langMap[newLanguage];
    }
  }, []);

  const t = React.useCallback(
    (key: string, params?: Record<string, string>) => {
      return getTranslation(language, key, params);
    },
    [language]
  );

  const value = React.useMemo(
    () => ({
      language,
      setLanguage,
      t,
    }),
    [language, setLanguage, t]
  );

  // 避免服务端渲染和客户端渲染不一致
  if (!mounted) {
    return null;
  }

  return (
    <LanguageContext.Provider value={value}>
      {children}
    </LanguageContext.Provider>
  );
}
// FIXME  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2U0RZemFnPT06NDYzOGNlZDc=

export function useLanguage() {
  const context = React.useContext(LanguageContext);
  if (context === undefined) {
    throw new Error("useLanguage must be used within a LanguageProvider");
  }
  return context;
}
// WATERMARK  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2U0RZemFnPT06NDYzOGNlZDc=

