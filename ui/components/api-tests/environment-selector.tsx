"use client";

import * as React from "react";
import { Server, Settings } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useProjectEnvironment } from "@/providers/ProjectEnvironmentProvider";
import { useLanguage } from "@/providers/LanguageProvider";

interface EnvironmentSelectorProps {
  onManage?: () => void;
}

export function EnvironmentSelector({ onManage }: EnvironmentSelectorProps) {
  const { t } = useLanguage();
  const {
    environments,
    selectedEnvironmentId,
    setSelectedEnvironmentId,
  } = useProjectEnvironment();

  return (
    <div className="flex items-center gap-1">
      <Select
        value={selectedEnvironmentId || ""}
        onValueChange={(value) => setSelectedEnvironmentId(value || null)}
      >
        <SelectTrigger className="w-[160px] h-9">
          <Server className="h-4 w-4 mr-1 shrink-0 text-muted-foreground" />
          <SelectValue placeholder={t("apiTests.selectEnvironment")} />
        </SelectTrigger>
        <SelectContent>
          {environments.length === 0 ? (
            <SelectItem value="__empty__" disabled>
              {t("apiTests.noEnvironment")}
            </SelectItem>
          ) : (
            environments.map((env) => (
              <SelectItem key={env.id} value={env.id}>
                <span className="flex items-center gap-1">
                  {env.name}
                  {env.is_default && (
                    <span className="text-xs text-muted-foreground">
                      ({t("environments.default")})
                    </span>
                  )}
                </span>
              </SelectItem>
            ))
          )}
        </SelectContent>
      </Select>
      {onManage && (
        <Button
          variant="ghost"
          size="icon"
          className="h-9 w-9"
          title={t("apiTests.manageEnvironments")}
          onClick={onManage}
        >
          <Settings className="h-4 w-4" />
        </Button>
      )}
    </div>
  );
}
