from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    """每个「前端传来的 userId」对应一行，用来区分不同用户。"""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    client_user_id: Mapped[str] = mapped_column(String(256), unique=True, index=True)
    # 展示用昵称；为空则接口层按 client_user_id 作为默认显示名（兼容旧数据）
    nickname: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    records: Mapped[list["AssessmentRecord"]] = relationship(back_populates="user")
    profile: Mapped["UserProfile | None"] = relationship(back_populates="user", uselist=False)


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(256), unique=True, index=True)
    password: Mapped[str] = mapped_column(String(256))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AssessmentRecord(Base):
    """每次调用分析接口产生一条历史记录。"""
    __tablename__ = "assessment_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    titai_fb = mapped_column(JSON, nullable=True)
    tixing_fb = mapped_column(JSON, nullable=True)
    titai_lr = mapped_column(JSON, nullable=True)
    tixing_lr = mapped_column(JSON, nullable=True)
    posture_analysis_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    tongue_analysis_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    comprehensive_analysis_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 历史分析折线图专用数据：按时间序列保存的数值指标快照
    history_chart_data = mapped_column(JSON, nullable=True)
    front_image_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    # 体态分析后的 processed 图（mask+关键点等）在服务器侧的保存路径
    processed_image_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    meta_json = mapped_column(JSON, nullable=True)
    # 用户多次提交的分析需求：JSON 数组，元素形如 {"seq":1,"text":"...","at":"ISO时间"}
    user_requirements = mapped_column(JSON, nullable=True)
    tcm_ten_questions = mapped_column(JSON, nullable=True)

    user: Mapped["User"] = relationship(back_populates="records")


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)

    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(32), nullable=True)
    height: Mapped[float | None] = mapped_column(nullable=True)
    weight: Mapped[float | None] = mapped_column(nullable=True)
    medical_history: Mapped[str | None] = mapped_column(String(64), nullable=True)
    work_habit: Mapped[str | None] = mapped_column(String(64), nullable=True)
    allergy_history: Mapped[str | None] = mapped_column(String(512), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user: Mapped["User"] = relationship(back_populates="profile")
