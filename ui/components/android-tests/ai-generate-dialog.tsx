/**
 * AI 生成 Android 测试对话框
 */
"use client";
// NOTE  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2WjFnMmNBPT06ZjVlOGRhYWI=

import * as React from "react";
import { Sparkles, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
// NOTE  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2WjFnMmNBPT06ZjVlOGRhYWI=

interface AIGenerateDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onGenerate: (prompt: string) => void;
}
// eslint-disable  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2WjFnMmNBPT06ZjVlOGRhYWI=

export function AIGenerateDialog({
  open,
  onOpenChange,
  onGenerate,
}: AIGenerateDialogProps) {
  const [appPackage, setAppPackage] = React.useState("");
  const [appActivity, setAppActivity] = React.useState("");
  const [deviceUdid, setDeviceUdid] = React.useState("");
  const [scriptFormat, setScriptFormat] = React.useState("midscene");
  const [requirements, setRequirements] = React.useState("");
  const [submitting, setSubmitting] = React.useState(false);

  const resetForm = () => {
    setAppPackage("");
    setAppActivity("");
    setDeviceUdid("");
    setScriptFormat("midscene");
    setRequirements("");
  };

  React.useEffect(() => {
    if (open) {
      resetForm();
    }
  }, [open]);

  const handleGenerate = () => {
    setSubmitting(true);

    const prompt = `请为以下 Android 应用生成测试计划、测试用例和测试脚本：

**应用包名**: ${appPackage || "请根据应用功能自动推断"}
**启动 Activity**: ${appActivity || "请根据应用包名自动推断"}
**目标设备**: ${deviceUdid || "连接的第一个可用设备"}
**脚本格式**: ${scriptFormat}

${requirements ? `**特殊要求**:\n${requirements}` : ""}

请按以下步骤执行：
1. 分析应用功能需求
2. 生成测试计划并保存
3. 生成测试用例并保存
4. 生成 ${scriptFormat} 格式的测试脚本并保存
5. 报告生成结果`;

    onGenerate(prompt);
    setSubmitting(false);
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[600px] max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-green-500" />
            AI 生成 Android 测试
          </DialogTitle>
          <DialogDescription>
            使用 AI 助手自动生成 Android 应用的功能测试。填写应用信息，AI 将为您生成完整的测试计划、用例和脚本。
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="appPackage">应用包名</Label>
              <Input
                id="appPackage"
                value={appPackage}
                onChange={(e) => setAppPackage(e.target.value)}
                placeholder="com.example.app"
              />
              <p className="text-xs text-muted-foreground">
                被测应用的包名，如 com.android.settings
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="appActivity">启动 Activity</Label>
              <Input
                id="appActivity"
                value={appActivity}
                onChange={(e) => setAppActivity(e.target.value)}
                placeholder=".MainActivity"
              />
              <p className="text-xs text-muted-foreground">
                应用入口 Activity，可选
              </p>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="deviceUdid">目标设备 UDID</Label>
              <Input
                id="deviceUdid"
                value={deviceUdid}
                onChange={(e) => setDeviceUdid(e.target.value)}
                placeholder="自动选择"
              />
              <p className="text-xs text-muted-foreground">
                指定设备 UDID，留空则自动选择
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="scriptFormat">脚本格式</Label>
              <Select value={scriptFormat} onValueChange={setScriptFormat}>
                <SelectTrigger id="scriptFormat">
                  <SelectValue placeholder="选择脚本格式" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="midscene">Midscene.js</SelectItem>
                  <SelectItem value="appium">Appium</SelectItem>
                  <SelectItem value="espresso">Espresso</SelectItem>
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">
                生成测试脚本的框架格式
              </p>
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="requirements">特殊要求</Label>
            <Textarea
              id="requirements"
              value={requirements}
              onChange={(e) => setRequirements(e.target.value)}
              placeholder={`例如：
- 需要测试登录/注册流程
- 重点关注手势交互（滑动、长按）
- 包含设备旋转测试场景
- 测试不同分辨率下的 UI 适配`}
              className="min-h-[120px] resize-none"
            />
            <p className="text-xs text-muted-foreground">
              可选。如果不填写，AI 将根据应用信息自动生成标准测试。
            </p>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={submitting}>
            取消
          </Button>
          <Button
            onClick={handleGenerate}
            disabled={submitting}
            className="bg-gradient-to-r from-green-500 to-emerald-500 hover:from-green-600 hover:to-emerald-600 text-white"
          >
            {submitting ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                生成中...
              </>
            ) : (
              <>
                <Sparkles className="mr-2 h-4 w-4" />
                AI 生成
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
// FIXME  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2WjFnMmNBPT06ZjVlOGRhYWI=
