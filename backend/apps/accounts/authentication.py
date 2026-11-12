import re
import jwt
import uuid
import json
import base64
import urllib.parse
import logging
from datetime import datetime, timedelta, timezone
from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

logger = logging.getLogger(__name__)
User = get_user_model()

JWT_SEGMENT_REGEX = re.compile(r'^[A-Za-z0-9_-]+$')


def is_valid_jwt_format(val: str) -> bool:
    """
    Validates that a string has the exact 3-part 'header.payload.signature' structure of a JWT
    with valid base64url characters in each segment.
    """
    if not val or not isinstance(val, str):
        return False
    clean = val.strip('"\' \t\r\n')
    parts = clean.split('.')
    if len(parts) != 3:
        return False
    return all(len(p) > 0 and bool(JWT_SEGMENT_REGEX.match(p)) for p in parts)


def parse_cookie_payload(raw_val: str):
    """
    Parses cookie value which may be:
    - Raw JWT string ('eyJhbGciOi...')
    - JSON dictionary string ('{"access_token": "...", "refresh_token": "..."}')
    - URL-encoded JSON string ('%7B%22access_token%22...')
    - Base64-encoded JSON string ('eyJhY2Nlc3NfdG9rZW4i...')
    - URL-encoded Base64 string
    """
    if not raw_val or not isinstance(raw_val, str):
        return None

    clean_raw = raw_val.strip('"\' \t\r\n')
    if is_valid_jwt_format(clean_raw):
        return {'access_token': clean_raw}

    candidates = [clean_raw]
    try:
        unquoted = urllib.parse.unquote(clean_raw)
        if unquoted != clean_raw:
            candidates.append(unquoted)
    except Exception:
        pass

    for cand in list(candidates):
        clean_cand = cand.strip('"\' \t\r\n')
        if is_valid_jwt_format(clean_cand):
            return {'access_token': clean_cand}

        # 1. Try parsing as JSON
        try:
            parsed = json.loads(clean_cand)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

        # 2. Try Base64 decoding
        try:
            if len(clean_cand) >= 8 and not any(c in clean_cand for c in ' \t\r\n{}[]"'):
                b64_bytes = base64.b64decode(clean_cand, validate=True)
                b64_str = b64_bytes.decode('utf-8', errors='ignore').strip('"\' \t\r\n')
                if is_valid_jwt_format(b64_str):
                    return {'access_token': b64_str}
                parsed = json.loads(b64_str)
                if isinstance(parsed, dict):
                    return parsed
        except Exception:
            pass

    return None


def extract_access_token_from_cookies(cookies: dict) -> str | None:
    """
    Extracts access_token from cookies, supporting arena.ai auth cookies
    ('arena-auth-prod-v1.0', 'arena-auth-prod-v1.1', 'access_token', 'token', etc.).
    """
    if not cookies:
        return None

    target_keys = ['arena-auth-prod-v1.0', 'arena-auth-prod-v1.1', 'access_token', 'token', 'auth_token', 'session_token']
    for key in target_keys:
        raw_val = cookies.get(key)
        if not raw_val:
            continue

        parsed = parse_cookie_payload(raw_val)
        if isinstance(parsed, dict):
            token = (
                parsed.get('access_token')
                or parsed.get('token')
                or (parsed.get('tokens') and parsed['tokens'].get('access_token'))
            )
            if token and isinstance(token, str):
                token_clean = token.strip('"\' \t\r\n')
                if token_clean.lower() not in ('undefined', 'null', 'none', '[object object]', ''):
                    return token_clean
        elif isinstance(parsed, str):
            token_clean = parsed.strip('"\' \t\r\n')
            if token_clean.lower() not in ('undefined', 'null', 'none', '[object object]', ''):
                return token_clean

    return None


def extract_refresh_token_from_cookies(cookies: dict) -> str | None:
    """
    Extracts refresh_token from cookies, supporting arena.ai auth cookies and HttpOnly refresh cookies.
    """
    if not cookies:
        return None

    target_keys = ['refresh_token', 'arena-auth-prod-v1.0', 'arena-auth-prod-v1.1', 'token']
    for key in target_keys:
        raw_val = cookies.get(key)
        if not raw_val:
            continue

        parsed = parse_cookie_payload(raw_val)
        if isinstance(parsed, dict):
            token = (
                parsed.get('refresh_token')
                or (parsed.get('tokens') and parsed['tokens'].get('refresh_token'))
            )
            if token and isinstance(token, str):
                token_clean = token.strip('"\' \t\r\n')
                if token_clean.lower() not in ('undefined', 'null', 'none', '[object object]', ''):
                    return token_clean
        elif key == 'refresh_token' and isinstance(raw_val, str):
            token_clean = raw_val.strip('"\' \t\r\n')
            if token_clean.lower() not in ('undefined', 'null', 'none', '[object object]', ''):
                return token_clean

    return None


