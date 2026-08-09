"""constants.py 常量预定义文件"""
from __future__ import annotations

import re
from collections.abc import Mapping as ABCMapping
from datetime import datetime, timezone, timedelta, timezone
from dataclasses import dataclass, field
from typing import Any, Mapping, Callable, Generic, Optional, TypeVar, Literal, Iterator, Union
from pathlib import Path

import yaml
from nonebot import logger

try:
    from thefuzz import process
except ImportError:
    process = None


__all__ = [
    # 服务器类型标识
    "server",
    # 默认时间
    "DEFAULT_DATETIME",
    # 常量映射表
    "RATE_ALIAS",
    "COMBO_MAP",
    "SYNC_MAP",
    "DIFFICULTY_MAP",
    "VERSION_MAP",
    "GENRE_MAP",
    # 基础路径
    "ASSETS_PATH",
]


# 服务器类型标识
server = Literal["JP", "CN"]
# 默认时间 (1970-11-01 00:00:00)
DEFAULT_DATETIME = datetime(1970, 11, 1, 0, 0, 0, tzinfo=timezone.utc)

# --- 基础路径 ---
PLUGIN_BASE_PATH = Path(__file__).parent
ASSETS_PATH = PLUGIN_BASE_PATH / "assets"

# --- 类型变量 ---
K = TypeVar("K")

# --- 内部函数 ---
def _default_normalize(value: Any) -> str:
    """默认 归一化函数"""
    return re.sub(r"\s+", "", str(value).strip().lower())

def _version_normalize(version_text: str) -> str:
    """版本文本 归一化函数"""
    text = _default_normalize(version_text)
    has_dx = "dx" in text or "でらっくす" in text
    text = text.replace("でらっくす", "dx")
    text = text.replace("+", "plus")
    if text == "maimaiplus":
        return "maiplus"
    if text.startswith("maimaidx"):
        text = text[8:].strip()
    elif text.startswith("maimai"):
        text = text[6:].strip()
    elif text.startswith("dx"):
        text = text[2:].strip()
    if not text:
        text = "dx" if has_dx else "maimai"
    return text

def _load_yaml(filename: str) -> dict[Any, Any]:
    """内部辅助函数：安全读取并解析 YAML 文件"""
    path = ASSETS_PATH / filename
    if not path.is_file():
        logger.warning(f"缺少配置文件: {path}")
        return {}
    try:
        content = path.read_text(encoding="utf-8")
        return yaml.safe_load(content) or {}
    except yaml.YAMLError as e:
        logger.error(f"解析 YAML 文件失败 ({path}): {e}")
        return {}


@dataclass(slots=True)
class AliasMap(Generic[K]):
    """通用映射表"""
    raw: dict[K, tuple[str, ...]]
    normalize: Callable[[Any], str] = _default_normalize

    _key_to_aliases: dict[K, tuple[str, ...]] = field(init=False, repr=False)
    _alias_to_key: dict[str, K] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._key_to_aliases = {}
        self._alias_to_key = {}

        for key, aliases in self.raw.items():
            aliases = tuple(aliases)
            self._key_to_aliases[key] = aliases

            # 允许 canonical key 自身参与查找
            self._alias_to_key[self.normalize(key)] = key

            for alias in aliases:
                norm = self.normalize(alias)
                if norm in self._alias_to_key and self._alias_to_key[norm] != key:
                    raise ValueError(f"别名冲突: {alias!r} -> {self._alias_to_key[norm]!r} / {key!r}")
                self._alias_to_key[norm] = key

    def key(self, value: Any) -> Optional[K]:
        """
        :param value: `alias` 或 `key`
        :return: `key` (or `None`)
        """
        if value is None:
            return None

        try:
            if value in self._key_to_aliases:
                return value
        except TypeError:
            pass
        
        return self._alias_to_key.get(self.normalize(value))

    def aliases(self, value: Any) -> Optional[tuple[str, ...]]:
        """
        :param value: `alias` 或 `key`
        :return: `aliases` (or `None`)
        """
        key = self.key(value)
        if key is None:
            return None
        return self._key_to_aliases[key]

    def label(self, value: Any, *, index: int = 0, upper: bool = False) -> Optional[str]:
        """
        :param value: `alias` 或 `key`
        :param index: 返回第几个别名
        :param upper: 是否返回大写标签
        :return: `label` (or `None`)
        """
        aliases = self.aliases(value)
        if not aliases:
            return None
        try:
            label = aliases[index]
        except IndexError:
            label = aliases[0]
        return label.upper() if upper else label

    def __contains__(self, value: Any) -> bool:
        return self.key(value) is not None

    def has(self, value: Any) -> bool:
        return self.__contains__(value)

    def keys(self):
        return self._key_to_aliases.keys()

    def items(self):
        return self._key_to_aliases.items()


