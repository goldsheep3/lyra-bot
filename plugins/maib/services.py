import time
from typing import List, Optional, Sequence
from collections import defaultdict

from sqlalchemy import select, or_, delete
from sqlalchemy.orm import selectinload

from . import utils
from .models import MaiData, MaiChart, MaiChartAch, MaiAlias
from .bot_registry import PluginRegistry

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
async def get_song_by_version(version: int, cn: bool = False) -> Sequence[MaiData]:
    """曲名/别名的精确搜索，返回所有匹配的乐曲数据"""
    
    async with get_session() as session:
        statement = (
            select(MaiData)
            .outerjoin(MaiAlias)  # 使用外连接，防止没有别名的曲目被过滤掉
            .where(
                or_(
                    (MaiData.version if not cn else MaiData.version_cn) == version,
                )
            )
            .distinct()
        )
        result = await session.execute(statement)
        return result.scalars().all()


# --- 根据谱面难度 (lv) 筛选 shortid 列表 ---
async def get_shortids_by_lv(min_lv: float, max_lv: float, server: utils.SERVER_TAG) -> Sequence[int]:
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


async def refresh_dxrating_cache(shortid: int, difficulty: int, current_version: int):
    """当定数改变时，重新计算该谱面下所有用户的 dxrating 缓存"""
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
        ach_statement = ach_statement.where(
            MaiChartAch.server == ("CN" if current_version >= 2000 else "JP")
        )
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

async def upload_achievements_batch(user_id: int, ach_list: List[utils.MaiChartAch]):
    """批量上传接口"""
    jp_ver, cn_ver = utils.get_current_versions()

    # 1. 按 shortid 分组，减少后续查询次数
    ach_group = defaultdict(list)
    for a in ach_list:
        ach_group[a.shortid].append(a)

    async with get_session() as session:
        for shortid, incoming_items in ach_group.items():
            # 2. 一次性获取该乐曲的所有谱面及该用户已有的所有成绩
            chart_stmt = select(MaiChart).where(MaiChart.shortid == shortid)
            chart_models = (await session.execute(chart_stmt)).scalars().all()
            if not chart_models:
                continue
            
            chart_dict = {c.difficulty: c for c in chart_models}
            
            exist_ach_stmt = select(MaiChartAch).where(
                MaiChartAch.user_id == user_id,
                MaiChartAch.shortid == shortid
            )
            existing_achs = (await session.execute(exist_ach_stmt)).scalars().all()
            # 唯一索引 key: (difficulty, server)
            existing_ach_dict = {(a.difficulty, a.server): a for a in existing_achs}

            for incoming in incoming_items:
                if incoming.difficulty not in chart_dict:
                    continue
                
                mct = chart_dict[incoming.difficulty]
                existing = existing_ach_dict.get((incoming.difficulty, incoming.server))
                
                # 转换到 Utils 进行逻辑判定
                maichart = mct.to_data()
                if existing:
                    maichart.set_ach(existing.to_data())
                
                # 记录原始状态用于对比是否真的需要更新
                old_achievement = maichart.get_ach(incoming.server).achievement
                
                # 3. 执行合并与 Rating 计算
                # 确定当前环境版本
                cur_ver = cn_ver if incoming.server == "CN" else jp_ver
                ap_bonus = 1 if 2000 > cur_ver >= 25 else 0
                
                # apply_item_achievement 会调用 update_with (取 max)
                updated_utils = maichart.update_ach(incoming)
                
                # 4. 只有当数据确实发生变化时（如成就率提高或牌子更新），才操作 Model
                # 如果是新成绩，或者成就率/DX分数等有提升
                if not existing or updated_utils.achievement > old_achievement or \
                   (existing.dxscore < updated_utils.dxscore):
                    
                    # 重新计算该环境下的缓存 Rating
                    calculated_rating = maichart.get_dxrating(server=incoming.server, ap_bonus=ap_bonus)
                    
                    if existing:
                        existing.achievement = updated_utils.achievement
                        existing.dxscore = updated_utils.dxscore
                        existing.dxrating = calculated_rating
                        existing.combo = updated_utils.combo
                        existing.sync = updated_utils.sync
                        existing.update_time = int(time.time())
                    else:
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
                            update_time=int(time.time())
                        )
                        session.add(new_ach)

        # 5. 最后一次性提交所有变更
        await session.commit()
