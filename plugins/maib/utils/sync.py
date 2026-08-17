"""sync/ 数据同步、缓存与查分器适配模块"""
from __future__ import annotations

import base64
import gzip
import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Awaitable, Callable, Mapping, Optional, Sequence, cast

import orjson

from .models import MaiChartAch, MaiData
from .enums import Server
from ..utils.map import Difficulties, ComboID, SyncID, Combos, Syncs


__all__ = [
    # 水鱼数据解析
    "parse_sy_player_record",
    "get_sy_records",
    # lyra-maisync 数据解析
    "parse_lyra_maisync_data",
    "normalize_legacy_lyra_record",
    "build_legacy_lyra_ach_list",
    "LegacyLyraImportResult",
    "LyraRecordV3",
    "LyraRecordImportResultV3",
    "build_record_hash",
    "normalize_lyra_record_v3",
    "build_lyra_records_v3",
]


_LYRA_HEADER_PATTERN = re.compile(
    r'^lyra_maisync:json\.gz\.base64:(?P<version>v[0-9a-z.\-]+);(?P<payload>.+)$'
)


@dataclass(slots=True)
class LegacyLyraRecord:
    """旧版 lyra-maimai 导入记录的标准化结果"""

    title: str
    record_type: str
    difficulty: int
    server: Server
    achievement: float
    dxscore: int
    combo: ComboID
    sync: SyncID


@dataclass(slots=True)
class LegacyLyraImportResult:
    """旧版 lyra-maimai 导入的解析结果"""

    ach_list: list[MaiChartAch] = field(default_factory=list)
    unmatched_titles: list[str] = field(default_factory=list)
    invalid_diff_items: list[str] = field(default_factory=list)
    parse_failed_items: list[str] = field(default_factory=list)


@dataclass(slots=True)
class LyraRecordV3:
    """v0.3.0 成绩记录的标准化结果。"""

    title: str
    cabinet: str
    record_type: str
    difficulty: int
    server: Server
    achievement: float
    dxscore: int
    combo: ComboID
    sync: SyncID
    play_time: datetime
    play_timestamp: int
    record_hash: str


@dataclass(slots=True)
class LyraRecordImportResultV3:
    """v0.3.0 成绩记录导入的解析结果。"""

    records: list[LyraRecordV3] = field(default_factory=list)
    invalid_diff_items: list[str] = field(default_factory=list)
    parse_failed_items: list[str] = field(default_factory=list)


def parse_lyra_maisync_data(raw_bytes: bytes) -> tuple[Any, str]:
    """解析 lyra-maisync 的 json.gz.base64 数据。"""
    try:
        decoded_str = raw_bytes.decode('utf-8')
    except UnicodeDecodeError as e:
        raise ValueError(f'输入数据非有效的 UTF-8 编码：{e}')

    match = _LYRA_HEADER_PATTERN.match(decoded_str)
    if not match:
        raise ValueError('数据头部格式不符合预期规范')

    file_version = match.group('version')
    b64_payload = match.group('payload')

    try:
        compressed_bytes = base64.b64decode(b64_payload)
    except Exception as e:
        raise ValueError(f'Base64 解码失败：{e}')

    try:
        json_bytes = gzip.decompress(compressed_bytes)
    except Exception as e:
        raise ValueError(f'Gzip 解压失败：{e}')

    try:
        return orjson.loads(json_bytes), file_version
    except Exception as e:
        raise ValueError(f'JSON 解析失败：{e}')


def normalize_legacy_lyra_record(record: Mapping[str, Any]) -> LegacyLyraRecord:
    """将旧版导入记录标准化为固定结构。"""
    return LegacyLyraRecord(
        title=str(record.get('title', '')).strip() or 'Unknown',
        record_type=str(record.get('type', 'sd')).lower(),
        difficulty=Difficulties.find_id(str(record.get('diff', ''))) or -1,
        server=Server.parse(record.get('server', 'JP')),
        achievement=float(record.get('achievement', 0)),
        dxscore=int(record.get('dxscore', 0)),
        combo=Combos.find_id(str(record.get('combo', '')).lower()) or 0,
        sync=Syncs.find_id(str(record.get('sync', '')).lower()) or 0,
    )


def _normalize_cabinet(value: Any) -> str:
    cabinet = str(value or 'sd').strip().upper()
    if cabinet == 'DX':
        return 'DX'
    if cabinet == 'SD':
        return 'SD'
    raise ValueError(f'非法 cabinet: {value!r}')


def _normalize_record_type(value: Any) -> str:
    record_type = str(value or 'history').strip().lower()
    if record_type in ('history', 'best'):
        return record_type
    raise ValueError(f'非法记录类型: {value!r}')


def build_record_hash(
    *,
    user_id: int,
    title: str,
    cabinet: str,
    difficulty: int,
    server: Server,
    record_type: str,
    achievement: float,
    dxscore: int,
    combo: int,
    sync: int,
    play_timestamp: int,
) -> str:
    payload = {
        'user_id': user_id,
        'title': title.strip(),
        'cabinet': cabinet.upper(),
        'difficulty': difficulty,
        'server': server,
        'type': record_type,
        'achievement': f'{achievement:.4f}',
        'dxscore': dxscore,
        'combo': combo,
        'sync': sync,
        'play_time': play_timestamp,
    }
    return hashlib.sha256(orjson.dumps(payload, option=orjson.OPT_SORT_KEYS)).hexdigest()


