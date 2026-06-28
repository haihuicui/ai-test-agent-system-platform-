"use client";
// eslint-disable  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2UWxab2FRPT06MzgzODExYTI=

import * as React from "react";
import {
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";
import { useLanguage } from "@/providers/LanguageProvider";
// TODO  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2UWxab2FRPT06MzgzODExYTI=

export interface PaginationProps {
  /**
   * 当前页码（从 1 开始）
   */
  page: number;
  /**
   * 每页显示数量
   */
  pageSize: number;
  /**
   * 总记录数
   */
  total: number;
  /**
   * 页码变化回调
   */
  onPageChange: (page: number) => void;
  /**
   * 每页数量变化回调
   */
  onPageSizeChange?: (pageSize: number) => void;
  /**
   * 可选的每页数量选项
   * @default [10, 20, 50, 100]
   */
  pageSizeOptions?: number[];
  /**
   * 显示的页码按钮数量（奇数）
   * @default 7
   */
  siblingCount?: number;
  /**
   * 是否显示总记录数
   * @default true
   */
  showInfo?: boolean;
  /**
   * 是否显示每页数量选择器
   * @default true
   */
  showPageSizeSelector?: boolean;
  /**
   * 自定义类名
   */
  className?: string;
}
// TODO  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2UWxab2FRPT06MzgzODExYTI=

/**
 * 计算显示的页码数组
 */
function generatePageNumbers({
  currentPage,
  totalPages,
  siblingCount = 1,
}: {
  currentPage: number;
  totalPages: number;
  siblingCount?: number;
}): (number | string)[] {
  const totalPageNumbers = siblingCount + 5; // siblings + first + last + current + 2*ellipsis

  if (totalPageNumbers >= totalPages) {
    return Array.from({ length: totalPages }, (_, i) => i + 1);
  }

  const leftSiblingIndex = Math.max(currentPage - siblingCount, 1);
  const rightSiblingIndex = Math.min(currentPage + siblingCount, totalPages);

  const shouldShowLeftEllipsis = leftSiblingIndex > 2;
  const shouldShowRightEllipsis = rightSiblingIndex < totalPages - 2;

  if (!shouldShowLeftEllipsis && shouldShowRightEllipsis) {
    const leftItemCount = 3 + 2 * siblingCount;
    return [
      ...Array.from({ length: leftItemCount }, (_, i) => i + 1),
      "...",
      totalPages,
    ];
  }

  if (shouldShowLeftEllipsis && !shouldShowRightEllipsis) {
    const rightItemCount = 3 + 2 * siblingCount;
    return [
      1,
      "...",
      ...Array.from(
        { length: rightItemCount },
        (_, i) => totalPages - rightItemCount + i + 1
      ),
    ];
  }

  if (shouldShowLeftEllipsis && shouldShowRightEllipsis) {
    const middleItemCount = 2 * siblingCount + 1;
    return [
      1,
      "...",
      ...Array.from(
        { length: middleItemCount },
        (_, i) => leftSiblingIndex + i
      ),
      "...",
      totalPages,
    ];
  }

  return [];
}

export function Pagination({
  page,
  pageSize,
  total,
  onPageChange,
  onPageSizeChange,
  pageSizeOptions = [10, 20, 50, 100],
  siblingCount = 1,
  showInfo = true,
  showPageSizeSelector = true,
  className,
}: PaginationProps) {
  const { t } = useLanguage();
  const totalPages = Math.ceil(total / pageSize);
  const pageNumbers = React.useMemo(
    () =>
      generatePageNumbers({
        currentPage: page,
        totalPages,
        siblingCount,
      }),
    [page, totalPages, siblingCount]
  );

  const startIndex = (page - 1) * pageSize + 1;
  const endIndex = Math.min(page * pageSize, total);

  const canPreviousPage = page > 1;
  const canNextPage = page < totalPages;

  // 如果没有数据或只有一页且不需要显示选择器，则不显示分页
  if (total === 0) {
    return null;
  }

  // 只有一页数据时，仍然显示信息但不显示页码按钮
  const showPagination = totalPages > 1;

  return (
    <div className={cn("flex items-center justify-between gap-4", className)}>
      {/* 左侧信息 */}
      <div className="flex items-center gap-4">
        {showInfo && (
          <div className="text-sm text-muted-foreground">
            {t("common.showing")} <span className="font-medium">{total > 0 ? startIndex : 0}</span> -{" "}
            <span className="font-medium">{endIndex}</span>
            {" "}/ <span className="font-medium">{total}</span> {t("common.items")}
          </div>
        )}
        {showPageSizeSelector && onPageSizeChange && (
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground">{t("common.perPage")}</span>
            <Select
              value={String(pageSize)}
              onValueChange={(value) => onPageSizeChange(Number(value))}
            >
              <SelectTrigger className="h-8 w-16">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {pageSizeOptions.map((size) => (
                  <SelectItem key={size} value={String(size)}>
                    {size}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <span className="text-sm text-muted-foreground">{t("common.items")}</span>
          </div>
        )}
      </div>

      {/* 右侧页码按钮 */}
      {showPagination && (
        <div className="flex items-center gap-1">
          {/* 第一页 */}
          <Button
            variant="outline"
            size="icon"
            className="h-8 w-8"
            disabled={!canPreviousPage}
            onClick={() => onPageChange(1)}
            aria-label={t("common.firstPage")}
          >
            <ChevronsLeft className="h-4 w-4" />
          </Button>

          {/* 上一页 */}
          <Button
            variant="outline"
            size="icon"
            className="h-8 w-8"
            disabled={!canPreviousPage}
            onClick={() => onPageChange(page - 1)}
            aria-label={t("common.previousPage")}
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>

          {/* 页码按钮 */}
          <div className="flex items-center gap-1">
            {pageNumbers.map((pageNumber, index) => {
              if (pageNumber === "...") {
                return (
                  <span
                    key={`ellipsis-${index}`}
                    className="flex h-8 w-8 items-center justify-center text-sm text-muted-foreground"
                  >
                    ...
                  </span>
                );
              }

              const currentPageNum = pageNumber as number;
              const isActive = currentPageNum === page;

              return (
                <Button
                  key={currentPageNum}
                  variant={isActive ? "default" : "outline"}
                  size="icon"
                  className="h-8 w-8"
                  onClick={() => onPageChange(currentPageNum)}
                  aria-label={t("common.pageNumber", { page: currentPageNum.toString() })}
                  aria-current={isActive ? "page" : undefined}
                >
                  {currentPageNum}
                </Button>
              );
            })}
          </div>

          {/* 下一页 */}
          <Button
            variant="outline"
            size="icon"
            className="h-8 w-8"
            disabled={!canNextPage}
            onClick={() => onPageChange(page + 1)}
            aria-label={t("common.nextPage")}
          >
            <ChevronRight className="h-4 w-4" />
          </Button>

          {/* 最后一页 */}
          <Button
            variant="outline"
            size="icon"
            className="h-8 w-8"
            disabled={!canNextPage}
            onClick={() => onPageChange(totalPages)}
            aria-label={t("common.lastPage")}
          >
            <ChevronsRight className="h-4 w-4" />
          </Button>
        </div>
      )}
    </div>
  );
}
// TODO  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2UWxab2FRPT06MzgzODExYTI=
