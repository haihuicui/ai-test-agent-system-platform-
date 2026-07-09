"""
敏感数据加密工具

使用 Fernet 对称加密存储项目环境配置中的 token、api_key 等敏感字段。
密钥来自环境变量 TESTAGENT_SECRET_KEY（通过 settings.testagent_secret_key 读取）。

注意：
- 这是企业级最小可行方案，后续可替换为 Vault/KMS 集成，但接口保持兼容。
- 密钥必须在生产环境部署时显式设置，否则服务启动后无法加密/解密敏感数据。
"""

from cryptography.fernet import Fernet, InvalidToken

from app.config.settings import settings


class SecretEncryptionError(Exception):
    """敏感数据加密/解密异常"""
    pass


def _get_fernet() -> Fernet:
    """
    获取 Fernet 实例

    Returns:
        Fernet 实例

    Raises:
        SecretEncryptionError: 当未配置 testagent_secret_key 时
    """
    key = settings.testagent_secret_key
    if not key:
        raise SecretEncryptionError(
            "TESTAGENT_SECRET_KEY 未配置，无法加密/解密敏感数据。"
            "请在 .env 中设置 TESTAGENT_SECRET_KEY，"
            "可通过 python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\" 生成。"
        )
    # Fernet 要求 key 为 32 字节 url-safe base64 编码字符串
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except ValueError as e:
        raise SecretEncryptionError(f"TESTAGENT_SECRET_KEY 格式无效: {e}") from e


def encrypt_secret(plain_text: str | None) -> str | None:
    """
    加密敏感字符串

    Args:
        plain_text: 明文，可为 None

    Returns:
        加密后的字符串；输入为 None 时返回 None

    Raises:
        SecretEncryptionError: 加密失败或密钥未配置
    """
    if plain_text is None:
        return None
    try:
        fernet = _get_fernet()
        return fernet.encrypt(plain_text.encode("utf-8")).decode("utf-8")
    except SecretEncryptionError:
        raise
    except Exception as e:
        raise SecretEncryptionError(f"加密失败: {e}") from e


def decrypt_secret(cipher_text: str | None) -> str | None:
    """
    解密敏感字符串

    Args:
        cipher_text: 密文，可为 None

    Returns:
        解密后的明文；输入为 None 时返回 None

    Raises:
        SecretEncryptionError: 解密失败、密钥未配置或密文被篡改
    """
    if cipher_text is None:
        return None
    try:
        fernet = _get_fernet()
        return fernet.decrypt(cipher_text.encode("utf-8")).decode("utf-8")
    except InvalidToken as e:
        raise SecretEncryptionError("解密失败：密文无效或密钥不匹配") from e
    except SecretEncryptionError:
        raise
    except Exception as e:
        raise SecretEncryptionError(f"解密失败: {e}") from e