class JWTTokenService:
    @staticmethod
    def generate_tokens_for_user(user):
        """Generate Access Token (60 mins) and Refresh Token (7 days)."""
        now = datetime.now(timezone.utc)
        refresh_jti = str(uuid.uuid4())
        
        access_payload = {
            'user_id': str(user.id),
            'sub': str(user.id),
            'email': user.email,
            'role': user.role,
            'full_name': user.full_name,
            'type': 'access',
            'exp': now + timedelta(minutes=60),
            'iat': now,
        }
        refresh_payload = {
            'user_id': str(user.id),
            'sub': str(user.id),
            'email': user.email,
            'jti': refresh_jti,
            'type': 'refresh',
            'exp': now + timedelta(days=7),
            'iat': now,
        }

        access_token = jwt.encode(access_payload, settings.SECRET_KEY, algorithm='HS256')
        refresh_token = jwt.encode(refresh_payload, settings.SECRET_KEY, algorithm='HS256')

        return {
            'access_token': access_token,
            'refresh_token': refresh_token,
            'expires_in': 3600,
        }

    @staticmethod
    def decode_token(token, expected_type='access'):
        try:
            clean_token = token.strip('"\' \t\r\n') if isinstance(token, str) else token
            payload = jwt.decode(clean_token, settings.SECRET_KEY, algorithms=['HS256'])
            now_ts = datetime.now(timezone.utc).timestamp()
            exp_ts = payload.get('exp', 0)
            is_expired = now_ts > exp_ts

            logger.info(
                f"[JWT DECODE] type={payload.get('type')} user_id={payload.get('user_id')} "
                f"email={payload.get('email')} role={payload.get('role')} "
                f"exp={exp_ts} current_ts={int(now_ts)} is_expired={is_expired}"
            )

            token_type = payload.get('type') or ('access' if expected_type == 'access' else payload.get('type'))
            if token_type != expected_type:
                logger.warning(f"[JWT DECODE] Type mismatch: got '{payload.get('type')}', expected '{expected_type}'")
                raise AuthenticationFailed(f'Invalid token type. Expected {expected_type}.')

            if expected_type == 'refresh':
                jti = payload.get('jti')
                if jti:
                    from apps.accounts.models import RevokedRefreshToken
                    if RevokedRefreshToken.objects.filter(token_jti=jti).exists():
                        logger.warning(f"[JWT DECODE] Refresh token with jti={jti} has been revoked.")
                        raise AuthenticationFailed('This refresh token has been revoked.')

            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("[JWT DECODE] Signature expired.")
            raise AuthenticationFailed('Token has expired.')
        except jwt.InvalidTokenError as e:
            logger.warning(f"[JWT DECODE] Invalid token error: {e}")
            raise AuthenticationFailed('Invalid token.')

    @staticmethod
    def revoke_refresh_token(token, user):
        try:
            clean_token = token.strip('"\' \t\r\n') if isinstance(token, str) else token
            payload = jwt.decode(clean_token, settings.SECRET_KEY, algorithms=['HS256'])
            jti = payload.get('jti')
            if jti:
                from apps.accounts.models import RevokedRefreshToken
                RevokedRefreshToken.objects.get_or_create(token_jti=jti, user=user)
        except Exception:
            pass


class JWTAuthentication(BaseAuthentication):
    """
    Authoritative Custom JWT Authentication supporting:
    1. 'Authorization: Bearer <token>' header (case-insensitive, whitespace tolerant)
    2. 'HTTP_AUTHORIZATION' WSGI meta
    3. Cookies ('arena-auth-prod-v1.0', 'arena-auth-prod-v1.1', 'access_token', 'token')
    """
    def authenticate_header(self, request):
        return 'Bearer realm="api"'

    def authenticate(self, request):
        auth_header = (
            request.headers.get('Authorization')
            or request.headers.get('authorization')
            or request.META.get('HTTP_AUTHORIZATION')
            or request.META.get('Authorization')
        )
        token = None

        if auth_header:
            parts = auth_header.strip().split()
            if len(parts) == 2 and parts[0].lower() == 'bearer':
                candidate = parts[1].strip('"\' \t\r\n')
                if candidate.lower() not in ('undefined', 'null', 'none', '[object object]', ''):
                    token = candidate
            elif len(parts) == 1 and not parts[0].lower().startswith('basic'):
                candidate = parts[0].strip('"\' \t\r\n')
                if candidate.lower() not in ('undefined', 'null', 'none', '[object object]', ''):
                    token = candidate

        # Extract from cookies (including arena-auth-prod-v1.0, arena-auth-prod-v1.1, access_token)
        if not token:
            token = extract_access_token_from_cookies(request.COOKIES)

        has_token = bool(token)
        token_len = len(token) if token else 0
        has_arena_cookie = 'arena-auth-prod-v1.0' in request.COOKIES or 'arena-auth-prod-v1.1' in request.COOKIES

        logger.info(
            f"[DJANGO AUTH] method={request.method} path={request.path} "
            f"auth_source={'HEADER' if auth_header and token else ('COOKIE' if token else 'NONE')} "
            f"token_len={token_len} arena_cookie={'YES' if has_arena_cookie else 'NO'}"
        )

        if not token:
            return None

        payload = JWTTokenService.decode_token(token, expected_type='access')
        user_id = payload.get('user_id') or payload.get('sub') or payload.get('id')
        email = payload.get('email') or payload.get('user_email')

        user = None
        if user_id:
            try:
                user = User.objects.get(id=user_id, is_active=True)
            except (User.DoesNotExist, ValueError):
                pass

        if not user and email:
            try:
                user = User.objects.get(email=email, is_active=True)
            except User.DoesNotExist:
                pass

        if not user:
            logger.warning(f"[DJANGO AUTH] User id={user_id} / email={email} does not exist or is inactive.")
            raise AuthenticationFailed('User not found or deactivated.')

        return (user, token)
