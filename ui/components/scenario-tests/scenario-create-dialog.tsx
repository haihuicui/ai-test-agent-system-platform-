/**
 * 场景创建对话框
 */
// TODO  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2VFhWbmRBPT06OTBmOTc5ZDc=

"use client";
// eslint-disable  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2VFhWbmRBPT06OTBmOTc5ZDc=

import * as React from "react";
import { toast } from "sonner";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { createScenario } from "@/lib/api/scenarios";
import { useLanguage } from "@/providers/LanguageProvider";
// NOTE  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2VFhWbmRBPT06OTBmOTc5ZDc=

interface ScenarioCreateDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  projectId: string;
  onSuccess: (scenarioId: string) => void;
}
// FIXME  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2VFhWbmRBPT06OTBmOTc5ZDc=

export function ScenarioCreateDialog({
  open,
  onOpenChange,
  projectId,
  onSuccess,
}: ScenarioCreateDialogProps) {
  const { t } = useLanguage();
  const [name, setName] = React.useState("");
  const [description, setDescription] = React.useState("");
  const [submitting, setSubmitting] = React.useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!name.trim()) {
      toast.error(t("scenarioTests.pleaseEnterScenarioName"));
      return;
    }

    try {
      setSubmitting(true);
      const data: any = {
        name: name.trim(),
      };
      if (description.trim()) {
        data.description = description.trim();
      }
      const scenario = await createScenario(projectId, data);

      onSuccess(scenario.id);

      // 重置表单
      setName("");
      setDescription("");
    } catch (error: any) {
      console.error("Failed to create scenario:", error);
      toast.error(error.message || t("apiTests.scenarioCreateFailed"));
    } finally {
      setSubmitting(false);
    }
  };

  const handleCancel = () => {
    // 重置表单
    setName("");
    setDescription("");
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Plus className="h-5 w-5" />
              {t("scenarioTests.createTestScenario")}
            </DialogTitle>
            <DialogDescription>
              {t("scenarioTests.scenarioDescriptionHint")}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            {/* 场景名称 */}
            <div className="space-y-2">
              <Label htmlFor="name">
                {t("scenarioTests.scenarioNameLabel")} <span className="text-destructive">*</span>
              </Label>
              <Input
                id="name"
                placeholder={t("scenarioTests.scenarioNamePlaceholder")}
                value={name}
                onChange={(e) => setName(e.target.value)}
                disabled={submitting}
              />
            </div>

            {/* 场景描述 */}
            <div className="space-y-2">
              <Label htmlFor="description">{t("scenarioTests.scenarioDescriptionLabel")}</Label>
              <Textarea
                id="description"
                placeholder={t("scenarioTests.scenarioDescriptionPlaceholder")}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                disabled={submitting}
                rows={3}
              />
            </div>

            {/* 提示信息 */}
            <div className="rounded-lg bg-blue-50 dark:bg-blue-950/20 p-3 border border-blue-200 dark:border-blue-800">
              <p className="text-xs text-blue-700 dark:text-blue-400">
                💡 <strong>{t("common.info")}</strong>：{t("scenarioTests.scenarioCreateHint")}
              </p>
            </div>
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={handleCancel}
              disabled={submitting}
            >
              取消
            </Button>
            <Button type="submit" disabled={submitting}>
              {submitting ? t("scenarioTests.scenarioCreating") : t("apiTests.newScenario")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
