from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class AuthProviderInfo(BaseModel):
    """One linked OAuth provider on a user profile."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    provider: str | None = None
    email: str | None = None
    linked_at: str | None = None


class UserProfile(BaseModel):
    """The authenticated user, as returned by /auth/me and the token exchange."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    id: str
    email: str | None = None
    email_verified: bool | None = None
    user_name: str | None = None
    plan: str | None = None
    password_set: bool | None = None
    onboarded_at: str | None = None
    auth_providers: list[AuthProviderInfo] | None = None


class MeEnvelope(BaseModel):
    """Wire envelope of GET /auth/me; the SDK unwraps it to UserProfile."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    user: UserProfile


class OAuthTokens(BaseModel):
    """Token pair from the device-auth exchange or refresh.

    Refresh tokens rotate: after every refresh the previous refresh_token is
    dead, so always persist the newest pair.
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    access_token: str
    refresh_token: str
    user: UserProfile | None = None
