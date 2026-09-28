"""services/record.py 成绩记录 CRUD 与聚合操作"""
from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import utils
from ..utils.enums import Server
from . import execute_func
from .minfo import get_mdt
from .models import MaiData, MaiRecord


__all__ = [
    "add_record_batch",
    "get_record_achs",
    "backfill_record_shortids",
]


# TODO
_RecordKey = tuple[int, int, Server]


def _merge_ach(target: utils.MaiChartAch, source: MaiRecord) -> utils.MaiChartAch:
    candidate = utils.MaiChartAch(
        shortid=source.shortid if source.shortid is not None else -1,
        difficulty=source.difficulty,
        server=source.server,
        achievement=source.achievement,
        dxscore=source.dxscore,
        combo=source.combo,
        sync=source.sync,
        update_time=source.play_time,
        user_id=source.user_id,
    )
    if candidate > target:
        return target + candidate
    return target


async def _resolve_shortid(title: str, cabinet: str, *, session: AsyncSession) -> tuple[Optional[int], str]:
    song_list = await get_mdt.title(title, way='title', session=session)
    if len(song_list) == 0:
        return None, f"{title}[{cabinet}]"

    filtered = [song for song in song_list if song.cabinet == cabinet]
    if len(filtered) == 1:
        return filtered[0].shortid, title
    return None, f"{title}[{cabinet}]"


async def add_record_batch(
    user_id: int,
    records: Sequence[utils.sync.LyraRecordV3],
    *,
    session: Optional[AsyncSession] = None,
) -> tuple[set[_RecordKey], list[tuple[str, int]]]:
    """批量写入成绩记录，返回受影响谱面键与未匹配曲目。"""
    if not records:
        return set(), []

    async def _sqlite_postgresql_action(native_insert, session: AsyncSession) -> tuple[set[_RecordKey], list[tuple[str, int]]]:
        resolved_rows: list[dict[str, object]] = []
        backfill_rows: list[dict[str, object]] = []
        affected_keys: set[_RecordKey] = set()
        unmatched_items: list[tuple[str, int]] = []
        title_cache: dict[tuple[str, str], tuple[Optional[int], str]] = {}

        for record in records:
            cache_key = (record.title, record.cabinet)
            if cache_key not in title_cache:
                title_cache[cache_key] = await _resolve_shortid(record.title, record.cabinet, session=session)

            shortid, display_title = title_cache[cache_key]
            if shortid is None:
                unmatched = (display_title, record.difficulty)
                if unmatched not in unmatched_items:
                    unmatched_items.append(unmatched)
            else:
                affected_keys.add((shortid, record.difficulty, record.server))

            resolved_rows.append({
                "user_id": user_id,
                "record_hash": record.record_hash,
                "shortid": shortid,
                "title": record.title,
                "cabinet": record.cabinet,
                "type": record.record_type,
                "difficulty": record.difficulty,
                "server": record.server,
                "achievement": record.achievement,
                "dxscore": record.dxscore,
                "combo": record.combo,
                "sync": record.sync,
                "play_time": record.play_time,
            })
            if shortid is not None:
                backfill_rows.append({
                    "record_hash": record.record_hash,
                    "shortid": shortid,
                })

        if resolved_rows:
            stmt = native_insert(MaiRecord).values(resolved_rows)
            stmt = stmt.on_conflict_do_nothing(index_elements=["record_hash"])
            await session.execute(stmt)

        if backfill_rows:
            for backfill in backfill_rows:
                await session.execute(
                    # 能正常运作，此处忽略错误提示
                    MaiRecord.__table__.update()  # type: ignore
                    .where(
                        MaiRecord.record_hash == backfill["record_hash"],
                        MaiRecord.shortid.is_(None),
                    )
                    .values(shortid=backfill["shortid"])
                )

        return affected_keys, unmatched_items

    async def _action(session: AsyncSession) -> tuple[set[_RecordKey], list[tuple[str, int]]]:
        bind_engine = session.get_bind()
        dialect_name = bind_engine.dialect.name

        if dialect_name == 'sqlite':
            from sqlalchemy.dialects.sqlite import insert as native_insert
            return await _sqlite_postgresql_action(native_insert, session)
        if dialect_name == 'postgresql':
            from sqlalchemy.dialects.postgresql import insert as native_insert
            return await _sqlite_postgresql_action(native_insert, session)
        raise NotImplementedError(f"当前方案暂不支持数据库: {dialect_name}")

    return await execute_func.action(_action, session=session)


async def get_record_achs(
    user_id: int,
    record_keys: Sequence[_RecordKey],
    *,
    session: Optional[AsyncSession] = None,
) -> list[utils.MaiChartAch]:
    """按谱面键聚合用户历史成绩记录，生成当前有效成绩。"""
    if not record_keys:
        return []

    key_set = set(record_keys)
    shortids = sorted({shortid for shortid, _, _ in key_set})

    async def _query(session: AsyncSession) -> list[utils.MaiChartAch]:
        stmt = (
            select(MaiRecord)
            .where(
                MaiRecord.user_id == user_id,
                MaiRecord.shortid.in_(shortids),
                MaiRecord.shortid.is_not(None),
            )
        )
        rows = (await session.execute(stmt)).scalars().all()

        merged: dict[_RecordKey, utils.MaiChartAch] = {}
        for row in rows:
            if row.shortid is None:
                continue
            key = (row.shortid, row.difficulty, row.server)
            if key not in key_set:
                continue

            if key not in merged:
                merged[key] = utils.MaiChartAch(
                    shortid=row.shortid,
                    difficulty=row.difficulty,
                    server=row.server,
                    achievement=row.achievement,
                    dxscore=row.dxscore,
                    combo=row.combo,
                    sync=row.sync,
                    update_time=row.play_time,
                    user_id=user_id,
                )
                continue

            merged[key] = _merge_ach(merged[key], row)

        return list(merged.values())

    return await execute_func.select(_query, session=session)


async def backfill_record_shortids(
    *,
    session: Optional[AsyncSession] = None,
) -> dict[int, set[_RecordKey]]:
    """为曲库已收录的历史记录补填 shortid，并按用户返回受影响谱面。"""

    async def _action(session: AsyncSession) -> dict[int, set[_RecordKey]]:
        unresolved = (
            await session.execute(
                select(MaiRecord).where(MaiRecord.shortid.is_(None))
            )
        ).scalars().all()
        if not unresolved:
            return {}

        songs = (await session.execute(select(MaiData))).scalars().all()
        song_map = {(song.title, song.cabinet): song.shortid for song in songs}
        affected: dict[int, set[_RecordKey]] = {}
        for record in unresolved:
            shortid = song_map.get((record.title, record.cabinet))
            if shortid is None:
                continue
            record.shortid = shortid
            affected.setdefault(record.user_id, set()).add(
                (shortid, record.difficulty, record.server)
            )
        return affected

    return await execute_func.action(_action, session=session)
