"use client";
// WATERMARK  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2YVRKT05RPT06NGUxNmM3YzE=

import * as React from "react";
import { Upload, X, FileIcon, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { uploadTestCaseAttachment } from "@/lib/api/attachments";
// NOTE  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2YVRKT05RPT06NGUxNmM3YzE=

interface AttachmentFile {
  id: string;
  file: File;
  uploading?: boolean;
  uploaded?: boolean;
  url?: string;
}

interface AttachmentUploadProps {
  testCaseId?: string;
  testCaseIdentifier?: string;
  projectIdentifier?: string;
  onFilesChange?: (files: File[]) => void;
  autoUpload?: boolean; // 是否自动上传（编辑模式）
  maxFiles?: number;
  maxSize?: number; // in MB
}
// NOTE  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2YVRKT05RPT06NGUxNmM3YzE=

export function AttachmentUpload({
  testCaseId,
  testCaseIdentifier,
  projectIdentifier,
  onFilesChange,
  autoUpload = false,
  maxFiles = 10,
  maxSize = 50,
}: AttachmentUploadProps) {
  const [files, setFiles] = React.useState<AttachmentFile[]>([]);
  const fileInputRef = React.useRef<HTMLInputElement>(null);

  const handleFileSelect = async (selectedFiles: FileList | null) => {
    if (!selectedFiles || selectedFiles.length === 0) return;

    const newFiles: AttachmentFile[] = [];
    const maxSizeBytes = maxSize * 1024 * 1024;

    for (let i = 0; i < selectedFiles.length; i++) {
      const file = selectedFiles[i];

      // 检查文件大小
      if (file.size > maxSizeBytes) {
        toast.error(`文件 ${file.name} 超过 ${maxSize}MB 限制`);
        continue;
      }

      // 检查文件数量
      if (files.length + newFiles.length >= maxFiles) {
        toast.error(`最多只能上传 ${maxFiles} 个文件`);
        break;
      }

      newFiles.push({
        id: `${Date.now()}-${i}`,
        file,
        uploading: autoUpload,
        uploaded: false,
      });
    }

    const updatedFiles = [...files, ...newFiles];
    setFiles(updatedFiles);
    onFilesChange?.(updatedFiles.map((f) => f.file));

    // 如果是编辑模式且有测试用例标识符，自动上传
    if (autoUpload && testCaseIdentifier && projectIdentifier) {
      for (const fileItem of newFiles) {
        try {
          await uploadTestCaseAttachment(
            projectIdentifier,
            testCaseIdentifier,
            fileItem.file
          );

          // 更新文件状态
          setFiles((prev) =>
            prev.map((f) =>
              f.id === fileItem.id
                ? { ...f, uploading: false, uploaded: true }
                : f
            )
          );

          toast.success(`文件 ${fileItem.file.name} 上传成功`);
        } catch (error) {
          console.error("Upload failed:", error);
          toast.error(`文件 ${fileItem.file.name} 上传失败`);

          // 移除上传失败的文件
          setFiles((prev) => prev.filter((f) => f.id !== fileItem.id));
        }
      }
    }
  };

  const removeFile = (id: string) => {
    const updatedFiles = files.filter((f) => f.id !== id);
    setFiles(updatedFiles);
    onFilesChange?.(updatedFiles.map((f) => f.file));
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div className="space-y-3">
      <Label>附件</Label>

      {/* 文件列表 */}
      {files.length > 0 && (
        <div className="space-y-2">
          {files.map((fileItem) => (
            <div
              key={fileItem.id}
              className="flex items-center gap-3 rounded-lg border p-3"
            >
              <FileIcon className="h-5 w-5 text-muted-foreground shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">{fileItem.file.name}</p>
                <p className="text-xs text-muted-foreground">
                  {formatFileSize(fileItem.file.size)}
                </p>
              </div>
              {fileItem.uploading ? (
                <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
              ) : (
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 shrink-0"
                  onClick={() => removeFile(fileItem.id)}
                >
                  <X className="h-4 w-4" />
                </Button>
              )}
            </div>
          ))}
        </div>
      )}

      {/* 上传按钮 */}
      {files.length < maxFiles && (
        <div className="rounded-lg border border-dashed p-4">
          <input
            ref={fileInputRef}
            type="file"
            multiple
            className="hidden"
            onChange={(e) => handleFileSelect(e.target.files)}
            accept="image/*,.pdf,.doc,.docx,.txt,.xls,.xlsx"
          />
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="w-full"
            onClick={() => fileInputRef.current?.click()}
          >
            <Upload className="mr-2 h-4 w-4" />
            上传文件
          </Button>
          <p className="mt-2 text-xs text-center text-muted-foreground">
            最大文件大小: {maxSize} MB | 最多文件数: {maxFiles} 个
          </p>
        </div>
      )}
    </div>
  );
}

// FIXME  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2YVRKT05RPT06NGUxNmM3YzE=
