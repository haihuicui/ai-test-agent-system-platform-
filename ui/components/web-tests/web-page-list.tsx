"use client";
// NOTE  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2U2tVMmRnPT06ZWYwNTc1NjU=

import * as React from "react";
import { Globe, Play, Trash2, Edit } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useLanguage } from "@/providers/LanguageProvider";
import type { WebPage } from "@/lib/api/web-tests";
// TODO  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2U2tVMmRnPT06ZWYwNTc1NjU=

interface WebPageListProps {
  pages: WebPage[];
  selectedPageId: string | null;
  onPageSelect: (pageId: string) => void;
  onPageRun: (pageId: string) => void;
  onPageDelete: (pageId: string) => void;
}
// TODO  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2U2tVMmRnPT06ZWYwNTc1NjU=

export function WebPageList({
  pages,
  selectedPageId,
  onPageSelect,
  onPageRun,
  onPageDelete,
}: WebPageListProps) {
  const { t } = useLanguage();

  return (
    <div className="space-y-2">
      {pages.length === 0 ? (
        <div className="text-center py-8 text-muted-foreground">
          <Globe className="mx-auto h-12 w-12 mb-4 opacity-50" />
          <p className="text-sm">{t("webTests.noPageData")}</p>
        </div>
      ) : (
        pages.map((page) => (
          <div
            key={page.id}
            className={`border rounded-lg p-3 cursor-pointer transition-colors hover:bg-accent ${
              selectedPageId === page.id ? "bg-accent border-primary" : ""
            }`}
            onClick={() => onPageSelect(page.id)}
          >
            <div className="flex items-start justify-between">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <h4 className="font-semibold text-sm truncate">{page.display_name}</h4>
                  <span className="text-xs px-2 py-0.5 bg-secondary rounded">
                    {page.page_type}
                  </span>
                </div>
                <p className="text-xs text-muted-foreground mt-1 truncate">
                  🌐 {page.url}
                </p>
                {page.description && (
                  <p className="text-xs text-muted-foreground mt-1 line-clamp-2">
                    {page.description}
                  </p>
                )}
                <div className="flex gap-3 mt-2 text-xs text-muted-foreground">
                  <span>📋 {page.total_test_cases} {t("webTests.testCases")}</span>
                  <span>▶️ {page.total_test_runs} {t("webTests.testRuns")}</span>
                  {page.last_run_status && (
                    <span className={
                      page.last_run_status === "passed" ? "text-green-600" :
                      page.last_run_status === "failed" ? "text-red-600" :
                      "text-yellow-600"
                    }>
                      {page.last_run_status === "passed" ? "✅" :
                       page.last_run_status === "failed" ? "❌" : "⏳"}
                    </span>
                  )}
                </div>
              </div>
              <div className="flex gap-1 ml-2">
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-8 w-8 p-0"
                  onClick={(e) => {
                    e.stopPropagation();
                    onPageRun(page.id);
                  }}
                  title={t("webTests.executeTest")}
                >
                  <Play className="h-4 w-4" />
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-8 w-8 p-0"
                  onClick={(e) => {
                    e.stopPropagation();
                    onPageDelete(page.id);
                  }}
                  title={t("common.delete")}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </div>
        ))
      )}
    </div>
  );
}
// WATERMARK  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2U2tVMmRnPT06ZWYwNTc1NjU=