def normalize_lyra_record_v3(record: Mapping[str, Any], *, user_id: int) -> LyraRecordV3:
    title = str(record.get('title', '')).strip()
    if not title:
        raise ValueError('空标题记录')

    difficulty = Difficulties.find_id(str(record.get('diff', ''))) or -1
    if difficulty < 0:
        raise KeyError(f"{title}[{record.get('diff', '?')}]")

    play_timestamp = int(record.get('play_time', 0))
    if play_timestamp <= 0:
        raise ValueError(f'非法游玩时间: {record.get("play_time")!r}')

    cabinet = _normalize_cabinet(record.get('cabinet', 'sd'))
    record_type = _normalize_record_type(record.get('type', 'history'))
    target_server = Server.parse(record.get('server', 'JP'))
    combo = Combos.find_id(record.get('combo', '')) or 0
    sync = Syncs.find_id(record.get('sync', '')) or 0
    achievement = float(f"{float(record.get('achievement', 0)):.4f}")

    return LyraRecordV3(
        title=title,
        cabinet=cabinet,
        record_type=record_type,
        difficulty=difficulty,
        server=target_server,
        achievement=achievement,
        dxscore=int(record.get('dxscore', 0)),
        combo=combo,
        sync=sync,
        play_time=datetime.fromtimestamp(play_timestamp),
        play_timestamp=play_timestamp,
        record_hash=build_record_hash(
            user_id=user_id,
            title=title,
            cabinet=cabinet,
            difficulty=difficulty,
            server=target_server,
            record_type=record_type,
            achievement=achievement,
            dxscore=int(record.get('dxscore', 0)),
            combo=combo,
            sync=sync,
            play_timestamp=play_timestamp,
        ),
    )


def _format_parse_failed_title(record: Mapping[str, Any]) -> str:
    return str(record.get('title', '')).strip() or '(无标题)'


def _format_invalid_diff_title(record: Mapping[str, Any]) -> str:
    title = str(record.get('title', '')).strip() or 'Unknown'
    return f"{title}[{record.get('diff', '?')}]"


def _append_unique(items: list[str], value: str) -> None:
    value = value.strip()
    if value and value not in items:
        items.append(value)


def build_lyra_records_v3(
    file_data: Sequence[Mapping[str, Any]],
    *,
    user_id: int,
) -> LyraRecordImportResultV3:
    result = LyraRecordImportResultV3()

    for record in file_data:
        try:
            result.records.append(normalize_lyra_record_v3(record, user_id=user_id))
        except KeyError:
            if isinstance(record, Mapping):
                _append_unique(result.invalid_diff_items, _format_invalid_diff_title(record))
        except Exception:
            if isinstance(record, Mapping):
                _append_unique(result.parse_failed_items, _format_parse_failed_title(record))

    return result


async def build_legacy_lyra_ach_list(
    file_data: Sequence[Mapping[str, Any]],
    *,
    user_id: int,
    resolve_shortid: Callable[[str, str], Awaitable[tuple[Optional[int], str]]],
) -> LegacyLyraImportResult:
    """将旧版导入 JSON 转换成可入库的成绩对象列表。"""
    result = LegacyLyraImportResult()
    title_type_cache: dict[tuple[str, str], tuple[Optional[int], str]] = {}

    for record in file_data:
        try:
            parsed = normalize_legacy_lyra_record(record)
            cache_key = (parsed.title, parsed.record_type)

            if cache_key not in title_type_cache:
                title_type_cache[cache_key] = await resolve_shortid(
                    parsed.title,
                    parsed.record_type,
                )

            shortid, display_title = title_type_cache[cache_key]
            if shortid is None:
                _append_unique(result.unmatched_titles, display_title)
                continue

            if parsed.difficulty < 0:
                _append_unique(
                    result.invalid_diff_items,
                    f"{parsed.title}[{record.get('diff', '?')}]",
                )
                continue

            result.ach_list.append(
                MaiChartAch(
                    shortid=shortid,
                    difficulty=parsed.difficulty,
                    server=parsed.server,
                    achievement=parsed.achievement,
                    dxscore=parsed.dxscore,
                    combo=parsed.combo,
                    sync=parsed.sync,
                    user_id=user_id,
                )
            )

        except Exception:
            if isinstance(record, Mapping):
                rec_title = str(record.get('title', '')).strip() or '(无标题)'
                _append_unique(result.parse_failed_items, rec_title)
            continue
    
    return result


def _parse_single_sy_record(record: dict, server: Server = Server.CN) -> Optional[MaiChartAch]:
    """将单条原始 record 字典解析为 MaiChartAch 对象，若无效则返回 None"""
    shortid = record.get("song_id")
    level_idx = record.get("level_index")
    if not shortid or level_idx is None:
        return None

    return MaiChartAch(
        shortid=shortid,
        difficulty=level_idx + 2,
        server=server,
        achievement=record.get("achievements", 0.0),
        dxscore=record.get("dxScore", 0),
        combo=Combos.find_id(record.get("fc", "").lower()) or 0,
        sync=Syncs.find_id(record.get("fs", "").lower()) or 0,
        update_time=datetime.now()
    )

def parse_sy_player_record(maidata: MaiData, records: list, server: Server = Server.CN) -> MaiData:
    """解析水鱼玩家记录并更新到 MaiData 对象中"""
    for record in records:
        if record.get("song_id") != maidata.shortid:
            continue
            
        ach = _parse_single_sy_record(record, server=server)
        if ach and (chart := maidata.get_chart(ach.difficulty)):
            chart.set_ach(ach)
    
    return maidata        

def get_sy_records(records: list[dict]) -> list[MaiChartAch]:
    """解析水鱼记录为成就对象"""
    return [
        ach for record in records 
        if (ach := _parse_single_sy_record(record)) is not None
    ]
