"""Refresh token rotation and revocation service."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional, Tuple
import secrets

from sqlalchemy.orm import Session

from app.config import settings
from app.core.exceptions import AuthenticationError
from app.core.security import create_access_token, create_refresh_token, decode_token
from app.models.security import RefreshToken
from app.models.user import User


class TokenService:
    """Manage refresh-token family lifecycle."""

    @staticmethod
    def _naive_utc(dt: datetime) -> datetime:
        return dt.replace(tzinfo=None) if dt and dt.tzinfo else dt

    @staticmethod
    def _create_refresh_record(
        db: Session,
        *,
        user_id: int,
        family_id: str,
        token_jti: str,
        expires_at: datetime,
    ) -> RefreshToken:
        record = RefreshToken(
            user_id=user_id,
            family_id=family_id,
            token_jti=token_jti,
            expires_at=expires_at,
            revoked=False,
        )
        db.add(record)
        db.flush()
        return record

    @staticmethod
    def issue_token_pair(db: Session, user: User) -> Tuple[str, str]:
        family_id = secrets.token_urlsafe(32)
        access_token = create_access_token({"sub": str(user.id), "username": user.username, "role": user.role})
        refresh_token = create_refresh_token(
            {"sub": str(user.id), "username": user.username, "role": user.role},
            family_id=family_id,
            expires_delta=timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
        refresh_payload = decode_token(refresh_token) or {}
        token_jti = refresh_payload.get("jti")
        exp = refresh_payload.get("exp")
        if not token_jti or not exp:
            raise AuthenticationError("Failed to generate refresh token")
        expires_at = datetime.utcfromtimestamp(exp)
        TokenService._create_refresh_record(
            db,
            user_id=user.id,
            family_id=family_id,
            token_jti=token_jti,
            expires_at=expires_at,
        )
        db.commit()
        return access_token, refresh_token

    @staticmethod
    def revoke_family(db: Session, family_id: str) -> int:
        tokens = (
            db.query(RefreshToken)
            .filter(RefreshToken.family_id == family_id, RefreshToken.revoked == False)  # noqa: E712
            .all()
        )
        now = datetime.utcnow()
        for token in tokens:
            token.revoked = True
            token.revoked_at = now
        db.commit()
        return len(tokens)

    @staticmethod
    def rotate_refresh_token(db: Session, refresh_token: str) -> Tuple[User, str, str]:
        payload = decode_token(refresh_token)
        if not payload:
            raise AuthenticationError("Invalid refresh token")
        if payload.get("typ") != "refresh":
            raise AuthenticationError("Token is not a refresh token")

        user_id_raw = payload.get("sub")
        token_jti = payload.get("jti")
        family_id = payload.get("fam")
        exp = payload.get("exp")
        if not user_id_raw or not token_jti or not family_id or not exp:
            raise AuthenticationError("Malformed refresh token")

        user = db.query(User).filter(User.id == int(user_id_raw)).first()
        if not user or not user.is_active:
            raise AuthenticationError("User not found or inactive")

        record = (
            db.query(RefreshToken)
            .filter(RefreshToken.token_jti == token_jti, RefreshToken.user_id == user.id)
            .first()
        )
        if not record:
            # Unknown token reuse attempt: revoke entire family defensively.
            TokenService.revoke_family(db, family_id)
            raise AuthenticationError("Refresh token not recognized")

        if record.revoked:
            TokenService.revoke_family(db, record.family_id)
            raise AuthenticationError("Refresh token already revoked")

        expires_claim = datetime.utcfromtimestamp(exp)
        record_exp = TokenService._naive_utc(record.expires_at)
        if expires_claim <= datetime.utcnow() or (record_exp and record_exp <= datetime.utcnow()):
            record.revoked = True
            record.revoked_at = datetime.utcnow()
            db.commit()
            raise AuthenticationError("Refresh token expired")

        # Rotate token.
        new_access = create_access_token({"sub": str(user.id), "username": user.username, "role": user.role})
        new_refresh = create_refresh_token(
            {"sub": str(user.id), "username": user.username, "role": user.role},
            family_id=record.family_id,
            expires_delta=timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
        new_payload = decode_token(new_refresh) or {}
        new_jti = new_payload.get("jti")
        new_exp = new_payload.get("exp")
        if not new_jti or not new_exp:
            raise AuthenticationError("Failed to rotate refresh token")

        record.revoked = True
        record.revoked_at = datetime.utcnow()
        record.replaced_by_jti = new_jti
        TokenService._create_refresh_record(
            db,
            user_id=user.id,
            family_id=record.family_id,
            token_jti=new_jti,
            expires_at=datetime.utcfromtimestamp(new_exp),
        )

        # Keep token family bounded.
        family_tokens = (
            db.query(RefreshToken)
            .filter(RefreshToken.family_id == record.family_id)
            .order_by(RefreshToken.created_at.desc())
            .all()
        )
        if len(family_tokens) > settings.MAX_REFRESH_TOKEN_FAMILY_SIZE:
            for stale in family_tokens[settings.MAX_REFRESH_TOKEN_FAMILY_SIZE:]:
                db.delete(stale)

        db.commit()
        return user, new_access, new_refresh

    @staticmethod
    def revoke_refresh_token(db: Session, refresh_token: str) -> bool:
        payload = decode_token(refresh_token)
        if not payload or payload.get("typ") != "refresh":
            return False
        token_jti = payload.get("jti")
        if not token_jti:
            return False
        record = db.query(RefreshToken).filter(RefreshToken.token_jti == token_jti).first()
        if not record:
            return False
        if not record.revoked:
            record.revoked = True
            record.revoked_at = datetime.utcnow()
            db.commit()
        return True


token_service = TokenService()
