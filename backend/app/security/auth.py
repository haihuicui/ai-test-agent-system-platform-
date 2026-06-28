from dotenv import load_dotenv
from langgraph_sdk import Auth
import os
from jose import jwt

# VALID_TOKENS = {
#     "user1-token": {"id": "user1", "name": "Alice"},
#     "user2-token": {"id": "user2", "name": "Bob"},
# }
load_dotenv()
auth = Auth()
AUTH_SECRET = os.environ["AUTH_DEV_SECRET"]
AUTH_AUDIENCE = os.environ.get("AUTH_AUDIENCE")
print(f"AUTH_AUDIENCE: {AUTH_AUDIENCE}")
# @auth.authenticate
# async def get_current_user(authorization: str | None) -> Auth.types.MinimalUserDict:
#     """Our authentication handler from the previous tutorial."""
#     assert authorization
#     scheme, token = authorization.split()
#     assert scheme.lower() == "bearer"
#
#     if token not in VALID_TOKENS:
#         raise Auth.exceptions.HTTPException(status_code=401, detail="Invalid token")
#
#     user_data = VALID_TOKENS[token]
#     return {
#         "identity": user_data["id"],
#     }
# pragma: no cover  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2VWxrNVJRPT06OTdhYjk5MmE=

@auth.authenticate
async def get_current_user(authorization: str | None) -> Auth.types.MinimalUserDict:
    """Validate JWT tokens issued by our own login service.

    Expects an Authorization header of the form "Bearer <token>" where
    <token> is a JWT signed with AUTH_DEV_SECRET and audience AUTH_AUDIENCE.
    """
    print(f"in authenticate middleware,the authorization is{authorization} ")
# pylint: disable  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2VWxrNVJRPT06OTdhYjk5MmE=

    # 临时测试用
    authorization = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJkZXYtdXNlciIsImVtYWlsIjoiZGV2LXVzZXJAZGV2LmxvY2FsIiwiYXVkIjoibGFuZ2dyYXBoLWRldiIsImlhdCI6MTc3ODU3MjI5NiwiZXhwIjoyMDkzOTMyMjk2fQ.dWcdKr8572NP2Xz1L2lUy9-v1w4ctcDpmNxnRODtw7k"
    if not authorization:
        raise Auth.exceptions.HTTPException(status_code=401, detail="Missing authorization header")

    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise ValueError("Unsupported auth scheme")

        payload = jwt.decode(
            token,
            AUTH_SECRET,
            algorithms=["HS256"],
            audience=AUTH_AUDIENCE,
        )
        print(f"payload is {payload}")
        return {
            "identity": payload["sub"],  # Unique user identifier
            "email": payload.get("email"),
            "is_authenticated": True,
        }
    except Exception as e:  # pragma: no cover - keep error simple for now
        raise Auth.exceptions.HTTPException(status_code=401, detail=str(e))


# pragma: no cover  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2VWxrNVJRPT06OTdhYjk5MmE=

@auth.on
async def add_owner(
    ctx: Auth.types.AuthContext,  # Contains info about the current user
    value: dict,  # The resource being created/accessed
):
    """Make resources private to their creator."""
    # Examples:
    # ctx: AuthContext(
    #     permissions=[],
    #     user=ProxyUser(
    #         identity='user1',
    #         is_authenticated=True,
    #         display_name='user1'
    #     ),
    #     resource='threads',
    #     action='create_run'
    # )
    # value:
    # {
    #     'thread_id': UUID('1e1b2733-303f-4dcd-9620-02d370287d72'),
    #     'assistant_id': UUID('fe096781-5601-53d2-b2f6-0d3403f7e9ca'),
    #     'run_id': UUID('1efbe268-1627-66d4-aa8d-b956b0f02a41'),
    #     'status': 'pending',
    #     'metadata': {},
    #     'prevent_insert_if_inflight': True,
    #     'multitask_strategy': 'reject',
    #     'if_not_exists': 'reject',
    #     'after_seconds': 0,
    #     'kwargs': {
    #         'input': {'messages': [{'role': 'user', 'content': 'Hello!'}]},
    #         'command': None,
    #         'config': {
    #             'configurable': {
    #                 'langgraph_auth_user': ... Your user object...
    #                 'langgraph_auth_user_id': 'user1'
    #             }
    #         },
    #         'stream_mode': ['values'],
    #         'interrupt_before': None,
    #         'interrupt_after': None,
    #         'webhook': None,
    #         'feedback_keys': None,
    #         'temporary': False,
    #         'subgraphs': False
    #     }
    # }
# pylint: disable  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2VWxrNVJRPT06OTdhYjk5MmE=

    # Does 2 things:
    # 1. Add the user's ID to the resource's metadata. Each LangGraph resource has a `metadata` dict that persists with the resource.
    # this metadata is useful for filtering in read and update operations
    # 2. Return a filter that lets users only see their own resources
    print(f"in add_owner middleware,the ctx.user.identity is{ctx.user.identity} ")
    metadata = value.setdefault("metadata", {})
    metadata["owner"] = ctx.user.identity

    # 对于查询/读取操作，不限制 owner filter，允许访问 system 创建的默认 assistant
    if ctx.action in ("search", "read"):
        return {}

    # 对于创建/更新/删除操作，返回 owner filter 确保用户只能操作自己的资源
    return {"owner": ctx.user.identity}