"""简历解析 —— 文件上传、结构化简历、检索 的领域模型"""

from typing import Literal

from pydantic import BaseModel, Field


# ── 结构化简历 ──

class WorkExperience(BaseModel):
    """工作经历"""
    company: str
    position: str
    start_date: str | None = None
    end_date: str | None = None
    description: str = ""
    achievements: list[str] = Field(default_factory=list)


class ProjectExperience(BaseModel):
    """项目经验"""
    name: str
    role: str = ""
    start_date: str | None = None
    end_date: str | None = None
    description: str = ""
    tech_stacks: list[str] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)


class Education(BaseModel):
    """教育经历"""
    school: str
    degree: str
    major: str = ""
    start_date: str | None = None
    end_date: str | None = None


class ParsedResume(BaseModel):
    """解析后的结构化简历"""
    id: str
    file_name: str
    name: str = ""
    email: str | None = None
    phone: str | None = None
    education: list[Education] = Field(default_factory=list)
    work_experience: list[WorkExperience] = Field(default_factory=list)
    projects: list[ProjectExperience] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    certificates: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    parsed_at: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class ResumeListResponse(BaseModel):
    """简历分页列表"""
    items: list[ParsedResume]
    total: int
    page: int
    page_size: int


# ── 文件上传 ──

class ResumeUploadResponse(BaseModel):
    """简历上传结果"""
    file_id: str
    file_name: str
    file_size: int
    file_type: Literal["pdf", "docx"]
    upload_time: str


# ── 简历检索 ──

class ResumeSearchQuery(BaseModel):
    """简历检索条件"""
    keyword: str | None = None
    skills: list[str] | None = None
    education_level: str | None = None
    years_of_experience: int | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
