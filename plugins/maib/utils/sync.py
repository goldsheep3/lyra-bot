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

from ..constants import COMBO_MAP, DIFFICULTY_MAP, SYNC_MAP, server
from .models import MaiChartAch, MaiData


__all__ = [
    # 水鱼数据解析
    "parse_sy_player_record",
    "get_sy_records",
    # lyra-maisync 数据解析
    "parse_lyra_maisync_data",
    "normalize_legacy_lyra_record",
    "build_legacy_lyra_ach_list",
    "LegacyLyraImportResult",
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
    server: server
    achievement: float
    dxscore: int
    combo: int
    sync: int


@dataclass(slots=True)
class LegacyLyraImportResult:
    """旧版 lyra-maimai 导入的解析结果"""

    ach_list: list[MaiChartAch] = field(default_factory=list)
    unmatched_titles: list[str] = field(default_factory=list)
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
        difficulty=DIFFICULTY_MAP.key(str(record.get('diff', '')).lower()) or -1,
        server=cast(server, str(record.get('server', 'JP'))),
        achievement=float(record.get('achievement', 0)),
        dxscore=int(record.get('dxscore', 0)),
        combo=COMBO_MAP.key(str(record.get('combo', '')).lower()) or 0,
        sync=SYNC_MAP.key(str(record.get('sync', '')).lower()) or 0,
    )


def _append_unique(items: list[str], value: str) -> None:
    value = value.strip()
    if value and value not in items:
        items.append(value)


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


def _parse_single_sy_record(record: dict) -> Optional[MaiChartAch]:
    """将单条原始 record 字典解析为 MaiChartAch 对象，若无效则返回 None"""
    shortid = record.get("song_id")
    level_idx = record.get("level_index")
    if not shortid or level_idx is None:
        return None

    return MaiChartAch(
        shortid=shortid,
        difficulty=level_idx + 2,
        server="CN",
        achievement=record.get("achievements", 0.0),
        dxscore=record.get("dxScore", 0),
        combo=COMBO_MAP.key(record.get("fc", "").lower()) or 0,
        sync=SYNC_MAP.key(record.get("fs", "").lower()) or 0,
        update_time=datetime.now()
    )

def parse_sy_player_record(maidata: MaiData, records: list) -> MaiData:
    """解析水鱼玩家记录并更新到 MaiData 对象中"""
    for record in records:
        if record.get("song_id") != maidata.shortid:
            continue
            
        ach = _parse_single_sy_record(record)
        if ach and (chart := maidata.get_chart(ach.difficulty)):
            chart.set_ach(ach)
    
    return maidata        

def get_sy_records(records: list[dict]) -> list[MaiChartAch]:
    """解析水鱼记录为成就对象"""
    return [
        ach for record in records 
        if (ach := _parse_single_sy_record(record)) is not None
    ]
