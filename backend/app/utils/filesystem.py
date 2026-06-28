from deepagents.backends import FilesystemBackend
# type: ignore  MC8yOmFIVnBZMlhsdEpUbXRiZm92b2s2VTA1Sk13PT06ZDZiZGJjNmY=

# fmt: off  MS8yOmFIVnBZMlhsdEpUbXRiZm92b2s2VTA1Sk13PT06ZDZiZGJjNmY=

class FixedFilesystemBackend(FilesystemBackend):
    """修复 Windows 路径分隔符问题的 FilesystemBackend

    在 Windows 上，ls_info 返回的路径可能混合了 / 和 \\ 分隔符。
    这个子类确保所有返回的路径都使用 POSIX 格式（只用 /）。
    """

    def ls_info(self, path: str) -> list:
        """列出目录内容，确保返回 POSIX 格式的路径"""
        results = super().ls_info(path)
        # 修复路径分隔符：将 \\ 替换为 /
        for item in results:
            if 'path' in item:
                # 将反斜杠替换为正斜杠，但保留开头的 /
                original = item['path']
                fixed = '/' + original.lstrip('/').replace('\\', '/')
                item['path'] = fixed
                # 调试日志
                import logging
                logger = logging.getLogger(__name__)
                logger.info(f"[FixedFilesystemBackend] ls_info({path}): {repr(original)} -> {repr(fixed)}")
        return results
