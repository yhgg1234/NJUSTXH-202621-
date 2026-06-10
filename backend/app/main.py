"""
XH-202621 多源异构数据驱动岗位和能力图谱构建与动态演化分析研究
Backend Application Entry Point
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="岗位能力图谱系统 API",
    description="多源异构数据驱动的岗位和能力图谱构建与动态演化分析系统",
    version="0.1.0",
)

# CORS 中间件配置（开发阶段允许前端跨域访问）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """健康检查接口"""
    return {
        "status": "ok",
        "project": "XH-202621 岗位能力图谱系统",
        "version": "0.1.0",
    }


@app.get("/api/health")
async def health_check():
    """系统健康检查"""
    return {
        "backend": "running",
        "neo4j": "pending",
        "mysql": "pending",
        "mongodb": "pending",
    }
