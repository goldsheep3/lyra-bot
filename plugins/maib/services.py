from functools import wraps
import time
from typing import cast, Optional, Sequence, Any, Callable, Coroutine

from sqlalchemy import select, or_, delete, func, update, bindparam, Select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from . import utils
from .models import MaiData, MaiChart, MaiChartAch, MaiAlias, MaiUser, MaiDataModel
from .bot_registry import PluginRegistry
from .constants import *


def with_session(func: Callable[..., Coroutine[Any, Any, Any]]):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        session = kwargs.get('session')
        if session is not None:
            # 已提供，直接使用
            result = await func(*args, **kwargs)
            return result
        
        # 如果没提供，则调用工厂函数获取上下文管理器
        get_session = PluginRegistry.get_session
        async with get_session() as session:
            kwargs['session'] = session
            result = await func(*args, **kwargs)
            await session.commit()
            return result
      
    return wrapper


BASE_STMT = (
    select(MaiData)
    .options(
        selectinload(MaiData.charts).noload(MaiChart.achs),
        selectinload(MaiData.aliases),
        )
    )

# 模糊查询结果过多时的最大允许值，超过该值会抛出 ValueError 异常
MAX_BLUR_SEARCH_RESULTS = 100


# === 实际业务逻辑 ===
# --- 查 (get) ---

# 通过 `user_id` 获取 `MaiUser`（唯一）
# 通常使用 `get_or_set_user_by_id` 替代，后者会在用户不存在时自动创建
@with_session
async def get_user_by_id(user_id: int, *, session: AsyncSession) -> Optional[MaiUser]:
    """通过 `user_id` 获取 `MaiUser`（唯一）"""
    statement = (
        select(MaiUser)
        .where(MaiUser.user_id == user_id)
    )
    result = await session.execute(statement)
    return result.scalar_one_or_none()

# 通过 `shortid` 获取 `MaiData`（唯一）
@with_session
async def get_mdt_by_id(shortid: int, achs_userid: int | None = None, *, session: AsyncSession | None = None) -> Optional[MaiData]:
    """通过 `shortid` 获取 `MaiData`（唯一）"""
    session = cast(AsyncSession, session)  # 装饰器已保证 session 不为 None 
    
    statement = (
        select(MaiData)
        .options(
            selectinload(MaiData.charts)
            .selectinload(MaiChart.achs.and_(MaiChartAch.user_id == achs_userid)),
            selectinload(MaiData.aliases),
            )
        .where(MaiData.shortid == shortid)
    )
    result = await session.execute(statement)
    return result.scalar_one_or_none()

# 通过 `曲名` 获取 `MaiData`（唯一）
@with_session
async def get_mdt_by_title(title: str, achs_userid: int | None = None, *, session: AsyncSession) -> Optional[MaiData]:
    """通过 `曲名` 获取 `MaiData`（唯一）"""
    statement = (
        select(MaiData)
        .options(
            selectinload(MaiData.charts)
            .selectinload(MaiChart.achs.and_(MaiChartAch.user_id == achs_userid)),
            selectinload(MaiData.aliases),
            )
        .outerjoin(MaiAlias)  # 使用外连接，防止没有别名的曲目被过滤掉
        .where(MaiData.title == title)
        .distinct()
    )
    result = await session.execute(statement)
    return result.scalar_one_or_none()

