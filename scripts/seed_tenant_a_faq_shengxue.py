#!/usr/bin/env python3
"""Idempotent seed: 10 HFUU 2026 招生 FAQ for tenant-a; 2 marked is_hot (F13).

Source docs: data-collection/output/hfuu/plans/2026/

Usage (from repo root, venv active):

  python scripts/seed_tenant_a_faq_shengxue.py

Requires tenant-a (see scripts/seed_dev_tenant.py).
"""

from __future__ import annotations

import hashlib
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

_API_SRC = Path(__file__).resolve().parents[1] / "apps" / "api" / "src"
sys.path.insert(0, str(_API_SRC))

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from rag_api.config import get_settings
from rag_api.db.models import Document, FaqSuggestionStats, Tenant, TenantMember, User

TENANT_NAME = "tenant-a"
SEED_KEY = "tenant_a_faq_hfuu_2026"

# (question title, body, is_hot) — grounded in HFUU 2026 admission plan docs
FAQS: list[tuple[str, str, bool]] = [
    (
        "合肥大学2026年安徽省院校代码是多少？",
        "合肥大学2026年在安徽省招生院校代码为9015（普通本科、专项计划、中外合作办学均标注该代码）。"
        "填报时请以安徽省考试院公布为准。",
        True,
    ),
    (
        "计算机、软件工程2026年安徽招多少人？",
        "据2026年安徽省本科分专业计划（不含专项、中外合作）：计算机科学与技术86人、软件工程88人、"
        "网络工程88人、智能科学与技术88人、数据科学与大数据技术98人；选考要求均为物理+化学，授工学学位。"
        "咨询电话可查人工智能与大数据学院相关号码（如计算机0551-62158585）。",
        True,
    ),
    (
        "国家专项和地方专项分别招哪些专业？",
        "2026年安徽专项（物理类）专业包括：应用统计学、智慧交通、智能建造、智慧建筑与建造、"
        "食品科学与工程、生物工程、无机非金属材料工程、化学工程与工艺、能源化学工程。"
        "国家专项与地方专项组内专业相同，计划人数不同（例如应用统计学国家专项5人、地方专项9人）。"
        "选考均为物理+化学。",
        False,
    ),
    (
        "电子信息、自动化类专业选考要求是什么？",
        "电子信息与自动化学院相关专业（电子信息工程、通信工程、集成电路设计与集成系统、自动化）"
        "2026年安徽计划选考要求均为物理+化学，授工学学位。"
        "省内计划示例：电子信息工程158人、自动化145人、通信工程88人、集成电路设计与集成系统88人。",
        False,
    ),
    (
        "历史类考生能报合肥大学哪些专业？",
        "2026年安徽本科计划中，历史+不限可选专业包括：经济学、金融学、国际经济与贸易、工商管理、会计学、"
        "物流管理、汉语言文学、新闻学、网络与新媒体、旅游管理、英语、德语、小学教育、应用心理学等。"
        "另有物流管理（中外合作办学）历史类计划19人。具体以院校专业组与考试院公布为准。",
        False,
    ),
    (
        "中外合作办学2026年有哪些专业？",
        "国际学院中外合作：车辆工程（中外合作）物理+化学，物理类04，省内44人；"
        "信息与计算科学（中外合作）物理+化学，物理类04，省内42人；"
        "物流管理（中外合作）物理+不限（物理类05）15人，以及历史+不限（历史类02）19人。"
        "安徽省院校代码9015。",
        False,
    ),
    (
        "设计学院艺术类要不要选考科目？",
        "2026年设计学院艺术类专业（动画、视觉传达设计、环境设计、产品设计、艺术与科技）选考要求为「不限科目」，"
        "授艺术学学位。另工业设计属工学，选考物理+化学，省内计划84人。",
        False,
    ),
    (
        "新能源材料与器件安徽招多少人？",
        "能源材料与化工学院「新能源材料与器件」2026年安徽本科计划130人，选考物理+化学，授工学学位；"
        "咨询电话0551-62158393。同学院还有无机非金属材料工程25人、化学工程与工艺62人、能源化学工程68人。",
        False,
    ),
    (
        "汉语言文学2026年安徽计划多少人？",
        "文化与旅游学院汉语言文学2026年安徽计划150人，选考历史+不限，授文学学位；咨询电话0551-62159277。"
        "同学院历史类还有新闻学64人、网络与新媒体121人、旅游管理64人等。",
        False,
    ),
    (
        "外省计划和体检要求怎么确认？",
        "外省本科分专业计划不含安徽与中外合作计划；如有变动，以各省市考试院公布为准。"
        "专业对高考体检结论有要求（例如不录取色盲、色弱考生），请查阅《普通高等学校招生体检工作指导意见》、"
        "《合肥大学2026年招生章程》及本人体检结论告知书后合理填报。",
        False,
    ),
    (
        "哪些专业色弱不能报？",
        "合肥大学2026年招生计划说明：部分专业对高考体检结论有要求，例如不录取色盲、色弱考生。"
        "分专业计划表未逐条列出受限专业名单，请以《普通高等学校招生体检工作指导意见》、"
        "《合肥大学2026年招生章程》以及本人体检结论告知书为准，填报前核对目标专业是否限色弱/色盲。",
        False,
    ),
]


