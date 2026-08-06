"use client";

import { useState, useRef, useEffect, ChangeEvent } from "react";
import { toast } from "sonner";
import { uploadDocument } from "@/lib/api/documents";
import {
  SUPPORTED_FILE_TYPES,
  SUPPORTED_IMAGE_TYPES,
  computeFileFingerprint,
  fileToImageBlock,
  type ChatAttachmentBlock,
  type FileBlock,
  type ImageBlock,
} from "@/lib/langgraph/multimodal";
// WATERMARK  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZFhZMmVBPT06Yjk2ZTRiNWM=

interface UseFileUploadOptions {
  initialBlocks?: ChatAttachmentBlock[];
}

/** 取 block 的展示名（图片用 name，文件用 filename） */
function blockDisplayName(b: ChatAttachmentBlock): string | undefined {
  return b.type === "image" ? b.metadata?.name : b.metadata?.filename;
}

/** 与现有 block 重名时自动加序号：image.png -> image-2.png -> image-3.png */
function nextAvailableName(name: string, blocks: ChatAttachmentBlock[]): string {
  const existing = new Set(blocks.map(blockDisplayName).filter(Boolean));
  if (!existing.has(name)) return name;
  const dot = name.lastIndexOf(".");
  const stem = dot > 0 ? name.slice(0, dot) : name;
  const ext = dot > 0 ? name.slice(dot) : "";
  let i = 2;
  while (existing.has(`${stem}-${i}${ext}`)) i++;
  return `${stem}-${i}${ext}`;
}

