"use client";
// WATERMARK  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2YURJMk13PT06NTY0NmUwMzA=

import * as React from "react";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { toast } from "sonner";
import { useLanguage } from "@/providers/LanguageProvider";
import { bulkUpdateTestCases } from "@/lib/api/testCases";
import type {
  Priority,
  TestCaseState,
  TestCaseType,
  AutomationStatus,
  TestCaseUpdate,
} from "@/lib/api/types";
// NOTE  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2YURJMk13PT06NTY0NmUwMzA=

interface BulkEditDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  projectId: string;
  selectedIds: Set<string>;
  onSuccess?: () => void;
}

type FieldKey = "status" | "priority" | "case_type" | "automation_status" | "owner" | "module";

interface FieldState {
  enabled: boolean;
  value: string | undefined;
}

const statusOptions: { value: TestCaseState; label: string }[] = [
  { value: "new", label: "🆕 新建" },
  { value: "review_pending", label: "⏳ 待评审" },
  { value: "reviewed", label: "✅ 已评审" },
  { value: "not_run", label: "⚪ 未执行" },
  { value: "passed", label: "✅ 通过" },
  { value: "failed", label: "❌ 失败" },
  { value: "blocked", label: "🚫 阻塞" },
  { value: "skipped", label: "⏭️ 跳过" },
];

const priorityOptions: { value: Priority; label: string }[] = [
  { value: "critical", label: "🔴 紧急" },
  { value: "high", label: "🟠 高" },
  { value: "medium", label: "🟡 中" },
  { value: "low", label: "🟢 低" },
];

const caseTypeOptions: { value: TestCaseType; label: string }[] = [
  { value: "functional", label: "功能测试" },
  { value: "smoke_sanity", label: "冒烟测试" },
  { value: "regression", label: "回归测试" },
  { value: "security", label: "安全测试" },
  { value: "performance", label: "性能测试" },
  { value: "usability", label: "可用性测试" },
  { value: "acceptance", label: "验收测试" },
  { value: "integration", label: "集成测试" },
  { value: "exploratory", label: "探索性测试" },
  { value: "other", label: "其他" },
];

const automationStatusOptions: { value: AutomationStatus; label: string }[] = [
  { value: "not_automated", label: "未自动化" },
  { value: "automated", label: "已自动化" },
  { value: "in_progress", label: "自动化进行中" },
];

const fieldLabels: Record<FieldKey, string> = {
  status: "状态",
  priority: "优先级",
  case_type: "用例类型",
  automation_status: "自动化状态",
  owner: "负责人",
  module: "所属模块",
};

