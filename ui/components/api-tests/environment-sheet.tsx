"use client";

import * as React from "react";
import { toast } from "sonner";
import {
  Server,
  Plus,
  Pencil,
  Trash2,
  Check,
  Loader2,
} from "lucide-react";
import { useLanguage } from "@/providers/LanguageProvider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Drawer,
  DrawerContent,
  DrawerHeader,
  DrawerTitle,
  DrawerDescription,
  DrawerFooter,
} from "@/components/ui/drawer";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  listEnvironments,
  createEnvironment,
  updateEnvironment,
  deleteEnvironment,
  testEnvironmentConnection,
  testDynamicBearerConnection,
} from "@/lib/api/environments";
import type {
  EnvironmentInfo,
  EnvironmentCreate,
  EnvironmentUpdate,
  AuthType,
} from "@/lib/api/types";

const AUTH_TYPES: { value: AuthType; label: string }[] = [
  { value: "none", label: "无认证" },
  { value: "bearer", label: "Bearer Token" },
  { value: "dynamic_bearer", label: "动态 Bearer Token" },
  { value: "api_key", label: "API Key" },
  { value: "oauth2", label: "OAuth2" },
];

function parseKeyValueText(text: string): Record<string, string> {
  const result: Record<string, string> = {};
  text.split("\n").forEach((line) => {
    const idx = line.indexOf(":");
    if (idx > 0) {
      const key = line.slice(0, idx).trim();
      const value = line.slice(idx + 1).trim();
      if (key) result[key] = value;
    }
  });
  return result;
}

function keyValueToText(obj: Record<string, unknown>): string {
  return Object.entries(obj)
    .map(([k, v]) => `${k}: ${String(v)}`)
    .join("\n");
}

function buildAuthConfig(form: {
  auth_type: AuthType;
  auth_config_text: string;
  token_url: string;
  token_method: "GET" | "POST";
  token_path: string;
  token_body_text: string;
  token_headers_text: string;
  token_ttl_seconds: string;
}): Record<string, unknown> {
  if (form.auth_type !== "dynamic_bearer") {
    return parseKeyValueText(form.auth_config_text);
  }

  const cfg: Record<string, unknown> = {
    token_url: form.token_url,
    token_method: form.token_method,
    token_path: form.token_path,
  };

  if (form.token_body_text.trim()) {
    try {
      cfg.token_body = JSON.parse(form.token_body_text);
    } catch {
      cfg.token_body = parseKeyValueText(form.token_body_text);
    }
  }

  if (form.token_headers_text.trim()) {
    try {
      cfg.token_headers = JSON.parse(form.token_headers_text);
    } catch {
      cfg.token_headers = parseKeyValueText(form.token_headers_text);
    }
  }

  const ttl = parseInt(form.token_ttl_seconds, 10);
  if (!Number.isNaN(ttl) && ttl >= 0) {
    cfg.token_ttl_seconds = ttl;
  }

  return cfg;
}

function isAuthConfigured(env: EnvironmentInfo): boolean {
  if (env.auth_type === "dynamic_bearer") {
    return Boolean((env.auth_config?.token_url as string)?.trim());
  }
  return env.has_auth_secret;
}

interface EnvironmentSheetProps {
  projectId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onEnvironmentsChange?: (envs: EnvironmentInfo[]) => void;
}

