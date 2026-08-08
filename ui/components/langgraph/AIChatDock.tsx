"use client";

import React, { useCallback, useLayoutEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";

interface AIChatDockProps {
  /** 面板是否打开；关闭时宽度动画收起为 0，主内容区自动回弹 */
  open: boolean;
  children: React.ReactNode;
  /** localStorage 持久化键，按页面区分记忆宽度（如 "web-tests"） */
  storageKey: string;
  /** 默认宽度（px），未记忆过时使用 */
  defaultWidth?: number;
  /** 拖拽允许的最小宽度（px） */
  minWidth?: number;
  /** 最大宽度占视口宽度的比例 */
  maxWidthRatio?: number;
}

/**
 * 挤压式 AI 聊天侧栏：作为 flex 子项占据文档流，打开时主内容区自动收窄，
 * 不再 absolute 覆盖页面内容。左边缘可拖拽调宽，宽度记忆到 localStorage。
 */
export function AIChatDock({
  open,
  children,
  storageKey,
  defaultWidth = 1200,
  minWidth = 480,
  maxWidthRatio = 0.8,
}: AIChatDockProps) {
  const persistKey = `aiChatDockWidth:${storageKey}`;
  const [width, setWidth] = useState<number>(defaultWidth);
  const [dragging, setDragging] = useState(false);
  const dragState = useRef<{ startX: number; startWidth: number } | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);

  const clampWidth = useCallback(
    (w: number) => {
      // 上限按父容器（页面内容区）宽度计算，而不是整个视口：
      // shrink-0 的 flex 子项可以溢出容器，按视口 clamp 会导致右缘被裁剪。
      const container =
        rootRef.current?.parentElement?.clientWidth ??
        (typeof window !== "undefined" ? window.innerWidth : defaultWidth);
      const max = Math.floor(container * maxWidthRatio);
      return Math.min(Math.max(w, minWidth), max);
    },
    [minWidth, maxWidthRatio, defaultWidth]
  );

  // 挂载后确定初始宽度：优先记忆的宽度；否则取 min(defaultWidth, 55vw)，
  // 避免视口不宽时默认面板把主内容区挤得不可用。
  // 用 useLayoutEffect 在绘制前完成，避免宽度闪跳；SSR 期间保持 defaultWidth。
  useLayoutEffect(() => {
    let next: number | null = null;
    try {
      const saved = window.localStorage.getItem(persistKey);
      if (saved) {
        const parsed = Number(saved);
        if (Number.isFinite(parsed) && parsed > 0) {
          next = parsed;
        }
      }
    } catch {
      // localStorage 不可用时忽略
    }
    if (next === null) {
      next = Math.min(defaultWidth, Math.floor(window.innerWidth * 0.55));
    }
    setWidth(clampWidth(next));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [persistKey]);

  const persistWidth = useCallback(
    (w: number) => {
      try {
        window.localStorage.setItem(persistKey, String(w));
      } catch {
        // localStorage 不可用时忽略
      }
    },
    [persistKey]
  );

  const onHandlePointerDown = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      e.preventDefault();
      dragState.current = { startX: e.clientX, startWidth: width };
      setDragging(true);

      const onMove = (ev: PointerEvent) => {
        if (!dragState.current) return;
        // 面板在右侧：指针向左拖 → 变宽，向右拖 → 变窄
        const delta = dragState.current.startX - ev.clientX;
        setWidth(clampWidth(dragState.current.startWidth + delta));
      };
      const onUp = () => {
        if (dragState.current) {
          setWidth((current) => {
            persistWidth(current);
            return current;
          });
        }
        dragState.current = null;
        setDragging(false);
        window.removeEventListener("pointermove", onMove);
        window.removeEventListener("pointerup", onUp);
      };
      window.addEventListener("pointermove", onMove);
      window.addEventListener("pointerup", onUp);
    },
    [width, clampWidth, persistWidth]
  );

  // 双击拖拽条恢复默认宽度（与初始默认一致：min(defaultWidth, 55vw)）
  const onHandleDoubleClick = useCallback(() => {
    const w = clampWidth(
      Math.min(defaultWidth, Math.floor(window.innerWidth * 0.55))
    );
    setWidth(w);
    persistWidth(w);
  }, [clampWidth, defaultWidth, persistWidth]);

  return (
    <div
      ref={rootRef}
      className={cn(
        "relative h-full shrink-0 overflow-hidden bg-background",
        !dragging && "transition-[width] duration-300 ease-in-out",
        open ? "border-l" : "border-l-0"
      )}
      style={{ width: open ? width : 0 }}
      aria-hidden={!open}
    >
      {/* 内部内容固定为面板宽度，开合动画期间不参与外层 reflow */}
      <div className="h-full" style={{ width }}>
        {children}
      </div>

      {/* 左边缘拖拽调宽把手 */}
      {open && (
        <div
          role="separator"
          aria-orientation="vertical"
          aria-label="调整 AI 助手面板宽度"
          title="拖拽调整宽度，双击恢复默认"
          onPointerDown={onHandlePointerDown}
          onDoubleClick={onHandleDoubleClick}
          className={cn(
            "absolute left-0 top-0 z-10 h-full w-1.5 cursor-col-resize",
            "hover:bg-primary/30",
            dragging && "bg-primary/40"
          )}
        />
      )}
    </div>
  );
}
