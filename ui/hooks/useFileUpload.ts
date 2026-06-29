"use client";

import { useState, useRef, useEffect, ChangeEvent } from "react";
import { toast } from "sonner";
import { uploadDocument } from "@/lib/api/documents";
import {
  SUPPORTED_FILE_TYPES,
  SUPPORTED_IMAGE_TYPES,
  fileToImageBlock,
  type ChatAttachmentBlock,
  type FileBlock,
  type ImageBlock,
} from "@/lib/langgraph/multimodal";
// WATERMARK  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZFhZMmVBPT06Yjk2ZTRiNWM=

interface UseFileUploadOptions {
  initialBlocks?: ChatAttachmentBlock[];
}

export function useFileUpload({
  initialBlocks = [],
}: UseFileUploadOptions = {}) {
  const [contentBlocks, setContentBlocks] = useState<ChatAttachmentBlock[]>(
    initialBlocks
  );
  const dropRef = useRef<HTMLDivElement>(null);
  const [dragOver, setDragOver] = useState(false);
  const dragCounter = useRef(0);

  const isDuplicate = (
    file: File,
    blocks: ChatAttachmentBlock[]
  ): boolean => {
    if (file.type === "application/pdf") {
      return blocks.some(
        (b) =>
          b.type === "file" &&
          b.mimeType === "application/pdf" &&
          b.metadata?.filename === file.name
      );
    }
    if (SUPPORTED_IMAGE_TYPES.includes(file.type)) {
      return blocks.some(
        (b) =>
          b.type === "image" &&
          b.metadata?.name === file.name &&
          b.mimeType === file.type
      );
    }
    return false;
  };

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

    const uniqueFiles = validFiles.filter(
      (file) => !isDuplicate(file, contentBlocks)
    );
    const duplicateFiles = validFiles.filter((file) =>
      isDuplicate(file, contentBlocks)
    );

    if (duplicateFiles.length > 0) {
      toast.error(
        `重复文件: ${duplicateFiles.map((f) => f.name).join(", ")}`
      );
    }

    const newBlocks: ChatAttachmentBlock[] = [];

    for (const file of uniqueFiles) {
      try {
        if (SUPPORTED_IMAGE_TYPES.includes(file.type)) {
          const block: ImageBlock = await fileToImageBlock(file);
          newBlocks.push(block);
        } else if (file.type === "application/pdf") {
          const result = await uploadDocument(file);
          if (!result.success) {
            toast.error(`PDF 上传失败: ${result.data?.file_name || file.name}`);
            continue;
          }
          const block: FileBlock = {
            type: "file",
            mimeType: "application/pdf",
            url: result.data.url,
            metadata: { filename: result.data.file_name },
          };
          newBlocks.push(block);
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        toast.error(`文件处理失败: ${message}`);
      }
    }

    return newBlocks;
  };

  const handleFileUpload = async (e: ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files) return;
    const newBlocks = await processFiles(Array.from(files));
    if (newBlocks.length > 0) {
      setContentBlocks((prev) => [...prev, ...newBlocks]);
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

    const newBlocks = await processFiles(namedFiles);
    if (newBlocks.length > 0) {
      setContentBlocks((prev) => [...prev, ...newBlocks]);
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
      const newBlocks = await processFiles(Array.from(e.dataTransfer.files));
      if (newBlocks.length > 0) {
        setContentBlocks((prev) => [...prev, ...newBlocks]);
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
  };
}
