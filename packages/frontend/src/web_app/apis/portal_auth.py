# ログインと認証アプリ登録の手順を管理する。
from __future__ import annotations

import json
from typing import Any

from pyodide.http import pyfetch

from apis import client


class LoginError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        messages = {
            "NotAuthorizedException": "入力内容を確認してください。認証の有効期限が切れた場合は、ログインからやり直してください。",
            "UserNotFoundException": "ユーザー名とパスワードを確認してください。",
            "InvalidPasswordException": "新しいパスワードには14文字以上で英大文字・英小文字・数字・記号を含めてください。",
            "CodeMismatchException": "確認コードが一致しません。最新のコードを入力してください。",
            "EnableSoftwareTokenMFAException": "認証アプリに表示された最新の6桁のコードを入力してください。",
            "ExpiredCodeException": "確認コードの有効期限が切れました。再設定を最初からやり直してください。",
            "LimitExceededException": "しばらく待ってから、もう一度お試しください。",
            "TooManyRequestsException": "しばらく待ってから、もう一度お試しください。",
            "InvalidParameterException": "手続きを続けられません。登録情報を管理者に確認してください。",
        }
        self.user_error = code in messages
        super().__init__(
            messages.get(code, "認証を完了できませんでした。ログインからやり直してください。")
        )


async def request(endpoint: str, operation: str, **payload: object) -> dict[str, Any]:
    """指定した認証操作を実行して応答を検査する。"""
    try:
        response = await pyfetch(
            endpoint,
            method="POST",
            headers={
                "Content-Type": "application/x-amz-json-1.1",
                "X-Amz-Target": "AWSCognitoIdentityProviderService." + operation,
            },
            body=json.dumps(payload),
            credentials="omit",
            redirect="error",
        )
        data: dict[str, Any] = await response.json()
    except Exception:
        raise ValueError("認証サービスに接続できませんでした。通信状況を確認してください。") from None
    if not response.ok:
        raise LoginError(data.get("__type", "").split("#")[-1])
    return data


class PortalLogin:
    def __init__(self, config: dict[str, Any]) -> None:
        self.endpoint = config["identity_endpoint"]
        self.client_id = config["client_id"]
        self.username = ""
        self.reset()

    def reset(self, step: str = "signin") -> None:
        """認証の途中状態を破棄する。"""
        self.step = step
        self.session = None
        self.secret = None

    async def call(self, operation: str, **fields: object) -> dict[str, Any]:
        """認証サービスに操作を送る。"""
        return await request(self.endpoint, operation, **fields)

    async def respond(self, challenge: str, **answers: str) -> dict[str, Any]:
        """現在のセッションでチャレンジに応答する。"""
        return await self.call(
            "RespondToAuthChallenge",
            ClientId=self.client_id,
            Session=self.session,
            ChallengeName=challenge,
            ChallengeResponses={"USERNAME": self.username, **answers},
        )

    async def submit(self, *, username: str = "", password: str = "", code: str = "") -> str | None:
        """入力内容で認証を次の手順へ進める。"""
        if self.step in {"signin", "forgot"}:
            self.username = username.strip()
        if self.step == "forgot":
            await self.call("ForgotPassword", ClientId=self.client_id, Username=self.username)
            self.step = "confirm_reset"
            return None
        if self.step == "confirm_reset":
            await self.call(
                "ConfirmForgotPassword",
                ClientId=self.client_id,
                Username=self.username,
                ConfirmationCode=code,
                Password=password,
            )
            self.reset()
            return None
        if self.step == "signin":
            try:
                result = await self.call(
                    "InitiateAuth",
                    ClientId=self.client_id,
                    AuthFlow="USER_PASSWORD_AUTH",
                    AuthParameters={"USERNAME": self.username, "PASSWORD": password},
                )
            except LoginError as exc:
                if exc.code != "PasswordResetRequiredException":
                    raise
                self.reset("forgot")
                raise client.InputError(
                    "パスワードの再設定が必要です。確認コードを受け取ってください。"
                ) from None
        elif self.step == "new_password":
            result = await self.respond("NEW_PASSWORD_REQUIRED", NEW_PASSWORD=password)
        elif self.step == "mfa":
            result = await self.respond("SOFTWARE_TOKEN_MFA", SOFTWARE_TOKEN_MFA_CODE=code)
        elif self.step == "setup":
            verified = await self.call("VerifySoftwareToken", Session=self.session, UserCode=code)
            if verified.get("Status") != "SUCCESS":
                raise LoginError("CodeMismatchException")
            self.session = verified["Session"]
            self.secret = None
            self.step = "finish_setup"
            result = await self.respond("MFA_SETUP")
        elif self.step == "finish_setup":
            result = await self.respond("MFA_SETUP")
        else:
            raise LoginError("UnknownChallenge")

        token: str | None = result.get("AuthenticationResult", {}).get("AccessToken")
        if token:
            self.reset()
            return token
        challenge = result.get("ChallengeName")
        session = result.get("Session")
        if not session or challenge not in {"NEW_PASSWORD_REQUIRED", "MFA_SETUP", "SOFTWARE_TOKEN_MFA"}:
            self.reset()
            raise LoginError("UnknownChallenge")
        params = result.get("ChallengeParameters", {})
        self.username = params.get("USER_ID_FOR_SRP") or params.get("USERNAME") or self.username
        self.session = session
        if challenge == "MFA_SETUP":
            try:
                registration = await self.call("AssociateSoftwareToken", Session=session)
                self.session = registration["Session"]
                self.secret = registration["SecretCode"]
            except Exception:
                self.reset()
                raise
            self.step = "setup"
        else:
            self.step = "new_password" if challenge == "NEW_PASSWORD_REQUIRED" else "mfa"
        return None
