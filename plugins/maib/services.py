import time
from typing import List, Optional, Sequence
from collections import defaultdict

from sqlalchemy import select, or_, delete, func
from sqlalchemy.orm import selectinload

from . import utils
from .models import MaiData, MaiChart, MaiChartAch, MaiAlias
from .bot_registry import PluginRegistry
from .constants import *

get_session = PluginRegistry.get_session


# --- 通过 shortid 查询指定乐曲 ---
async def get_song_by_id(shortid: int) -> Optional[MaiData]:
    """通过 shortid 获取乐曲，同时加载其所有谱面和别名"""
    async with get_session() as session:
        # 使用 selectinload 预加载关联表，避免异步环境下的惰性加载错误
        statement = (
            select(MaiData)
            .where(MaiData.shortid == shortid)
        )
        result = await session.execute(statement)
        return result.scalar_one_or_none()


# --- [精确] 通过曲名/别名查询谱面 ---
async def get_song_by_name(keyword: str) -> Sequence[MaiData]:
    """曲名/别名的精确搜索，返回所有匹配的乐曲数据"""
    async with get_session() as session:
        statement = (
            select(MaiData)
            .outerjoin(MaiAlias)  # 使用外连接，防止没有别名的曲目被过滤掉
            .where(
                or_(
                    MaiData.title == keyword,
                    MaiAlias.alias == keyword
                )
            )
            .distinct()
        )
        result = await session.execute(statement)
        return result.scalars().all()

# --- [模糊] 通过曲名/别名查询谱面 ---
# TODO 考虑 SQLite FTS5 实现中文、日文罗马字等智能模糊搜索
async def get_song_by_name_blur(keyword: str) -> Sequence[MaiData]:
    """曲名/别名的模糊搜索，返回所有匹配的乐曲数据"""
    async with get_session() as session:
        statement = (
            select(MaiData)
            .outerjoin(MaiAlias)  # 使用外连接，防止没有别名的曲目被过滤掉
            .where(
                or_(
                    MaiData.title.contains(keyword),
                    MaiAlias.alias.contains(keyword)
                )
            )
            .distinct()
        )
        result = await session.execute(statement)
        return result.scalars().all()

# --- [智能] 通过曲名/别名查询谱面 ---
async def get_song_by_name_smart(keyword: str) -> Sequence[MaiData]:
    """曲名/别名的智能搜索，先尝试精确匹配，若无结果则进行模糊匹配"""
    songs = await get_song_by_name(keyword)
    if songs:
        return songs
    return await get_song_by_name_blur(keyword)


# --- 通过版本筛选查询谱面 ---
async def get_song_by_version(version: int) -> Sequence[MaiData]:
    """按版本筛选乐曲：version>=2000 查 version_cn，否则查 version。"""
    async with get_session() as session:
        version_field = MaiData.version_cn if version >= 2000 else MaiData.version
        statement = select(MaiData).where(version_field == version)
        result = await session.execute(statement)
        return result.scalars().all()


async def get_song_by_genre(genre: int) -> Sequence[MaiData]:
    """按流派筛选乐曲。"""
    async with get_session() as session:
        statement = select(MaiData).where(MaiData.genre == genre)
        result = await session.execute(statement)
        return result.scalars().all()


# --- 根据谱面难度 (lv) 筛选 shortid 列表 ---
async def get_shortids_by_lv(min_lv: float, max_lv: float, server: SERVER_TAG) -> Sequence[int]:
    """查询定数在指定范围内的所有乐曲 ID"""
    async with get_session() as session:
        statement = (
            select(MaiChart.shortid)
            .distinct()
        )
        if server == "CN":
            statement = statement.where(MaiChart.lv_cn >= min_lv, MaiChart.lv_cn <= max_lv)
        else:
            statement = statement.where(MaiChart.lv >= min_lv, MaiChart.lv <= max_lv)

        result = await session.execute(statement)
        return result.scalars().all()


async def set_lv_synh(shortid: int, difficulty: int, lvnh: float):
    """设置指定谱面的水鱼拟合定数"""
    async with get_session() as session:
        stmt = (
            select(MaiChart)
            .where(MaiChart.shortid == shortid, MaiChart.difficulty == difficulty)
        )
        chart = (await session.execute(stmt)).scalar_one_or_none()
        if chart:
            chart.lv_synh = lvnh
            await session.commit()

