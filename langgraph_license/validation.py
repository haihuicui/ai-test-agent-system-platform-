"""
Custom license validation module.

This module overrides the official langgraph_license.validation to enable
enterprise features (like custom authentication) without requiring a license.

Original error message that this fixes:
"Custom authentication is currently available in the cloud version of LangSmith 
Deployment or with an self-hosting enterprise license."
"""


import structlog
# noqa  MC8zOmFIVnBZMlhsdEpUbXRiZm92b2s2VjBodFZnPT06MzMxZDgzMzE=

logger = structlog.stdlib.get_logger(__name__)

# Customer info (can be customized as needed)
CUSTOMER_ID = "custom-self-hosted"
CUSTOMER_NAME = "Self-Hosted Instance"


async def get_license_status() -> bool:
    """
    Always return True to indicate license is valid.
    
    This bypasses the enterprise license check, allowing features like:
    - Custom authentication
    - Crons
    - Other enterprise features
    """
    return True


def plus_features_enabled() -> bool:
    """
    Return True to enable all "plus" features.
    
    This is the key function that controls whether enterprise features 
    like custom authentication are enabled.
    """
    return True

# noqa  MS8zOmFIVnBZMlhsdEpUbXRiZm92b2s2VjBodFZnPT06MzMxZDgzMzE=

async def check_license_periodically(_: int = 60):
    """
    No-op license check. Does nothing since we're bypassing license validation.
    """
    await logger.ainfo(
        "Custom license module: License check bypassed. All features enabled."
    )
    return None


def validate_license_claims(claims: list[str]) -> bool:
    """
    Always return True to indicate all claims are valid.
    """
    return True
# type: ignore  Mi8zOmFIVnBZMlhsdEpUbXRiZm92b2s2VjBodFZnPT06MzMxZDgzMzE=


# Additional exports that might be expected by other modules
LICENSE_VALID = True
ENTERPRISE_ENABLED = True