@dataclass(slots=True, frozen=True)
class VersionMap(ABCMapping[int, str]):
    """版本数据映射表"""
    raw: Mapping[int, Any]
    _versions: dict[int, str] = field(init=False, repr=False)
    _name_index: dict[str, int] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        """解析 YAML 时，将 name 抽取作为字典的值，并构建反向查找索引"""
        versions: dict[int, str] = {}
        index: dict[str, int] = {}
        
        for k, v in self.raw.items():
            if isinstance(v, dict):
                # 提取名称并防止 None
                name = v.get("name")
                version_name = name if name is not None else ""
                
                # 将 name, code, plate_name 都加入反向索引中，方便任意别名查 ID
                if version_name:
                    index[_version_normalize(version_name)] = k
                if code := v.get("code"):
                    index[_version_normalize(code)] = k
                if plate := v.get("plate_name"):
                    index[_version_normalize(plate)] = k
            else:
                version_name = str(v)
                index[_version_normalize(version_name)] = k
                
            versions[k] = version_name

        # 对 frozen dataclass 使用 object.__setattr__ 进行赋值
        object.__setattr__(self, "_versions", versions)
        object.__setattr__(self, "_name_index", index)

    def get_id_by_text(self, version_text: str, cn: bool = False) -> Optional[int]:
        """根据版本名、代号(code)或牌子名(plate_name)反查 version_id"""
        result = self._name_index.get(_version_normalize(version_text))
        
        if cn and result is not None:
            "如果指定了 `cn=True`，则将结果映射到国服版本号 (>=2000)"
            # maimai ~ FiNALE
            if result < 13:
                pass
            # DX2020(DX) ~ DX2025(PRiSM)
            elif 13 <= result < 24:
                result = (result - 13) // 2 + 2020
            # DX2026(PRiSM PLUS)
            elif result >= 24:
                # PRiSM PLUS 在这个算法也会被解析为 PRiSM 的 dx2025
                # 由于 SBGA 的更新节奏，暂时直接将 PRiSM PLUS 解析为 dx2026 视作单次偏移
                result = (result - 13) // 2 + 2020 + 1
        
        return result

    def name(self, version_id: int) -> Optional[str]:
        """获取版本名 (如: 舞萌DX 2024)"""
        return self.get(version_id)

    def code(self, version_id: int) -> Optional[str]:
        """获取版本代号 (如: dx2024)"""
        raw_data = self.raw.get(version_id)
        if isinstance(raw_data, dict):
            return raw_data.get("code")
        return None

    def plate_name(self, version_id: int) -> Optional[str]:
        """获取牌子名 (如: 双宴，注意可能有 None)"""
        raw_data = self.raw.get(version_id)
        if isinstance(raw_data, dict):
            return raw_data.get("plate_name")
        return None

    def version_id_list(self) -> list[int]:
        """获取所有版本 ID 列表"""
        return list(self._versions.keys())

    def get_latest_version_id(self, server: server) -> int:
        """获取指定服务器的最新版本 ID"""
        if server == "JP":
            jp_versions = [v for v in self._versions.keys() if v < 2000]
            return max(jp_versions) if jp_versions else 13  # 默认返回 13 (maimai DX)
        elif server == "CN":
            cn_versions = [v for v in self._versions.keys() if v >= 2000]
            return max(cn_versions) if cn_versions else 2020  # 默认返回 2020 (舞萌DX 2020)
        raise KeyError(f"Unknown server: {server}")

    def get_cut_version(self, server_or_version: Union[server, int]) -> int:
        """获取 B50 分段所需的 cut_version"""
        if isinstance(server_or_version, int):
            version = server_or_version
        else:
            version = VERSION_MAP.get_latest_version_id(server_or_version)
            
        # 从 PRiSM PLUS(24) 开始，best15 扩展一个版本
        # 但与国服(2000+) 无关
        if 2000 > version >= 24:
            version -= 1
        return version

    # ---------- 字典底层魔法方法 (代理给 _versions，兼容旧版) ----------
    def __getitem__(self, version_id: int) -> str:
        return self._versions[version_id]

    def __iter__(self) -> Iterator[int]:
        return iter(self._versions)

    def __len__(self) -> int:
        return len(self._versions)