async def set_lv_synh_batch(data: Sequence[tuple[int, int, float]]):
    """批量设置水鱼拟合定数，输入为 (shortid, difficulty, lvnh) 的列表"""
    async with get_session() as session:
        for shortid, difficulty, lvnh in data:
            stmt = (
                select(MaiChart)
                .where(MaiChart.shortid == shortid, MaiChart.difficulty == difficulty)
            )
            chart = (await session.execute(stmt)).scalar_one_or_none()
            if chart:
                chart.lv_synh = lvnh
        await session.commit()


# --- 别名的添加 ---
async def add_alias(shortid: int, alias_text: str, qq: int, group_id: Optional[int] = None) -> bool:
    """添加别名，若已存在则返回 False"""
    async with get_session() as session:
        # 检查是否已存在该别名
        check_stmt = select(MaiAlias).where(MaiAlias.shortid == shortid, MaiAlias.alias == alias_text)
        existing = await session.execute(check_stmt)
        if existing.scalar_one_or_none():
            return False

        new_alias = MaiAlias(
            shortid=shortid,
            alias=alias_text,
            create_time=int(time.time()),
            create_qq=qq,
            create_qq_group=group_id
        )
        session.add(new_alias)
        await session.commit()
        return True

async def add_aliases(data: Sequence[tuple[int, str]], source_id: int, add_time: int):
    """批量添加别名"""
    # 1. 提取所有目标 shortid
    requested_ids = {shortid for shortid, _ in data}
    if not requested_ids:
        return

    async with get_session() as session:
        # 2. 【核心修改】检查哪些 shortid 在 maidata 主表中确实存在
        valid_ids_stmt = select(MaiData.shortid).where(MaiData.shortid.in_(list(requested_ids)))
        valid_ids_result = await session.execute(valid_ids_stmt)
        existing_song_ids = {row[0] for row in valid_ids_result.all()}

        # 3. 查出已有的别名（仅针对主表存在的歌）
        existing_alias_stmt = select(MaiAlias.shortid, MaiAlias.alias).where(
            MaiAlias.shortid.in_(list(existing_song_ids))
        )
        existing_alias_result = await session.execute(existing_alias_stmt)
        known_aliases = {(row[0], row[1]) for row in existing_alias_result.all()}

        # 4. 过滤并添加
        new_count = 0
        for shortid, alias_text in data:
            # 只有当：1. 主表有这首歌  2. 别名表没这个别名 时才插入
            if shortid in existing_song_ids and (shortid, alias_text) not in known_aliases:
                session.add(MaiAlias(
                    shortid=shortid,
                    alias=alias_text,
                    create_time=add_time,
                    create_qq=source_id
                ))
                known_aliases.add((shortid, alias_text)) # 防止 data 内部重复
                new_count += 1
        
        if new_count > 0:
            await session.commit()

# --- 7. 别名的鉴权和删除 ---
async def get_alias_info(alias_text: str) -> List[MaiAlias]:
    """获取别名详情"""
    async with get_session() as session:
        stmt = select(MaiAlias).where(MaiAlias.alias == alias_text)
        result = await session.execute(stmt)
        return list(result.scalars().all())


async def get_alias_info_from_shortid(shortid: int) -> List[MaiAlias]:
    """获取曲目所有别名详情"""
    async with get_session() as session:
        statement = select(MaiAlias).where(MaiAlias.shortid == shortid)
        result = await session.execute(statement)
        return list(result.scalars().all())


async def delete_alias_by_id(alias_id: int):
    """根据别名 ID 删除"""
    async with get_session() as session:
        stmt = delete(MaiAlias).where(MaiAlias.id == alias_id)
        await session.execute(stmt)
        await session.commit()


async def refresh_dxrating_cache(shortid: int, difficulty: int, server: SERVER_TAG):
    """当定数改变时，重新计算该谱面下所有用户的 dxrating 缓存"""
    jp_ver, cn_ver = utils.get_current_versions()
    current_version = cn_ver if server == "CN" else jp_ver

    async with get_session() as session:
        # 1. 获取谱面 Model 并转为 Utils
        statement = (
            select(MaiChart)
            .where(MaiChart.shortid == shortid, MaiChart.difficulty == difficulty)
        )
        mct = (await session.execute(statement)).scalar_one_or_none()
        if not mct:
            return
        
        maichart = mct.to_data()
        
        # 2. 获取该谱面所有关联成绩
        ach_statement = select(MaiChartAch).where(
            MaiChartAch.shortid == shortid,
            MaiChartAch.difficulty == difficulty
        )
        ach_statement = ach_statement.where(MaiChartAch.server == server)
        mct_achs = (await session.execute(ach_statement)).scalars().all()
        
        # 3. 批量更新
        for mct_ach in mct_achs:
            # maiJP 25(CiRCLE) 及以后版本计算 AP Bonus
            ap_bonus = 1 if 2000 > current_version >= 25 else 0
            
            # 使用 utils 计算
            ach = mct_ach.to_data()
            maichart.set_ach(ach)
            mct_ach.dxrating = maichart.get_dxrating(server=mct_ach.server, ap_bonus=ap_bonus)

        # 4. 提交变更
        await session.commit()


