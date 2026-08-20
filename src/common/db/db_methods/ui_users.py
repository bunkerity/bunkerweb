#!/usr/bin/env python3
from datetime import datetime, timedelta
from typing import List, Optional, Union

from model import (  # type: ignore
    Roles,
    RolesPermissions,
    RolesUsers,
    UserPreferences,
    UserRecoveryCodes,
    UserSessions,
    Users,
    UserWebauthnCredentials,
)

from sqlalchemy import delete, select, update
from sqlalchemy.orm import joinedload

from .common import DatabaseMixinBase


class DatabaseUIUsersMixin(DatabaseMixinBase):
    """Web UI users, sessions, recovery codes and RBAC reads."""

    def cleanup_expired_ui_sessions(self, max_age_days: int) -> str:
        """Remove UI sessions older than the provided age threshold."""
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            cutoff = datetime.now().astimezone() - timedelta(days=max_age_days)

            deleted = session.execute(delete(UserSessions).where(UserSessions.last_activity < cutoff).execution_options(synchronize_session=False)).rowcount

            try:
                session.commit()
            except BaseException as e:
                return str(e)

        return f"Removed {deleted} expired UI user sessions"

    def get_ui_users(self, *, as_dict: bool = False) -> Union[str, List[Union[Users, dict]]]:
        """Get ui users."""
        with self._db_session() as session:
            try:
                users = (
                    session.scalars(select(Users).options(joinedload(Users.roles), joinedload(Users.recovery_codes), joinedload(Users.preferences)))
                    .unique()
                    .all()
                )
                if not as_dict:
                    return users

                users_data = []
                for user in users:
                    user_data = {
                        "username": user.username,
                        "email": user.email,
                        "password": user.password.encode("utf-8"),
                        "method": user.method,
                        "admin": user.admin,
                        "theme": user.theme,
                        "totp_secret": user.totp_secret,
                        "creation_date": user.creation_date.astimezone(),
                        "update_date": user.update_date.astimezone(),
                        "roles": [role.role_name for role in user.roles],
                        "recovery_codes": [recovery_code.code for recovery_code in user.recovery_codes],
                    }

                    users_data.append(user_data)

                return users_data
            except BaseException as e:
                return str(e)

    def get_ui_user_sessions(self, username: str, current_session_id: Optional[str] = None) -> List[dict]:
        """Get ui user sessions."""
        with self._db_session() as session:
            sessions = []
            if current_session_id:
                current_session = session.scalars(select(UserSessions).filter_by(user_name=username, id=current_session_id)).all()
                other_sessions = session.scalars(
                    select(UserSessions).filter_by(user_name=username).where(UserSessions.id != current_session_id).order_by(UserSessions.creation_date.desc())
                ).all()
                query = current_session + other_sessions
            else:
                query = session.scalars(select(UserSessions).filter_by(user_name=username).order_by(UserSessions.creation_date.desc())).all()

            for session_data in query:
                sessions.append(
                    {
                        "id": session_data.id,
                        "ip": session_data.ip,
                        "user_agent": self._empty_if_none(session_data.user_agent),
                        "creation_date": session_data.creation_date,
                        "last_activity": session_data.last_activity,
                    }
                )

            return sessions

    def get_ui_user(self, *, username: Optional[str] = None, as_dict: bool = False) -> Optional[Union[Users, dict]]:
        """Get ui user. If username is None, return the first admin user."""
        with self._db_session() as session:
            query = select(Users)
            query = query.filter_by(username=username) if username else query.filter_by(admin=True)
            query = query.options(joinedload(Users.roles), joinedload(Users.recovery_codes), joinedload(Users.webauthn_credentials))

            ui_user = session.scalars(query.limit(1)).unique().first()
            if not ui_user:
                return None

            if not as_dict:
                return ui_user

            return {
                "username": ui_user.username,
                "email": ui_user.email,
                "password": ui_user.password.encode("utf-8"),
                "method": ui_user.method,
                "admin": ui_user.admin,
                "theme": ui_user.theme,
                "language": ui_user.language,
                "totp_secret": ui_user.totp_secret,
                "creation_date": ui_user.creation_date.astimezone(),
                "update_date": ui_user.update_date.astimezone(),
                "roles": [role.role_name for role in ui_user.roles],
                "recovery_codes": [rc.code for rc in ui_user.recovery_codes],
                # the UI's second-factor gate needs to know whether a passkey exists, without
                # paying for a second round trip on every request
                "webauthn_credentials_count": len(ui_user.webauthn_credentials),
            }

    def create_ui_user(
        self,
        username: str,
        password: bytes,
        roles: List[str],
        email: Optional[str] = None,
        *,
        theme: str = "light",
        language: str = "en",
        totp_secret: Optional[str] = None,
        totp_recovery_codes: Optional[List[str]] = None,
        creation_date: Optional[datetime] = None,
        method: str = "manual",
        admin: bool = False,
    ) -> str:
        """Create ui user."""
        from bcrypt import gensalt, hashpw

        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            if admin and session.execute(select(Users.username).filter_by(admin=True).limit(1)).first():
                return "An admin user already exists"

            user = session.execute(select(Users.username).filter_by(username=username).limit(1)).first()
            if user:
                return f"User {username} already exists"

            # Auto-create default roles and permissions if they don't exist
            _DEFAULT_ROLES = {
                "admin": ("Admins can create new users, edit and read the data.", ["manage", "write", "read"]),
                "writer": ("Writers can edit and read the data but can't create new users.", ["write", "read"]),
                "reader": ("Readers can only read the data.", ["read"]),
            }
            for role in roles:
                if not session.execute(select(Roles.name).filter_by(name=role).limit(1)).first():
                    if role in _DEFAULT_ROLES:
                        desc, perms = _DEFAULT_ROLES[role]
                        from model import Permissions, RolesPermissions  # type: ignore

                        session.add(Roles(name=role, description=desc, update_datetime=datetime.now().astimezone()))
                        for perm in perms:
                            if not session.execute(select(Permissions.name).filter_by(name=perm).limit(1)).first():
                                session.add(Permissions(name=perm))
                            session.add(RolesPermissions(role_name=role, permission_name=perm))
                    else:
                        return f"Role {role} doesn't exist"
                session.add(RolesUsers(user_name=username, role_name=role))

            current_time = datetime.now().astimezone()
            session.add(
                Users(
                    username=username,
                    email=email,
                    password=password.decode("utf-8"),
                    method=method,
                    admin=admin,
                    theme=theme,
                    language=language,
                    totp_secret=totp_secret,
                    creation_date=creation_date or current_time,
                    update_date=current_time,
                )
            )

            for code in totp_recovery_codes or []:
                session.add(UserRecoveryCodes(user_name=username, code=hashpw(code.encode("utf-8"), gensalt(rounds=10)).decode("utf-8")))

            try:
                session.commit()
            except BaseException as e:
                return str(e)

        return ""

    def update_ui_user(
        self,
        username: str,
        password: bytes,
        totp_secret: Optional[str],
        *,
        theme: str = "light",
        old_username: Optional[str] = None,
        email: Optional[str] = None,
        totp_recovery_codes: Optional[List[str]] = None,
        method: str = "manual",
        language: str = "en",
    ) -> str:
        """Update ui user."""
        totp_changed = False
        old_username = old_username or username
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            user = session.scalars(select(Users).filter_by(username=old_username).limit(1)).first()
            if not user:
                return f"User {old_username} doesn't exist"

            if username != old_username:
                if session.execute(select(Users.username).filter_by(username=username).limit(1)).first():
                    return f"User {username} already exists"

                user.username = username

                session.execute(update(RolesUsers).filter_by(user_name=old_username).values({"user_name": username}))
                session.execute(update(UserRecoveryCodes).filter_by(user_name=old_username).values({"user_name": username}))
                session.execute(update(UserSessions).filter_by(user_name=old_username).values({"user_name": username}))
                session.execute(update(UserPreferences).filter_by(user_name=old_username).values({"user_name": username}))
                session.execute(update(UserWebauthnCredentials).filter_by(user_name=old_username).values({"user_name": username}))

            totp_changed = user.totp_secret != totp_secret

            user.email = email
            user.password = password.decode("utf-8")
            user.totp_secret = totp_secret
            user.method = method
            user.theme = theme
            user.language = language
            user.update_date = datetime.now().astimezone()

            try:
                session.commit()
            except BaseException as e:
                return str(e)

        if totp_changed:
            if totp_recovery_codes:
                self.refresh_ui_user_recovery_codes(username, totp_recovery_codes)
            else:
                self._delete_ui_user_recovery_codes(username)

        return ""

    def mark_ui_user_login(self, username: str, date: datetime, ip: str, user_agent: str) -> Union[str, int]:
        """Mark ui user login."""
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            user = session.scalars(select(Users).filter_by(username=username).limit(1)).first()
            if not user:
                return f"User {username} doesn't exist"

            user_session = UserSessions(
                user_name=username,
                ip=ip,
                user_agent=user_agent,
                creation_date=date,
                last_activity=date,
            )
            session.add(user_session)

            try:
                session.flush()
                session_id = user_session.id
                session.commit()
                return session_id
            except BaseException as e:
                return str(e)

    def delete_ui_user_old_sessions(self, username: str, keep_session_id: Optional[int] = None) -> str:
        """Delete every session of a ui user except ``keep_session_id``.

        The caller's own session id must be passed explicitly: keeping the newest row instead
        would spare an attacker who logged in more recently than the caller and delete the
        caller's own session. ``None`` means there is no current row to keep, so all are deleted.
        """
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            user = session.scalars(select(Users).filter_by(username=username).limit(1)).first()
            if not user:
                return f"User {username} doesn't exist"

            query = select(UserSessions).filter_by(user_name=username)
            if keep_session_id is not None:
                query = query.filter(UserSessions.id != keep_session_id)
            for session_to_delete in session.scalars(query).all():
                session.delete(session_to_delete)

            try:
                session.commit()
            except BaseException as e:
                return str(e)

        return ""

    def refresh_ui_user_recovery_codes(self, username: str, codes: List[str]) -> str:
        """Refresh ui user recovery codes."""
        from bcrypt import gensalt, hashpw

        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            if not codes:
                return "No recovery codes provided"

            user = session.scalars(select(Users).filter_by(username=username).limit(1)).first()
            if not user:
                return f"User {username} doesn't exist"

            session.execute(delete(UserRecoveryCodes).filter_by(user_name=username))

            for code in codes:
                session.add(UserRecoveryCodes(user_name=username, code=hashpw(code.encode("utf-8"), gensalt(rounds=10)).decode("utf-8")))

            try:
                session.commit()
            except BaseException as e:
                return str(e)

        return ""

    def _delete_ui_user_recovery_codes(self, username: str) -> str:
        """Delete ui user recovery codes."""
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            session.execute(delete(UserRecoveryCodes).filter_by(user_name=username))

            try:
                session.commit()
            except BaseException as e:
                return str(e)

        return ""

    def use_ui_user_recovery_code(self, username: str, hashed_code: str) -> str:
        """Use ui user recovery code."""
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            user = session.scalars(select(Users).filter_by(username=username).limit(1)).first()
            if not user:
                return f"User {username} doesn't exist"

            recovery_code = session.scalars(select(UserRecoveryCodes).filter_by(user_name=username, code=hashed_code).limit(1)).first()
            if not recovery_code:
                return "Invalid recovery code"

            session.delete(recovery_code)

            try:
                session.commit()
            except BaseException as e:
                return str(e)

        return ""

    def mark_ui_user_access(self, session_id, date):
        """Mark ui user access."""
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"
            user_session = session.scalars(select(UserSessions).filter_by(id=session_id).limit(1)).first()
            if not user_session:
                return f"Session {session_id} doesn't exist"
            user_session.last_activity = date
            try:
                session.commit()
            except BaseException as e:
                return str(e)
        return ""

    def get_ui_user_preference(self, username, key, default=None):
        """Get one of a ui user's preferences."""
        with self._db_session() as session:
            preference = session.scalars(select(UserPreferences).filter_by(user_name=username, key=key).limit(1)).first()
            if not preference:
                return {} if default is None else default
            return preference.value

    def set_ui_user_preference(self, username, key, value):
        """Set one of a ui user's preferences, creating it if it does not exist yet."""
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"
            user = session.scalars(select(Users).filter_by(username=username).limit(1)).first()
            if not user:
                return f"User {username} doesn't exist"
            preference = session.scalars(select(UserPreferences).filter_by(user_name=username, key=key).limit(1)).first()
            if not preference:
                session.add(UserPreferences(user_name=username, key=key, value=value))
            else:
                preference.value = value
            try:
                session.commit()
            except BaseException as e:
                return str(e)
        return ""

    def get_ui_role_permissions(self, role_name):
        """Get ui role permissions."""
        with self._db_session() as session:
            return [permission.permission_name for permission in session.execute(select(RolesPermissions.permission_name).filter_by(role_name=role_name))]

    @staticmethod
    def _webauthn_credential_to_dict(credential: UserWebauthnCredentials) -> dict:
        """Serialize a WebAuthn credential row. Only public material, no secrets involved."""
        return {
            "username": credential.user_name,
            "credential_id": credential.credential_id,
            "user_handle": credential.user_handle,
            "public_key": credential.public_key,
            "sign_count": credential.sign_count,
            "transports": [t for t in (credential.transports or "").split(",") if t],
            "device_type": credential.device_type,
            "backed_up": credential.backed_up,
            "name": credential.name,
            "creation_date": credential.creation_date.astimezone(),
            "last_used": credential.last_used.astimezone() if credential.last_used else None,
        }

    def get_ui_user_webauthn_credentials(self, username: str, *, as_dict: bool = False) -> List[Union[UserWebauthnCredentials, dict]]:
        """Get every WebAuthn credential registered by a ui user, newest last."""
        with self._db_session() as session:
            credentials = session.scalars(select(UserWebauthnCredentials).filter_by(user_name=username).order_by(UserWebauthnCredentials.creation_date)).all()
            if not as_dict:
                return list(credentials)
            return [self._webauthn_credential_to_dict(credential) for credential in credentials]

    def get_ui_user_webauthn_credential(self, credential_id: str, *, as_dict: bool = False) -> Optional[Union[UserWebauthnCredentials, dict]]:
        """Get a single WebAuthn credential by its credential ID, whatever user owns it.

        This is the passwordless lookup: the assertion carries a credential ID but no username, so
        the owner has to be resolved from the credential itself.
        """
        with self._db_session() as session:
            credential = session.scalars(select(UserWebauthnCredentials).filter_by(credential_id=credential_id).limit(1)).first()
            if not credential:
                return None
            return self._webauthn_credential_to_dict(credential) if as_dict else credential

    def get_ui_user_webauthn_handle(self, username: str) -> Optional[str]:
        """Get the user handle already used by this user's credentials, if any.

        Every credential of a given user must share one handle so authenticators recognize a second
        passkey as belonging to the same account instead of creating a duplicate entry.
        """
        with self._db_session() as session:
            return session.scalars(select(UserWebauthnCredentials.user_handle).filter_by(user_name=username).limit(1)).first()

    def create_ui_user_webauthn_credential(
        self,
        username: str,
        *,
        credential_id: str,
        user_handle: str,
        public_key: str,
        sign_count: int = 0,
        transports: Optional[List[str]] = None,
        device_type: Optional[str] = None,
        backed_up: bool = False,
        name: str,
        creation_date: Optional[datetime] = None,
    ) -> str:
        """Register a verified WebAuthn credential for a ui user."""
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            user = session.scalars(select(Users).filter_by(username=username).limit(1)).first()
            if not user:
                return f"User {username} doesn't exist"

            if session.scalars(select(UserWebauthnCredentials).filter_by(credential_id=credential_id).limit(1)).first():
                return "This credential already exists"

            session.add(
                UserWebauthnCredentials(
                    user_name=username,
                    credential_id=credential_id,
                    user_handle=user_handle,
                    public_key=public_key,
                    sign_count=sign_count,
                    transports=",".join(transports) if transports else None,
                    device_type=device_type,
                    backed_up=backed_up,
                    name=name,
                    creation_date=creation_date or datetime.now().astimezone(),
                )
            )

            try:
                session.commit()
            except BaseException as e:
                return str(e)

        return ""

    def update_ui_user_webauthn_credential(
        self,
        credential_id: str,
        *,
        sign_count: Optional[int] = None,
        last_used: Optional[datetime] = None,
        name: Optional[str] = None,
    ) -> str:
        """Update a WebAuthn credential after a successful ceremony, or rename it."""
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            credential = session.scalars(select(UserWebauthnCredentials).filter_by(credential_id=credential_id).limit(1)).first()
            if not credential:
                return "Credential not found"

            if sign_count is not None:
                credential.sign_count = sign_count
            if last_used is not None:
                credential.last_used = last_used
            if name is not None:
                credential.name = name

            try:
                session.commit()
            except BaseException as e:
                return str(e)

        return ""

    def delete_ui_user_webauthn_credential(self, username: str, credential_id: str) -> str:
        """Delete a WebAuthn credential. Scoped by username so a user can only remove their own."""
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            credential = session.scalars(select(UserWebauthnCredentials).filter_by(user_name=username, credential_id=credential_id).limit(1)).first()
            if not credential:
                return "Credential not found"

            session.delete(credential)

            try:
                session.commit()
            except BaseException as e:
                return str(e)

        return ""