export function BulkEditDialog({
  open,
  onOpenChange,
  projectId,
  selectedIds,
  onSuccess,
}: BulkEditDialogProps) {
  const { t } = useLanguage();
  const [submitting, setSubmitting] = React.useState(false);
  const [fields, setFields] = React.useState<Record<FieldKey, FieldState>>({
    status: { enabled: false, value: undefined },
    priority: { enabled: false, value: undefined },
    case_type: { enabled: false, value: undefined },
    automation_status: { enabled: false, value: undefined },
    owner: { enabled: false, value: undefined },
    module: { enabled: false, value: undefined },
  });

  React.useEffect(() => {
    if (open) {
      setFields({
        status: { enabled: false, value: undefined },
        priority: { enabled: false, value: undefined },
        case_type: { enabled: false, value: undefined },
        automation_status: { enabled: false, value: undefined },
        owner: { enabled: false, value: undefined },
        module: { enabled: false, value: undefined },
      });
    }
  }, [open]);

  const toggleField = (key: FieldKey, enabled: boolean) => {
    setFields((prev) => ({
      ...prev,
      [key]: { ...prev[key], enabled },
    }));
  };

  const setValue = (key: FieldKey, value: string | undefined) => {
    setFields((prev) => ({
      ...prev,
      [key]: { ...prev[key], value },
    }));
  };

  const handleSubmit = async () => {
    if (selectedIds.size === 0) {
      toast.error(t("testCases.selectToEdit"));
      return;
    }

    const updateData: Partial<TestCaseUpdate> = {};
    (Object.keys(fields) as FieldKey[]).forEach((key) => {
      const field = fields[key];
      if (!field.enabled || field.value === undefined) return;

      const trimmed = field.value.trim();
      if (!trimmed) return;

      if (key === "status") {
        updateData.status = trimmed as TestCaseState;
      } else if (key === "priority") {
        updateData.priority = trimmed as Priority;
      } else if (key === "case_type") {
        updateData.case_type = trimmed as TestCaseType;
      } else if (key === "automation_status") {
        updateData.automation_status = trimmed as AutomationStatus;
      } else if (key === "owner") {
        updateData.owner = trimmed;
      } else if (key === "module") {
        updateData.module = trimmed;
      }
    });

    if (Object.keys(updateData).length === 0) {
      toast.error(t("testCases.bulkEditNoField"));
      return;
    }

    try {
      setSubmitting(true);
      const response = await bulkUpdateTestCases(
        projectId,
        Array.from(selectedIds),
        updateData
      );

      if (response.success) {
        toast.success(
          t("testCases.bulkEditSuccess", {
            count: response.affected_count.toString(),
          })
        );
        onSuccess?.();
        onOpenChange(false);
      } else {
        toast.error(t("testCases.bulkEditFailed"));
      }
    } catch (error) {
      console.error("Failed to bulk update test cases:", error);
      toast.error(t("testCases.bulkEditFailedRetry"));
    } finally {
      setSubmitting(false);
    }
  };

  const renderFieldControl = (key: FieldKey) => {
    const field = fields[key];

    switch (key) {
      case "status":
        return (
          <Select
            value={field.value || ""}
            onValueChange={(value) => setValue(key, value)}
            disabled={!field.enabled}
          >
            <SelectTrigger className="flex-1">
              <SelectValue placeholder="选择状态" />
            </SelectTrigger>
            <SelectContent>
              {statusOptions.map((opt) => (
                <SelectItem key={opt.value} value={opt.value}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        );
      case "priority":
        return (
          <Select
            value={field.value || ""}
            onValueChange={(value) => setValue(key, value)}
            disabled={!field.enabled}
          >
            <SelectTrigger className="flex-1">
              <SelectValue placeholder="选择优先级" />
            </SelectTrigger>
            <SelectContent>
              {priorityOptions.map((opt) => (
                <SelectItem key={opt.value} value={opt.value}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        );
      case "case_type":
        return (
          <Select
            value={field.value || ""}
            onValueChange={(value) => setValue(key, value)}
            disabled={!field.enabled}
          >
            <SelectTrigger className="flex-1">
              <SelectValue placeholder="选择用例类型" />
            </SelectTrigger>
            <SelectContent>
              {caseTypeOptions.map((opt) => (
                <SelectItem key={opt.value} value={opt.value}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        );
      case "automation_status":
        return (
          <Select
            value={field.value || ""}
            onValueChange={(value) => setValue(key, value)}
            disabled={!field.enabled}
          >
            <SelectTrigger className="flex-1">
              <SelectValue placeholder="选择自动化状态" />
            </SelectTrigger>
            <SelectContent>
              {automationStatusOptions.map((opt) => (
                <SelectItem key={opt.value} value={opt.value}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        );
      case "owner":
      case "module":
        return (
          <Input
            className="flex-1"
            placeholder={key === "owner" ? "输入负责人邮箱" : "输入所属模块"}
            value={field.value || ""}
            onChange={(e) => setValue(key, e.target.value)}
            disabled={!field.enabled}
          />
        );
      default:
        return null;
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>
            {t("testCases.bulkEditTitle", { count: selectedIds.size.toString() })}
          </DialogTitle>
          <DialogDescription>{t("testCases.bulkEditDescription")}</DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {(Object.keys(fields) as FieldKey[]).map((key) => (
            <div key={key} className="flex items-center gap-3">
              <Checkbox
                id={`bulk-edit-${key}`}
                checked={fields[key].enabled}
                onCheckedChange={(checked) => toggleField(key, checked as boolean)}
              />
              <Label
                htmlFor={`bulk-edit-${key}`}
                className="w-24 shrink-0 text-sm"
              >
                {fieldLabels[key]}
              </Label>
              {renderFieldControl(key)}
            </div>
          ))}
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={submitting}
          >
            {t("common.cancel")}
          </Button>
          <Button onClick={handleSubmit} disabled={submitting}>
            {submitting ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                {t("testCases.saving")}
              </>
            ) : (
              t("common.save")
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
// NOTE  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2YURJMk13PT06NTY0NmUwMzA=

// FIXME  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2YURJMk13PT06NTY0NmUwMzA=