async def sync_cn_data_batch(
    data: Sequence[tuple[int, int, list[float | int]]],
    commit_every: int = 200,
) -> tuple[int, int]:
    """批量同步国服版本与定数（自管 session）。

    参数 data 项格式: (shortid, version_cn, ds)
    返回: (命中曲目数, 发生 lv_cn 变更的谱面数)
    """
    if not data:
        return 0, 0

    if commit_every <= 0:
        commit_every = 200

    hit_song_count = 0
    changed_tasks: set[tuple[int, int, SERVER_TAG]] = set()

    async with get_session() as session:
        for idx, (shortid, version_cn, ds) in enumerate(data, start=1):
            result = await session.execute(
                select(MaiData)
                .where(MaiData.shortid == shortid)
                .options(selectinload(MaiData.charts))
            )
            existing = result.scalar_one_or_none()
            if existing is None:
                continue

            hit_song_count += 1
            existing.version_cn = version_cn

            for chart in existing.charts:
                ds_idx = chart.difficulty - 2
                if ds_idx < 0 or ds_idx >= len(ds):
                    continue
                lv_cn_raw = ds[ds_idx]
                if lv_cn_raw is None:
                    continue
                try:
                    lv_cn = float(lv_cn_raw)
                except (TypeError, ValueError):
                    continue

                if chart.lv_cn != lv_cn:
                    changed_tasks.add((shortid, chart.difficulty, "CN"))
                    chart.lv_cn = lv_cn

            if idx % commit_every == 0:
                await session.commit()

        await session.commit()

    # lv_cn 改变后必须刷新对应谱面的 dxrating 缓存（CN 侧）。
    for sid, diff, server in changed_tasks:
        await refresh_dxrating_cache(sid, diff, server)

    return hit_song_count, len(changed_tasks)


async def sync_cn_data_by_shortid(shortid: int, version_cn: int, ds: list[float | int]) -> bool:
    """按 shortid 同步国服版本与定数（自管 session）。"""
    hit_song_count, _ = await sync_cn_data_batch([(shortid, version_cn, ds)], commit_every=1)
    return hit_song_count > 0

