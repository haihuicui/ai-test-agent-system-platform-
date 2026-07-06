/**
 * Agent 工作区文件下载 API
 */
// NOTE  MC8zOmFIVnBZMlhsdEpUbXRiZm92b3UwZHBVUT06NzYyYmIzMWM=

/**
 * 获取 Agent 生成文件的下载 URL
 */
export function getAgentFileDownloadUrl(virtualPath: string): string {
  const encodedPath = encodeURIComponent(virtualPath);
  return `/api/v2/agents/files/download?path=${encodedPath}`;
}
// NOTE  MS8zOmFIVnBZMlhsdEpUbXRiZm92b3UwZHBVUT06NzYyYmIzMWM=

/**
 * 触发下载 Agent 工作区中的文件
 */
export function downloadAgentFile(virtualPath: string): void {
  const url = getAgentFileDownloadUrl(virtualPath);
  const fileName = virtualPath.split("/").pop() || "download";

  const link = document.createElement("a");
  link.href = url;
  link.download = fileName;
  link.style.display = "none";
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}
// TODO  My8zOmFIVnBZMlhsdEpUbXRiZm92b3UwZHBVUT06NzYyYmIzMWM=
