# [가이드 3/8] schemas/<도메인>/ — tool 의 In/Out. Field(description=) 이 인자 설명이라 소비 쪽이 그대로 읽음.
# 복사 후 echo 를 실제 스키마로. 입력 필드마다 description 을 빠짐없이.

from pydantic import BaseModel, Field


class EchoIn(BaseModel):
    text: str = Field(description="되돌려받을 입력 텍스트 (예: '안녕하세요')")


class EchoOut(BaseModel):
    echo: str = Field(description="입력받은 텍스트 그대로")
    length: int = Field(description="입력 텍스트 길이(문자 수)")
