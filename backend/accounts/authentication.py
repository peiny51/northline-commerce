import os

import jwt
from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed


class Auth0JWTAuthentication(BaseAuthentication):
    def authenticate(self, request):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            if settings.DEMO_MODE:
                name = request.headers.get("X-Demo-User", "customer")
                if name not in {"customer", "agent", "manager"}:
                    raise AuthenticationFailed("Invalid demo identity.")
                # Demo accounts are created only with the explicit local demo switch.
                user, _ = get_user_model().objects.get_or_create(username=f"demo_{name}")
                return user, None
            return None

        token = header.removeprefix("Bearer ").strip()
        domain = os.getenv("AUTH0_DOMAIN", "").strip().replace("https://", "").rstrip("/")
        audience = os.getenv("AUTH0_AUDIENCE", "").strip()
        if not domain or not audience:
            raise AuthenticationFailed("Auth0 is not configured.")
        try:
            key = jwt.PyJWKClient(f"https://{domain}/.well-known/jwks.json").get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token, key.key, algorithms=["RS256"],
                audience=audience, issuer=f"https://{domain}/",
            )
        except jwt.PyJWTError as exc:
            raise AuthenticationFailed("Invalid access token.") from exc

        subject = claims.get("sub")
        if not subject:
            raise AuthenticationFailed("Missing token subject.")
        user, _ = get_user_model().objects.get_or_create(
            auth0_sub=subject, defaults={"username": f"auth0_{__import__('hashlib').sha256(subject.encode()).hexdigest()[:32]}"}
        )
        return user, claims
