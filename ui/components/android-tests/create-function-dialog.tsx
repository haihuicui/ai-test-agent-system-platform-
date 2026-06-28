/**
 * 创建/编辑 Android 功能对话框
 */
"use client";
// TODO  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2UzBFNFFRPT06ODI1NDI5YTY=

import * as React from "react";
import { useState } from "react";
import { Loader2, Smartphone } from "lucide-react";
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
import { toast } from "sonner";
import type { AndroidFunction } from "@/lib/api/android-tests";
// FIXME  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2UzBFNFFRPT06ODI1NDI5YTY=

interface CreateAndroidFunctionDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  projectId: string;
  folderId?: string | null;
  editingFunction?: AndroidFunction | null;
  onSuccess?: () => void;
}
// eslint-disable  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2UzBFNFFRPT06ODI1NDI5YTY=

export function CreateAndroidFunctionDialog({
  open,
  onOpenChange,
  projectId,
  folderId,
  editingFunction,
  onSuccess,
}: CreateAndroidFunctionDialogProps) {
  const [submitting, setSubmitting] = useState(false);
  const isEditMode = !!editingFunction;

  const [displayName, setDisplayName] = useState("");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [appPackage, setAppPackage] = useState("");
  const [appActivity, setAppActivity] = useState("");
  const [deviceUdid, setDeviceUdid] = useState("");
  const [businessModule, setBusinessModule] = useState("");
  const [scriptFormat, setScriptFormat] = useState("midscene");

  const resetForm = () => {
    setDisplayName("");
    setName("");
    setDescription("");
    setAppPackage("");
    setAppActivity("");
    setDeviceUdid("");
    setBusinessModule("");
    setScriptFormat("midscene");
  };

  React.useEffect(() => {
    if (open && editingFunction) {
      setDisplayName(editingFunction.display_name || "");
      setName(editingFunction.name || "");
      setDescription(editingFunction.description || "");
      setAppPackage(editingFunction.app_package || "");
      setAppActivity(editingFunction.app_activity || "");
      setDeviceUdid(editingFunction.device_udid || "");
      setBusinessModule(editingFunction.business_module || "");
      setScriptFormat(editingFunction.script_format || "midscene");
    } else if (open && !editingFunction) {
      resetForm();
    }
  }, [open, editingFunction]);

  const handleOpenChange = (open: boolean) => {
    if (!open && !submitting) resetForm();
    onOpenChange(open);
  };

  const handleSave = async () => {
    if (!displayName.trim()) { toast.error("请输入显示名称"); return; }
    if (!name.trim()) { toast.error("请输入英文名称"); return; }
    const nameRegex = /^[a-zA-Z0-9-_]+$/;
    if (!nameRegex.test(name.trim())) { toast.error("英文名称只能包含字母、数字、连字符和下划线"); return; }

    try {
      setSubmitting(true);
      const requestBody: any = {
        display_name: displayName.trim(),
        name: name.trim(),
        script_format: scriptFormat,
      };
      if (description.trim()) requestBody.description = description.trim();
      if (appPackage.trim()) requestBody.app_package = appPackage.trim();
      if (appActivity.trim()) requestBody.app_activity = appActivity.trim();
      if (deviceUdid.trim()) requestBody.device_udid = deviceUdid.trim();
      requestBody.business_module = businessModule.trim();
      if (folderId) requestBody.folder_id = folderId;

      let response;
      if (isEditMode && editingFunction) {
        response = await fetch(`/api/v2/projects/${projectId}/android-functions/${editingFunction.id}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(requestBody),
        });
        if (!response.ok) { const error = await response.json(); throw new Error(error.detail || "更新 Android 功能失败"); }
        toast.success("Android 功能更新成功");
      } else {
        response = await fetch(`/api/v2/projects/${projectId}/android-functions`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(requestBody),
        });
        if (!response.ok) { const error = await response.json(); throw new Error(error.detail || "创建 Android 功能失败"); }
        toast.success("Android 功能创建成功");
      }
      resetForm();
      onOpenChange(false);
      onSuccess?.();
    } catch (error: any) {
      console.error(isEditMode ? "更新 Android 功能失败:" : "创建 Android 功能失败:", error);
      toast.error(error.message || (isEditMode ? "更新 Android 功能失败" : "创建 Android 功能失败"));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-[600px] max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Smartphone className="h-5 w-5 text-green-500" />
            {isEditMode ? "编辑 Android 功能" : "创建 Android 功能"}
          </DialogTitle>
          <DialogDescription>
            {isEditMode ? "编辑现有的 Android 功能配置" : "手工创建单个 Android 功能，填写应用信息和测试配置"}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <Label htmlFor="displayName">显示名称 <span className="text-destructive">*</span></Label>
            <Input id="displayName" value={displayName} onChange={(e) => setDisplayName(e.target.value)} placeholder="例如：用户登录功能" disabled={submitting} />
            <p className="text-xs text-muted-foreground">功能的中文名称，用于界面显示</p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="name">英文名称 <span className="text-destructive">*</span></Label>
            <Input id="name" value={name} onChange={(e) => setName(e.target.value)} placeholder="例如：user-login" disabled={submitting} />
            <p className="text-xs text-muted-foreground">功能的英文标识符，只能包含字母、数字、连字符和下划线</p>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="appPackage">应用包名</Label>
              <Input id="appPackage" value={appPackage} onChange={(e) => setAppPackage(e.target.value)} placeholder="com.example.app" disabled={submitting} />
              <p className="text-xs text-muted-foreground">被测 Android 应用的包名</p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="appActivity">启动 Activity</Label>
              <Input id="appActivity" value={appActivity} onChange={(e) => setAppActivity(e.target.value)} placeholder=".MainActivity" disabled={submitting} />
              <p className="text-xs text-muted-foreground">应用入口 Activity</p>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="deviceUdid">目标设备 UDID</Label>
              <Input id="deviceUdid" value={deviceUdid} onChange={(e) => setDeviceUdid(e.target.value)} placeholder="自动选择" disabled={submitting} />
              <p className="text-xs text-muted-foreground">指定测试设备的 UDID</p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="scriptFormat">脚本格式</Label>
              <Select value={scriptFormat} onValueChange={setScriptFormat} disabled={submitting}>
                <SelectTrigger id="scriptFormat"><SelectValue placeholder="选择脚本格式" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="midscene">Midscene.js</SelectItem>
                  <SelectItem value="appium">Appium</SelectItem>
                  <SelectItem value="espresso">Espresso</SelectItem>
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">测试脚本使用的框架</p>
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="businessModule">业务模块</Label>
            <Input id="businessModule" value={businessModule} onChange={(e) => setBusinessModule(e.target.value)} placeholder="例如：用户管理、订单服务等" disabled={submitting} />
            <p className="text-xs text-muted-foreground">用于功能分类和模块化管理</p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="description">详细描述</Label>
            <Textarea id="description" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="详细描述功能的作用、测试要点等" className="min-h-[100px] resize-none" disabled={submitting} />
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={submitting}>取消</Button>
          <Button onClick={handleSave} disabled={submitting}>
            {submitting ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" />{isEditMode ? "保存中..." : "创建中..."}</> : (isEditMode ? "保存更改" : "创建功能")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
// eslint-disable  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2UzBFNFFRPT06ODI1NDI5YTY=
