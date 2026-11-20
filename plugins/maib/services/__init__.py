from typing import Optional, Sequence, Literal, Mapping

from ..utils.enums import ServerScope
from ..utils.models import MaiData, MaiChart, MaiChartAch, MaiUser, MaiB50Data
from ..utils.models import Server, SLevelSource
from ..utils.report import MaiChartAchDiffReport
from ..utils.sync import LyraRecordV3

from ._refactoring import catalog as _catalog  # catalog
from ._refactoring import _mlist as _query  # query
from ._refactoring import alias as _alias  # alias
from ._refactoring import _sync as _sync  # achievement
from ._refactoring import b50 as _b50  # b50
from ._refactoring import user as _user  # user
from ._refactoring import link as _link
from ._refactoring import aime as _aime  # aime
from ._refactoring import _websync as _websync  # websync
from ._refactoring import _file as _file  # archive
from ._refactoring import mcp_sql as _mcp_sql  # mcp_sql
from ._refactoring import _id_remapper as _idmap  # id_mapping
from ._refactoring import _record as _record  # record
from ._refactoring import _fetch as _fetch  # maintenance.catalog


class catalog:
    @staticmethod
    async def get_maidata(
        shortid: int,
        *,
        qq: Optional[int] = None,
        server: ServerScope = ServerScope.CN,
        provider: Optional[str] = None,
    ) -> Optional[MaiData]:
        """获取乐曲信息"""
        return await _catalog.get_maidata(shortid, qq=qq, server=server, provider=provider)

    @staticmethod
    async def search_maidata(
        keyword: str,
        *,
        qq: Optional[int] = None,
        server: ServerScope = ServerScope.CN,
        provider: Optional[str] = None,
        mode: Literal["smart", "title", "name", "blur"] = "smart",
    ) -> Sequence[MaiData]:
        """搜索乐曲信息"""
        return await _catalog.search_maidata(keyword, qq=qq, server=server, provider=provider, mode=mode)

class query:
    @staticmethod
    async def list_maidata_by_genre(genre: int, *, qq: Optional[int] = None) -> Sequence[MaiData]:
        """通过流派获取乐曲列表"""
        return [a.to_utils() for a in await _query.get_mdt_list.genre(genre, achs_user_id=qq)]

    @staticmethod
    async def list_maidata_by_version(
        ver: int | tuple[int, int],
        allow_utage: bool = False,
        *,
        qq: Optional[int] = None
    ) -> Sequence[MaiData]:
        """通过版本获取乐曲列表"""
        return [a.to_utils() for a in await _query.get_mdt_list.version(ver, achs_user_id=qq, allow_utage=allow_utage)]

    @staticmethod
    async def list_charts_by_level(
        lv: float | tuple[float, float],
        server: Server,
        allow_utage: bool = False,
        *,
        qq: Optional[int] = None
    ) -> Sequence[MaiChart]:
        """通过难度获取谱面列表"""
        return [a.to_utils() for a in await _query.get_mct_list.level(lv, server, achs_user_id=qq, allow_utage=allow_utage)]

    @staticmethod
    async def list_achievements_by_user(
        server: Server,
        allow_utage: bool = False,
        *,
        qq: int
    ) -> Sequence[MaiChartAch]:
        """通过用户获取成绩列表"""
        return [a.to_utils() for a in await _query.get_mca_list.user(qq, server, allow_utage=allow_utage)]

    @staticmethod
    async def list_achievements_by_rate(
        ach: float | tuple[float, float],
        server: Server,
        allow_utage: bool = False,
        *,
        qq: int
    ) -> Sequence[MaiChartAch]:
        """通过达成率获取成绩列表"""
        return [a.to_utils() for a in await _query.get_mca_list.achievement(ach, server, qq, allow_utage=allow_utage)]

    @staticmethod
    async def list_achievements_by_dxrating(
        dxra: float | tuple[float, float],
        server: Server,
        *,
        qq: int
    ) -> Sequence[MaiChartAch]:
        """通过 DX Rating 获取成绩列表"""
        return [a.to_utils() for a in await _query.get_mca_list.dxrating(dxra, server, qq)]