async def upload_achievements_batch(user_id: int, ach_list: List[utils.MaiChartAch]):
    """批量上传接口"""
    jp_ver, cn_ver = utils.get_current_versions()
    changes_log = []  # 追踪所有变更

    # --- 1. 预处理：对输入数据进行内部去重，防止 ach_list 自身包含重复 key ---
    # 唯一键定义为 (shortid, difficulty, server)
    unique_incoming = {}
    for a in ach_list:
        key = (a.shortid, a.difficulty, a.server)
        if key not in unique_incoming or a.achievement > unique_incoming[key].achievement:
            unique_incoming[key] = a

    # 将去重后的数据按 shortid 分组
    ach_group = defaultdict(list)
    for a in unique_incoming.values():
        ach_group[a.shortid].append(a)

    async with get_session() as session:
        for shortid, incoming_items in ach_group.items():
            # 2. 获取谱面信息
            chart_stmt = select(MaiChart).where(MaiChart.shortid == shortid)
            chart_models = (await session.execute(chart_stmt)).scalars().all()
            if not chart_models:
                continue
            
            chart_dict = {c.difficulty: c for c in chart_models}
            
            # 获取该用户已有的成绩
            exist_ach_stmt = select(MaiChartAch).where(
                MaiChartAch.user_id == user_id,
                MaiChartAch.shortid == shortid
            )
            existing_achs = (await session.execute(exist_ach_stmt)).scalars().all()
            existing_ach_dict = {(a.difficulty, a.server): a for a in existing_achs}

            for incoming in incoming_items:
                if incoming.difficulty not in chart_dict:
                    continue
                
                mct = chart_dict[incoming.difficulty]
                existing = existing_ach_dict.get((incoming.difficulty, incoming.server))
                
                maichart = mct.to_data()
                if existing:
                    maichart.set_ach(existing.to_data())
                
                old_achievement = maichart.get_ach(incoming.server).achievement
                
                # 3. 计算逻辑
                cur_ver = cn_ver if incoming.server == "CN" else jp_ver
                ap_bonus = 1 if 2000 > cur_ver >= 25 else 0
                updated_utils = maichart.update_ach(incoming)
                
                # 4. 判断更新或新增
                if not existing or updated_utils.achievement > old_achievement or \
                   (existing.dxscore < updated_utils.dxscore):
                    
                    calculated_rating = maichart.get_dxrating(server=incoming.server, ap_bonus=ap_bonus)
                    
                    if existing:
                        # 更新已有记录
                        change_type = "update"
                        old_data = {
                            "achievement": existing.achievement,
                            "dxscore": existing.dxscore,
                            "dxrating": existing.dxrating,
                            "combo": existing.combo,
                            "sync": existing.sync,
                        }
                        existing.achievement = updated_utils.achievement
                        existing.dxscore = updated_utils.dxscore
                        existing.dxrating = calculated_rating
                        existing.combo = updated_utils.combo
                        existing.sync = updated_utils.sync
                    else:
                        # 新增记录
                        change_type = "insert"
                        old_data = None
                        new_ach = MaiChartAch(
                            user_id=user_id,
                            shortid=shortid,
                            chart_id=mct.id,
                            difficulty=incoming.difficulty,
                            server=incoming.server,
                            achievement=updated_utils.achievement,
                            dxscore=updated_utils.dxscore,
                            dxrating=calculated_rating,
                            combo=updated_utils.combo,
                            sync=updated_utils.sync,
                        )
                        session.add(new_ach)
                    
                    # 记录变更
                    new_data = {
                            "achievement": updated_utils.achievement,
                            "dxscore": updated_utils.dxscore,
                            "dxrating": calculated_rating,
                            "combo": updated_utils.combo,
                            "sync": updated_utils.sync,
                        }
                    if old_data != new_data:
                        # 仅当数据实际发生变化时才记录，避免无意义的更新日志
                        changes_log.append({
                            "type": change_type,
                            "shortid": shortid,
                            "song_name": mct.maidata.title if mct.maidata else "Unknown",
                            "difficulty": incoming.difficulty,
                            "server": incoming.server,
                            "old": old_data,
                            "new": new_data
                        })

        # 5. 提交
        try:
            await session.commit()
        except Exception as e:
            await session.rollback()
            raise e
    
    return changes_log


async def get_user_achievements_with_charts(user_id: int, server: Optional[str] = None) -> list[MaiChartAch]:
    """获取指定用户的成绩，并预加载对应谱面与曲目数据。"""
    async with get_session() as session:
        stmt = select(MaiChartAch).options(
            selectinload(MaiChartAch.chart).selectinload(MaiChart.maidata)
        ).where(MaiChartAch.user_id == user_id)
        if server:
            stmt = stmt.where(MaiChartAch.server == server)
        result = await session.execute(stmt)
        return list(result.scalars().all())


async def get_b50_entries_for_user(user_id: int, server: SERVER_TAG) -> list[tuple[utils.MaiData, int]]:
    """构建 B50 所需条目列表，格式为 (maidata, diff)。"""
    user_achs = await get_user_achievements_with_charts(user_id, server=server)
    maidata_map: dict[int, utils.MaiData] = {}
    entries: list[tuple[utils.MaiData, int]] = []

    for ach in user_achs:
        if ach.difficulty < 1 or ach.difficulty > 7:
            continue
        if not ach.chart or not ach.chart.maidata:
            continue

        shortid = ach.shortid
        if shortid not in maidata_map:
            maidata_map[shortid] = ach.chart.maidata.to_data(clear_chart_achs=True)

        user_ach = utils.MaiChartAch(
            shortid=ach.shortid,
            difficulty=ach.difficulty,
            server=ach.server,
            achievement=ach.achievement,
            dxscore=ach.dxscore,
            combo=ach.combo,
            sync=ach.sync,
            update_time=ach.update_time,
            user_id=user_id,
        )
        maidata_map[shortid].set_chart_ach(ach.difficulty, user_ach)
        entries.append((maidata_map[shortid], ach.difficulty))

    return entries


async def get_user_server_latest_update_time(user_id: int, server: SERVER_TAG) -> Optional[int]:
    """获取指定用户在指定服务器上的成绩最后更新时间（update_time 最大值）。"""
    async with get_session() as session:
        stmt = select(func.max(MaiChartAch.update_time)).where(
            MaiChartAch.user_id == user_id,
            MaiChartAch.server == server,
        )
        result = await session.execute(stmt)
        return result.scalar_one()
