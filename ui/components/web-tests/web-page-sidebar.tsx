"use client";
// NOTE  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2UVdsaVJnPT06NzJlZjMxNGU=

import * as React from "react";
import { Globe, Calendar, ExternalLink } from "lucide-react";
import { useLanguage } from "@/providers/LanguageProvider";
import { Button } from "@/components/ui/button";
import type { WebPage } from "@/lib/api/web-tests";
// eslint-disable  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2UVdsaVJnPT06NzJlZjMxNGU=

interface WebPageSidebarProps {
  page: WebPage | null;
  onClose: () => void;
}
// eslint-disable  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2UVdsaVJnPT06NzJlZjMxNGU=

export function WebPageSidebar({ page, onClose }: WebPageSidebarProps) {
  const { t } = useLanguage();

  if (!page) {
    return (
      <div className="h-full flex items-center justify-center text-muted-foreground">
        <div className="text-center">
          <Globe className="mx-auto h-12 w-12 mb-4 opacity-50" />
          <p className="text-sm">{t("webTests.selectFolderOrImport")}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="border-b p-4">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold text-lg">{t("webTests.webPages")}</h3>
          <Button variant="ghost" size="sm" onClick={onClose}>
            ✕
          </Button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-6">
        {/* Basic Info */}
        <div>
          <h4 className="text-sm font-medium mb-3 flex items-center gap-2">
            <Globe className="h-4 w-4" />
            {t("webTests.pageName")}
          </h4>
          <div className="space-y-2 text-sm">
            <div>
              <label className="text-muted-foreground">{t("common.name")}</label>
              <p className="font-medium">{page.display_name}</p>
            </div>
            <div>
              <label className="text-muted-foreground">{t("webTests.pageUrl")}</label>
              <p className="font-mono text-xs break-all">{page.url}</p>
            </div>
            {page.page_title && (
              <div>
                <label className="text-muted-foreground">{t("webTests.pageTitle")}</label>
                <p>{page.page_title}</p>
              </div>
            )}
            <div>
              <label className="text-muted-foreground">{t("webTests.pageType")}</label>
              <p>
                <span className="px-2 py-1 bg-secondary rounded text-xs">
                  {page.page_type}
                </span>
              </p>
            </div>
            {page.description && (
              <div>
                <label className="text-muted-foreground">{t("common.description")}</label>
                <p className="text-sm">{page.description}</p>
              </div>
            )}
          </div>
        </div>

        {/* Statistics */}
        <div>
          <h4 className="text-sm font-medium mb-3">{t("common.status")}</h4>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">{t("webTests.testCases")}</span>
              <span className="font-medium">{page.total_test_cases}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">{t("webTests.testRuns")}</span>
              <span className="font-medium">{page.total_test_runs}</span>
            </div>
            {page.last_run_status && (
              <div className="flex justify-between">
                <span className="text-muted-foreground">Last Status</span>
                <span className={`font-medium ${
                  page.last_run_status === "passed" ? "text-green-600" :
                  page.last_run_status === "failed" ? "text-red-600" :
                  "text-yellow-600"
                }`}>
                  {page.last_run_status}
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Elements */}
        {page.elements && Array.isArray(page.elements) && page.elements.length > 0 && (
          <div>
            <h4 className="text-sm font-medium mb-3">{t("webTests.elements")}</h4>
            <div className="space-y-1 text-sm">
              {page.elements.slice(0, 5).map((element: any, index: number) => (
                <div key={index} className="p-2 bg-muted rounded text-xs">
                  <p className="font-medium">{element.name || element.selector}</p>
                  <p className="text-muted-foreground">{element.type}</p>
                </div>
              ))}
              {page.elements.length > 5 && (
                <p className="text-xs text-muted-foreground">
                  ... and {page.elements.length - 5} more
                </p>
              )}
            </div>
          </div>
        )}

        {/* Timestamps */}
        <div>
          <h4 className="text-sm font-medium mb-3 flex items-center gap-2">
            <Calendar className="h-4 w-4" />
            {t("common.createdAt")}
          </h4>
          <p className="text-xs text-muted-foreground">
            {new Date(page.created_at).toLocaleString()}
          </p>
          {page.updated_at && (
            <p className="text-xs text-muted-foreground mt-1">
              Updated: {new Date(page.updated_at).toLocaleString()}
            </p>
          )}
        </div>
      </div>

      {/* Actions */}
      <div className="border-t p-4 space-y-2">
        <Button className="w-full" size="sm">
          {t("webTests.aiGenerateTests")}
        </Button>
        <Button className="w-full" variant="outline" size="sm">
          <ExternalLink className="mr-2 h-4 w-4" />
          Open Page
        </Button>
      </div>
    </div>
  );
}
// eslint-disable  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2UVdsaVJnPT06NzJlZjMxNGU=
