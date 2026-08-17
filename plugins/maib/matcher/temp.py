#!/usr/bin/env python3
"""temp.py - 临时管理命令"""


from nonebot import on_regex
from nonebot.internal.matcher import Matcher
from nonebot.adapters import Bot, Event
from nonebot.permission import SUPERUSER
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from nonebot_plugin_datastore import create_session

from .. import services
from ..utils.enums import Server
from ..utils.map import Versions
from ..services.models import MaiChartAch, MaiUser
from ..services.refresh import _calc_mca_dxrating, _refresh_single_user_dxrating_cache
from . import reply

# temp=True - 临时模块，可能随时移除
__maib_temp__ = True

recalc_dxrating = on_regex(r"^重算dxrating$", permission=SUPERUSER, block=True, priority=1)


@recalc_dxrating.handle()
async def recalc_dxrating_handled(bot: Bot, event: Event, matcher: Matcher):
    """全量重算所有用户的 DXRating"""
    await matcher.send("🔄 开始全量重算 DXRating...")

    async with create_session() as session:
        # 1. 获取所有用户 ID
        user_stmt = select(MaiUser.user_id).distinct()
        user_ids = (await session.execute(user_stmt)).scalars().all()
        
        if not user_ids:
            await matcher.finish("❌ 数据库中没有用户数据")
            return

        # 2. 获取所有成绩记录，按用户分组
        achs_stmt = (
            select(MaiChartAch)
            .options(selectinload(MaiChartAch.chart))
            .order_by(MaiChartAch.user_id, MaiChartAch.server)
        )
        all_achs = (await session.execute(achs_stmt)).scalars().all()

        total = len(all_achs)
        updated = 0
        skipped = 0

        # 3. 逐条重算 dxrating
        for mca in all_achs:
            current_version = Versions.latest(mca.server)
            old_rating = mca.dxrating
            try:
                new_rating = _calc_mca_dxrating(mca, current_version)
            except (ValueError, AttributeError):
                skipped += 1
                continue

            if old_rating != new_rating:
                mca.dxrating = new_rating
                updated += 1

        await session.flush()
        await matcher.send(
            f"📊 重算完成：共 {total} 条成绩，"
            f"更新 {updated} 条，跳过 {skipped} 条"
        )

        # 4. 刷新所有用户的汇总缓存
        refreshed_users = 0
        for user_id in user_ids:
            for srv in (Server.JP, Server.CN):
                try:
                    await _refresh_single_user_dxrating_cache(
                        user_id=user_id,
                        server=srv,
                        session=session,
                    )
                    refreshed_users += 1
                except Exception:
                    pass

        await session.commit()

    await matcher.finish(
        f"✅ 全量重算完成！已刷新 {refreshed_users} 个用户缓存"
    )