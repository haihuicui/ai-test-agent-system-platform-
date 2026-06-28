
from langgraph_sdk.auth.types import StudioUser as StudioUserBase
from starlette.authentication import BaseUser
# noqa  MC8yOmFIVnBZMlhsdEpUbXRiZm92b2s2WTNkQmVnPT06NWYzYTg3NjI=


class StudioUser(StudioUserBase, BaseUser):
    """StudioUser class."""

    def dict(self):
        return {
            "kind": "StudioUser",
            "is_authenticated": self.is_authenticated,
            "display_name": self.display_name,
            "identity": self.identity,
            "permissions": self.permissions,
        }
# pylint: disable  MS8yOmFIVnBZMlhsdEpUbXRiZm92b2s2WTNkQmVnPT06NWYzYTg3NjI=
