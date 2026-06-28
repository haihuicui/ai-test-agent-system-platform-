"use client";
// NOTE  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2YlhoQ2R3PT06YmQxZWRiMjQ=

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
import type { AndroidFunction } from "@/lib/api/android-tests";
import { toast } from "sonner";

interface AndroidFunctionFolderTreeProps {
  projectId: string;
  selectedFolderId?: string | null;
  onSelectFolder: (folder: FolderInfo | null) => void;
  onCreateFolder: (parentId?: string) => void;
  onEditFolder: (folder: FolderInfo) => void;
  onDeleteFolder: (folder: FolderInfo) => void;
  onMoveFolder?: (folder: FolderInfo) => void;
  onCreateAndroidFunction: (folderId?: string | null) => void;
  onSelectAndroidFunction: (functionId: string) => void;
  selectedAndroidFunctionId?: string | null;
}
// eslint-disable  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2YlhoQ2R3PT06YmQxZWRiMjQ=

export interface AndroidFunctionFolderTreeRef {
  refresh: () => void;
  updateFolderLocally: (folderId: string, updates: Partial<FolderInfo>) => void;
  removeFolderLocally: (folderId: string) => void;
  addFolderLocally: (folder: FolderInfo, parentId: string | null) => void;
  moveFolderLocally: (folderId: string, newParentId: string | null, updatedFolder: FolderInfo) => void;
}
// FIXME  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2YlhoQ2R3PT06YmQxZWRiMjQ=

const ANDROID_TEST_FOLDER_TYPE = "android_test";
// NOTE  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2YlhoQ2R3PT06YmQxZWRiMjQ=

