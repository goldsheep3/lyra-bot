"""services/ CRUD 模块"""
from typing import Protocol, TypeVar, Awaitable, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from nonebot_plugin_datastore import create_session


"""
命名速查表
---
对于 services 的数据对象，命名：
- `mdt` -> `MaiData`
- `mct` -> `MaiChart`
- `mca` -> `MaiChartAch`
- `ma` -> `MaiAlias`
- `mu` -> `MaiUser`
与之相对：
- `maidata` -> `utils.MaiData`
- `maichart` -> `utils.MaiChart`
- `maichartach`(`ach`) -> `utils.MaiChartAch`
- `maialias` -> `utils.MaiAlias`
- `maiuser` -> `utils.MaiUser`
"""


get_session = create_session

_T_co = TypeVar("_T_co", covariant=True)


class FuncWithSession(Protocol[_T_co]):
    def __call__(self, *, session: AsyncSession) -> Awaitable[_T_co]: ...


class execute_func:

    @staticmethod
    async def select(
        func: FuncWithSession[_T_co],
        *,
        session: Optional[AsyncSession],
    ) -> _T_co:
        if session is not None:
            return await func(session=session)

        async with get_session() as session:
            return await func(session=session)

    @staticmethod
    async def action(
        func: FuncWithSession[_T_co],
        *,
        session: Optional[AsyncSession],
        refresh: bool = False,
        ) -> _T_co:
        if session is not None:
            result = await func(session=session)
            await session.flush()
            if refresh and result is not None:
                await session.refresh(result)
            return result

        async with get_session() as session:
            result = await func(session=session)
            await session.commit()
            if refresh and result is not None:
                await session.refresh(result)
            return result


from .models import MaiData, MaiChart, MaiChartAch, MaiAlias, MaiRecord, MaiIDMap, MaiSyncPairingCode, MaiSyncToken

from .alias import get_ma, add_ma, add_ma_batch, del_ma
from .fetch import set_mct_level, set_mct_level_batch, set_mct_version, set_mdt_version_batch, sync_mdt_list
from .file import upd_mdt_tg_fileid
from .id_remapper import get_pending_mappings, resolve_id_mapping
from .mlist import get_b50, get_mdt_list, get_mct_list, get_mca_list
from .record import add_record_batch, get_record_achs, backfill_record_shortids
from .minfo import get_mdt, add_mdt, add_mct, get_mca
from .refresh import (rfs_mu_dxra, rfs_mu_dxra_batch, rfs_dxra_mct, rfs_dxra_batch,
                      rfs_mu_dxra_with_mct, rfs_mu_dxra_with_mct_batch)
from .sync import set_mca, upd_ach_batch, get_last_sy_hash, set_last_sy_hash
from .user import get_mu, check_mu, set_mu_username, get_mu_from_tgid, set_mu_tgid, del_mu_tgid
from .websync import (
    PAIRING_CODE_PREFIX,
    PairingCodeError,
    AccessTokenError,
    PairingCodeIssueResult,
    create_pairing_code,
    exchange_pairing_code,
    authenticate_access_token,
)


__all__ = [
    # __init__
    "get_session",
    # models
    "MaiData", "MaiChart", "MaiChartAch", "MaiAlias", "MaiRecord", "MaiIDMap", "MaiSyncPairingCode", "MaiSyncToken",
    # alias
    "get_ma", "add_ma", "add_ma_batch", "del_ma",
    # fetch
    "set_mct_level", "set_mct_level_batch", "set_mct_version", "set_mdt_version_batch", "sync_mdt_list",
    # file
    "upd_mdt_tg_fileid",
    # id_remapper
    "get_pending_mappings", "resolve_id_mapping",
    # mlist
    "get_b50", "get_mdt_list", "get_mct_list", "get_mca_list",
    # record
    "add_record_batch", "get_record_achs", "backfill_record_shortids",
    # minfo
    "get_mdt", "add_mdt", "add_mct", "get_mca",
    # refresh
    "rfs_mu_dxra", "rfs_mu_dxra_batch", "rfs_dxra_mct", "rfs_dxra_batch",
    "rfs_mu_dxra_with_mct", "rfs_mu_dxra_with_mct_batch",
    # sync
    "set_mca", "upd_ach_batch", "get_last_sy_hash", "set_last_sy_hash",
    # user
    "get_mu", "check_mu", "set_mu_username",
    "get_mu_from_tgid", "set_mu_tgid", "del_mu_tgid",
    # websync
    "PAIRING_CODE_PREFIX", "PairingCodeError", "AccessTokenError", "PairingCodeIssueResult",
    "create_pairing_code", "exchange_pairing_code", "authenticate_access_token",
]
