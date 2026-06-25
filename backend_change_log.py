"""
后端修改记录（用于对接同事）
生成时间: 2026-04-03
项目路径: C:/Users/HP/Desktop/Web/4
"""

BACKEND_CHANGELOG = {
    "entrypoint": {
        "file": "jb666_for_front.py",
        "changes": [
            "保留 FastAPI 初始化、CORS、DB 初始化与路由注册",
            "新增 register_app_routers(application) 显式路由注册函数",
            "本地 __main__ 启动段已注释，便于联调环境统一从 uvicorn 启动",
        ],
    },
    "router_registration": {
        "file": "routes/__init__.py",
        "changes": [
            "路由注册迁移到 routes/New 子目录",
            "当前启用: auth, reports, New/profile, New/posture, New/tongue, New/history_joint",
            "旧 assessment 路由文件仍在仓库，但已不作为主流程入口",
        ],
    },
    "new_routes": {
        "folder": "routes/New",
        "files": {
            "profile.py": {
                "prefix": "/api/profile",
                "apis": [
                    "GET /api/profile?userId=...",
                    "POST /api/profile/upload",
                    "PUT /api/profile/update",
                    "POST /api/profile/save  (有则更新、无则新增)",
                ],
                "notes": "个人信息不再收集姓名字段",
            },
            "posture.py": {
                "prefix": "/api/posture",
                "apis": [
                    "POST /api/posture/analyze",
                ],
                "request_fields": [
                    "meta(file/json)",
                    "userId(form)",
                    "frontImage(file)",
                    "sideImage(file, optional)",
                    "authorization(header, optional)",
                ],
                "response_notes": [
                    "当前为联调占位：固定/随机示例指标 + 固定示例报告",
                    "保留 resultImageUrl 返回，并通过 resultImageTransform=rotate(180deg) 让前端显示倒置效果",
                ],
                "db": "会写入 assessment_records",
            },
            "tongue.py": {
                "prefix": "/api/tongue",
                "apis": [
                    "POST /api/tongue/analyze",
                ],
                "request_fields": [
                    "meta(file/json)",
                    "userId(form)",
                    "tongueImage(file)",
                    "authorization(header, optional)",
                ],
                "response_notes": [
                    "当前为联调占位：返回固定 aiReport",
                ],
                "db": "会写入 assessment_records",
            },
            "history_joint.py": {
                "prefix": "/api/history",
                "apis": [
                    "POST /api/history/joint-analyze",
                ],
                "purpose": "历史记录多条勾选后联合分析（占位）",
                "response_notes": [
                    "返回固定联合分析报告 jointReport",
                ],
                "db": "会写入 assessment_records，titai_fb.type=history_joint",
            },
        },
    },
    "schemas": {
        "file": "routes/schemas.py",
        "changes": [
            "新增 ProfilePayload（无 name 字段）",
            "新增 JointHistoryItem",
            "新增 JointAnalyzePayload",
        ],
    },
    "database": {
        "files": ["db/models.py", "db/crud.py"],
        "changes": [
            "新增 UserProfile 模型（user_profiles 表）",
            "字段：age, gender, height, weight, medical_history, work_habit",
            "已从个人信息链路移除 name 字段",
            "新增 profile CRUD：查询/新增/更新/自动保存(save)",
        ],
    },
    "compatibility_notes": [
        "为避免环境依赖问题，posture 路由已去除 cv2/numpy 强依赖",
        "联调占位阶段所有新路由都保留正式接口结构，后续可无缝替换真实算法",
    ],
}


def print_summary() -> None:
    print("=== Backend Change Summary ===")
    for section, detail in BACKEND_CHANGELOG.items():
        print(f"\n[{section}]")
        print(detail)


if __name__ == "__main__":
    print_summary()
