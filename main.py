# conda activate openmmlab
# python -m uvicorn main:app --reload --port 8081

# Stop-Process -Id <PID> -Force

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from db.database import init_db

from routes import router

# AI 调用开关：True=走测试假数据，False=走真实智能体
MOCK_AI_ENABLED = False
# MOCK_AI_ENABLED = True
os.environ["MOCK_AI_ENABLED"] = "1" if MOCK_AI_ENABLED else "0"

app = FastAPI()


@app.on_event("startup")
def _startup_init_db() -> None:
    init_db()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def register_app_routers(application: FastAPI) -> None:
    application.include_router(router)


register_app_routers(app)

# 本地脚本直启逻辑（测试阶段可不需要，保留注释）
# if __name__ == "__main__":
#     import uvicorn
#
#     uvicorn.run(
#         "jb666_for_front:app",
#         host="127.0.0.1",
#         port=8081,
#         reload=True,
#     )