# 通过 `曲名/别名` 获取 `MaiData`（列表）
@with_session
async def get_mdt_by_name(keyword: str, achs_userid: int | None = None, *, session: AsyncSession) -> Sequence[MaiData]:
    """通过 曲名/别名 精确获取 `MaiData`（列表）"""
    statement = (
        select(MaiData)
        .options(
            selectinload(MaiData.charts)
            .selectinload(MaiChart.achs.and_(MaiChartAch.user_id == achs_userid)),
            selectinload(MaiData.aliases),
            )
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

# 通过 `曲名/别名` 模糊获取 `MaiData`（列表）
@with_session
async def get_mdt_by_name_blur(keyword: str, achs_userid: int | None = None, *, session: AsyncSession) -> Sequence[MaiData]:
    """通过 曲名/别名 模糊获取 `MaiData`（列表）"""
    filters = or_(
        MaiData.title.contains(keyword),
        MaiAlias.alias.contains(keyword)
    )

    count_statement = (
        select(func.count())
        .select_from(
            select(MaiData.shortid)
            .outerjoin(MaiAlias)
            .where(filters)
            .distinct()
            .subquery()
        )
    )
    result = await session.execute(count_statement)
    matched_count = result.scalar_one()
    if matched_count > MAX_BLUR_SEARCH_RESULTS:
        raise ValueError(
            f"模糊搜索结果过多（{matched_count} 条），请尝试更精确的关键词进行搜索喵qwq"
        )

    statement = (
        select(MaiData)
        .options(
            selectinload(MaiData.charts)
            .selectinload(MaiChart.achs.and_(MaiChartAch.user_id == achs_userid)),
            selectinload(MaiData.aliases),
            )
        .outerjoin(MaiAlias)  # 使用外连接，防止没有别名的曲目被过滤掉
        .where(filters)
        .distinct()
    )
    result = await session.execute(statement)
    return result.scalars().all()

# 通过 曲名/别名 智能获取 `MaiData`（列表）
@with_session
async def get_mdt_by_name_smart(keyword: str, achs_userid: int | None = None, *, session: AsyncSession) -> Sequence[MaiData]:
    """通过 曲名/别名 智能获取 `MaiData`（列表）"""
    songs = await get_mdt_by_name(keyword, achs_userid=achs_userid, session=session)
    if songs:
        return songs
    return await get_mdt_by_name_blur(keyword, achs_userid=achs_userid, session=session)

# 通过 `流派ID` 获取 `MaiData`（列表）
@with_session
async def get_mdt_by_genre(genre: int, achs_userid: int | None = None, *, session: AsyncSession) -> Sequence[MaiData]:
    """通过 流派ID 获取 `MaiData`（列表）"""
    statement = (
        select(MaiData)
        .options(
            selectinload(MaiData.charts)
            .selectinload(MaiChart.achs.and_(MaiChartAch.user_id == achs_userid)),
            selectinload(MaiData.aliases),
        )
        .where(MaiData.genre == genre)
    )
    result = await session.execute(statement)
    return result.scalars().all()

# 通过 等级(或范围) 获取 `MaiChart`（列表）
@with_session
async def get_mct_by_level(lv: float | tuple[float, float], server: SERVER_TAG, achs_userid: int | None = None, *,
                           session: AsyncSession) -> Sequence[MaiChart]:
    """通过 等级范围 获取 `MaiChart`（列表）"""
    if isinstance(lv, float):
        min_lv, max_lv = lv, lv
    elif isinstance(lv, tuple) and len(lv) == 2:
        min_lv, max_lv = lv
    else:
        return list()

    level_field = MaiChart.lv_cn if server == "CN" else MaiChart.lv
    statement = (
        select(MaiChart)
        .options(
            selectinload(MaiChart.maidata)
            .selectinload(MaiData.aliases),
            selectinload(MaiChart.achs.and_(MaiChartAch.user_id == achs_userid)),
        )
        .where(level_field >= min_lv, level_field <= max_lv)
    )

    result = await session.execute(statement)
    return result.scalars().all()

# "通过 别名 获取 `MaiAlias`（列表）
@with_session
async def get_mdt_alias_list(alias_text: str, *, session: AsyncSession) -> Sequence[MaiAlias]:
    """通过 别名 获取 `MaiAlias`（列表）"""
    statement = (
        select(MaiAlias)
        .where(MaiAlias.alias == alias_text)
    )
    result = await session.execute(statement)
    return result.scalars().all()

# "通过 别名, `shortid` 获取 `MaiAlias`（唯一）
@with_session
async def get_mdt_alias(alias_text: str, shortid: int, *, session: AsyncSession) -> MaiAlias | None:
    """通过 别名, `shortid` 获取 `MaiAlias`（唯一）"""
    statement = (
        select(MaiAlias)
        .where(MaiAlias.alias == alias_text, MaiAlias.shortid == shortid)
    )
    result = await session.execute(statement)
    return result.scalar_one_or_none()

# 通过 `user_id, server, shortid, difficulty` 获取 `MaiChartAch`（唯一）
@with_session
async def get_mct_ach(user_id: int, server: SERVER_TAG, shortid: int, difficulty: int, *, session: AsyncSession) -> MaiChartAch | None:
    """通过 `user_id, server, shortid, difficulty` 获取 `MaiChartAch`（唯一）"""
    statement = (
        select(MaiChartAch)
        .where(
            MaiChartAch.user_id == user_id,
            MaiChartAch.server == server,
            MaiChartAch.shortid == shortid,
            MaiChartAch.difficulty == difficulty
        )
    )
    result = await session.execute(statement)
    return result.scalar_one_or_none()

# 通过 `user_id, server, shortid` 获取 `MaiChartAch`（列表）
@with_session
async def get_mct_achs(user_id: int, server: SERVER_TAG, shortid: int, *, session: AsyncSession) -> Sequence[MaiChartAch]:
    """通过 `user_id, server, shortid` 获取 `MaiChartAch`（列表）"""
    statement = (
        select(MaiChartAch)
        .where(
            MaiChartAch.user_id == user_id,
            MaiChartAch.server == server,
            MaiChartAch.shortid == shortid
        )
    )
    result = await session.execute(statement)
    return result.scalars().all()


def _ach_to_change_json(ach: utils.MaiChartAch | None) -> dict[str, Any] | None:
    """把成绩对象转为可序列化的变更数据"""
    if ach is None:
        return None

    return {
        "shortid": ach.shortid,
        "difficulty": ach.difficulty,
        "server": ach.server,
        "achievement": ach.achievement,
        "dxscore": ach.dxscore,
        "combo": ach.combo,
        "sync": ach.sync,
        "update_time": ach.update_time,
        "user_id": ach.user_id,
    }


def generate_change_log(chart: MaiChart, new_ach: utils.MaiChartAch, old_ach: utils.MaiChartAch | None) -> dict[str, Any] | None:
    """生成成绩变更的 JSON 描述。

    返回值同时保留结构化字段和展示所需信息，调用方可以直接把 `lines` 串接后交给
    `image_gen.simple_list()`。
    """
    if old_ach is not None and not (new_ach > old_ach):
        return None

    merged_ach = new_ach if old_ach is None else utils.MaiChartAch(
        shortid=new_ach.shortid,
        difficulty=new_ach.difficulty,
        server=new_ach.server,
        achievement=max(new_ach.achievement, old_ach.achievement),
        dxscore=max(new_ach.dxscore, old_ach.dxscore),
        combo=max(new_ach.combo, old_ach.combo),
        sync=max(new_ach.sync, old_ach.sync),
        update_time=int(time.time()),
        user_id=new_ach.user_id,
    )
    title = chart.maidata.title if chart.maidata else ""
    diff_text = DIFFS_DICT.get(chart.difficulty, str(chart.difficulty))

    payload: dict[str, Any] = {
        "action": "insert" if old_ach is None else "update",
        "song": {
            "shortid": chart.shortid,
            "title": title,
            "difficulty": chart.difficulty,
            "difficulty_text": diff_text,
            "server": new_ach.server,
        },
        "old": _ach_to_change_json(old_ach),
        "new": _ach_to_change_json(merged_ach),
    }

    lines = [f"{chart.shortid}. {title}({diff_text})"]
    if old_ach is None:
        lines.extend([
            f"Achievement: {merged_ach.achievement:.2f}%",
            f"DX Score: {merged_ach.dxscore}",
            f"Combo: {DF_FC_DICT.get(merged_ach.combo, None)}",
            f"Sync: {DF_FS_DICT.get(merged_ach.sync, None)}",
        ])
    else:
        lines.extend([
            f"Achievement: {old_ach.achievement:.2f}% -> {merged_ach.achievement:.2f}%",
            f"DX Score: {old_ach.dxscore} -> {merged_ach.dxscore}",
            f"Combo: {DF_FC_DICT.get(old_ach.combo, None)} -> {DF_FC_DICT.get(merged_ach.combo, None)}",
            f"Sync: {DF_FS_DICT.get(old_ach.sync, None)} -> {DF_FS_DICT.get(merged_ach.sync, None)}",
        ])

    payload["lines"] = lines
    return payload


def change_log_to_text(change_log: dict[str, Any]) -> str:
    """把成绩变更 JSON 转为 `simple_list` 可直接渲染的文本"""
    return "\n".join(change_log.get("lines", []))


def _is_achievement_priority_better(new_ach: utils.MaiChartAch, old_ach: utils.MaiChartAch) -> bool:
    """成绩优先比较：先比较 achievement，再比较其余字段。"""
    return (
        new_ach.achievement,
        new_ach.dxscore,
        new_ach.combo,
        new_ach.sync,
    ) > (
        old_ach.achievement,
        old_ach.dxscore,
        old_ach.combo,
        old_ach.sync,
    )


# 通过 `user_id, server, cut_version` 获取 `MaiChartAch`（列表）（用于 best 50 生成）
@with_session
async def get_mdts_for_b50(user_id: int, server: SERVER_TAG, cut_version: int, *, session: AsyncSession) -> tuple[Sequence[MaiChartAch], Sequence[MaiChartAch]]:
    """
    通过 `user_id, server, cut_version` 获取 `MaiChartAch`（列表）（用于 best 50 生成）
    Returns:
    - b35 列表（版本 < cut_version，按 DX Rating 降序，最多 35 条）
    - b15 列表（版本 >= cut_version，按 DX Rating 降序，最多 15 条）
    """
    def _build_b50_statement(
    user_id: int, server: SERVER_TAG, version_condition, limit_count: int
    ) -> Select:
        """构建 B50 查询语句"""
        return (
            select(MaiChartAch)
            .join(MaiChartAch.chart)
            .join(MaiChart.maidata)
            .options(
                selectinload(MaiChartAch.chart).selectinload(MaiChart.maidata)
            )
            .where(
                MaiChartAch.user_id == user_id,
                MaiChartAch.server == server,
                version_condition,
            )
            .order_by(MaiChartAch.dxrating.desc(), MaiChartAch.achievement.desc())
            .limit(limit_count)
        )
    
    version_field = MaiData.version_cn if server == "CN" else MaiData.version

    stmt_b35 = _build_b50_statement(
        user_id=user_id,
        server=server,
        version_condition=version_field < cut_version,
        limit_count=35,
    )
    result = await session.execute(stmt_b35)
    achs_b35 = result.scalars().all()

    stmt_b15 = _build_b50_statement(
        user_id=user_id,
        server=server,
        version_condition=version_field >= cut_version,
        limit_count=15,
    )
    result = await session.execute(stmt_b15)
    achs_b15 = result.scalars().all()

    return achs_b35, achs_b15


# --- 增 (add) ---

# 新增 `MaiData`（全新曲目）
@with_session
async def add_mdt(mdt: MaiData, *, session: AsyncSession) -> None:
    """新增 `MaiData`（全新曲目）"""
    session.add(mdt)


# 通过 `shortid` 新增 `MaiChart`
@with_session
async def add_mct(shortid: int, mct: MaiChart, *, session: AsyncSession) -> None:
    """通过 `shortid` 新增 `MaiChart`"""
    statement = (
        select(MaiData)
        .where(MaiData.shortid == shortid)
    )
    result = await session.execute(statement)
    mdt = result.scalar_one_or_none()
    
    if mdt:
        mdt.charts.append(mct)


# --- 删 (del) ---

# 通过 `alias_id` 删除 `MaiAlias`
@with_session
async def del_mdt_alias_by_id(alias_id: int, *, session: AsyncSession):
    """通过 `alias_id` 删除 `MaiAlias`"""
    statement = (
        delete(MaiAlias)
        .where(MaiAlias.id == alias_id)
    )
    await session.execute(statement)


# --- 改 (update) ---

# 通过 `shortid` 更新 `MaiData`（已有曲目）
@with_session
async def update_mdt(mdt: MaiData, *, session: AsyncSession):
    """通过 `shortid` 更新 `MaiData`（已有曲目）"""

    existing = await get_mdt_by_id(mdt.shortid, session=session)
    if existing:
        # 直接覆盖字段
        existing.title = mdt.title
        existing.artist = mdt.artist
        existing.genre = mdt.genre
        existing.version = mdt.version
        existing.version_cn = mdt.version_cn
        existing.utage_tag = mdt.utage_tag
        existing.buddy = mdt.buddy
        # 检查并更新谱面数据
        difficulty_set = {chart.difficulty for chart in existing.charts + mdt.charts}
        for difficulty in difficulty_set:
            existing_chart = next((c for c in existing.charts if c.difficulty == difficulty), None)
            new_chart = next((c for c in mdt.charts if c.difficulty == difficulty), None)
            if new_chart:
                # TODO 后续优化到 update_mct 复用
                if existing_chart:
                    # 已有谱面，更新字段
                    existing_chart.lv = new_chart.lv
                    existing_chart.lv_cn = new_chart.lv_cn
                    existing_chart.lv_synh = new_chart.lv_synh
                    existing_chart.des = new_chart.des
                    existing_chart.inote = new_chart.inote
                    
                    existing_chart.note_count_tap = new_chart.note_count_tap
                    existing_chart.note_count_hold = new_chart.note_count_hold
                    existing_chart.note_count_slide = new_chart.note_count_slide
                    existing_chart.note_count_touch = new_chart.note_count_touch
                    existing_chart.note_count_break = new_chart.note_count_break
                else:
                    # 全新难度，直接添加
                    existing.charts.append(new_chart)
        # 检查并更新别名数据
        # TODO
        # 问题： 在更新曲目时，每有一个别名就去查一次数据库。如果批量更新 100 首歌，每首歌 5 个别名，就会产生 500 次查询。
        # 建议： 先用 in_() 语句一次性查出该曲目的所有别名，在内存中进行比对。
        aliases = {alias.alias: alias for alias in mdt.aliases}
        for alias_text, mdt_alias in aliases.items():
            alias = await get_mdt_alias(alias_text, existing.shortid, session=session)
            if not alias:
                # 数据库不存在该别名，直接添加
                existing.aliases.append(mdt_alias)

# 设置 `MaiChart` 的 `level` (通过 `shortid, difficulty, server ( 支持 synh )`)
@with_session
async def set_mct_level(mct: MaiChart | tuple[int, int], server: SERVER_TAG | Literal['synh'], level: float,
                        *, session: AsyncSession):
    """
    设置 `MaiChart` 的 `level`
    通过 `shortid, difficulty, server`
    Args:
      mct: MaiChart 实例或 (shortid, difficulty) 元组
      server: 支持：'JP' / 'CN' / 'synh'
      level: 定数（可以是小数）
    """

    if isinstance(mct, MaiChart):
        chart = mct
    else:
        shortid, difficulty = mct
        statement = (
            select(MaiChart)
            .where(MaiChart.shortid == shortid, MaiChart.difficulty == difficulty)
        )
        result = await session.execute(statement)
        chart = result.scalar_one_or_none()
    
    if chart:
        if server == 'CN':
            chart.lv_cn = level
        elif server == 'synh':
            chart.lv_synh = level
        elif server == 'JP':
            chart.lv = level
        else:
            return

# [批量] 通过 `shortid, difficulty, server (支持 synh)` 设置 `MaiChart` 的 `level`
@with_session
async def set_mct_level_batch(data: list[dict], server: SERVER_TAG | Literal['synh'], 
                              *, session: AsyncSession):
    """
    [批量] 通过 `shortid, difficulty, server (支持 synh)` 设置 `MaiChart` 的 `level`
    data 格式: [{"shortid": 123, "difficulty": 2, "level": 14.5}, ...]
    """

    # 1. 定义 server 与 数据库字段的映射
    server_field_map = {
        'JP': MaiChart.lv,
        'CN': MaiChart.lv_cn,
        'synh': MaiChart.lv_synh
    }

    if server not in server_field_map:
        raise ValueError(f"Unsupported server: {server}")

    target_field = server_field_map[server]

    # 2. 构建动态 update 语句
    # 使用 bindparam("level") 对应 data 字典中的 "level" 键
    statement = (
        update(MaiChart)
        .where(MaiChart.shortid == bindparam("shortid"))
        .where(MaiChart.difficulty == bindparam("difficulty"))
        .values({target_field: bindparam("level")})
    )

    # 3. 执行批量操作
    await session.execute(statement, data)

# 设置 `MaiData` 的 `version` (通过 `shortid, server`)
@with_session
async def set_mct_version(shortid: int, server: SERVER_TAG, version: int,
                          *, session: AsyncSession):
    """
    设置 `MaiData` 的 `version`
    通过 `shortid, server`
    Args:
      shortid: 曲目 ID
      server: 支持：'JP' / 'CN' / 'synh'
      version: 版本号
    """

    statement = (
        select(MaiData)
        .where(MaiData.shortid == shortid)
    )
    result = await session.execute(statement)

    if mdt := result.scalar_one_or_none():
        if server == 'CN':
            mdt.version_cn = version
        elif server == 'JP':
            mdt.version = version
        else:
            return

# [批量] 设置 `MaiData` 的 `version` (通过 `shortid, server`)
@with_session
async def set_mdt_version_batch(data: list[tuple[int, int]],  server: SERVER_TAG,
                                *, session: AsyncSession):
    """
    [批量] 设置 `MaiData` 的 `version`
    data 格式: [(shortid, version), ...]
    """
    if not data:
        return

    # 1. 映射服务器标签到数据库字段
    server_field_map = {
        'CN': MaiData.version_cn,
        'JP': MaiData.version
    }

    if server not in server_field_map:
        # 如果传入了不支持的 server 标签，直接返回或报错
        return

    target_field = server_field_map[server]

    # 2. 构建动态批量更新语句
    statement = (
        update(MaiData)
        .where(MaiData.shortid == bindparam("shortid"))
        .values({target_field: bindparam("version")})
    )

    # 3. 执行批量更新
    await session.execute(statement, [{"shortid": sid, "version": version} for sid, version in data])

# 通过 `shortid` 添加 `MaiData.aliases`，带鉴权属性
@with_session
async def add_mdt_alias(shortid: int, alias_text: str, create_qq: int, create_qq_group: Optional[int] = None,
                        *, session: AsyncSession | None = None) -> bool:
    """
    通过 `shortid` 添加 `MaiData.aliases`，带鉴权属性
    返回值 bool 若为 False 表示已存在该别名
    """
    session = cast(AsyncSession, session)

    # 检查是否已存在该别名
    check_statement = (
        select(MaiAlias)
        .where(MaiAlias.shortid == shortid, MaiAlias.alias == alias_text)
    )
    existing = await session.execute(check_statement)
    if existing.scalar_one_or_none():
        return False

    # 设置新别名
    new_alias = MaiAlias(
        shortid=shortid,
        alias=alias_text,
        create_qq=create_qq,
        create_qq_group=create_qq_group,
        create_time=int(time.time())
    )
    session.add(new_alias)
    return True

# [批量] 通过 `shortid` 添加 `MaiData.aliases`，带鉴权属性
@with_session
async def add_mdt_alias_batch(data: list[tuple[int, str]], create_qq: int,
                              *, session: AsyncSession):
    """
    [批量] 通过 `shortid` 添加 `MaiData.aliases`，带鉴权属性
    Args:
      data: `[(shortid, "别名文本"), ...]`
      create_qq: 占位 qq
    """
    if not data:
        return

    # 统一为每一条数据注入 create_qq，groupid 保持为 None
    full_data = [
        {"shortid": sid, "alias": alias, "create_qq": create_qq, "create_qq_group": None, "create_time": int(time.time())} 
        for sid, alias in data
    ]
    
    sql_type = PluginRegistry.get_sql_name()

    # 1. 尝试使用高性能方言 (SQLite / PostgreSQL)
    if sql_type in ("sqlite", "postgresql"):
        if sql_type == "sqlite":
            from sqlalchemy.dialects.sqlite import insert as dialect_insert
        else:
            from sqlalchemy.dialects.postgresql import insert as dialect_insert
            
        # 使用补全后的 full_data
        stmt = dialect_insert(MaiAlias).values(full_data)
        stmt = stmt.on_conflict_do_nothing(index_elements=['shortid', 'alias'])
        await session.execute(stmt)
    
    # 2. 通用降级逻辑 (MySQL 或其他)
    else:
        sids = {d['shortid'] for d in full_data}
        result = await session.execute(
            select(MaiAlias).where(MaiAlias.shortid.in_(sids))
        )
        existing_set = {(a.shortid, a.alias) for a in result.scalars().all()}

        new_objs = []
        for d in full_data:
            if (d['shortid'], d['alias']) not in existing_set:
                new_objs.append(MaiAlias(**d))
                existing_set.add((d['shortid'], d['alias'])) 
        
        if new_objs:
            session.add_all(new_objs)


# 设置 `MaiChart` 的成绩
@with_session
async def set_mct_ach(server: SERVER_TAG, ach: utils.MaiChartAch,
                      *, session: AsyncSession):
    """
    设置 `MaiChart` 的成绩
    Args:
      server: 支持：'JP' / 'CN' / 'synh'
      ach: 成绩数据
    """

    statement = (
        select(MaiChart)
        .options(selectinload(MaiChart.maidata))
        .where(MaiChart.shortid == ach.shortid, MaiChart.difficulty == ach.difficulty)
    )
    result = await session.execute(statement)
    chart = result.scalar_one_or_none()
    
    if chart:
        new_ach = ach
        mct_ach = await get_mct_ach(
            user_id=ach.user_id,
            server=server,
            shortid=chart.shortid,
            difficulty=chart.difficulty,
            session=session
        )
        old_ach = cast(utils.MaiChartAch, mct_ach.to_data()) if mct_ach else None
        if mct_ach is not None:
            if old_ach is not None and not (new_ach > old_ach):
                return None
            mct_ach.update(new_ach)
        else:
            session.add(MaiChartAch(
                user_id=ach.user_id,
                chart_id=chart.id,
                shortid=chart.shortid,
                difficulty=chart.difficulty,
                server=server,
                achievement=new_ach.achievement,
                dxscore=new_ach.dxscore,
                combo=new_ach.combo,
                sync=new_ach.sync,
                update_time=int(time.time()),
            ))

        return generate_change_log(chart, new_ach, old_ach)
    return None


# 设置 `MaiUser` 的 `username`
@with_session
async def set_username(user_id: int, new_username: str,
                       *, session: AsyncSession):
    """
    设置 `MaiUser` 的 `username`
    Args:
      user_id: 用户 ID
      new_username: 新用户名
    """

    statement = (
        select(MaiUser)
        .where(MaiUser.user_id == user_id)
    )
    result = await session.execute(statement)
    user = result.scalar_one_or_none()
    
    if user:
        user.username = new_username

# --- 其他 ---

# 通过 `mdt_list` 高效同步曲目列表
@with_session
async def sync_mdt_list(mdt_list: list[MaiData], *, session: AsyncSession):
    """
    高效同步曲目列表：自动处理新增与更新
    Args:
        mdt_list: 准备同步的实体对象列表
    """
    if not mdt_list:
        return

    # 1. 一次性查出所有现有的数据（包含关联的 charts）
    sids = [m.shortid for m in mdt_list]
    stmt = (
        select(MaiData)
        .where(MaiData.shortid.in_(sids))
        .options(selectinload(MaiData.charts))
    )
    result = await session.execute(stmt)
    existing_map = {m.shortid: m for m in result.scalars().all()}

    for new_mdt in mdt_list:
        existing = existing_map.get(new_mdt.shortid)
        
        if not existing:
            # A. 数据库没有：直接添加
            session.add(new_mdt)
        else:
            # B. 数据库已有：手动更新字段（Merge 逻辑）
            # 基础属性更新
            for field in ['title', 'bpm', 'artist', 'genre', 'cabinet',
                          'version', 'version_cn', 'converter', 'zip_path',
                          'is_utage', 'utage_tag', 'buddy']:
                setattr(existing, field, getattr(new_mdt, field))
            
            # 谱面更新逻辑 (Charts)
            existing_charts = {c.difficulty: c for c in existing.charts}
            for new_mct in new_mdt.charts:
                existing_chart = existing_charts.get(new_mct.difficulty)
                if existing_chart:
                    # 更新已有难度属性
                    for f in ['lv', 'lv_cn', 'lv_synh', 'des', 'inote', 
                              'note_count_tap', 'note_count_hold', 'note_count_slide', 
                              'note_count_touch', 'note_count_break']:
                        setattr(existing_chart, f, getattr(new_mct, f))
                else:
                    # 添加新难度
                    existing.charts.append(new_mct)


def _normalize_server_for_user_cache(server: SERVER_TAG) -> Literal["JP", "CN"]:
    """将服务器标签归一到 `MaiUser` 缓存字段使用的 JP/CN。"""
    return "CN" if server == "CN" else "JP"


def _get_current_version_by_server(server: SERVER_TAG) -> int:
    """获取对应服务器的当前版本号"""
    jp_ver, cn_ver = utils.get_current_versions()
    return cn_ver if server == "CN" else jp_ver


def get_cut_version(server: SERVER_TAG) -> int:
    """获取 B50 分段所需的 cut_version。"""
    return _get_current_version_by_server(server)


async def _recalculate_single_mct_ach_dxrating(
    mct_ach: MaiChartAch,
    maichart: utils.MaiChart,
    *,
    current_version: int,
) -> int:
    """重算单条成绩的 DXRating 并写回模型，返回最新 DXRating。"""
    # maiJP 25(CiRCLE) 及以后版本计算 AP Bonus（CN 版本号统一 >= 2000，不参与该规则）
    ap_bonus = 1 if 2000 > current_version >= 25 else 0

    ach = mct_ach.to_data()
    maichart.set_ach(ach)
    new_dxrating = maichart.get_dxrating(server=mct_ach.server, ap_bonus=ap_bonus)
    mct_ach.dxrating = new_dxrating
    return new_dxrating


@with_session
async def refresh_user_dxrating_cache(user_id: int, server: SERVER_TAG,
                                      *, session: AsyncSession):
    """重算单个用户在指定服务器（JP/CN）的 DXRating 汇总缓存。"""

    cache_server = _normalize_server_for_user_cache(server)
    cut_version = _get_current_version_by_server(cache_server)

    b35, b15 = await get_mdts_for_b50(
        user_id=user_id,
        server=cache_server,
        cut_version=cut_version,
        session=session,
    )
    total_dxrating = sum(a.dxrating for a in b35) + sum(a.dxrating for a in b15)

    latest_update_stmt = (
        select(func.max(MaiChartAch.update_time))
        .where(MaiChartAch.user_id == user_id, MaiChartAch.server == cache_server)
    )
    latest_update_time = (await session.execute(latest_update_stmt)).scalar_one_or_none() or 0

    user = await get_user_by_id(user_id=user_id, session=session)
    if not user:
        user = MaiUser(user_id=user_id)
        session.add(user)

    if cache_server == "CN":
        user.cn_dxrating = total_dxrating
        user.cn_update_time = latest_update_time
    else:
        user.jp_dxrating = total_dxrating
        user.jp_update_time = latest_update_time


@with_session
async def refresh_user_dxrating_cache_batch(user_ids: Sequence[int], server: SERVER_TAG,
                                            *, session: AsyncSession):
    """批量重算用户 DXRating 汇总缓存。"""
    if not user_ids:
        return

    for uid in set(user_ids):
        await refresh_user_dxrating_cache(user_id=uid, server=server, session=session)


@with_session
async def refresh_dxrating_cache_by_chart(shortid: int, difficulty: int, server: SERVER_TAG,
                                          *, session: AsyncSession):
    """
    场景 1：谱面定数变动后，刷新 `shortid, difficulty, server` 下所有用户的该谱面 DXRating，
    并重算受影响用户的 `MaiUser` DXRating 缓存。
    """

    statement = (
        select(MaiChart)
        .where(MaiChart.shortid == shortid, MaiChart.difficulty == difficulty)
    )
    mct = (await session.execute(statement)).scalar_one_or_none()
    if not mct:
        return

    maichart = mct.to_data()
    current_version = _get_current_version_by_server(server)

    ach_statement = (
        select(MaiChartAch)
        .where(
            MaiChartAch.shortid == shortid,
            MaiChartAch.difficulty == difficulty,
            MaiChartAch.server == server,
        )
    )
    mct_achs = (await session.execute(ach_statement)).scalars().all()
    if not mct_achs:
        return

    affected_user_ids: set[int] = set()
    for mct_ach in mct_achs:
        await _recalculate_single_mct_ach_dxrating(
            mct_ach=mct_ach,
            maichart=maichart,
            current_version=current_version,
        )
        if mct_ach.user_id is not None:
            affected_user_ids.add(mct_ach.user_id)

    if affected_user_ids:
        await refresh_user_dxrating_cache_batch(
            user_ids=list(affected_user_ids),
            server=server,
            session=session,
        )


@with_session
async def refresh_dxrating_cache_by_chart_user(shortid: int, difficulty: int, server: SERVER_TAG, user_id: int,
                                               *, session: AsyncSession):
    """
    场景 2：谱面成绩批量上传时，刷新指定 `shortid, difficulty, server, user_id` 的谱面 DXRating，
    并重算该用户 `MaiUser` DXRating 缓存。
    """

    statement = (
        select(MaiChart)
        .where(MaiChart.shortid == shortid, MaiChart.difficulty == difficulty)
    )
    mct = (await session.execute(statement)).scalar_one_or_none()
    if not mct:
        return

    ach_statement = (
        select(MaiChartAch)
        .where(
            MaiChartAch.shortid == shortid,
            MaiChartAch.difficulty == difficulty,
            MaiChartAch.server == server,
            MaiChartAch.user_id == user_id,
        )
    )
    mct_ach = (await session.execute(ach_statement)).scalar_one_or_none()
    if not mct_ach:
        # 该用户该谱面该服无成绩时，也同步兜底刷新一次用户缓存。
        await refresh_user_dxrating_cache(user_id=user_id, server=server, session=session)
        return

    maichart = mct.to_data()
    current_version = _get_current_version_by_server(server)
    await _recalculate_single_mct_ach_dxrating(
        mct_ach=mct_ach,
        maichart=maichart,
        current_version=current_version,
    )
    await refresh_user_dxrating_cache(user_id=user_id, server=server, session=session)


async def get_or_set_user_by_id(user_id: int) -> MaiUser:
    """通过 `user_id` 获取 `MaiUser`，如果不存在则创建一个新的"""
    # 该方法不接受外部 session，内部自行管理生命周期
    async with PluginRegistry.get_session() as session:
        user = await get_user_by_id(user_id, session=session)
        if user:
            return user

        new_user = MaiUser(user_id=user_id)
        session.add(new_user)
        await session.commit()
    return new_user


@with_session
async def upload_achievements_batch(user_id: int, ach_list: Sequence[utils.MaiChartAch],
                                    *, session: AsyncSession) -> list[dict[str, Any]]:
    """批量上传成绩并返回变更列表。"""
    if not ach_list:
        return []

    # 1. 输入去重：同一 key 只保留更优成绩
    unique_incoming: dict[tuple[int, int, SERVER_TAG], utils.MaiChartAch] = {}
    for ach in ach_list:
        ach.user_id = user_id
        key = (ach.shortid, ach.difficulty, ach.server)
        prev = unique_incoming.get(key)
        if prev is None or _is_achievement_priority_better(ach, prev):
            unique_incoming[key] = ach

    if not unique_incoming:
        return []

    shortids = sorted({sid for sid, _, _ in unique_incoming.keys()})

    # 2. 一次性加载谱面与用户已有成绩
    chart_stmt = (
        select(MaiChart)
        .options(selectinload(MaiChart.maidata))
        .where(MaiChart.shortid.in_(shortids))
    )
    chart_models = (await session.execute(chart_stmt)).scalars().all()
    chart_map = {(c.shortid, c.difficulty): c for c in chart_models}

    exist_stmt = (
        select(MaiChartAch)
        .where(
            MaiChartAch.user_id == user_id,
            MaiChartAch.shortid.in_(shortids),
        )
    )
    existing_achs = (await session.execute(exist_stmt)).scalars().all()
    existing_map = {(a.shortid, a.difficulty, a.server): a for a in existing_achs}

    changes_log: list[dict[str, Any]] = []
    affected_servers: set[SERVER_TAG] = set()

    # 3. 批量更新/插入
    for (shortid, difficulty, server), incoming in unique_incoming.items():
        chart = chart_map.get((shortid, difficulty))
        if not chart:
            continue

        maichart = chart.to_data()
        current_version = _get_current_version_by_server(server)
        ap_bonus = 1 if 2000 > current_version >= 25 else 0

        existing = existing_map.get((shortid, difficulty, server))
        if existing:
            old_ach = existing.to_data()
            if not _is_achievement_priority_better(incoming, old_ach):
                continue

            existing.update(incoming)
            merged = existing.to_data()
            maichart.set_ach(merged)
            new_dxrating = maichart.get_dxrating(server=server, ap_bonus=ap_bonus)

            old_payload = {
                "achievement": existing.achievement,
                "dxscore": existing.dxscore,
                "dxrating": existing.dxrating,
                "combo": existing.combo,
                "sync": existing.sync,
            }

            existing.dxrating = new_dxrating
            existing.update_time = int(time.time())

            new_payload = {
                "achievement": merged.achievement,
                "dxscore": merged.dxscore,
                "dxrating": new_dxrating,
                "combo": merged.combo,
                "sync": merged.sync,
            }

            if old_payload != new_payload:
                unified_log = generate_change_log(chart, incoming, old_ach)
                if unified_log:
                    # 统一返回 generate_change_log 原生结构
                    changes_log.append(unified_log)
                affected_servers.add(server)
            continue

        maichart.set_ach(incoming)
        new_dxrating = maichart.get_dxrating(server=server, ap_bonus=ap_bonus)

        new_model = MaiChartAch(
            user_id=user_id,
            shortid=shortid,
            chart_id=chart.id,
            difficulty=difficulty,
            server=server,
            achievement=incoming.achievement,
            dxscore=incoming.dxscore,
            dxrating=new_dxrating,
            combo=incoming.combo,
            sync=incoming.sync,
            update_time=int(time.time()),
        )
        session.add(new_model)

        new_payload = {
            "achievement": incoming.achievement,
            "dxscore": incoming.dxscore,
            "dxrating": new_dxrating,
            "combo": incoming.combo,
            "sync": incoming.sync,
        }
        unified_log = generate_change_log(chart, incoming, None)
        if unified_log:
            # 统一返回 generate_change_log 原生结构
            changes_log.append(unified_log)
        affected_servers.add(server)

    # 4. 重算用户缓存（按受影响服务器）
    for server in affected_servers:
        await refresh_user_dxrating_cache(user_id=user_id, server=server, session=session)

    return changes_log