@dataclass(slots=True, frozen=True)
class GenreMap(ABCMapping[int, dict[str, str]]):
    """曲目分类数据映射表"""
    raw: Mapping[int, dict[str, str]]
    # 反向映射索引
    _name_index: dict[str, int] = field(init=False, repr=False)

    def __post_init__(self):
        """初始化反向索引构建"""
        index: dict[str, int] = {}
        for genre_id, attrs in self.raw.items():
            for key, val in attrs.items():
                if key != "color":
                    index[_default_normalize(val)] = genre_id
        # 保存构建的反向索引，对 frozen dataclass 使用 object.__setattr__ 绕过限制
        object.__setattr__(self, "_name_index", index)

    def get_id_by_name(self, name: str, fuzzy: bool = False, threshold: int = 85) -> Optional[int]:
        """
        反向查找 genre_id
        
        :param name: 输入的分类名称
        :param fuzzy: 是否在精确匹配失败时启用模糊匹配
        :param threshold: 模糊匹配的最低置信度 (0-100)
        """
        normalized = _default_normalize(name)
        
        # 精确匹配尝试
        exact_id = self._name_index.get(normalized)
        if exact_id is not None:
            return exact_id
            
        # 安装了 thefuzz 库时，模糊匹配尝试
        if fuzzy and process is not None:
            match_result = process.extractOne(normalized, self._name_index.keys())
            
            if match_result:
                best_match, score = match_result[0], match_result[1]
                if score >= threshold:
                    return self._name_index[best_match]
                    
        return None

    def name(self, genre_id: int, lang: str = "cn") -> Optional[str]:
        """获取分类名称，支持多语言切换。"""
        genre = self.get(genre_id)
        return genre.get(lang) if genre else None

    def color(self, genre_id: int) -> Optional[str]:
        """获取分类对应的主题色 (如: #ff972a)"""
        genre = self.get(genre_id)
        return genre.get("color") if genre else None

    def __getitem__(self, genre_id: int) -> dict[str, str]:
        return self.raw[genre_id]

    def __iter__(self) -> Iterator[int]:
        return iter(self.raw)

    def __len__(self) -> int:
        return len(self.raw)


# TODO float 100.7891 -> int 1,007,891
RATE_ALIAS = AliasMap[float]({
    101.0000: ("ap+", "理论"),
    100.7500: ("ap",),
    100.5000: ("鸟加", "鸟家", "sss+", "3s+"),
    100.0000: ("鸟", "鸟s", "sss", "3s"),
    99.5000:  ("ss+", "2s+"),
    99.0000:  ("ss", "2s"),
    98.0000:  ("s+", "1s+"),
    97.0000:  ("s", "1s"),
    94.0000:  ("鸟a", "aaa", "3a"),
    90.0000:  ("aa", "2a"),
    80.0000:  ("a", "1a"),
    75.0000:  ("鸟b", "bbb", "3b"),
    70.0000:  ("bb", "2b"),
    60.0000:  ("b", "1b"),
    50.0000:  ("c", "1c"),
    0.0000:   ("d", "1d"),
})

COMBO_MAP = AliasMap[int]({
    1: ('fc', 'fullcombo'),
    2: ('fc+', 'fcp', 'fullcombo+', 'fullcomboplus'),
    3: ('ap', 'allperfect'),
    4: ('ap+', 'app', 'allperfect+', 'allperfectplus'),
})

SYNC_MAP = AliasMap[int]({
    1: ('sync', 'syncplay'),
    2: ('fs', 'fullsync'),
    3: ('fs+', 'fsp', 'fullsync+', 'fullsyncplus'),
    4: ('fdx', 'fsd', 'fullsyncdx', 'fullsyncdeluxe'),
    5: ('fdx+', 'fdxp', 'fsd+', 'fsdp',
        'fullsyncdx+', 'fullsyncdxplus', 'fullsyncdeluxe+', 'fullsyncdeluxeplus'),
})

DIFFICULTY_MAP = AliasMap[int]({
    1: ("蓝", 'EASY', 'easy'),
    2: ("绿", 'BASIC', 'basic'),
    3: ("黄", 'ADVANCED', 'advanced'),
    4: ("红", 'EXPERT', 'expert'),
    5: ("紫", 'MASTER', 'master'),
    6: ("白", "Re:MASTER", "remaster", "re:master"),
    7: ('宴', 'U·TA·GE', '宴会场', '宴·会·场', 'utage', 'u·ta·ge'),
})

VERSION_MAP = VersionMap(_load_yaml("versions.yaml"))

GENRE_MAP = GenreMap(_load_yaml("genres.yaml"))
