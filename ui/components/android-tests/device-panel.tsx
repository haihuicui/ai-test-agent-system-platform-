/**
 * Android 设备管理面板
 * 显示已连接的设备列表和状态，支持刷新设备列表
 */
"use client";
// FIXME  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2Y210TlR3PT06OGEyM2NhYTE=

import * as React from "react";
import {
  Smartphone,
  RefreshCw,
  Monitor,
  Circle,
  AlertCircle,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { toast } from "sonner";
import type { AndroidDevice } from "@/lib/api/android-tests";
import { listAndroidDevices, refreshAndroidDevices } from "@/lib/api/android-tests";
// NOTE  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2Y210TlR3PT06OGEyM2NhYTE=

interface DevicePanelProps {
  projectId: string;
  selectedDeviceUdid?: string | null;
  onSelectDevice?: (device: AndroidDevice | null) => void;
}
// WATERMARK  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2Y210TlR3PT06OGEyM2NhYTE=

export function DevicePanel({
  projectId,
  selectedDeviceUdid,
  onSelectDevice,
}: DevicePanelProps) {
  const [devices, setDevices] = React.useState<AndroidDevice[]>([]);
  const [loading, setLoading] = React.useState(false);
  const [refreshing, setRefreshing] = React.useState(false);

  const loadDevices = React.useCallback(async () => {
    try {
      setLoading(true);
      const data = await listAndroidDevices(projectId);
      setDevices(data);
    } catch (error) {
      console.error("Failed to load devices:", error);
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  const handleRefresh = async () => {
    try {
      setRefreshing(true);
      const data = await refreshAndroidDevices(projectId);
      setDevices(data);
      toast.success("设备列表已刷新");
    } catch (error) {
      console.error("Failed to refresh devices:", error);
      toast.error("刷新设备列表失败");
    } finally {
      setRefreshing(false);
    }
  };

  React.useEffect(() => {
    if (projectId) {
      loadDevices();
    }
  }, [projectId, loadDevices]);

  const getStatusColor = (status: string) => {
    switch (status) {
      case "connected":
        return "bg-green-500";
      case "busy":
        return "bg-yellow-500";
      case "offline":
      case "disconnected":
        return "bg-red-500";
      default:
        return "bg-gray-500";
    }
  };

  const getStatusLabel = (status: string) => {
    switch (status) {
      case "connected":
        return "已连接";
      case "busy":
        return "忙碌";
      case "offline":
        return "离线";
      case "disconnected":
        return "未连接";
      default:
        return status;
    }
  };

  return (
    <div className="flex h-full flex-col border-r bg-muted/5">
      {/* 头部 */}
      <div className="flex items-center justify-between border-b p-3 bg-background">
        <div className="flex items-center gap-2">
          <Monitor className="h-4 w-4 text-green-500" />
          <span className="font-medium text-sm">设备管理</span>
          {devices.length > 0 && (
            <Badge variant="secondary" className="text-xs">
              {devices.filter(d => d.status === "connected").length}/{devices.length}
            </Badge>
          )}
        </div>
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7"
          onClick={handleRefresh}
          disabled={refreshing}
        >
          <RefreshCw className={cn("h-4 w-4", refreshing && "animate-spin")} />
        </Button>
      </div>

      {/* 设备列表 */}
      <ScrollArea className="flex-1">
        {loading ? (
          <div className="py-4 text-center text-sm text-muted-foreground">
            加载设备...
          </div>
        ) : devices.length === 0 ? (
          <div className="flex flex-col items-center justify-center gap-3 py-8 px-4">
            <AlertCircle className="h-8 w-8 text-muted-foreground/50" />
            <div className="text-center">
              <p className="text-sm text-muted-foreground">暂无设备</p>
              <p className="text-xs text-muted-foreground mt-1">
                请连接 Android 设备或启动模拟器
              </p>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={handleRefresh}
              disabled={refreshing}
            >
              <RefreshCw className={cn("mr-2 h-3 w-3", refreshing && "animate-spin")} />
              刷新
            </Button>
          </div>
        ) : (
          <div className="p-2 space-y-1">
            {/* 全部设备选项 */}
            <div
              className={cn(
                "flex items-center gap-2 rounded-md px-2 py-2 text-sm cursor-pointer hover:bg-accent transition-colors",
                selectedDeviceUdid === null && "bg-accent"
              )}
              onClick={() => onSelectDevice?.(null)}
            >
              <Smartphone className="h-4 w-4 text-muted-foreground shrink-0" />
              <span className="truncate">全部设备</span>
            </div>

            {devices.map((device) => (
              <div
                key={device.udid}
                className={cn(
                  "flex items-center gap-2 rounded-md px-2 py-2 text-sm cursor-pointer hover:bg-accent transition-colors",
                  selectedDeviceUdid === device.udid && "bg-accent"
                )}
                onClick={() => onSelectDevice?.(device)}
              >
                <Smartphone className="h-4 w-4 text-green-500 shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5">
                    <span className="truncate font-medium">{device.name || device.model}</span>
                    <Circle
                      className={cn(
                        "h-2 w-2 fill-current shrink-0",
                        getStatusColor(device.status)
                      )}
                    />
                  </div>
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <span className="truncate">{device.udid.slice(0, 16)}...</span>
                    {device.version && (
                      <Badge variant="outline" className="text-[10px] h-4 px-1">
                        Android {device.version}
                      </Badge>
                    )}
                  </div>
                  {device.screen_resolution && (
                    <span className="text-xs text-muted-foreground">
                      {device.screen_resolution}
                    </span>
                  )}
                </div>
                <Badge
                  variant="outline"
                  className={cn(
                    "text-[10px] h-5 px-1.5 shrink-0",
                    device.status === "connected" && "border-green-500 text-green-600 bg-green-50 dark:bg-green-950/20",
                    device.status === "busy" && "border-yellow-500 text-yellow-600 bg-yellow-50 dark:bg-yellow-950/20",
                    (device.status === "offline" || device.status === "disconnected") && "border-red-500 text-red-600 bg-red-50 dark:bg-red-950/20"
                  )}
                >
                  {getStatusLabel(device.status)}
                </Badge>
              </div>
            ))}
          </div>
        )}
      </ScrollArea>

      {/* 底部提示 */}
      <div className="border-t p-2 text-xs text-muted-foreground text-center">
        通过 ADB 连接设备后刷新列表
      </div>
    </div>
  );
}
// TODO  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2Y210TlR3PT06OGEyM2NhYTE=
