# 各操作で返す業務エラーをOpenAPIに記載する。
from http import HTTPStatus

from app.schemas.outputs import ErrorDetail


def domain_errors(*statuses: int) -> dict:
    return {
        status: {"description": HTTPStatus(status).phrase, "model": ErrorDetail} for status in statuses
    }
