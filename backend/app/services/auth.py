"""Minimal account registration and authentication service."""

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import create_access_token, hash_password, verify_password
from app.models import User
from app.repositories import UserRepository
from app.schemas import LoginRequest, RegisterRequest, TokenResponse, UserRead
from app.services.exceptions import DuplicateUserError, InvalidCredentialsError


class AuthService:
    """Register users and issue bearer access tokens."""

    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or Settings.from_env()
        self.users = UserRepository(session)

    def register(self, data: RegisterRequest) -> TokenResponse:
        """Create a unique account and immediately authenticate it."""
        email = str(data.email).casefold()
        if self.users.get_by_email(email) is not None:
            raise DuplicateUserError("an account with this email already exists")
        user = self.users.create(
            email=email,
            password_hash=hash_password(data.password),
            full_name=data.full_name,
        )
        self._commit()
        return self._token_response(user)

    def login(self, data: LoginRequest) -> TokenResponse:
        """Authenticate an email/password pair and issue an access token."""
        user = self.users.get_by_email(str(data.email).casefold())
        if user is None or not verify_password(data.password, user.password_hash):
            raise InvalidCredentialsError("invalid email or password")
        return self._token_response(user)

    def _token_response(self, user: User) -> TokenResponse:
        token = create_access_token(
            user.id,
            secret_key=self.settings.jwt_secret_key,
            algorithm=self.settings.jwt_algorithm,
            expires_minutes=self.settings.jwt_access_token_expire_minutes,
        )
        return TokenResponse(access_token=token, user=UserRead.model_validate(user))

    def _commit(self) -> None:
        try:
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