def _body_bytes(title: str, body: str) -> bytes:
    return f"{title}\n\n{body}\n".encode("utf-8")


def main() -> None:
    engine = create_engine(get_settings().database_url)
    with Session(engine) as db:
        tenant = db.scalar(select(Tenant).where(Tenant.tenant_name == TENANT_NAME))
        if tenant is None:
            raise SystemExit(
                f"tenant {TENANT_NAME!r} not found; run scripts/seed_dev_tenant.py first"
            )

        member = db.scalar(
            select(TenantMember).where(TenantMember.tenant_id == tenant.tenant_id)
        )
        if member is None:
            user = db.scalar(select(User).limit(1))
            if user is None:
                raise SystemExit("no user found to set created_by")
            created_by = user.user_id
        else:
            created_by = member.user_id

        keep_titles = {title for title, _, _ in FAQS}
        # Soft-delete prior FAQ seeds not in the new set (old 升学 / previous HFUU titles).
        prior = list(
            db.scalars(
                select(Document).where(
                    Document.tenant_id == tenant.tenant_id,
                    Document.doc_tag == "faq",
                    Document.is_latest.is_(True),
                    Document.deleted_at.is_(None),
                    Document.source_type == "seed",
                )
            ).all()
        )
        retired = 0
        now = datetime.now(UTC).replace(tzinfo=None)
        for doc in prior:
            meta = doc.source_metadata or {}
            seed = meta.get("seed")
            if seed in ("tenant_a_faq_shengxue", SEED_KEY) and doc.doc_name not in keep_titles:
                doc.deleted_at = now
                doc.is_latest = False
                retired += 1

        created = 0
        updated = 0
        for title, body, is_hot in FAQS:
            existing = db.scalar(
                select(Document).where(
                    Document.tenant_id == tenant.tenant_id,
                    Document.doc_name == title,
                    Document.doc_tag == "faq",
                    Document.is_latest.is_(True),
                    Document.deleted_at.is_(None),
                )
            )
            content = _body_bytes(title, body)
            sha = hashlib.sha256(content).hexdigest()
            if existing is None:
                group_id = uuid4()
                doc = Document(
                    tenant_id=tenant.tenant_id,
                    doc_name=title,
                    doc_tag="faq",
                    doc_group_id=group_id,
                    content_sha256=sha,
                    publish_status="published",
                    index_status="ready",
                    is_latest=True,
                    version_number=1,
                    doc_size=len(content),
                    created_by=created_by,
                    source_type="seed",
                    source_metadata={"seed": SEED_KEY, "university": "HFUU", "year": 2026},
                )
                db.add(doc)
                db.flush()
                created += 1
                group_id = doc.doc_group_id
            else:
                existing.publish_status = "published"
                existing.doc_tag = "faq"
                existing.content_sha256 = sha
                existing.doc_size = len(content)
                existing.index_status = "ready"
                existing.source_metadata = {
                    "seed": SEED_KEY,
                    "university": "HFUU",
                    "year": 2026,
                }
                group_id = existing.doc_group_id
                updated += 1

            stats = db.scalar(
                select(FaqSuggestionStats).where(
                    FaqSuggestionStats.tenant_id == tenant.tenant_id,
                    FaqSuggestionStats.document_group_id == group_id,
                )
            )
            if stats is None:
                stats = FaqSuggestionStats(
                    tenant_id=tenant.tenant_id,
                    document_group_id=group_id,
                    click_count=10 if is_hot else 0,
                    is_hot=is_hot,
                )
                db.add(stats)
            else:
                stats.is_hot = is_hot
                if is_hot and stats.click_count < 1:
                    stats.click_count = 10

        db.commit()
        print(
            f"tenant={TENANT_NAME} faqs created={created} updated={updated} "
            f"retired={retired} total={len(FAQS)}"
        )
        print(f"hot marked: {[t for t, _, h in FAQS if h]}")


if __name__ == "__main__":
    main()
