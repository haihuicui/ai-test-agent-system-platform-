"use client";
// TODO  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2Y2xWWmFnPT06NTI3YWM2YmY=

import * as React from "react";
import {
  ChevronRight,
  ChevronDown,
  Folder,
  FolderOpen,
  Plus,
  MoreVertical,
  Pencil,
  Trash2,
  FolderPlus,
  Copy,
  Move,
  Link,
  Share2,
  ChevronsDownUp,
  ChevronsUpDown,
  GripVertical,
  FileCode,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  DndContext,
  DragOverlay,
  closestCenter,
  PointerSensor,
  useSensor,
  useSensors,
  DragStartEvent,
  DragEndEvent,
  DragOverEvent,
} from "@dnd-kit/core";
import {
  useSortable,
  SortableContext,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { getFolders, moveFolder as moveFolderApi, copyFolder as copyFolderApi, type FolderTreeNode } from "@/lib/api/folders";
import type { FolderInfo } from "@/lib/api/types";
import { toast } from "sonner";
// TODO  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2Y2xWWmFnPT06NTI3YWM2YmY=

interface APIFolderTreeProps {
  projectId: string;
  selectedFolderId?: string | null;
  onSelectFolder: (folder: FolderInfo | null) => void;
  onCreateFolder: (parentId?: string) => void;
  onEditFolder: (folder: FolderInfo) => void;
  onDeleteFolder: (folder: FolderInfo) => void;
  onMoveFolder?: (folder: FolderInfo) => void;
  onCreateAPIEndpoint: (folderId?: string | null) => void;
  onSelectAPIEndpoint: (endpointId: string) => void;
  selectedAPIEndpointId?: string | null;
}

// 暴露给父组件的方法
export interface APIFolderTreeRef {
  refresh: () => void;
  updateFolderLocally: (folderId: string, updates: Partial<FolderInfo>) => void;
  removeFolderLocally: (folderId: string) => void;
  addFolderLocally: (folder: FolderInfo, parentId: string | null) => void;
  moveFolderLocally: (folderId: string, newParentId: string | null, updatedFolder: FolderInfo) => void;
}
// WATERMARK  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2Y2xWWmFnPT06NTI3YWM2YmY=

// API 测试文件夹类型常量
const API_TEST_FOLDER_TYPE = "api_test";

export const APIFolderTree = React.forwardRef<APIFolderTreeRef, APIFolderTreeProps>(function APIFolderTree({
  projectId,
  selectedFolderId,
  onSelectFolder,
  onCreateFolder,
  onEditFolder,
  onDeleteFolder,
  onMoveFolder,
  onCreateAPIEndpoint,
  onSelectAPIEndpoint,
  selectedAPIEndpointId,
}, ref) {
  const [folders, setFolders] = React.useState<FolderTreeNode[]>([]);
  const [expandedIds, setExpandedIds] = React.useState<Set<string>>(new Set());
  const [loading, setLoading] = React.useState(true);
  const [activeId, setActiveId] = React.useState<string | null>(null);

  // 拖动状态
  const [dropState, setDropState] = React.useState<{
    overId: string | null;
    dropPosition: 'before' | 'after' | 'inside' | null;
  }>({ overId: null, dropPosition: null });

  // 用于节流的 ref
  const lastDropStateRef = React.useRef(dropState);
  const rafIdRef = React.useRef<number | null>(null);

  // 配置拖动传感器
  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 8,
      },
    })
  );

  // 计算文件夹及其所有子文件夹的总端点数
  const calculateTotalEndpoints = (node: FolderTreeNode): number => {
    let total = node.api_endpoints?.length || 0;
    if (node.children) {
      for (const child of node.children) {
        total += calculateTotalEndpoints(child);
      }
    }
    return total;
  };

  // 加载根文件夹
  const loadRootFolders = React.useCallback(async () => {
    try {
      setLoading(true);
      const response = await getFolders(projectId, API_TEST_FOLDER_TYPE);
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
  }, [projectId]);

  React.useEffect(() => {
    if (projectId) {
      loadRootFolders();
    }
  }, [projectId, loadRootFolders]);

  // 加载子文件夹
  const loadChildren = async (folderId: string) => {
    try {
      const response = await getFolders(projectId, API_TEST_FOLDER_TYPE, folderId);
      if (response.success && response.data) {
        const updatedFolder = response.data.find((f) => f.id === folderId);
        setFolders((prev) =>
          updateFolderWithChildren(prev, folderId, response.data, updatedFolder)
        );
      }
    } catch (error) {
      console.error("Failed to load children:", error);
    }
  };

  // 更新文件夹及其子节点
  const updateFolderWithChildren = (
    nodes: FolderTreeNode[],
    parentId: string,
    children: FolderInfo[],
    updatedFolder?: FolderInfo
  ): FolderTreeNode[] => {
    return nodes.map((node) => {
      if (node.id === parentId) {
        return {
          ...node,
          ...(updatedFolder && {
            api_endpoints: updatedFolder.api_endpoints,
          }),
          children: children.filter((c) => c.id !== parentId).map((c) => ({
            ...c,
            children: undefined,
            loading: false,
            expanded: false,
          })),
          loading: false,
        };
      }
      if (node.children) {
        return {
          ...node,
          children: updateFolderWithChildren(node.children, parentId, children, updatedFolder),
        };
      }
      return node;
    });
  };

  // 切换展开/折叠
  const toggleExpand = async (folder: FolderTreeNode) => {
    const newExpanded = new Set(expandedIds);
    if (newExpanded.has(folder.id)) {
      newExpanded.delete(folder.id);
    } else {
      newExpanded.add(folder.id);
      if (!folder.children && folder.sub_folders_count > 0) {
        await loadChildren(folder.id);
      }
    }
    setExpandedIds(newExpanded);
  };

  // 递归收集所有子文件夹 ID
  const collectAllChildIds = (node: FolderTreeNode): string[] => {
    const ids: string[] = [node.id];
    if (node.children) {
      for (const child of node.children) {
        ids.push(...collectAllChildIds(child));
      }
    }
    return ids;
  };

  // 递归加载所有子文件夹
  const loadAllChildren = async (node: FolderTreeNode): Promise<void> => {
    if (node.sub_folders_count > 0 && !node.children) {
      await loadChildren(node.id);
    }
    const findNode = (nodes: FolderTreeNode[], id: string): FolderTreeNode | null => {
      for (const n of nodes) {
        if (n.id === id) return n;
        if (n.children) {
          const found = findNode(n.children, id);
          if (found) return found;
        }
      }
      return null;
    };
    const updatedNode = findNode(folders, node.id);
    if (updatedNode?.children) {
      for (const child of updatedNode.children) {
        await loadAllChildren(child);
      }
    }
  };

  // 展开全部
  const handleExpandAll = async (folder: FolderTreeNode) => {
    await loadAllChildren(folder);
    const newExpanded = new Set(expandedIds);
    const allIds = collectAllChildIds(folder);
    allIds.forEach((id) => newExpanded.add(id));
    setExpandedIds(newExpanded);
    toast.success("已展开全部文件夹");
  };

  // 折叠全部
  const handleCollapseAll = (folder: FolderTreeNode) => {
    const newExpanded = new Set(expandedIds);
    const allIds = collectAllChildIds(folder);
    allIds.forEach((id) => newExpanded.delete(id));
    setExpandedIds(newExpanded);
    toast.success("已折叠全部文件夹");
  };

  // 复制文件夹 URL
  const handleCopyFolderURL = (folder: FolderInfo) => {
    const url = `${window.location.origin}${window.location.pathname}?folder=${folder.id}`;
    navigator.clipboard.writeText(url).then(() => {
      toast.success("文件夹 URL 已复制到剪贴板");
    }).catch(() => {
      toast.error("复制失败");
    });
  };

  // 通过公共链接分享
  const handleShareViaPublicLink = (folder: FolderInfo) => {
    toast.info("公共链接分享功能开发中");
  };

  // 拖动开始
  const handleDragStart = (event: DragStartEvent) => {
    setActiveId(event.active.id as string);
  };

  // 跟踪鼠标位置
  const mousePositionRef = React.useRef<{ x: number; y: number }>({ x: 0, y: 0 });

  React.useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      mousePositionRef.current = { x: e.clientX, y: e.clientY };
    };
    document.addEventListener('mousemove', handleMouseMove);
    return () => document.removeEventListener('mousemove', handleMouseMove);
  }, []);

  // 拖动经过
  const handleDragOver = React.useCallback((event: DragOverEvent) => {
    const { over } = event;

    if (rafIdRef.current) {
      cancelAnimationFrame(rafIdRef.current);
    }

    if (!over) {
      if (lastDropStateRef.current.overId !== null || lastDropStateRef.current.dropPosition !== null) {
        const newState = { overId: null, dropPosition: null };
        lastDropStateRef.current = newState;
        setDropState(newState);
      }
      return;
    }

    const newOverId = over.id as string;

    const overElement = document.querySelector(`[data-folder-id="${over.id}"]`);
    let newPosition: 'before' | 'after' | 'inside' = 'inside';

    if (overElement) {
      const rect = overElement.getBoundingClientRect();
      const mouseY = mousePositionRef.current.y;
      const relativeY = mouseY - rect.top;
      const height = rect.height;

      if (relativeY < height * 0.3) {
        newPosition = 'before';
      } else if (relativeY > height * 0.7) {
        newPosition = 'after';
      } else {
        newPosition = 'inside';
      }
    }

    if (lastDropStateRef.current.overId !== newOverId || lastDropStateRef.current.dropPosition !== newPosition) {
      rafIdRef.current = requestAnimationFrame(() => {
        const newState = { overId: newOverId, dropPosition: newPosition };
        lastDropStateRef.current = newState;
        setDropState(newState);
      });
    }
  }, []);

  // 拖动结束
  const handleDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event;
    const position = lastDropStateRef.current.dropPosition;

    if (rafIdRef.current) {
      cancelAnimationFrame(rafIdRef.current);
      rafIdRef.current = null;
    }

    const resetState = { overId: null, dropPosition: null };
    lastDropStateRef.current = resetState;
    setDropState(resetState);
    setActiveId(null);

    if (!over || active.id === over.id) {
      return;
    }

    const activeFolder = findFolderById(folders, active.id as string);
    const overFolder = findFolderById(folders, over.id as string);

    if (!activeFolder || !overFolder) {
      return;
    }

    try {
      let targetParentId: string | null = null;
      let message = "";

      if (position === 'inside') {
        targetParentId = overFolder.id;
        message = `已将 "${activeFolder.name}" 移动到 "${overFolder.name}" 下`;
      } else {
        targetParentId = overFolder.parent_id || null;
        message = position === 'before'
          ? `已将 "${activeFolder.name}" 移动到 "${overFolder.name}" 上方`
          : `已将 "${activeFolder.name}" 移动到 "${overFolder.name}" 下方`;
      }

      const response = await moveFolderApi(projectId, activeFolder.id, targetParentId);

      if (response.success) {
        toast.success(message);
        updateTreeAfterMove(activeFolder.id, targetParentId, response.data);
      } else {
        toast.error("移动文件夹失败");
      }
    } catch (error) {
      console.error("移动文件夹失败:", error);
      toast.error("移动文件夹失败");
    }
  };

  // 本地更新树结构（移动后）
  const updateTreeAfterMove = (
    movedFolderId: string,
    newParentId: string | null,
    updatedFolder: FolderInfo
  ) => {
    setFolders((prev) => {
      const removeFolder = (nodes: FolderTreeNode[]): FolderTreeNode[] => {
        return nodes.filter((node) => {
          if (node.id === movedFolderId) return false;
          if (node.children) {
            node.children = removeFolder(node.children);
          }
          return true;
        });
      };

      const newNode: FolderTreeNode = {
        ...updatedFolder,
        children: findFolderById(prev, movedFolderId)?.children,
        loading: false,
        expanded: expandedIds.has(movedFolderId),
      };

      const addFolder = (nodes: FolderTreeNode[], parentId: string | null): FolderTreeNode[] => {
        if (parentId === null) {
          return [...removeFolder(nodes), newNode];
        }
        return nodes.map((node) => {
          if (node.id === parentId) {
            return {
              ...node,
              children: [...(node.children || []), newNode],
              sub_folders_count: (node.sub_folders_count || 0) + 1,
            };
          }
          if (node.children) {
            return { ...node, children: addFolder(node.children, parentId) };
          }
          return node;
        });
      };

      const withoutMoved = removeFolder(prev);
      return addFolder(withoutMoved, newParentId);
    });

    if (newParentId) {
      setExpandedIds((prev) => {
        const newSet = new Set(prev);
        newSet.add(newParentId);
        return newSet;
      });
    }
  };

  // 查找文件夹
  const findFolderById = (
    nodes: FolderTreeNode[],
    id: string
  ): FolderTreeNode | null => {
    for (const node of nodes) {
      if (node.id === id) return node;
      if (node.children) {
        const found = findFolderById(node.children, id);
        if (found) return found;
      }
    }
    return null;
  };

  // 本地添加复制后的文件夹
  const addCopiedFolderToTree = (copiedFolder: FolderInfo, parentId: string | null) => {
    const newNode: FolderTreeNode = {
      ...copiedFolder,
      children: undefined,
      loading: false,
      expanded: false,
    };

    setFolders((prev) => {
      if (parentId === null) {
        return [...prev, newNode];
      }

      const addToParent = (nodes: FolderTreeNode[]): FolderTreeNode[] => {
        return nodes.map((node) => {
          if (node.id === parentId) {
            return {
              ...node,
              children: [...(node.children || []), newNode],
              sub_folders_count: (node.sub_folders_count || 0) + 1,
            };
          }
          if (node.children) {
            return { ...node, children: addToParent(node.children) };
          }
          return node;
        });
      };
      return addToParent(prev);
    });

    if (parentId) {
      setExpandedIds((prev) => {
        const newSet = new Set(prev);
        newSet.add(parentId);
        return newSet;
      });
    }
  };

  // 复制文件夹
  const handleCopyFolderInternal = async (folder: FolderInfo) => {
    try {
      const response = await copyFolderApi(projectId, folder.id);
      if (response.success && response.data) {
        toast.success(`文件夹 "${folder.name}" 复制成功`);
        addCopiedFolderToTree(response.data, folder.parent_id || null);
      } else {
        toast.error("复制文件夹失败");
      }
    } catch (error) {
      console.error("Failed to copy folder:", error);
      toast.error("复制文件夹失败");
    }
  };

  // 递归重新加载已展开的文件夹
  const reloadExpandedFolders = async (nodes: FolderTreeNode[]): Promise<FolderTreeNode[]> => {
    const reloadedNodes: FolderTreeNode[] = [];

    for (const node of nodes) {
      const isExpanded = expandedIds.has(node.id);
      let children: FolderTreeNode[] | undefined = undefined;

      if (isExpanded && node.sub_folders_count > 0) {
        try {
          const response = await getFolders(projectId, API_TEST_FOLDER_TYPE, node.id);
          if (response.success && response.data) {
            const updatedFolder = response.data.find((f) => f.id === node.id);

            const childNodes = response.data.filter((c) => c.parent_id === node.id).map((c) => ({
              ...c,
              children: undefined,
              loading: false,
              expanded: false,
            }));
            children = await reloadExpandedFolders(childNodes);

            reloadedNodes.push({
              ...node,
              ...(updatedFolder && {
                api_endpoints: updatedFolder.api_endpoints,
              }),
              children,
              loading: false,
              expanded: isExpanded,
            });
            continue;
          }
        } catch (error) {
          console.error(`Failed to reload children for folder ${node.id}:`, error);
        }
      }

      reloadedNodes.push({
        ...node,
        children,
        loading: false,
        expanded: isExpanded,
      });
    }

    return reloadedNodes;
  };

  // 刷新文件夹树
  const refresh = async () => {
    try {
      setLoading(true);
      const response = await getFolders(projectId, API_TEST_FOLDER_TYPE);
      if (response.success && response.data) {
        const rootFolders = response.data.filter(
          (f) => f.parent_id === null || f.parent_id === undefined
        );

        const rootNodes = rootFolders.map((f) => ({
          ...f,
          children: undefined,
          loading: false,
          expanded: false,
        }));

        const reloadedNodes = await reloadExpandedFolders(rootNodes);
        setFolders(reloadedNodes);
      }
    } catch (error) {
      console.error("Failed to refresh folders:", error);
    } finally {
      setLoading(false);
    }
  };

  // 本地更新单个文件夹
  const updateFolderLocally = (folderId: string, updates: Partial<FolderInfo>) => {
    setFolders((prev) => {
      const updateNode = (nodes: FolderTreeNode[]): FolderTreeNode[] => {
        return nodes.map((node) => {
          if (node.id === folderId) {
            return { ...node, ...updates };
          }
          if (node.children) {
            return { ...node, children: updateNode(node.children) };
          }
          return node;
        });
      };
      return updateNode(prev);
    });
  };

  // 本地删除文件夹
  const removeFolderLocally = (folderId: string) => {
    setFolders((prev) => {
      const removeNode = (nodes: FolderTreeNode[]): FolderTreeNode[] => {
        return nodes.filter((node) => {
          if (node.id === folderId) return false;
          if (node.children) {
            node.children = removeNode(node.children);
          }
          return true;
        });
      };
      return removeNode(prev);
    });
  };

  // 本地添加文件夹
  const addFolderLocally = (folder: FolderInfo, parentId: string | null) => {
    const newNode: FolderTreeNode = {
      ...folder,
      children: undefined,
      loading: false,
      expanded: false,
    };

    setFolders((prev) => {
      if (parentId === null) {
        return [...prev, newNode];
      }
      const addToParent = (nodes: FolderTreeNode[]): FolderTreeNode[] => {
        return nodes.map((node) => {
          if (node.id === parentId) {
            return {
              ...node,
              children: [...(node.children || []), newNode],
              sub_folders_count: (node.sub_folders_count || 0) + 1,
            };
          }
          if (node.children) {
            return { ...node, children: addToParent(node.children) };
          }
          return node;
        });
      };
      return addToParent(prev);
    });

    if (parentId) {
      setExpandedIds((prev) => {
        const newSet = new Set(prev);
        newSet.add(parentId);
        return newSet;
      });
    }
  };

  // 本地移动文件夹
  const moveFolderLocally = (folderId: string, newParentId: string | null, updatedFolder: FolderInfo) => {
    updateTreeAfterMove(folderId, newParentId, updatedFolder);
  };

  // 暴露方法给父组件
  React.useImperativeHandle(ref, () => ({
    refresh,
    updateFolderLocally,
    removeFolderLocally,
    addFolderLocally,
    moveFolderLocally,
  }));

  // 可拖动的文件夹节点组件
  const DraggableFolderNode = ({
    node,
    level,
  }: {
    node: FolderTreeNode;
    level: number;
  }) => {
    const {
      attributes,
      listeners,
      setNodeRef,
      transform,
      transition,
      isDragging,
    } = useSortable({ id: node.id });

    const style = {
      transform: CSS.Transform.toString(transform),
      transition,
      opacity: isDragging ? 0.5 : 1,
    };

    const isExpanded = expandedIds.has(node.id);
    const isSelected = selectedFolderId === node.id;
    const hasChildren = node.sub_folders_count > 0;

    const isDropTarget = dropState.overId === node.id && activeId !== node.id;
    const currentDropPosition = isDropTarget ? dropState.dropPosition : null;

    return (
      <div key={node.id}>
        {/* 上方放置指示器 */}
        {isDropTarget && currentDropPosition === 'before' && (
          <div className="h-0.5 bg-primary mb-1" style={{ marginLeft: `${level * 12 + 8}px` }} />
        )}

        <div
          ref={setNodeRef}
          style={style}
          data-folder-id={node.id}
          className={cn(
            "group relative grid rounded-md py-1.5 text-sm hover:bg-accent transition-colors",
            isSelected && "bg-accent",
            isDropTarget && currentDropPosition === 'inside' && "bg-primary/10 ring-2 ring-primary"
          )}
        >
          <div
            className="flex items-center col-start-1"
            style={{
              display: 'grid',
              gridTemplateColumns: `${level * 12}px 20px 20px minmax(0, 1fr) 50px`,
              alignItems: 'center',
              paddingRight: '8px',
              paddingLeft: '8px',
            }}
          >
            {/* 1. 缩进占位 */}
            <div />

            {/* 2. 拖动手柄 */}
            <div
              {...attributes}
              {...listeners}
              className="cursor-grab active:cursor-grabbing opacity-0 group-hover:opacity-100 flex items-center justify-center"
            >
              <GripVertical className="h-4 w-4 text-muted-foreground" />
            </div>

            {/* 3. 展开/折叠按钮 */}
            <Button
              variant="ghost"
              size="icon"
              className="h-5 w-5 p-0"
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

            {/* 4. 文件夹图标 + 名称 + 菜单 */}
            <div className="flex items-center gap-1 min-w-0 overflow-hidden">
              <div
                className="flex cursor-pointer items-center gap-1 min-w-0 overflow-hidden"
                onClick={() => onSelectFolder(node)}
              >
                {isExpanded ? (
                  <FolderOpen className="h-4 w-4 shrink-0 text-primary" />
                ) : (
                  <Folder className="h-4 w-4 shrink-0 text-primary" />
                )}
                <Tooltip>
                  <TooltipTrigger asChild>
                    <span className="truncate">{node.name}</span>
                  </TooltipTrigger>
                  <TooltipContent side="bottom" className="max-w-xs">
                    <p className="break-words">{node.name}</p>
                  </TooltipContent>
                </Tooltip>
              </div>

              {/* 三点菜单 */}
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-5 w-5 shrink-0 opacity-0 group-hover:opacity-100 p-0"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <MoreVertical className="h-3.5 w-3.5" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="start" className="w-48">
                  {/* 展开/折叠 */}
                  <DropdownMenuItem
                    onClick={() => handleExpandAll(node)}
                    disabled={!hasChildren}
                  >
                    <ChevronsUpDown className="mr-2 h-4 w-4" />
                    展开全部
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    onClick={() => handleCollapseAll(node)}
                    disabled={!hasChildren}
                  >
                    <ChevronsDownUp className="mr-2 h-4 w-4" />
                    折叠全部
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  {/* 创建操作 */}
                  <DropdownMenuItem onClick={() => onCreateAPIEndpoint(node.id)}>
                    <FileCode className="mr-2 h-4 w-4" />
                    创建接口
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => onCreateFolder(node.id)}>
                    <FolderPlus className="mr-2 h-4 w-4" />
                    添加子文件夹
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  {/* 文件夹操作 */}
                  <DropdownMenuItem onClick={() => handleCopyFolderInternal(node)}>
                    <Copy className="mr-2 h-4 w-4" />
                    复制文件夹
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => onMoveFolder?.(node)}>
                    <Move className="mr-2 h-4 w-4" />
                    移动文件夹
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => onEditFolder(node)}>
                    <Pencil className="mr-2 h-4 w-4" />
                    编辑文件夹
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  {/* 链接操作 */}
                  <DropdownMenuItem onClick={() => handleCopyFolderURL(node)}>
                    <Link className="mr-2 h-4 w-4" />
                    复制文件夹 URL
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => handleShareViaPublicLink(node)}>
                    <Share2 className="mr-2 h-4 w-4" />
                    通过公共链接分享
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  {/* 删除 */}
                  <DropdownMenuItem
                    className="text-destructive focus:text-destructive"
                    onClick={() => onDeleteFolder(node)}
                  >
                    <Trash2 className="mr-2 h-4 w-4" />
                    删除
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>

            {/* 5. 统计数字 - 显示端点数 */}
            <div className="text-xs text-muted-foreground text-right whitespace-nowrap">
              {node.api_endpoints?.length || 0}({calculateTotalEndpoints(node)})
            </div>
          </div>
        </div>

        {/* 下方放置指示器 */}
        {isDropTarget && currentDropPosition === 'after' && (
          <div className="h-0.5 bg-primary mt-1" style={{ marginLeft: `${level * 12 + 8}px` }} />
        )}

        {/* 子节点 */}
        {isExpanded && node.children && (
          <div>
            {node.children.map((child) => (
              <DraggableFolderNode key={child.id} node={child} level={level + 1} />
            ))}
          </div>
        )}

        {/* API 端点节点 */}
        {isExpanded && node.api_endpoints && node.api_endpoints.length > 0 && (
          <div>
            {node.api_endpoints.map((endpoint) => (
              <div
                key={endpoint.id}
                className={cn(
                  "group grid rounded-md py-1.5 text-sm hover:bg-accent transition-colors cursor-pointer",
                  selectedAPIEndpointId === endpoint.id && "bg-accent"
                )}
                style={{
                  display: 'grid',
                  gridTemplateColumns: `${(level + 1) * 12}px 20px 20px minmax(0, 1fr) 50px`,
                  alignItems: 'center',
                  paddingRight: '8px',
                  paddingLeft: '8px',
                }}
                onClick={() => onSelectAPIEndpoint(endpoint.id)}
              >
                {/* 1. 缩进占位 */}
                <div />

                {/* 2. 拖动手柄占位 */}
                <div />

                {/* 3. 展开/折叠按钮占位 */}
                <div className="flex items-center justify-center">
                  <span className="w-4" />
                </div>

                {/* 4. 端点图标 + 名称 */}
                <div className="flex items-center gap-1.5 min-w-0 overflow-hidden">
                  <FileCode className="h-4 w-4 shrink-0 text-blue-500" />
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <span className="truncate text-xs">{endpoint.display_name}</span>
                    </TooltipTrigger>
                    <TooltipContent side="bottom" className="max-w-xs">
                      <p className="break-words">{endpoint.display_name}</p>
                    </TooltipContent>
                  </Tooltip>
                </div>

                {/* 5. 统计数字 */}
                <div className="text-xs text-muted-foreground text-right whitespace-nowrap">
                  {endpoint.total_test_cases || 0}({endpoint.total_test_runs || 0})
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  };

  // 获取所有文件夹ID
  const getAllFolderIds = (nodes: FolderTreeNode[]): string[] => {
    const ids: string[] = [];
    for (const node of nodes) {
      ids.push(node.id);
      if (node.children) {
        ids.push(...getAllFolderIds(node.children));
      }
    }
    return ids;
  };

  return (
    <TooltipProvider delayDuration={300}>
      <div className="flex h-full flex-col border-r">
        {/* 头部 */}
        <div className="flex items-center justify-between border-b p-3">
          <h3 className="font-medium">文件夹</h3>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7"
              >
                <Plus className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => onCreateFolder()}>
                <FolderPlus className="mr-2 h-4 w-4" />
                创建文件夹
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => onCreateAPIEndpoint()}>
                <FileCode className="mr-2 h-4 w-4" />
                创建接口
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        {/* 文件夹树 */}
        <ScrollArea className="flex-1">
          <DndContext
            sensors={sensors}
            collisionDetection={closestCenter}
            onDragStart={handleDragStart}
            onDragOver={handleDragOver}
            onDragEnd={handleDragEnd}
          >
            <div className="p-2">
              {/* 全部用例 */}
              <div
                className={cn(
                  "flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-accent",
                  selectedFolderId === null && "bg-accent"
                )}
                onClick={() => onSelectFolder(null)}
              >
                <Folder className="h-4 w-4 text-muted-foreground" />
                <span>全部接口</span>
              </div>

              {/* 文件夹列表 */}
              {loading ? (
                <div className="py-4 text-center text-sm text-muted-foreground">
                  加载中...
                </div>
              ) : folders.length === 0 ? (
                <div className="py-4 text-center text-sm text-muted-foreground">
                  暂无文件夹
                </div>
              ) : (
                <SortableContext
                  items={getAllFolderIds(folders)}
                  strategy={verticalListSortingStrategy}
                >
                  {folders.map((folder) => (
                    <DraggableFolderNode key={folder.id} node={folder} level={0} />
                  ))}
                </SortableContext>
              )}
            </div>

            {/* 拖动覆盖层 */}
            <DragOverlay>
              {activeId ? (
                <div className="rounded-md bg-accent p-2 shadow-lg">
                  <div className="flex items-center gap-2">
                    <Folder className="h-4 w-4 text-primary" />
                    <span className="text-sm font-medium">
                      {findFolderById(folders, activeId)?.name}
                    </span>
                  </div>
                </div>
              ) : null}
            </DragOverlay>
          </DndContext>
        </ScrollArea>
      </div>
    </TooltipProvider>
  );
});
// FIXME  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2Y2xWWmFnPT06NTI3YWM2YmY=