class alias:
    @staticmethod
    async def add_alias(shortid: int, alias: str, *, qq: int) -> _alias.AliasAddStatus:
        """添加曲目别名"""
        return await _alias.add_alias(shortid, alias, qq=qq)

    @staticmethod
    async def remove_alias(shortid: int, alias: str, *, qq: int) -> _alias.AliasRemoveStatus:
        """删除曲目别名"""
        return await _alias.remove_alias(shortid, alias, qq=qq)

class achievement:
    @staticmethod
    async def is_diving_fish_source_current(*, qq: int, hash: str) -> bool:
        """检查 DivingFish 数据源是否为最新"""
        last_hash = await _sync.get_last_sy_hash(qq)
        return last_hash == hash
    
    @staticmethod
    async def update_achievements(*, qq: int, ach_list: Sequence[MaiChartAch], diving_fish_hash: Optional[str] = None) -> MaiChartAchDiffReport:
        """上传成绩并返回报告，支持自动更新 hash"""
        report = await _sync.upd_ach_batch(qq, ach_list)
        if report.has_changes and (report.server == Server.CN) and diving_fish_hash is not None:
            await _sync.set_last_sy_hash(qq, diving_fish_hash)
        return report

class record:
    @staticmethod
    async def ingest_records(records: Sequence[LyraRecordV3], *, qq: int):
        """批量上传 LyraRecordV3 成绩记录并返回报告"""
        record_keys, unmatched_items = await _record.add_record_batch(qq, records)
        ach_list = await _record.get_record_achs(qq, list(record_keys))
        if ach_list:
            report = await _sync.upd_ach_batch(qq, ach_list)
        else:
            report = MaiChartAchDiffReport()
        for title, difficulty in unmatched_items:
            report.no_data_song.append((0, title, difficulty))
        return report

class b50:
    @staticmethod
    async def get_b50_data(
        qq: int,
        scope: ServerScope = ServerScope.CN,
        *,
        provider: Optional[str] = None,
        current_version: Optional[int] = None,
        special_tag: Optional[str] = None,
    ) -> MaiB50Data:
        """获取 B50 曲目列表"""
        return await _b50.get_b50_data(qq, scope, provider=provider, current_version=current_version, special_tag=special_tag)

class user:
    """QQ/TG -> AID 迁移最终入口"""
    @staticmethod
    async def get_or_create_from_qq(qq: int) -> MaiUser:
        return await _user.get_or_create_maiuser_from_qq(qq)

    @staticmethod
    async def get_or_create_from_telegram(telegram_id: int) -> MaiUser:
        return await _user.get_or_create_maiuser_from_tg(telegram_id)

    @staticmethod
    async def get_qq_from_telegram(telegram_id: int) -> Optional[int]:
        return await _link.get_qq_from_tg(telegram_id)

class aime:
    AimeAlreadyLinkedError = _aime.AimeAlreadyLinkedError
    AimeAlreadyLinkedSelfError = _aime.AimeAlreadyLinkedSelfError
    AimeNotFoundError = _aime.AimeNotFoundError
    AimeNotLinkedError = _aime.AimeNotLinkedError
    AimeNotOwnerError = _aime.AimeNotOwnerError
    AimeMultipleFoundError = _aime.AimeMultipleFoundError

    @staticmethod
    async def link(access: str, *, qq: int) -> None:
        """绑定 Aime 卡片"""
        return await _aime.link(access, qq=qq)

    @staticmethod
    async def unlink(access: str, *, qq: int) -> None:
        """解绑 Aime 卡片"""
        return await _aime.unlink(access, qq=qq)

    @staticmethod
    async def find(access: str) -> Optional[_aime.AimeFoundInfo]:
        """查找 Aime 卡片绑定信息"""
        return await _aime.find_aime(access)

    @staticmethod
    async def find_by_access4(access4: str) -> _aime.AimeFoundInfo:
        """使用 Aime 卡片后四位查找绑定信息"""
        return await _aime.find_aime_by_access4(access4)

    @staticmethod
    async def list_for_user(*, qq: int):
        """列出用户绑定的所有 Aime 卡片"""
        return await _aime.get_aimes(qq=qq)