export const AndroidFunctionFolderTree = React.forwardRef<AndroidFunctionFolderTreeRef, AndroidFunctionFolderTreeProps>(
  function AndroidFunctionFolderTree({
    projectId,
    selectedFolderId,
    onSelectFolder,
    onCreateFolder,
    onEditFolder,
    onDeleteFolder,
    onMoveFolder,
    onCreateAndroidFunction,
    onSelectAndroidFunction,
    selectedAndroidFunctionId,
  }, ref) {
    const [folders, setFolders] = React.useState<FolderTreeNode[]>([]);
    const [expandedIds, setExpandedIds] = React.useState<Set<string>>(new Set());
    const [loading, setLoading] = React.useState(true);
    const [activeId, setActiveId] = React.useState<string | null>(null);
    const [dropState, setDropState] = React.useState<{ overId: string | null; dropPosition: 'before' | 'after' | 'inside' | null }>({ overId: null, dropPosition: null });
    const lastDropStateRef = React.useRef(dropState);
    const rafIdRef = React.useRef<number | null>(null);

    const sensors = useSensors(
      useSensor(PointerSensor, { activationConstraint: { distance: 8 } })
    );

    const loadRootFolders = React.useCallback(async () => {
      try {
        setLoading(true);
        const response = await getFolders(projectId, ANDROID_TEST_FOLDER_TYPE);
        if (response.success && response.data) {
          const rootFolders = response.data.filter((f) => f.parent_id === null || f.parent_id === undefined);
          setFolders(rootFolders.map((f) => ({ ...f, children: undefined, loading: false, expanded: false })));
        }
      } catch (error) {
        console.error("Failed to load folders:", error);
      } finally {
        setLoading(false);
      }
    }, [projectId]);

    React.useEffect(() => {
      if (projectId) loadRootFolders();
    }, [projectId, loadRootFolders]);

    const loadChildren = async (folderId: string) => {
      try {
        const response = await getFolders(projectId, ANDROID_TEST_FOLDER_TYPE, folderId);
        if (response.success && response.data) {
          const updatedFolder = response.data.find((f) => f.id === folderId);
          setFolders((prev) => updateFolderWithChildren(prev, folderId, response.data, updatedFolder));
        }
      } catch (error) {
        console.error("Failed to load children:", error);
      }
    };

    const updateFolderWithChildren = (nodes: FolderTreeNode[], parentId: string, children: FolderInfo[], updatedFolder?: FolderInfo): FolderTreeNode[] => {
      return nodes.map((node) => {
        if (node.id === parentId) {
          return { ...node, ...(updatedFolder && { web_functions: updatedFolder.web_functions }), children: children.filter((c) => c.id !== parentId).map((c) => ({ ...c, children: undefined, loading: false, expanded: false })), loading: false };
        }
        if (node.children) {
          return { ...node, children: updateFolderWithChildren(node.children, parentId, children, updatedFolder) };
        }
        return node;
      });
    };

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

    const collectAllChildIds = (node: FolderTreeNode): string[] => {
      const ids: string[] = [node.id];
      if (node.children) {
        for (const child of node.children) ids.push(...collectAllChildIds(child));
      }
      return ids;
    };

    const handleExpandAll = async (folder: FolderTreeNode) => {
      const loadAllChildren = async (node: FolderTreeNode): Promise<void> => {
        if (node.sub_folders_count > 0 && !node.children) await loadChildren(node.id);
        const findNode = (nodes: FolderTreeNode[], id: string): FolderTreeNode | null => {
          for (const n of nodes) { if (n.id === id) return n; if (n.children) { const found = findNode(n.children, id); if (found) return found; } }
          return null;
        };
        const updatedNode = findNode(folders, node.id);
        if (updatedNode?.children) { for (const child of updatedNode.children) await loadAllChildren(child); }
      };
      await loadAllChildren(folder);
      const newExpanded = new Set(expandedIds);
      collectAllChildIds(folder).forEach((id) => newExpanded.add(id));
      setExpandedIds(newExpanded);
    };

    const handleCollapseAll = (folder: FolderTreeNode) => {
      const newExpanded = new Set(expandedIds);
      collectAllChildIds(folder).forEach((id) => newExpanded.delete(id));
      setExpandedIds(newExpanded);
    };

    const handleCopyFolderURL = (folder: FolderInfo) => {
      const url = `${window.location.origin}${window.location.pathname}?folder=${folder.id}`;
      navigator.clipboard.writeText(url).then(() => toast.success("文件夹 URL 已复制")).catch(() => toast.error("复制失败"));
    };

    const handleShareViaPublicLink = (folder: FolderInfo) => {
      toast.info("公共链接分享功能开发中");
    };

    const handleDragStart = (event: DragStartEvent) => setActiveId(event.active.id as string);

    const mousePositionRef = React.useRef<{ x: number; y: number }>({ x: 0, y: 0 });
    React.useEffect(() => {
      const handleMouseMove = (e: MouseEvent) => { mousePositionRef.current = { x: e.clientX, y: e.clientY }; };
      document.addEventListener('mousemove', handleMouseMove);
      return () => document.removeEventListener('mousemove', handleMouseMove);
    }, []);

    const handleDragOver = React.useCallback((event: DragOverEvent) => {
      const { over } = event;
      if (rafIdRef.current) cancelAnimationFrame(rafIdRef.current);
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
        const relativeY = mousePositionRef.current.y - rect.top;
        const height = rect.height;
        if (relativeY < height * 0.3) newPosition = 'before';
        else if (relativeY > height * 0.7) newPosition = 'after';
      }
      if (lastDropStateRef.current.overId !== newOverId || lastDropStateRef.current.dropPosition !== newPosition) {
        rafIdRef.current = requestAnimationFrame(() => {
          const newState = { overId: newOverId, dropPosition: newPosition };
          lastDropStateRef.current = newState;
          setDropState(newState);
        });
      }
    }, []);

    const handleDragEnd = async (event: DragEndEvent) => {
      const { active, over } = event;
      const position = lastDropStateRef.current.dropPosition;
      if (rafIdRef.current) { cancelAnimationFrame(rafIdRef.current); rafIdRef.current = null; }
      const resetState = { overId: null, dropPosition: null };
      lastDropStateRef.current = resetState;
      setDropState(resetState);
      setActiveId(null);
      if (!over || active.id === over.id) return;
      const activeFolder = findFolderById(folders, active.id as string);
      const overFolder = findFolderById(folders, over.id as string);
      if (!activeFolder || !overFolder) return;
      try {
        let targetParentId: string | null = null;
        let message = "";
        if (position === 'inside') { targetParentId = overFolder.id; message = `已将 "${activeFolder.name}" 移动到 "${overFolder.name}" 下`; }
        else { targetParentId = overFolder.parent_id || null; message = position === 'before' ? `已将 "${activeFolder.name}" 移动到 "${overFolder.name}" 上方` : `已将 "${activeFolder.name}" 移动到 "${overFolder.name}" 下方`; }
        const response = await moveFolderApi(projectId, activeFolder.id, targetParentId);
        if (response.success) { toast.success(message); updateTreeAfterMove(activeFolder.id, targetParentId, response.data); }
        else toast.error("移动文件夹失败");
      } catch (error) { console.error("移动文件夹失败:", error); toast.error("移动文件夹失败"); }
    };

    const updateTreeAfterMove = (movedFolderId: string, newParentId: string | null, updatedFolder: FolderInfo) => {
      setFolders((prev) => {
        const removeFolder = (nodes: FolderTreeNode[]): FolderTreeNode[] => {
          return nodes.filter((node) => { if (node.id === movedFolderId) return false; if (node.children) node.children = removeFolder(node.children); return true; });
        };
        const newNode: FolderTreeNode = { ...updatedFolder, children: findFolderById(prev, movedFolderId)?.children, loading: false, expanded: expandedIds.has(movedFolderId) };
        const addFolder = (nodes: FolderTreeNode[], parentId: string | null): FolderTreeNode[] => {
          if (parentId === null) return [...removeFolder(nodes), newNode];
          return nodes.map((node) => {
            if (node.id === parentId) return { ...node, children: [...(node.children || []), newNode], sub_folders_count: (node.sub_folders_count || 0) + 1 };
            if (node.children) return { ...node, children: addFolder(node.children, parentId) };
            return node;
          });
        };
        const withoutMoved = removeFolder(prev);
        return addFolder(withoutMoved, newParentId);
      });
      if (newParentId) setExpandedIds((prev) => { const newSet = new Set(prev); newSet.add(newParentId); return newSet; });
    };

    const findFolderById = (nodes: FolderTreeNode[], id: string): FolderTreeNode | null => {
      for (const node of nodes) { if (node.id === id) return node; if (node.children) { const found = findFolderById(node.children, id); if (found) return found; } }
      return null;
    };

    const addCopiedFolderToTree = (copiedFolder: FolderInfo, parentId: string | null) => {
      const newNode: FolderTreeNode = { ...copiedFolder, children: undefined, loading: false, expanded: false };
      setFolders((prev) => {
        if (parentId === null) return [...prev, newNode];
        const addToParent = (nodes: FolderTreeNode[]): FolderTreeNode[] => {
          return nodes.map((node) => {
            if (node.id === parentId) return { ...node, children: [...(node.children || []), newNode], sub_folders_count: (node.sub_folders_count || 0) + 1 };
            if (node.children) return { ...node, children: addToParent(node.children) };
            return node;
          });
        };
        return addToParent(prev);
      });
      if (parentId) setExpandedIds((prev) => { const newSet = new Set(prev); newSet.add(parentId); return newSet; });
    };

    const handleCopyFolderInternal = async (folder: FolderInfo) => {
      try {
        const response = await copyFolderApi(projectId, folder.id);
        if (response.success && response.data) { toast.success(`文件夹 "${folder.name}" 复制成功`); addCopiedFolderToTree(response.data, folder.parent_id || null); }
        else toast.error("复制文件夹失败");
      } catch (error) { console.error("Failed to copy folder:", error); toast.error("复制文件夹失败"); }
    };

    const reloadExpandedFolders = async (nodes: FolderTreeNode[]): Promise<FolderTreeNode[]> => {
      const reloadedNodes: FolderTreeNode[] = [];
      for (const node of nodes) {
        const isExpanded = expandedIds.has(node.id);
        let children: FolderTreeNode[] | undefined = undefined;
        if (isExpanded && node.sub_folders_count > 0) {
          try {
            const response = await getFolders(projectId, ANDROID_TEST_FOLDER_TYPE, node.id);
            if (response.success && response.data) {
              const updatedFolder = response.data.find((f) => f.id === node.id);
              const childNodes = response.data.filter((c) => c.parent_id === node.id).map((c) => ({ ...c, children: undefined, loading: false, expanded: false }));
              children = await reloadExpandedFolders(childNodes);
              reloadedNodes.push({ ...node, ...(updatedFolder && { web_functions: updatedFolder.web_functions }), children, loading: false, expanded: isExpanded });
              continue;
            }
          } catch (error) { console.error(`Failed to reload children for folder ${node.id}:`, error); }
        }
        reloadedNodes.push({ ...node, children, loading: false, expanded: isExpanded });
      }
      return reloadedNodes;
    };

    const refresh = async () => {
      try {
        setLoading(true);
        const response = await getFolders(projectId, ANDROID_TEST_FOLDER_TYPE);
        if (response.success && response.data) {
          const rootFolders = response.data.filter((f) => f.parent_id === null || f.parent_id === undefined);
          const rootNodes = rootFolders.map((f) => ({ ...f, children: undefined, loading: false, expanded: false }));
          const reloadedNodes = await reloadExpandedFolders(rootNodes);
          setFolders(reloadedNodes);
        }
      } catch (error) { console.error("Failed to refresh folders:", error); }
      finally { setLoading(false); }
    };

    const updateFolderLocally = (folderId: string, updates: Partial<FolderInfo>) => {
      setFolders((prev) => {
        const updateNode = (nodes: FolderTreeNode[]): FolderTreeNode[] => {
          return nodes.map((node) => { if (node.id === folderId) return { ...node, ...updates }; if (node.children) return { ...node, children: updateNode(node.children) }; return node; });
        };
        return updateNode(prev);
      });
    };

    const removeFolderLocally = (folderId: string) => {
      setFolders((prev) => {
        const removeNode = (nodes: FolderTreeNode[]): FolderTreeNode[] => {
          return nodes.filter((node) => { if (node.id === folderId) return false; if (node.children) node.children = removeNode(node.children); return true; });
        };
        return removeNode(prev);
      });
    };

    const addFolderLocally = (folder: FolderInfo, parentId: string | null) => {
      const newNode: FolderTreeNode = { ...folder, children: undefined, loading: false, expanded: false };
      setFolders((prev) => {
        if (parentId === null) return [...prev, newNode];
        const addToParent = (nodes: FolderTreeNode[]): FolderTreeNode[] => {
          return nodes.map((node) => { if (node.id === parentId) return { ...node, children: [...(node.children || []), newNode], sub_folders_count: (node.sub_folders_count || 0) + 1 }; if (node.children) return { ...node, children: addToParent(node.children) }; return node; });
        };
        return addToParent(prev);
      });
      if (parentId) setExpandedIds((prev) => { const newSet = new Set(prev); newSet.add(parentId); return newSet; });
    };

    const moveFolderLocally = (folderId: string, newParentId: string | null, updatedFolder: FolderInfo) => {
      updateTreeAfterMove(folderId, newParentId, updatedFolder);
    };

    React.useImperativeHandle(ref, () => ({ refresh, updateFolderLocally, removeFolderLocally, addFolderLocally, moveFolderLocally }));

    const DraggableFolderNode = ({ node, level }: { node: FolderTreeNode; level: number }) => {
      const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: node.id });
      const style = { transform: CSS.Transform.toString(transform), transition, opacity: isDragging ? 0.5 : 1 };
      const isExpanded = expandedIds.has(node.id);
      const isSelected = selectedFolderId === node.id;
      const hasChildren = node.sub_folders_count > 0;
      const isDropTarget = dropState.overId === node.id && activeId !== node.id;
      const currentDropPosition = isDropTarget ? dropState.dropPosition : null;

      return (
        <div key={node.id}>
          {isDropTarget && currentDropPosition === 'before' && <div className="h-0.5 bg-primary mb-1" style={{ marginLeft: `${level * 12 + 8}px` }} />}
          <div ref={setNodeRef} style={style} data-folder-id={node.id} className={cn("group relative grid rounded-md py-1.5 text-sm hover:bg-accent transition-colors", isSelected && "bg-accent", isDropTarget && currentDropPosition === 'inside' && "bg-primary/10 ring-2 ring-primary")}>
            <div className="flex items-center col-start-1" style={{ display: 'grid', gridTemplateColumns: `${level * 12}px 20px 20px minmax(0, 1fr) 50px`, alignItems: 'center', paddingRight: '8px', paddingLeft: '8px' }}>
              <div />
              <div {...attributes} {...listeners} className="cursor-grab active:cursor-grabbing opacity-0 group-hover:opacity-100 flex items-center justify-center">
                <GripVertical className="h-4 w-4 text-muted-foreground" />
              </div>
              <Button variant="ghost" size="icon" className="h-5 w-5 p-0" onClick={(e) => { e.stopPropagation(); if (hasChildren) toggleExpand(node); }}>
                {hasChildren ? (isExpanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />) : <span className="w-4" />}
              </Button>
              <div className="flex items-center gap-1 min-w-0 overflow-hidden">
                <div className="flex cursor-pointer items-center gap-1 min-w-0 overflow-hidden" onClick={() => onSelectFolder(node)}>
                  {isExpanded ? <FolderOpen className="h-4 w-4 shrink-0 text-primary" /> : <Folder className="h-4 w-4 shrink-0 text-primary" />}
                  <Tooltip><TooltipTrigger asChild><span className="truncate">{node.name}</span></TooltipTrigger><TooltipContent side="bottom" className="max-w-xs"><p className="break-words">{node.name}</p></TooltipContent></Tooltip>
                </div>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button variant="ghost" size="icon" className="h-5 w-5 shrink-0 opacity-0 group-hover:opacity-100 p-0" onClick={(e) => e.stopPropagation()}>
                      <MoreVertical className="h-3.5 w-3.5" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="start" className="w-48">
                    <DropdownMenuItem onClick={() => handleExpandAll(node)} disabled={!hasChildren}><ChevronsUpDown className="mr-2 h-4 w-4" />展开全部</DropdownMenuItem>
                    <DropdownMenuItem onClick={() => handleCollapseAll(node)} disabled={!hasChildren}><ChevronsDownUp className="mr-2 h-4 w-4" />折叠全部</DropdownMenuItem>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem onClick={() => onCreateAndroidFunction(node.id)}><FileCode className="mr-2 h-4 w-4" />创建功能</DropdownMenuItem>
                    <DropdownMenuItem onClick={() => onCreateFolder(node.id)}><FolderPlus className="mr-2 h-4 w-4" />添加子文件夹</DropdownMenuItem>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem onClick={() => handleCopyFolderInternal(node)}><Copy className="mr-2 h-4 w-4" />复制文件夹</DropdownMenuItem>
                    <DropdownMenuItem onClick={() => onMoveFolder?.(node)}><Move className="mr-2 h-4 w-4" />移动文件夹</DropdownMenuItem>
                    <DropdownMenuItem onClick={() => onEditFolder(node)}><Pencil className="mr-2 h-4 w-4" />编辑文件夹</DropdownMenuItem>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem onClick={() => handleCopyFolderURL(node)}><Link className="mr-2 h-4 w-4" />复制文件夹 URL</DropdownMenuItem>
                    <DropdownMenuItem onClick={() => handleShareViaPublicLink(node)}><Share2 className="mr-2 h-4 w-4" />通过公共链接分享</DropdownMenuItem>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem className="text-destructive focus:text-destructive" onClick={() => onDeleteFolder(node)}><Trash2 className="mr-2 h-4 w-4" />删除</DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
              <div className="text-xs text-muted-foreground text-right whitespace-nowrap">{node.web_functions?.length || 0}({node.total_sub_functions || 0})</div>
            </div>
          </div>
          {isDropTarget && currentDropPosition === 'after' && <div className="h-0.5 bg-primary mt-1" style={{ marginLeft: `${level * 12 + 8}px` }} />}
          {isExpanded && node.children && <div>{node.children.map((child) => <DraggableFolderNode key={child.id} node={child} level={level + 1} />)}</div>}
          {isExpanded && node.web_functions && node.web_functions.length > 0 && (
            <div>
              {node.web_functions.map((func: any) => (
                <div key={func.id} className={cn("group grid rounded-md py-1.5 text-sm hover:bg-accent transition-colors cursor-pointer", selectedAndroidFunctionId === func.id && "bg-accent")} style={{ display: 'grid', gridTemplateColumns: `${(level + 1) * 12}px 20px 20px minmax(0, 1fr) 50px`, alignItems: 'center', paddingRight: '8px', paddingLeft: '8px' }} onClick={() => onSelectAndroidFunction(func.id)}>
                  <div /><div /><div className="flex items-center justify-center"><span className="w-4" /></div>
                  <div className="flex items-center gap-1.5 min-w-0 overflow-hidden">
                    <FileCode className="h-4 w-4 shrink-0 text-green-500" />
                    <Tooltip><TooltipTrigger asChild><span className="truncate text-xs">{func.display_name}</span></TooltipTrigger><TooltipContent side="bottom" className="max-w-xs"><p className="break-words">{func.display_name}</p></TooltipContent></Tooltip>
                  </div>
                  <div className="text-xs text-muted-foreground text-right whitespace-nowrap">{func.total_sub_functions || 0}({func.total_test_cases || 0})</div>
                </div>
              ))}
            </div>
          )}
        </div>
      );
    };

    const getAllFolderIds = (nodes: FolderTreeNode[]): string[] => {
      const ids: string[] = [];
      for (const node of nodes) { ids.push(node.id); if (node.children) ids.push(...getAllFolderIds(node.children)); }
      return ids;
    };

    return (
      <TooltipProvider delayDuration={300}>
        <div className="flex h-full flex-col border-r">
          <div className="flex items-center justify-between border-b p-3">
            <h3 className="font-medium">文件夹</h3>
            <DropdownMenu>
              <DropdownMenuTrigger asChild><Button variant="ghost" size="icon" className="h-7 w-7"><Plus className="h-4 w-4" /></Button></DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onClick={() => onCreateFolder()}><FolderPlus className="mr-2 h-4 w-4" />创建文件夹</DropdownMenuItem>
                <DropdownMenuItem onClick={() => onCreateAndroidFunction()}><FileCode className="mr-2 h-4 w-4" />创建功能</DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
          <ScrollArea className="flex-1">
            <DndContext sensors={sensors} collisionDetection={closestCenter} onDragStart={handleDragStart} onDragOver={handleDragOver} onDragEnd={handleDragEnd}>
              <div className="p-2">
                <div className={cn("flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-accent", selectedFolderId === null && "bg-accent")} onClick={() => onSelectFolder(null)}>
                  <Folder className="h-4 w-4 text-muted-foreground" /><span>全部功能</span>
                </div>
                {loading ? (
                  <div className="py-4 text-center text-sm text-muted-foreground">加载中...</div>
                ) : folders.length === 0 ? (
                  <div className="py-4 text-center text-sm text-muted-foreground">暂无文件夹</div>
                ) : (
                  <SortableContext items={getAllFolderIds(folders)} strategy={verticalListSortingStrategy}>
                    {folders.map((folder) => <DraggableFolderNode key={folder.id} node={folder} level={0} />)}
                  </SortableContext>
                )}
              </div>
              <DragOverlay>
                {activeId ? (
                  <div className="rounded-md bg-accent p-2 shadow-lg">
                    <div className="flex items-center gap-2">
                      <Folder className="h-4 w-4 text-primary" />
                      <span className="text-sm font-medium">{findFolderById(folders, activeId)?.name}</span>
                    </div>
                  </div>
                ) : null}
              </DragOverlay>
            </DndContext>
          </ScrollArea>
        </div>
      </TooltipProvider>
    );
  }
);
