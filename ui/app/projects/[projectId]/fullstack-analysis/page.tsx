"use client";

import { useEffect, useState } from "react";
import { MainLayout } from "@/components/layout/main-layout";
import { useLanguage } from "@/providers/LanguageProvider";

export default function FullstackAnalysisPage() {
  const { t } = useLanguage();
  const [iframeSrc, setIframeSrc] = useState("/gitnexus-web/index.html");

  useEffect(() => {
    // GitNexus SPA 需要通过 ?server= 参数知道后端地址；
    // nginx 已将 /gitnexus-api/ 反向代理到 gitnexus:4747
    const server = `${window.location.origin}/gitnexus-api`;
    setIframeSrc(`/gitnexus-web/index.html?server=${encodeURIComponent(server)}`);
  }, []);

  return (
    <MainLayout title={t("nav.fullstackAnalysis")}>
      <div className="-m-6 h-full">
        <iframe
          src={iframeSrc}
          className="h-full w-full border-0"
          title={t("nav.fullstackAnalysis")}
          allow="fullscreen"
        />
      </div>
    </MainLayout>
  );
}
