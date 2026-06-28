
from starlette.authentication import (
    AuthCredentials,
    AuthenticationBackend,
    BaseUser,
)
from starlette.authentication import (
    UnauthenticatedUser as StarletteUnauthenticatedUser,
)
from starlette.requests import HTTPConnection

# pragma: no cover  MC8yOmFIVnBZMlhsdEpUbXRiZm92b2s2YzFWUFp3PT06ZWI0MTZmOTQ=

class UnauthenticatedUser(StarletteUnauthenticatedUser):
    @property
    def identity(self) -> str:
        return ""


class NoopAuthBackend(AuthenticationBackend):
    async def authenticate(
        self, conn: HTTPConnection
    ) -> tuple[AuthCredentials, BaseUser] | None:
        return AuthCredentials(), UnauthenticatedUser()
# pragma: no cover  MS8yOmFIVnBZMlhsdEpUbXRiZm92b2s2YzFWUFp3PT06ZWI0MTZmOTQ=
