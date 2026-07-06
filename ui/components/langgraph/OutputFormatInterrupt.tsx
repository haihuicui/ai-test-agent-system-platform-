"use client";
// NOTE  MC8zOmFIVnBZMlhsdEpUbXRiZm92b3R5VjJ3PT06YjI0OTViMjY=

import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  FileText,
  FileSpreadsheet,
  FileJson,
  FileCode,
  AlertCircle,
  type LucideProps,
} from "lucide-react";
import { cn } from "@/lib/utils";
// NOTE  MS8zOmFIVnBZMlhsdEpUbXRiZm92b3R5VjJ3PT06YjI0OTViMjY=

interface OutputFormat {
  key: string;
  label: string;
}
// FIXME  Mi8zOmFIVnBZMlhsdEpUbXRiZm92b3R5VjJ3PT06YjI0OTViMjY=

interface OutputFormatInterruptProps {
  formats: OutputFormat[];
  description?: string;
  onResume: (value: any) => void;
  isLoading?: boolean;
}
// TODO  My8zOmFIVnBZMlhsdEpUbXRiZm92b3R5VjJ3PT06YjI0OTViMjY=

const FORMAT_ICONS: Record<string, React.ComponentType<LucideProps>> = {
  markdown: FileText,
  excel: FileSpreadsheet,
  json: FileJson,
  csv: FileCode,
};

export function OutputFormatInterrupt({
  formats,
  description,
  onResume,
  isLoading,
}: OutputFormatInterruptProps) {
  const [selectedKey, setSelectedKey] = useState<string | null>(null);

  const handleSelect = (key: string) => {
    setSelectedKey(key);
    onResume({ format: key });
  };

  return (
    <div className="w-full rounded-lg border-2 border-blue-300 bg-blue-50/80 p-4 dark:border-blue-700 dark:bg-blue-950/30">
      {/* 头部 */}
      <div className="mb-4 flex items-start gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-blue-100 dark:bg-blue-900">
          <AlertCircle
            size={18}
            className="text-blue-700 dark:text-blue-200"
          />
        </div>
        <div className="flex-1">
          <h3 className="text-base font-bold text-gray-900 dark:text-gray-100">
            选择最终交付物格式
          </h3>
          {description && (
            <p className="mt-1 text-sm text-gray-700 dark:text-gray-200">
              {description}
            </p>
          )}
        </div>
      </div>

      {/* 格式选项 */}
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        {formats.map((fmt) => {
          const Icon = FORMAT_ICONS[fmt.key] || FileText;
          const isSelected = selectedKey === fmt.key;
          return (
            <Button
              key={fmt.key}
              onClick={() => handleSelect(fmt.key)}
              variant="outline"
              disabled={isLoading}
              className={cn(
                "flex h-auto items-center justify-start gap-3 border-border bg-card p-3 text-left hover:bg-blue-50 dark:hover:bg-blue-950",
                isSelected && "border-blue-500 bg-blue-100 dark:bg-blue-900"
              )}
            >
              <Icon size={20} className="shrink-0 text-blue-600 dark:text-blue-300" />
              <span className="text-sm font-medium">{fmt.label}</span>
            </Button>
          );
        })}
      </div>

      {isLoading && selectedKey && (
        <p className="mt-3 text-xs text-blue-600 dark:text-blue-300">
          已选择格式，正在继续...
        </p>
      )}
    </div>
  );
}
// NOTE  My8zOmFIVnBZMlhsdEpUbXRiZm92b3R5VjJ3PT06YjI0OTViMjY=
