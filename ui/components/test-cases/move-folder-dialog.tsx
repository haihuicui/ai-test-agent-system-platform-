"use client";
// TODO  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2VDI1b2FRPT06OTE3NmMxMDA=

import * as React from "react";
import {
  ChevronRight,
  ChevronDown,
  Folder,
  FolderOpen,
  Info,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Label } from "@/components/ui/label";
import { ScrollArea } from "@/components/ui/scroll-area";
import { getFolders, moveFolder } from "@/lib/api/folders";
import type { FolderInfo } from "@/lib/api/types";
import { toast } from "sonner";
// TODO  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2VDI1b2FRPT06OTE3NmMxMDA=

interface FolderTreeNode extends FolderInfo {
  children?: FolderTreeNode[];
  expanded?: boolean;
  loading?: boolean;
}

interface MoveFolderDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  projectId: string;
  folder: FolderInfo | null;
  folderType?: string;
  onMoveSuccess: (folderId: string, newParentId: string | null, updatedFolder: FolderInfo) => void;
}
// NOTE  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2VDI1b2FRPT06OTE3NmMxMDA=

export function MoveFolderDialog({
  open,
  onOpenChange,
  projectId,
  folder,
  folderType,
  onMoveSuccess,
}: MoveFolderDialogProps) {
  const [moveType, setMoveType] = React.useState<"specific" | "root">("specific");
  const [selectedFolderId, setSelectedFolderId] = React.useState<string | null>(null);
  const [folders, setFolders] = React.useState<FolderTreeNode[]>([]);
  const [expandedIds, setExpandedIds] = React.useState<Set<string>>(new Set());
  const [loading, setLoading] = React.useState(false);
  const [submitting, setSubmitting] = React.useState(false);

  // 加载根文件夹
  const loadRootFolders = React.useCallback(async () => {
    try {
      setLoading(true);
      const response = await getFolders(projectId, folderType);
      if (response.success && response.data) {
        const rootFolders = response.data.filter(
          (f) => f.parent_id === null || f.parent_id === undefined
        );
        setFolders(
          rootFolders.map((f) => ({
            ...f,
            children: undefined,
            loading: false,
            expanded: false,
          }))
        );
      }
    } catch (error) {
      console.error("Failed to load folders:", error);
    } finally {
      setLoading(false);
    }
  }, [projectId, folderType]);

  // 加载子文件夹
  const loadChildren = async (folderId: string) => {
    try {
      const response = await getFolders(projectId, folderType, folderId);
      if (response.success && response.data) {
        setFolders((prev) => updateFolderChildren(prev, folderId, response.data));
      }
    } catch (error) {
      console.error("Failed to load children:", error);
    }
  };

  // 更新子文件夹
  const updateFolderChildren = (
    nodes: FolderTreeNode[],
    parentId: string,
    children: FolderInfo[]
  ): FolderTreeNode[] => {
    return nodes.map((node) => {
      if (node.id === parentId) {
        return {
          ...node,
          children: children.map((c) => ({
            ...c,
            children: undefined,
            loading: false,
            expanded: false,
          })),
          loading: false,
        };
      }
      if (node.children) {
        return { ...node, children: updateFolderChildren(node.children, parentId, children) };
      }
      return node;
    });
  };

  // 切换展开/折叠
  const toggleExpand = async (node: FolderTreeNode) => {
    if (expandedIds.has(node.id)) {
      setExpandedIds((prev) => {
        const newSet = new Set(prev);
        newSet.delete(node.id);
        return newSet;
      });
    } else {
      setExpandedIds((prev) => {
        const newSet = new Set(prev);
        newSet.add(node.id);
        return newSet;
      });
      // 如果没有加载过子文件夹，加载它们
      if (!node.children && node.sub_folders_count > 0) {
        await loadChildren(node.id);
      }
    }
  };

  // 检查是否可以选择该文件夹作为目标
  const canSelectAsTarget = (node: FolderTreeNode): boolean => {
    if (!folder) return false;
    // 不能移动到自身
    if (node.id === folder.id) return false;
    // 不能移动到自己的子文件夹（需要递归检查）
    // 这里简化处理，后端会做完整验证
    return true;
  };

  // 检查是否是当前移动文件夹的子孙
  const isDescendant = (node: FolderTreeNode, targetId: string): boolean => {
    if (node.id === targetId) return true;
    if (node.children) {
      return node.children.some((child) => isDescendant(child, targetId));
    }
    return false;
  };

  // 确认移动
  const handleConfirmMove = async () => {
    if (!folder) return;

    const targetParentId = moveType === "root" ? null : selectedFolderId;

    // 验证
    if (moveType === "specific" && !selectedFolderId) {
      toast.error("请选择目标文件夹");
      return;
    }

    // 不能移动到自身
    if (targetParentId === folder.id) {
      toast.error("不能将文件夹移动到自身");
      return;
    }

    // 不能移动到当前位置
    if (targetParentId === folder.parent_id) {
      toast.info("文件夹已在此位置");
      onOpenChange(false);
      return;
    }

    try {
      setSubmitting(true);
      const response = await moveFolder(projectId, folder.id, targetParentId);
      if (response.success && response.data) {
        toast.success(`文件夹 "${folder.name}" 移动成功`);
        onMoveSuccess(folder.id, targetParentId, response.data);
        onOpenChange(false);
      } else {
        toast.error("移动文件夹失败");
      }
    } catch (error) {
      console.error("Failed to move folder:", error);
      toast.error("移动文件夹失败");
    } finally {
      setSubmitting(false);
    }
  };

  // 对话框打开时加载文件夹
  React.useEffect(() => {
    if (open) {
      loadRootFolders();
      setMoveType("specific");
      setSelectedFolderId(null);
      setExpandedIds(new Set());
    }
  }, [open, loadRootFolders]);

  // 渲染文件夹节点
  const renderFolderNode = (node: FolderTreeNode, level: number = 0) => {
    const isExpanded = expandedIds.has(node.id);
    const hasChildren = node.sub_folders_count > 0;
    const isSelected = selectedFolderId === node.id;
    const isDisabled = folder?.id === node.id;
    const isCurrentFolder = folder?.id === node.id;

    return (
      <div key={node.id}>
        <div
          className={cn(
            "flex items-center py-1.5 px-2 rounded-md cursor-pointer hover:bg-accent transition-colors",
            isSelected && moveType === "specific" && "bg-primary/10 ring-1 ring-primary",
            isDisabled && "opacity-50 cursor-not-allowed"
          )}
          style={{ paddingLeft: `${level * 16 + 8}px` }}
          onClick={() => {
            if (!isDisabled && moveType === "specific") {
              setSelectedFolderId(node.id);
            }
          }}
        >
          {/* 展开/折叠按钮 */}
          <Button
            variant="ghost"
            size="icon"
            className="h-5 w-5 shrink-0 mr-1"
            onClick={(e) => {
              e.stopPropagation();
              if (hasChildren) {
                toggleExpand(node);
              }
            }}
          >
            {hasChildren ? (
              isExpanded ? (
                <ChevronDown className="h-4 w-4" />
              ) : (
                <ChevronRight className="h-4 w-4" />
              )
            ) : (
              <span className="w-4" />
            )}
          </Button>

          {/* 文件夹图标 */}
          {isExpanded ? (
            <FolderOpen className="h-4 w-4 shrink-0 text-primary mr-2" />
          ) : (
            <Folder className="h-4 w-4 shrink-0 text-primary mr-2" />
          )}

          {/* 文件夹名称 */}
          <span className={cn("flex-1 truncate text-sm", isCurrentFolder && "text-muted-foreground")}>
            {node.name}
            {isCurrentFolder && " (当前)"}
          </span>

          {/* 统计数字 */}
          <span className="text-xs text-muted-foreground ml-2 shrink-0">
            {node.direct_cases_count}({node.cases_count})
          </span>
        </div>

        {/* 子文件夹 */}
        {isExpanded && node.children && (
          <div>
            {node.children.map((child) => renderFolderNode(child, level + 1))}
          </div>
        )}
      </div>
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>移动文件夹</DialogTitle>
          <DialogDescription>
            选择要将文件夹 "{folder?.name}" 移动到的目标位置
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {/* 移动类型选择 */}
          <div className="space-y-2">
            <Label>移动到:</Label>
            <RadioGroup
              value={moveType}
              onValueChange={(v: string) => setMoveType(v as "specific" | "root")}
              className="flex gap-6"
            >
              <div className="flex items-center space-x-2">
                <RadioGroupItem value="specific" id="specific" />
                <Label htmlFor="specific" className="cursor-pointer">特定位置</Label>
              </div>
              <div className="flex items-center space-x-2">
                <RadioGroupItem value="root" id="root" />
                <Label htmlFor="root" className="cursor-pointer">根文件夹</Label>
              </div>
            </RadioGroup>
          </div>

          {/* 文件夹树 */}
          {moveType === "specific" && (
            <ScrollArea className="h-[300px] border rounded-md">
              <div className="p-2">
                {loading ? (
                  <div className="text-center py-4 text-muted-foreground">加载中...</div>
                ) : folders.length === 0 ? (
                  <div className="text-center py-4 text-muted-foreground">暂无文件夹</div>
                ) : (
                  folders.map((node) => renderFolderNode(node))
                )}
              </div>
            </ScrollArea>
          )}

          {/* 提示信息 */}
          <div className="flex items-start gap-2 p-3 bg-blue-50 dark:bg-blue-950 rounded-md text-sm text-blue-700 dark:text-blue-300">
            <Info className="h-4 w-4 shrink-0 mt-0.5" />
            <span>
              选中的文件夹将从当前位置移动到{moveType === "root" ? "根目录" : "上方选中的文件夹"}下。
            </span>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            取消
          </Button>
          <Button onClick={handleConfirmMove} disabled={submitting || (moveType === "specific" && !selectedFolderId)}>
            {submitting ? "移动中..." : "移动文件夹"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
// TODO  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2VDI1b2FRPT06OTE3NmMxMDA=

