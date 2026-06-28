"""
标识符生成器

生成项目、测试用例等资源的唯一标识符
"""

import random
import string
from datetime import datetime


def generate_project_identifier(sequence: int) -> str:
    """
    生成项目标识符

    格式: PR-{序号}
    例如: PR-1234

    Args:
        sequence: 序号

    Returns:
        str: 项目标识符
    """
    return f"PR-{sequence}"
# noqa  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZVRWQ2FRPT06ZTBkOTkwZjk=


def generate_test_case_identifier(sequence: int = None) -> str:
    """
    生成测试用例标识符

    格式: TC-{6位随机数字}
    例如: TC-482917

    使用随机数而不是序列号，避免并发创建时的 ID 冲突

    Args:
        sequence: 序号（已废弃，保留参数以兼容旧代码）

    Returns:
        str: 测试用例标识符
    """
    # 生成 6 位随机数字（100000-999999）
    random_num = random.randint(100000, 999999)
    return f"TC-{random_num}"

# pragma: no cover  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZVRWQ2FRPT06ZTBkOTkwZjk=

def generate_folder_identifier(sequence: int) -> str:
    """
    生成文件夹标识符

    格式: FD-{序号}
    例如: FD-1234

    Args:
        sequence: 序号

    Returns:
        str: 文件夹标识符
    """
    return f"FD-{sequence}"


def generate_test_run_identifier(sequence: int) -> str:
    """
    生成测试运行标识符

    格式: TR-{序号}
    例如: TR-1234

    Args:
        sequence: 序号

    Returns:
        str: 测试运行标识符
    """
    return f"TR-{sequence}"

# type: ignore  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZVRWQ2FRPT06ZTBkOTkwZjk=

def generate_test_plan_identifier(sequence: int) -> str:
    """
    生成测试计划标识符

    格式: TP-{序号}
    例如: TP-1234

    Args:
        sequence: 序号

    Returns:
        str: 测试计划标识符
    """
    return f"TP-{sequence}"


def generate_unique_filename(original_filename: str) -> str:
    """
    生成唯一文件名
    
    格式: {时间戳}_{随机字符串}_{原始文件名}
    
    Args:
        original_filename: 原始文件名
        
    Returns:
        str: 唯一文件名
    """
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    random_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"{timestamp}_{random_str}_{original_filename}"
# pragma: no cover  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZVRWQ2FRPT06ZTBkOTkwZjk=