export function useFileUpload({
  initialBlocks = [],
}: UseFileUploadOptions = {}) {
  const [contentBlocks, setContentBlocks] = useState<ChatAttachmentBlock[]>(
    initialBlocks
  );
  const [isUploading, setIsUploading] = useState(false);
  const dropRef = useRef<HTMLDivElement>(null);
  const [dragOver, setDragOver] = useState(false);
  const dragCounter = useRef(0);

  const processFiles = async (files: File[]): Promise<ChatAttachmentBlock[]> => {
    const validFiles = files.filter((file) =>
      SUPPORTED_FILE_TYPES.includes(file.type)
    );
    const invalidFiles = files.filter(
      (file) => !SUPPORTED_FILE_TYPES.includes(file.type)
    );

    if (invalidFiles.length > 0) {
      toast.error("仅支持上传 JPEG、PNG、GIF、WebP 图片或 PDF 文件");
    }

    const newBlocks: ChatAttachmentBlock[] = [];
    const duplicateNames: string[] = [];
    // 本批次指纹集合：同一批粘贴/选择多张相同图片时也要去重
    const batchFingerprints = new Set<string>();

    for (const file of validFiles) {
      // 按内容指纹查重（不按文件名）：剪贴板截图默认都叫 image.png，
      // 同名不同内容必须放行；同内容才判重复。
      const fingerprint = await computeFileFingerprint(file);
      const isDuplicate =
        batchFingerprints.has(fingerprint) ||
        contentBlocks.some((b) => b.metadata?.fingerprint === fingerprint);
      if (isDuplicate) {
        duplicateNames.push(file.name);
        continue;
      }
      batchFingerprints.add(fingerprint);

      try {
        const displayName = nextAvailableName(file.name, [
          ...contentBlocks,
          ...newBlocks,
        ]);
        if (SUPPORTED_IMAGE_TYPES.includes(file.type)) {
          const block: ImageBlock = await fileToImageBlock(
            new File([file], displayName, { type: file.type })
          );
          block.metadata = { ...block.metadata, fingerprint };
          newBlocks.push(block);
        } else if (file.type === "application/pdf") {
          const result = await uploadDocument(
            new File([file], displayName, { type: file.type })
          );
          if (!result.success) {
            toast.error(`PDF 上传失败: ${result.data?.file_name || displayName}`);
            continue;
          }
          const block: FileBlock = {
            type: "file",
            mimeType: "application/pdf",
            url: result.data.url,
            metadata: { filename: result.data.file_name, fingerprint },
          };
          newBlocks.push(block);
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        toast.error(`文件处理失败: ${message}`);
      }
    }

    if (duplicateNames.length > 0) {
      toast.error(`重复文件: ${duplicateNames.join(", ")}`);
    }

    return newBlocks;
  };

  const handleFileUpload = async (e: ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files) return;
    setIsUploading(true);
    try {
      const newBlocks = await processFiles(Array.from(files));
      if (newBlocks.length > 0) {
        setContentBlocks((prev) => [...prev, ...newBlocks]);
      }
    } finally {
      setIsUploading(false);
    }
    e.target.value = "";
  };

  const handlePaste = async (
    e: React.ClipboardEvent<HTMLTextAreaElement | HTMLInputElement>
  ) => {
    const items = e.clipboardData.items;
    if (!items) return;

    const files: File[] = [];
    for (let i = 0; i < items.length; i += 1) {
      const item = items[i];
      if (item.kind === "file") {
        const file = item.getAsFile();
        if (file) {
          files.push(file);
        }
      }
    }

    if (files.length === 0) return;
    e.preventDefault();

    // 粘贴文件通常没有文件名，补充一个默认名称
    const namedFiles = files.map((file) => {
      if (file.name) return file;
      const ext = file.type.split("/")[1] || "bin";
      return new File([file], `pasted-file.${ext}`, { type: file.type });
    });

    setIsUploading(true);
    try {
      const newBlocks = await processFiles(namedFiles);
      if (newBlocks.length > 0) {
        setContentBlocks((prev) => [...prev, ...newBlocks]);
      }
    } finally {
      setIsUploading(false);
    }
  };

  // 拖拽上传
  useEffect(() => {
    if (!dropRef.current) return;

    const handleWindowDragEnter = (e: DragEvent) => {
      if (e.dataTransfer?.types?.includes("Files")) {
        dragCounter.current += 1;
        setDragOver(true);
      }
    };
    const handleWindowDragLeave = (e: DragEvent) => {
      if (e.dataTransfer?.types?.includes("Files")) {
        dragCounter.current -= 1;
        if (dragCounter.current <= 0) {
          setDragOver(false);
          dragCounter.current = 0;
        }
      }
    };
    const handleWindowDrop = async (e: DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      dragCounter.current = 0;
      setDragOver(false);

      if (!e.dataTransfer) return;
      setIsUploading(true);
      try {
        const newBlocks = await processFiles(Array.from(e.dataTransfer.files));
        if (newBlocks.length > 0) {
          setContentBlocks((prev) => [...prev, ...newBlocks]);
        }
      } finally {
        setIsUploading(false);
      }
    };
    const handleWindowDragEnd = () => {
      dragCounter.current = 0;
      setDragOver(false);
    };
    const handleWindowDragOver = (e: DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
    };

    const handleElementDragOver = (e: DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setDragOver(true);
    };
    const handleElementDragEnter = (e: DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setDragOver(true);
    };
    const handleElementDragLeave = (e: DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setDragOver(false);
    };

    const element = dropRef.current;
    element.addEventListener("dragover", handleElementDragOver);
    element.addEventListener("dragenter", handleElementDragEnter);
    element.addEventListener("dragleave", handleElementDragLeave);

    window.addEventListener("dragenter", handleWindowDragEnter);
    window.addEventListener("dragleave", handleWindowDragLeave);
    window.addEventListener("drop", handleWindowDrop);
    window.addEventListener("dragend", handleWindowDragEnd);
    window.addEventListener("dragover", handleWindowDragOver);

    return () => {
      element.removeEventListener("dragover", handleElementDragOver);
      element.removeEventListener("dragenter", handleElementDragEnter);
      element.removeEventListener("dragleave", handleElementDragLeave);
      window.removeEventListener("dragenter", handleWindowDragEnter);
      window.removeEventListener("dragleave", handleWindowDragLeave);
      window.removeEventListener("drop", handleWindowDrop);
      window.removeEventListener("dragend", handleWindowDragEnd);
      window.removeEventListener("dragover", handleWindowDragOver);
      dragCounter.current = 0;
    };
  }, [contentBlocks]);

  const removeBlock = (idx: number) => {
    setContentBlocks((prev) => prev.filter((_, i) => i !== idx));
  };

  const resetBlocks = () => setContentBlocks([]);

  return {
    contentBlocks,
    setContentBlocks,
    handleFileUpload,
    dropRef,
    removeBlock,
    resetBlocks,
    dragOver,
    handlePaste,
    isUploading,
  };
}
