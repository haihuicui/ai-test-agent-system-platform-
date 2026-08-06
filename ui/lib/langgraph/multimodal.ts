import { toast } from "sonner";
// WATERMARK  MC8yOmFIVnBZMlhsdEpUbXRiZm92b2s2YzNSYVdRPT06ZWNlZjM2NDk=

/** 支持的图片 MIME 类型 */
export const SUPPORTED_IMAGE_TYPES = [
  "image/jpeg",
  "image/png",
  "image/gif",
  "image/webp",
];

/** 支持的文件 MIME 类型（含 PDF） */
export const SUPPORTED_FILE_TYPES = [
  ...SUPPORTED_IMAGE_TYPES,
  "application/pdf",
];

/** 图片内容块（base64 内联） */
export interface ImageBlock {
  type: "image";
  mimeType: string;
  /** 不含 data:*;base64, 前缀的 base64 字符串 */
  data: string;
  metadata?: {
    name?: string;
    /** 内容指纹（computeFileFingerprint），用于查重 */
    fingerprint?: string;
  };
}

/** 文件内容块（目前用于 PDF，使用 MinIO 预签名 URL） */
export interface FileBlock {
  type: "file";
  mimeType: string;
  /** MinIO 预签名 URL */
  url: string;
  metadata?: {
    filename?: string;
    /** 内容指纹（computeFileFingerprint），用于查重 */
    fingerprint?: string;
  };
}

/** 聊天附件内容块 */
export type ChatAttachmentBlock = ImageBlock | FileBlock;

/** image_url 块（OpenAI / Doubao 兼容格式） */
export interface ImageUrlBlock {
  type: "image_url";
  image_url: { url: string };
}

/** 将 File 转为 base64 字符串（去掉 data: 前缀） */
export async function fileToBase64(file: File): Promise<string> {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => {
      const result = reader.result as string;
      resolve(result.split(",")[1]);
    };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

/** 将图片文件转为 ImageBlock */
export async function fileToImageBlock(file: File): Promise<ImageBlock> {
  if (!SUPPORTED_IMAGE_TYPES.includes(file.type)) {
    toast.error(`不支持的图片类型: ${file.type}`);
    return Promise.reject(new Error(`Unsupported image type: ${file.type}`));
  }
  const data = await fileToBase64(file);
  return {
    type: "image",
    mimeType: file.type,
    data,
    metadata: { name: file.name },
  };
}

/**
 * cyrb53 散列（53 位），无需 secure context（crypto.subtle 在
 * 非 HTTPS/localhost 环境下不可用），用于附件内容指纹。
 */
function cyrb53(bytes: Uint8Array, seed = 0): number {
  let h1 = 0xdeadbeef ^ seed;
  let h2 = 0x41c6ce57 ^ seed;
  for (let i = 0; i < bytes.length; i++) {
    const ch = bytes[i];
    h1 = Math.imul(h1 ^ ch, 2654435761);
    h2 = Math.imul(h2 ^ ch, 1597334677);
  }
  h1 = Math.imul(h1 ^ (h1 >>> 16), 2246822507) ^ Math.imul(h2 ^ (h2 >>> 13), 3266489909);
  h2 = Math.imul(h2 ^ (h2 >>> 16), 2246822507) ^ Math.imul(h1 ^ (h1 >>> 13), 3266489909);
  return (h2 >>> 0) * 4294967296 + (h1 >>> 0);
}

/**
 * 计算文件内容指纹：size + 头 64KB / 尾 64KB 抽样散列。
 * 同名不同内容（多张剪贴板截图都叫 image.png）应判为不同文件；
 * 同内容应判为重复。抽样而非全量，避免大文件的读取开销。
 */
export async function computeFileFingerprint(file: File): Promise<string> {
  const SAMPLE = 64 * 1024;
  const head = new Uint8Array(await file.slice(0, SAMPLE).arrayBuffer());
  const tail =
    file.size > SAMPLE
      ? new Uint8Array(await file.slice(-SAMPLE).arrayBuffer())
      : new Uint8Array(0);
  const hash = cyrb53(head, file.size) ^ cyrb53(tail, 0x9e3779b9);
  return `${file.size}:${(hash >>> 0).toString(36)}`;
}

/** 类型守卫：是否为 ImageBlock */
export function isImageBlock(block: unknown): block is ImageBlock {
  if (typeof block !== "object" || block === null || !("type" in block)) {
    return false;
  }
  const b = block as { type: unknown; mimeType?: unknown; data?: unknown };
  return (
    b.type === "image" &&
    typeof b.mimeType === "string" &&
    b.mimeType.startsWith("image/") &&
    typeof b.data === "string"
  );
}

/** 类型守卫：是否为 FileBlock（PDF） */
export function isFileBlock(block: unknown): block is FileBlock {
  if (typeof block !== "object" || block === null || !("type" in block)) {
    return false;
  }
  const b = block as { type: unknown; mimeType?: unknown; url?: unknown };
  return (
    b.type === "file" &&
    typeof b.mimeType === "string" &&
    b.mimeType === "application/pdf" &&
    typeof b.url === "string"
  );
}

/** 类型守卫：是否为 image_url 块 */
export function isImageUrlBlock(block: unknown): block is ImageUrlBlock {
  if (typeof block !== "object" || block === null || !("type" in block)) {
    return false;
  }
  const b = block as { type: unknown; image_url?: unknown };
  if (b.type !== "image_url" || typeof b.image_url !== "object" || b.image_url === null) {
    return false;
  }
  return typeof (b.image_url as { url?: unknown }).url === "string";
}

/** 类型守卫：是否为 PDF 附件 */
export function isPdfAttachment(block: unknown): boolean {
  return isFileBlock(block);
}
