"use client";
// NOTE  MC8yOmFIVnBZMlhsdEpUbXRiZm92b2s2V1ZkRGRRPT06NThjNWEwMGE=

import { MainLayout } from "@/components/layout/main-layout";
import { useLanguage } from "@/providers/LanguageProvider";
// WATERMARK  MS8yOmFIVnBZMlhsdEpUbXRiZm92b2s2V1ZkRGRRPT06NThjNWEwMGE=

export default function FullstackAnalysisPage() {
  const { t } = useLanguage();

  return (
    <MainLayout title={t("nav.fullstackAnalysis")}>
      <div className="-m-6 h-full">
        <iframe
          src="/gitnexus-web/index.html"
          className="h-full w-full border-0"
          title={t("nav.fullstackAnalysis")}
          allow="fullscreen"
        />
      </div>
    </MainLayout>
  );
}