class websync:
    PairingCodeError = _websync.PairingCodeError
    AccessTokenError = _websync.AccessTokenError
    
    @staticmethod
    async def create_pairing_code(*, qq: int, expire_seconds: int = 300) -> _websync.PairingCodeIssueResult:
        """创建并返回最新配对码"""
        return await _websync.create_pairing_code(qq, ttl_seconds=expire_seconds)

    @staticmethod
    async def exchange_pairing_code(*, code: str, device_id: str, device_name: Optional[str] = None) -> tuple[int, str]:
        """使用配对码换取 access_token，返回用户 QQ"""
        return await _websync.exchange_pairing_code(code, device_id=device_id, device_name=device_name)

    @staticmethod
    async def authenticate_access_token(access_token: str) -> int:
        """验证 access_token 并返回用户 QQ"""
        return await _websync.authenticate_access_token(access_token)

class archive:
    @staticmethod
    async def update_telegram_file_id(shortid: int, tg_file_id: str, endname: Literal["adx", "zip"] = "adx") -> None:
        """更新乐曲谱面包的 telegram 文件缓存"""
        await _file.upd_mdt_tg_fileid(shortid, tg_file_id, endname=endname)

class mcp_sql:
    ReadOnlySqlError = _mcp_sql.ReadOnlySqlError

    @staticmethod
    async def sql_query(sql: str):
        """执行 SQL 查询并返回结果"""
        return await _mcp_sql.sql_query(sql)

class maintenance:
    class catalog:
        @staticmethod
        async def sync_song_library(songs: Sequence[MaiData]) -> None:
            """同步乐曲数据库"""
            return await _catalog.sync_song_library(songs)

        @staticmethod
        async def apply_cn_metadata(
            version_updates: Sequence[tuple[int, int]],
            level_updates: Sequence[Mapping[str, int | float]]
        ) -> None:
            """应用国服版本和定数更新"""
            return await _catalog.apply_cn_metadata(version_updates, level_updates)

        @staticmethod
        async def apply_fit_levels(data: list[dict]) -> None:
            """应用拟合定数更新"""
            return await _fetch.set_mct_level_batch(data=data, source=SLevelSource.FIT)

        @staticmethod
        async def has_song_library() -> bool:
            """检查乐曲数据库是否存在数据"""
            return await _catalog.has_song_library()
    
    class alias:
        @staticmethod
        async def sync_aliases(data: list[tuple[int, str]], *, create_qq: int) -> None:
            """同步别名库数据"""
            return await _alias.add_ma_batch(data=data, create_qq=create_qq)

    class id_mapping:
        @staticmethod
        async def get_pending_mappings() -> Sequence[tuple[int, int]]:
            """返回所有 mapped_id 不为 None 的待处理映射 (original_id, mapped_id)"""
            return await _idmap.get_pending_mappings()
        @staticmethod
        async def resolve_mapping(original_id: int, mapped_id: int):
            """对单个 original_id -> mapped_id 执行迁移"""
            return await _idmap.resolve_id_mapping(original_id, mapped_id)

    class record:
        @staticmethod
        async def backfill_and_rebuild_achievements():
            """尝试回填历史记录的未绑定乐曲数据，同步更新影响缓存"""
            affected_by_user = await _record.backfill_record_shortids()
            for qq, record_keys in affected_by_user.items():
                ach_list = await _record.get_record_achs(qq, list(record_keys))
                if ach_list:
                    await _sync.upd_ach_batch(qq, ach_list)


__all__ = [
    "catalog",
    "query",
    "alias",
    "achievement",
    "record",
    "b50",
    "user",
    "aime",
    "websync",
    "archive",
    "mcp_sql",
    "maintenance",
]
