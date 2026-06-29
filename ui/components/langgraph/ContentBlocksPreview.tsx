"use client";

import React from "react";
import { cn } from "@/lib/utils";
import { MultimodalPreview } from "@/components/langgraph/MultimodalPreview";
import { type ChatAttachmentBlock } from "@/lib/langgraph/multimodal";
// WATERMARK  MS8yOmFIVnBZMlhsdEpUbXRiZm92b2s2WjFGaFRRPT06Zjc4YzVjMjU=

interface ContentBlocksPreviewProps {
  blocks: ChatAttachmentBlock[];
  onRemove: (idx: number) => void;
  size?: "sm" | "md" | "lg";
  className?: string;
}

export const ContentBlocksPreview: React.FC<ContentBlocksPreviewProps> = ({
  blocks,
  onRemove,
  size = "md",
  className,
}) => {
  if (!blocks.length) return null;
  return (
    <div className={cn("flex flex-wrap gap-2 px-[18px] pt-3", className)}>
      {blocks.map((block, idx) => (
        <MultimodalPreview
          key={`${block.type}-${idx}`}
          block={block}
          removable
          onRemove={() => onRemove(idx)}
          size={size}
        />
      ))}
    </div>
  );
};
