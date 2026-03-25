import random
from typing import Sequence, Literal
from sqlalchemy import update, select, case, cast, Float
from sqlalchemy.dialects.sqlite import insert
from nonebot_plugin_datastore import create_session

from .models import EatableItem, ScoreRecord, UserPreference


async def get_user_preference(user_id: int) -> UserPreference:
    """获取用户偏好"""
    async with create_session() as session:
        query = select(UserPreference).where(UserPreference.user_id == user_id)
        result = await session.scalar(query)
        if not result:
            # 创建默认偏好
            result = UserPreference(user_id=user_id, offset=3.0)
            session.add(result)
            await session.commit()
        return result

async def set_user_preference(user_id: int, offset: float) -> None:
    """设置用户偏好"""
    async with create_session() as session:
        query = update(UserPreference).where(UserPreference.user_id == user_id).values(offset=offset)
        await session.execute(query)
        await session.commit()


async def add_item(name: str, category: Literal['Food', 'Drink'], user_id: int, alcohol: bool,
                   ai_score: int | None = None, ai_reason: str | None = None) -> EatableItem:
    """添加餐点"""
    async with create_session() as session:
        # 创建餐点
        category = category
        new_item = EatableItem(
            name=name, 
            category=category, 
            create_qq=user_id,
            is_wine=alcohol
        )
        session.add(new_item)
        await session.flush()  # 获取 new_item.id

        if ai_score is not None:
            # 同时添加 AI 评分记录，权重设为 30
            ai_record = ScoreRecord(
                item_id=new_item.id,
                user_id=-200,  # AI 设定特殊 user_id
                score=ai_score,
                weight=30,
                reason=ai_reason or ""
            )
            session.add(ai_record)

            # 更新餐点的评分统计
            new_item.total_weighted_sum += ai_score * 30
            new_item.total_weight += 30
            new_item.current_score = new_item.total_weighted_sum / new_item.total_weight

        await session.commit()
        return new_item

async def get_item(item_id: int) -> EatableItem | None:
    """根据 ID 获取餐点"""
    async with create_session() as session:
        query = select(EatableItem).where(EatableItem.id == item_id)
        result = await session.scalar(query)
        return result

async def get_item_by_name(name: str, category: Literal['Food', 'Drink']) -> EatableItem | None:
    """根据名称和类别获取餐点"""
    async with create_session() as session:
        query = select(EatableItem).where(
            EatableItem.name == name,
            EatableItem.category == category
        )
        result = await session.scalar(query)
        return result

async def get_items(category: Literal['Food', 'Drink'], offset: float = 0) -> Sequence[EatableItem]:
    """获取餐点列表，支持基于评分的偏好过滤"""
    async with create_session() as session:
        query = select(EatableItem).where(EatableItem.category == category)
        if offset > 0:
            query = query.where(EatableItem.current_score > offset)
        elif offset < 0:
            query = query.where(EatableItem.current_score < abs(offset))
        result = await session.execute(query)
        return result.scalars().all()

async def choice_item(category: Literal['Food', 'Drink'], offset: float = 0) -> EatableItem | None:
    """基于评分偏好随机选择餐点"""
    items = await get_items(category, offset)
    if not items:
        return None
    # 基于 current_score 进行加权随机选择
    # 若 offset > 0 则倾向于选择评分高于 offset 的餐点，offset < 0 则倾向于选择评分低于 abs(offset) 的餐点
    weights = []
    for item in items:
        if offset > 0:
            weight = max(item.current_score - offset, 0) + 1  # 确保权重至少为 1
        elif offset < 0:
            weight = max(abs(offset) - item.current_score, 0) + 1
        else:
            weight = 1  # 无偏好时权重相等
        weights.append(weight)
    chosen = random.choices(items, weights=weights, k=1)[0]
    return chosen

async def set_score(item_id: int, user_id: int, score: int, weight: int = 1) -> float:
    """设置评分，支持更新和插入，并返回新的平均分"""
    async with create_session() as session:
        # 获取旧记录用于计算 delta
        old_record = await session.scalar(
            select(ScoreRecord).where(
                ScoreRecord.item_id == item_id,
                ScoreRecord.user_id == user_id
            )
        )
        
        old_s = old_record.score if old_record else 0
        old_w = old_record.weight if old_record else 0

        # Upsert 评分记录
        stmt = insert(ScoreRecord).values(
            item_id=item_id,
            user_id=user_id,
            score=score,
            weight=weight
        ).on_conflict_do_update(
            index_elements=['item_id', 'user_id'],
            set_=dict(score=score, weight=weight)
        )
        await session.execute(stmt)

        # 计算增量
        delta_weighted_sum = (score * weight) - (old_s * old_w)
        delta_weight = weight - old_w

        # 使用 SQL 表达式进行原子更新
        update_stmt = (
            update(EatableItem)
            .where(EatableItem.id == item_id)
            .values({
                # 数据库层面执行：total_weight = total_weight + delta
                EatableItem.total_weighted_sum: EatableItem.total_weighted_sum + delta_weighted_sum,
                EatableItem.total_weight: EatableItem.total_weight + delta_weight,
                # 实时重新计算平均分
                EatableItem.current_score: case(
                    (EatableItem.total_weight + delta_weight == 0, 0.0),
                    else_=cast(EatableItem.total_weighted_sum + delta_weighted_sum, Float) / 
                          cast(EatableItem.total_weight + delta_weight, Float)
                )
            })
            .returning(EatableItem.current_score) # 返回新的平均分
        )
        
        result = await session.execute(update_stmt)
        new_avg = result.scalar_one()
        
        await session.commit()
        return round(new_avg, 2)
