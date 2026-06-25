from __future__ import annotations

from pydantic import BaseModel, Field


class AuthPayload(BaseModel):
    account: str
    password: str
    nickname: str | None = None
    """注册时可选；不传或与账号相同时存库为默认（展示名等于用户 ID）。"""


class ProfilePayload(BaseModel):
    userId: str
    age: int | None = None
    gender: str | None = None
    height: float | None = None
    weight: float | None = None
    medicalHistory: str | None = None
    workHabit: str | None = None
    allergyHistory: str | None = None
    """留空或未传时服务端存为「无过敏史」。"""
    nickname: str | None = None
    """仅在请求体包含该字段时更新 users.nickname；可与个人信息一并提交。"""


class NicknamePayload(BaseModel):
    userId: str
    nickname: str | None = None
    """传 null 或空串表示恢复为默认（展示名等于用户 ID）。"""


class TcmTenQuestionsPayload(BaseModel):
    """从个人信息页单独保存中医十问到 assessment_records。"""

    userId: str
    tcmTenQuestions: dict


class JointHistoryItem(BaseModel):
    id: int | None = None
    analysisType: str | None = None
    createdAt: str | None = None
    report: str | None = None
    data: dict | None = None


class JointAnalyzePayload(BaseModel):
    userId: str
    items: list[JointHistoryItem]


class JointReportPayload(BaseModel):
    userId: str
    postureReport: str
    tongueReport: str
    postureAt: str | None = None
    tongueAt: str | None = None
    postureData: dict | None = None
    tongueData: dict | None = None
    tcmTenQuestions: dict | None = None
    """与舌苔/体态分析一并提交的中医十问；优先于库内旧记录用于联合报告综合理解。"""
    model: str | None = None
    """可选：DeepSeek 等模型名；不传则使用服务端环境变量默认。"""
    analysisMode: str | None = None
    """分析模式：normal 或 expert。"""


class JointUserRequirementAppend(BaseModel):
    userId: str
    text: str = ""
    clearExisting: bool = False
    """为 True 时仅清空已保存需求，忽略 text。"""
    recordId: int | None = None
    """assessment_records.id；个性化需求仅存于该表 user_requirements 列。"""


class JointDetailedAnalysisPayload(BaseModel):
    userId: str
    recordId: int | None = None
    maxRounds: int = 3
    model: str | None = None
    userRequirement: str | None = None
    analysisMode: str | None = None


class HistoryAnalysisItem(BaseModel):
    id: int | None = None
    createdAt: str | None = None
    postureReport: str | None = None
    tongueReport: str | None = None
    jointReport: str | None = None


class HistoryAnalysisPayload(BaseModel):
    userId: str
    items: list[HistoryAnalysisItem] = Field(default_factory=list)
    """前端勾选记录列表，至少提供 items[].id 或 recordIds。"""
    recordIds: list[int] | None = None
    """可选：仅传记录 id 列表（与 items 二选一或同时提供时合并去重）。"""
    model: str | None = None
    """可选：DeepSeek 模型名；不传则使用服务端环境变量默认。"""
