import sys
from pathlib import Path
from typing import List, Set, Tuple

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

# 导入 maib 插件中的 MaiData 相关类
sys.path.insert(0, Path.cwd().as_posix())
from plugins.maib import utils, models


async def init_db(engine):
    """初始化数据库表结构"""
    async with engine.begin() as conn:
        await conn.run_sync(models.Model.metadata.create_all)
    logger.info("数据库表结构同步完成")


async def upsert_maidata(session: AsyncSession, data: utils.MaiData):
    """插入或更新 MaiData 数据"""
    result = await session.execute(
        select(models.MaiData)
        .where(models.MaiData.shortid == data.shortid)
        .options(
            selectinload(models.MaiData.charts),
            selectinload(models.MaiData.aliases))
    )
    existing = result.scalar_one_or_none()
    if existing:
        # 更新已有数据
        existing.title = data.title
        existing.bpm = data.bpm
        existing.artist = data.artist
        existing.genre = data.genre
        existing.cabinet = data.cabinet
        existing.version = data.version
        existing.version_cn = data.version_cn
        existing.converter = data.converter
        existing.zip_path = str(data.zip_path) if data.zip_path else None
        existing.is_utage = data.is_utage
        existing.utage_tag = data.utage_tag
        existing.buddy = data.buddy
    else:
        # 创建新数据
        existing = models.MaiDataModelFactory.mai_data(data)
        session.add(existing)
        if not existing.charts:
            existing.charts = []
        if not existing.aliases:
            existing.aliases = []

    # 处理谱面数据
    existing_charts = {chart.difficulty: chart for chart in existing.charts}
    for chart in data.charts:
        chart_num = chart.difficulty
        if chart_num in existing_charts:
            # 更新已有谱面
            existing_chart = existing_charts[chart_num]
            existing_chart.lv = chart.lv
            existing_chart.des = chart.des
            existing_chart.inote = chart.inote
            existing_chart.note_count_tap = chart.notes[0]
            existing_chart.note_count_hold = chart.notes[1]
            existing_chart.note_count_slide = chart.notes[2]
            existing_chart.note_count_touch = chart.notes[3]
            existing_chart.note_count_break = chart.notes[4]
        else:
            # 添加新谱面
            new_chart = models.MaiDataModelFactory.mai_chart(chart, data.shortid)
            existing.charts.append(new_chart)

    # 处理别名数据
    existing_set: Set[Tuple[int, str]] = {(a.shortid, a.alias) for a in existing.aliases}
    for alias in data.aliases:
        if (alias.shortid, alias.alias) not in existing_set:
            new_alias = models.MaiDataModelFactory.mai_alias(alias)
            existing.aliases.append(new_alias)
            existing_set.add((alias.shortid, alias.alias))
