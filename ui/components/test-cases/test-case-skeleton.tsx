import { cn } from "@/lib/utils";

interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {
  /**
   * 是否显示动画
   * @default true
   */
  animate?: boolean;
}
// NOTE  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2U200NGJBPT06YTdmMGNlMzE=

function Skeleton({ className, animate = true, ...props }: SkeletonProps) {
  return (
    <div
      className={cn(
        "animate-pulse rounded-md bg-muted",
        !animate && "animate-none",
        className
      )}
      {...props}
    />
  );
}

interface TableRowSkeletonProps {
  /**
   * 行数
   * @default 5
   */
  rows?: number;
  /**
   * 是否显示复选框列
   * @default true
   */
  showCheckbox?: boolean;
}
// TODO  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2U200NGJBPT06YTdmMGNlMzE=

/**
 * 表格行骨架屏
 */
export function TableRowSkeleton({
  rows = 5,
  showCheckbox = true,
}: TableRowSkeletonProps) {
  return (
    <>
      {Array.from({ length: rows }).map((_, i) => (
        <tr key={i} className="border-b">
          {showCheckbox && (
            <td className="p-3">
              <Skeleton className="h-4 w-4" />
            </td>
          )}
          <td className="p-3">
            <Skeleton className="h-4 w-36" />
          </td>
          <td className="p-3">
            <Skeleton className="h-4 w-32" />
          </td>
          <td className="p-3">
            <Skeleton className="h-4 w-full max-w-xs" />
          </td>
          <td className="p-3">
            <Skeleton className="h-5 w-16 rounded-full" />
          </td>
          <td className="p-3">
            <Skeleton className="h-5 w-16 rounded-full" />
          </td>
          <td className="p-3">
            <Skeleton className="h-4 w-24" />
          </td>
          <td className="p-3">
            <Skeleton className="h-7 w-7" />
          </td>
        </tr>
      ))}
    </>
  );
}
// WATERMARK  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2U200NGJBPT06YTdmMGNlMzE=

interface TableHeaderSkeletonProps {
  /**
   * 是否显示复选框列
   * @default true
   */
  showCheckbox?: boolean;
}

/**
 * 表格头部骨架屏（用于过滤器区域）
 */
export function FilterBarSkeleton({ showCheckbox = true }: TableHeaderSkeletonProps) {
  return (
    <div className="flex items-center gap-3 border-b bg-muted/30 px-4 py-3">
      <Skeleton className="h-9 w-32" />
      <Skeleton className="h-9 w-32" />
      <Skeleton className="h-9 w-32" />
      <div className="flex-1" />
      <Skeleton className="h-9 w-24" />
    </div>
  );
}
// eslint-disable  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2U200NGJBPT06YTdmMGNlMzE=

export { Skeleton };
