"use client";

import { useEffect, useState } from "react";

/**
 * 延迟卸载 hook。
 *
 * 当 `mounted` 为 true 时立即返回 true；当 `mounted` 变为 false 时，
 * 在 `delayMs` 毫秒后才返回 false。用于配合 CSS 过渡动画，在组件
 * 视觉上滑出/淡出完成后再真正从 React 树中移除，避免动画中断。
 */
export function useDelayedUnmount(mounted: boolean, delayMs: number): boolean {
  const [render, setRender] = useState(mounted);

  useEffect(() => {
    if (mounted) {
      setRender(true);
    } else {
      const timer = setTimeout(() => setRender(false), delayMs);
      return () => clearTimeout(timer);
    }
  }, [mounted, delayMs]);

  return render;
}
