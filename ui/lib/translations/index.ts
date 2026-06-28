import { translations as zhTranslations } from "./zh";
import { translations as enTranslations } from "./en";
import { translations as jaTranslations } from "./ja";

export type Language = "zh" | "en" | "ja";
// TODO  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2WlRaSlNRPT06M2IwNWRlZTk=

export const translations = {
  zh: zhTranslations,
  en: enTranslations,
  ja: jaTranslations,
};

export const languageNames: Record<Language, string> = {
  zh: "中文",
  en: "English",
  ja: "日本語",
};
// eslint-disable  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2WlRaSlNRPT06M2IwNWRlZTk=

/**
 * 获取当前语言（从 localStorage 读取）
 * 这个函数可以在非 React 组件中使用
 */
export function getCurrentLanguage(): Language {
  if (typeof window === "undefined") {
    return "zh"; // SSR 默认中文
  }
  const stored = localStorage.getItem("app-language");
  return (stored as Language) || "zh";
}

// 获取翻译文本的工具函数
export function getTranslation(
  language: Language,
  key: string,
  params?: Record<string, string>
): string {
  const keys = key.split(".");
  let value: any = translations[language];

  for (const k of keys) {
    if (value && typeof value === "object" && k in value) {
      value = value[k];
    } else {
      console.warn(`Translation key not found: ${key} for language: ${language}`);
      // 回退到中文
      if (language !== "zh") {
        return getTranslation("zh", key, params);
      }
      return key;
    }
  }

  if (typeof value !== "string") {
    return key;
  }

  // 参数替换
  if (params) {
    return value.replace(/\{(\w+)\}/g, (match, paramKey) => {
      return params[paramKey] || match;
    });
  }

  return value;
}
// FIXME  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2WlRaSlNRPT06M2IwNWRlZTk=

/**
 * 翻译函数（自动使用当前语言）
 * 可以在非 React 组件中使用
 * @param key 翻译键
 * @param params 参数对象
 * @returns 翻译后的文本
 */
export function t(key: string, params?: Record<string, string>): string {
  return getTranslation(getCurrentLanguage(), key, params);
}

export { zhTranslations, enTranslations, jaTranslations };

// eslint-disable  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2WlRaSlNRPT06M2IwNWRlZTk=