export function EnvironmentSheet({
  projectId,
  open,
  onOpenChange,
  onEnvironmentsChange,
}: EnvironmentSheetProps) {
  const { t } = useLanguage();

  const onEnvironmentsChangeRef = React.useRef(onEnvironmentsChange);
  React.useEffect(() => {
    onEnvironmentsChangeRef.current = onEnvironmentsChange;
  }, [onEnvironmentsChange]);

  const [environments, setEnvironments] = React.useState<EnvironmentInfo[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [dialogOpen, setDialogOpen] = React.useState(false);
  const [editingEnv, setEditingEnv] = React.useState<EnvironmentInfo | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = React.useState(false);
  const [envToDelete, setEnvToDelete] = React.useState<EnvironmentInfo | null>(null);
  const [saving, setSaving] = React.useState(false);

  const [form, setForm] = React.useState<{
    name: string;
    base_url: string;
    auth_type: AuthType;
    auth_secret: string;
    auth_config_text: string;
    token_url: string;
    token_method: "GET" | "POST";
    token_path: string;
    token_body_text: string;
    token_headers_text: string;
    token_ttl_seconds: string;
    timeout_ms: string;
    is_default: boolean;
  }>({
    name: "",
    base_url: "",
    auth_type: "none",
    auth_secret: "",
    auth_config_text: "",
    token_url: "",
    token_method: "POST",
    token_path: "$.data.token",
    token_body_text: "",
    token_headers_text: "",
    token_ttl_seconds: "300",
    timeout_ms: "30000",
    is_default: false,
  });

  const loadEnvironments = React.useCallback(async () => {
    setLoading(true);
    try {
      const res = await listEnvironments(projectId);
      const envs = res.data || [];
      setEnvironments(envs);
      onEnvironmentsChangeRef.current?.(envs);
    } catch (err: any) {
      toast.error(t("environments.loadFailed"));
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [projectId, t]);

  React.useEffect(() => {
    if (open) {
      loadEnvironments();
    }
  }, [open, loadEnvironments]);

  const resetForm = () => {
    setForm({
      name: "",
      base_url: "",
      auth_type: "none",
      auth_secret: "",
      auth_config_text: "",
      token_url: "",
      token_method: "POST",
      token_path: "$.data.token",
      token_body_text: "",
      token_headers_text: "",
      token_ttl_seconds: "300",
      timeout_ms: "30000",
      is_default: false,
    });
    setEditingEnv(null);
  };

  const openCreateDialog = () => {
    resetForm();
    setDialogOpen(true);
  };

  const openEditDialog = (env: EnvironmentInfo) => {
    setEditingEnv(env);
    const cfg = (env.auth_config || {}) as Record<string, unknown>;
    setForm({
      name: env.name,
      base_url: env.base_url,
      auth_type: env.auth_type as AuthType,
      auth_secret: env.auth_secret || "",
      auth_config_text: keyValueToText(env.auth_config || {}),
      token_url: String(cfg.token_url || ""),
      token_method: (cfg.token_method as "GET" | "POST") || "POST",
      token_path: String(cfg.token_path || "$.data.token"),
      token_body_text: cfg.token_body ? JSON.stringify(cfg.token_body, null, 2) : "",
      token_headers_text: cfg.token_headers ? keyValueToText(cfg.token_headers as Record<string, unknown>) : "",
      token_ttl_seconds: String(cfg.token_ttl_seconds || "300"),
      timeout_ms: String(env.timeout_ms || 30000),
      is_default: env.is_default,
    });
    setDialogOpen(true);
  };

  const openDeleteDialog = (env: EnvironmentInfo) => {
    setEnvToDelete(env);
    setDeleteDialogOpen(true);
  };

  const handleSave = async () => {
    if (!form.name.trim() || !form.base_url.trim()) {
      toast.error(t("environments.nameAndUrlRequired"));
      return;
    }

    const timeout = parseInt(form.timeout_ms, 10);
    if (Number.isNaN(timeout) || timeout < 1000) {
      toast.error(t("environments.invalidTimeout"));
      return;
    }

    if (form.auth_type === "dynamic_bearer" && !form.token_url.trim()) {
      toast.error(t("environments.dynamicBearerUrlRequired"));
      return;
    }

    const authConfig = buildAuthConfig(form);

    setSaving(true);
    try {
      if (editingEnv) {
        const payload: EnvironmentUpdate = {
          name: form.name,
          base_url: form.base_url,
          auth_type: form.auth_type,
          auth_secret: form.auth_secret || undefined,
          auth_config: authConfig,
          timeout_ms: timeout,
          is_default: form.is_default,
        };
        await updateEnvironment(projectId, editingEnv.id, payload);
        toast.success(t("environments.updateSuccess"));
      } else {
        const payload: EnvironmentCreate = {
          name: form.name,
          base_url: form.base_url,
          auth_type: form.auth_type,
          auth_secret: form.auth_secret || undefined,
          auth_config: authConfig,
          timeout_ms: timeout,
          is_default: form.is_default,
        };
        await createEnvironment(projectId, payload);
        toast.success(t("environments.createSuccess"));
      }
      setDialogOpen(false);
      resetForm();
      await loadEnvironments();
    } catch (err: any) {
      toast.error(err?.data?.message || t("environments.saveFailed"));
      console.error(err);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!envToDelete) return;
    try {
      await deleteEnvironment(projectId, envToDelete.id);
      toast.success(t("environments.deleteSuccess"));
      setDeleteDialogOpen(false);
      setEnvToDelete(null);
      await loadEnvironments();
    } catch (err: any) {
      toast.error(err?.data?.message || t("environments.deleteFailed"));
      console.error(err);
    }
  };

  const renderAuthFields = () => {
    switch (form.auth_type) {
      case "bearer":
        return (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label htmlFor="auth_secret">{t("environments.bearerToken")}</Label>
              {editingEnv?.has_auth_secret && form.auth_secret === "" && (
                <Badge variant="secondary" className="text-xs">
                  {t("environments.tokenConfigured")}
                </Badge>
              )}
            </div>
            <Input
              id="auth_secret"
              type="text"
              placeholder={t("environments.bearerTokenPlaceholder")}
              value={form.auth_secret}
              onChange={(e) => setForm({ ...form, auth_secret: e.target.value })}
            />
            {editingEnv && (
              <p className="text-xs text-muted-foreground">
                {t("environments.leaveBlankToKeep")}
              </p>
            )}
          </div>
        );
      case "dynamic_bearer":
        return (
          <>
            <div className="space-y-2">
              <Label htmlFor="token_url">{t("environments.tokenUrl")}</Label>
              <Input
                id="token_url"
                placeholder={t("environments.tokenUrlPlaceholder")}
                value={form.token_url}
                onChange={(e) => setForm({ ...form, token_url: e.target.value })}
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="token_method">{t("environments.tokenMethod")}</Label>
                <Select
                  value={form.token_method}
                  onValueChange={(value: "GET" | "POST") => setForm({ ...form, token_method: value })}
                >
                  <SelectTrigger id="token_method">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="POST">POST</SelectItem>
                    <SelectItem value="GET">GET</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="token_ttl_seconds">{t("environments.tokenTtl")}</Label>
                <Input
                  id="token_ttl_seconds"
                  type="number"
                  min={0}
                  step={1}
                  value={form.token_ttl_seconds}
                  onChange={(e) => setForm({ ...form, token_ttl_seconds: e.target.value })}
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="token_path">{t("environments.tokenPath")}</Label>
              <Input
                id="token_path"
                placeholder={t("environments.tokenPathPlaceholder")}
                value={form.token_path}
                onChange={(e) => setForm({ ...form, token_path: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="token_headers">{t("environments.tokenHeaders")}</Label>
              <Textarea
                id="token_headers"
                placeholder={t("environments.tokenHeadersPlaceholder")}
                value={form.token_headers_text}
                onChange={(e) => setForm({ ...form, token_headers_text: e.target.value })}
                rows={2}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="token_body">{t("environments.tokenBody")}</Label>
              <Textarea
                id="token_body"
                placeholder={t("environments.tokenBodyPlaceholder")}
                value={form.token_body_text}
                onChange={(e) => setForm({ ...form, token_body_text: e.target.value })}
                rows={3}
              />
            </div>
            <div className="flex items-center justify-between rounded-lg border p-3">
              <div className="space-y-0.5">
                <Label>{t("environments.testConnection")}</Label>
                <p className="text-xs text-muted-foreground">{t("environments.testConnectionHint")}</p>
              </div>
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={!form.token_url.trim()}
                onClick={async () => {
                  if (!form.token_url.trim()) {
                    toast.error(t("environments.dynamicBearerUrlRequired"));
                    return;
                  }
                  try {
                    let res;
                    if (editingEnv) {
                      res = await testEnvironmentConnection(projectId, editingEnv.id);
                    } else {
                      const authConfig = buildAuthConfig(form);
                      res = await testDynamicBearerConnection(projectId, authConfig);
                    }
                    if (res.data?.success) {
                      toast.success(`Token ${t("environments.testFetch")} ${t("common.success")}, length ${res.data.token_length}`);
                    } else {
                      toast.error(res.data?.error || t("common.error"));
                    }
                  } catch (err: any) {
                    toast.error(err?.data?.message || t("common.error"));
                  }
                }}
              >
                {t("environments.testFetch")}
              </Button>
            </div>
          </>
        );
      case "api_key":
        return (
          <>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label htmlFor="auth_secret">{t("environments.apiKey")}</Label>
                {editingEnv?.has_auth_secret && form.auth_secret === "" && (
                  <Badge variant="secondary" className="text-xs">
                    {t("environments.tokenConfigured")}
                  </Badge>
                )}
              </div>
              <Input
                id="auth_secret"
                type="text"
                placeholder={t("environments.apiKeyPlaceholder")}
                value={form.auth_secret}
                onChange={(e) => setForm({ ...form, auth_secret: e.target.value })}
              />
              {editingEnv && (
                <p className="text-xs text-muted-foreground">
                  {t("environments.leaveBlankToKeep")}
                </p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="api_key_header">{t("environments.apiKeyHeader")}</Label>
              <Input
                id="api_key_header"
                placeholder="X-API-Key"
                value={(parseKeyValueText(form.auth_config_text).api_key_header) || ""}
                onChange={(e) => {
                  const cfg = parseKeyValueText(form.auth_config_text);
                  cfg.api_key_header = e.target.value || "X-API-Key";
                  setForm({ ...form, auth_config_text: keyValueToText(cfg) });
                }}
              />
            </div>
          </>
        );
      case "oauth2":
        return (
          <>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label htmlFor="auth_secret">{t("environments.oauth2Token")}</Label>
                {editingEnv?.has_auth_secret && form.auth_secret === "" && (
                  <Badge variant="secondary" className="text-xs">
                    {t("environments.tokenConfigured")}
                  </Badge>
                )}
              </div>
              <Input
                id="auth_secret"
                type="text"
                placeholder={t("environments.oauth2TokenPlaceholder")}
                value={form.auth_secret}
                onChange={(e) => setForm({ ...form, auth_secret: e.target.value })}
              />
              {editingEnv && (
                <p className="text-xs text-muted-foreground">
                  {t("environments.leaveBlankToKeep")}
                </p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="oauth2_config">{t("environments.oauth2Config")}</Label>
              <Textarea
                id="oauth2_config"
                placeholder={t("environments.oauth2ConfigPlaceholder")}
                value={form.auth_config_text}
                onChange={(e) => setForm({ ...form, auth_config_text: e.target.value })}
                rows={3}
              />
            </div>
          </>
        );
      default:
        return null;
    }
  };

  return (
    <>
      <Drawer open={open} onOpenChange={onOpenChange}>
        <DrawerContent direction="right" className="w-full sm:max-w-2xl p-0">
          <div className="flex flex-col h-full">
            <DrawerHeader className="px-6 py-4 border-b">
              <DrawerTitle className="flex items-center gap-2">
                <Server className="h-5 w-5" />
                {t("environments.title")}
              </DrawerTitle>
              <DrawerDescription>
                {t("environments.description")}
              </DrawerDescription>
            </DrawerHeader>

            <div className="flex-1 overflow-y-auto p-6">
              <Button onClick={openCreateDialog} className="mb-4">
                <Plus className="h-4 w-4 mr-2" />
                {t("environments.create")}
              </Button>

              {loading ? (
                <div className="flex items-center justify-center py-20">
                  <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                </div>
              ) : environments.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-16 border rounded-lg">
                  <Server className="h-12 w-12 text-muted-foreground mb-4" />
                  <p className="text-muted-foreground">{t("environments.noData")}</p>
                  <Button variant="outline" className="mt-4" onClick={openCreateDialog}>
                    <Plus className="h-4 w-4 mr-2" />
                    {t("environments.create")}
                  </Button>
                </div>
              ) : (
                <div className="grid gap-3">
                  {environments.map((env) => (
                    <div
                      key={env.id}
                      className={cn(
                        "rounded-lg border p-4",
                        env.is_default && "border-primary"
                      )}
                    >
                      <div className="flex items-start justify-between">
                        <div>
                          <div className="flex items-center gap-2">
                            <h3 className="font-semibold">{env.name}</h3>
                            {env.is_default && (
                              <Badge variant="default">
                                <Check className="h-3 w-3 mr-1" />
                                {t("environments.default")}
                              </Badge>
                            )}
                          </div>
                          <p className="text-sm text-muted-foreground mt-1">
                            {env.base_url}
                          </p>
                        </div>
                        <div className="flex items-center gap-1">
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => openEditDialog(env)}
                          >
                            <Pencil className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => openDeleteDialog(env)}
                          >
                            <Trash2 className="h-4 w-4 text-destructive" />
                          </Button>
                        </div>
                      </div>

                      <div className="grid grid-cols-2 gap-4 text-sm mt-3">
                        <div>
                          <span className="text-muted-foreground">{t("environments.authType")}:</span>
                          <span className="ml-1 font-medium">
                            {AUTH_TYPES.find((t) => t.value === env.auth_type)?.label || env.auth_type}
                          </span>
                          {env.auth_type !== "none" && (
                            <Badge
                              variant={isAuthConfigured(env) ? "default" : "outline"}
                              className="ml-2 text-xs"
                            >
                              {isAuthConfigured(env)
                                ? t("environments.tokenConfigured")
                                : t("environments.tokenNotConfigured")}
                            </Badge>
                          )}
                        </div>
                        <div>
                          <span className="text-muted-foreground">{t("environments.timeout")}:</span>
                          <span className="ml-1 font-medium">{env.timeout_ms}ms</span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <DrawerFooter className="border-t px-6 py-4">
              <Button variant="outline" onClick={() => onOpenChange(false)}>
                {t("common.close")}
              </Button>
            </DrawerFooter>
          </div>
        </DrawerContent>
      </Drawer>

      {/* Create/Edit Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>
              {editingEnv ? t("environments.editTitle") : t("environments.createTitle")}
            </DialogTitle>
            <DialogDescription>
              {editingEnv ? t("environments.editDescription") : t("environments.createDescription")}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="name">{t("environments.name")}</Label>
              <Input
                id="name"
                placeholder={t("environments.namePlaceholder")}
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="base_url">{t("environments.baseUrl")}</Label>
              <Input
                id="base_url"
                placeholder="https://api.example.com"
                value={form.base_url}
                onChange={(e) => setForm({ ...form, base_url: e.target.value })}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="auth_type">{t("environments.authType")}</Label>
              <Select
                value={form.auth_type}
                onValueChange={(value: AuthType) => setForm({ ...form, auth_type: value })}
              >
                <SelectTrigger id="auth_type">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {AUTH_TYPES.map((type) => (
                    <SelectItem key={type.value} value={type.value}>
                      {type.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {renderAuthFields()}

            <div className="space-y-2">
              <Label htmlFor="timeout">{t("environments.timeout")}</Label>
              <Input
                id="timeout"
                type="number"
                min={1000}
                step={1000}
                value={form.timeout_ms}
                onChange={(e) => setForm({ ...form, timeout_ms: e.target.value })}
              />
            </div>

            <div className="flex items-center justify-between rounded-lg border p-3">
              <div className="space-y-0.5">
                <Label htmlFor="is_default">{t("environments.setAsDefault")}</Label>
                <p className="text-xs text-muted-foreground">
                  {t("environments.setAsDefaultHint")}
                </p>
              </div>
              <Switch
                id="is_default"
                checked={form.is_default}
                onCheckedChange={(checked) => setForm({ ...form, is_default: checked })}
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>
              {t("common.cancel")}
            </Button>
            <Button onClick={handleSave} disabled={saving}>
              {saving && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              {t("common.save")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Dialog */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("environments.deleteTitle")}</DialogTitle>
            <DialogDescription>
              {t("environments.deleteConfirm", { name: envToDelete?.name || "" })}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteDialogOpen(false)}>
              {t("common.cancel")}
            </Button>
            <Button variant="destructive" onClick={handleDelete}>
              {t("common.delete")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
