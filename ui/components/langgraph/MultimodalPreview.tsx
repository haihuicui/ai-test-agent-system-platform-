"use client";

import React from "react";
import { File, X as XIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { type ChatAttachmentBlock, isImageBlock, isFileBlock } from "@/lib/langgraph/multimodal";
// WATERMARK  MC8zOmFIVnBZMlhsdEpUbXRiZm92b2s2YUU1dGVRPT06Y2NmOTUwNWE=

export interface MultimodalPreviewProps {
  block: ChatAttachmentBlock;
  removable?: boolean;
  onRemove?: () => void;
  className?: string;
  size?: "sm" | "md" | "lg";
}

export const MultimodalPreview: React.FC<MultimodalPreviewProps> = ({
  block,
  removable = false,
  onRemove,
  className,
  size = "md",
}) => {
  if (isImageBlock(block)) {
    const url = `data:${block.mimeType};base64,${block.data}`;
    const sizeClasses =
      size === "sm" ? "h-10 w-10" : size === "lg" ? "h-24 w-24" : "h-16 w-16";
    return (
      <div className={cn("relative inline-block", className)}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={url}
          alt={block.metadata?.name || "上传的图片"}
          className={cn("rounded-md object-cover", sizeClasses)}
        />
        {removable && (
          <button
            type="button"
            onClick={onRemove}
            className="absolute -right-1 -top-1 z-10 rounded-full bg-muted p-0.5 text-muted-foreground shadow-sm hover:bg-accent hover:text-foreground"
            aria-label="移除图片"
          >
            <XIcon className="h-3 w-3" />
          </button>
        )}
      </div>
    );
  }

  if (isFileBlock(block)) {
    const filename = block.metadata?.filename || "PDF 文件";
    return (
      <div
        className={cn(
          "relative flex items-center gap-2 rounded-md border bg-muted px-3 py-2 text-foreground",
          className
        )}
      >
        <File
          className={cn(
            "shrink-0 text-primary",
            size === "sm" ? "h-4 w-4" : size === "lg" ? "h-8 w-8" : "h-6 w-6"
          )}
        />
        <span className="max-w-[160px] truncate text-sm" title={filename}>
          {filename}
        </span>
        {removable && (
          <button
            type="button"
            onClick={onRemove}
            className="ml-1 rounded-full p-0.5 text-muted-foreground hover:bg-accent hover:text-foreground"
            aria-label="移除 PDF"
          >
            <XIcon className="h-3 w-3" />
          </button>
        )}
      </div>
    );
  }

  return null;
};
