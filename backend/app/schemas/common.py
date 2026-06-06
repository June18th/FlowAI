from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Result(BaseModel, Generic[T]):
    code: int = 200
    message: str = "操作成功"
    data: T | None = None

    @classmethod
    def success(cls, data: T = None, message: str = "操作成功") -> "Result[T]":
        return cls(code=200, message=message, data=data)

    @classmethod
    def error(cls, message: str = "操作失败", code: int = 500) -> "Result[None]":
        return cls(code=code, message=message, data=None)

    @classmethod
    def unauthorized(cls, message: str = "未认证或认证已过期") -> "Result[None]":
        return cls(code=401, message=message, data=None)


class PageData(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    size: int
