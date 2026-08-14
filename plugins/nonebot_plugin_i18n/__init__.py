import yaml
import string
import random
import contextvars
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping, Sequence, cast

from nonebot import require, on_regex, logger
from nonebot.params import RegexGroup
from nonebot.adapters import Event, Bot
from nonebot.matcher import Matcher

require("nonebot_plugin_datastore")
from nonebot_plugin_datastore import get_plugin_data, create_session
from sqlalchemy import String, select
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.ext.asyncio import AsyncSession

Model = get_plugin_data().Model
get_session = create_session

# 核心：上下文容器
current_i18n_data: contextvars.ContextVar[dict[str, Any]] = contextvars.ContextVar("current_i18n_data")
INTERNAL_ASSETS = Path(__file__).parent / "assets" / "i18n"

# --- 安全格式化器 ---
class SafeFormatter(string.Formatter):
    def get_value(self, key: int | str, args: Sequence[Any], kwargs: Mapping[str, Any]) -> Any:
        if isinstance(key, str):
            try:
                return kwargs[key]
            except KeyError:
                logger.warning(f"[i18n] 语言包缺少参数: '{key}'")
                return f"{{{key}}}"
        return super().get_value(key, args, kwargs)

safe_formatter = SafeFormatter()

# --- 数据库模型 ---
class User(Model):
    __tablename__ = "i18n_user"
    
    platform: Mapped[str] = mapped_column(String(50), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    language: Mapped[str] = mapped_column(String(20), default="en_US", nullable=False)


# --- 树状 Dict 展平工具 ---
def _flatten_dict(d: dict, parent_key: str = "", sep: str = ".") -> dict:
    items = {}
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.update(_flatten_dict(v, new_key, sep=sep))
        else:
            items[new_key] = v
    return items


# --- LRU 缓存加载器（返回副本，防止内存污染） ---
@lru_cache(maxsize=64)
def _load_raw_i18n(asset_dir: Path, lang: str) -> dict[str, Any]:
    yaml_path = asset_dir / f"{lang}.yaml"
    
    # 降级策略: 目标 > 中文 > 英文
    if not yaml_path.exists():
        yaml_path = asset_dir / "zh_CN.yaml"
    if not yaml_path.exists():
        yaml_path = asset_dir / "en_US.yaml"
        
    if yaml_path.exists():
        try:
            with open(yaml_path, "r", encoding="utf-8") as f:
                raw_data = cast(dict, yaml.safe_load(f) or {})
                return _flatten_dict(raw_data)
        except Exception:
            logger.error("Load i18n file failed: %s", yaml_path, exc_info=True)
    return {}

def load_flattened_i18n(asset_dir: Path, lang: str) -> dict[str, Any]:
    """导出层：返回缓存的浅拷贝，避免业务端修改引发全局缓存污染"""
    return _load_raw_i18n(asset_dir, lang).copy()


# --- 依赖注入项工厂 ---
def use_i18n(asset_dir: Path) -> Any:
    """依赖注入工厂：安全地单向向当前协程上下文注入语言包"""
    from nonebot.params import Depends

    async def i18n_dependency(bot: Bot, event: Event):
        platform = bot.adapter.get_name()
        try:
            user_id = str(event.get_user_id())
        except Exception:
            user_id = "default"
        
        async with get_session() as session:
            stmt = select(User.language).where(
                User.platform == platform, 
                User.user_id == user_id
            )
            result = await session.execute(stmt)
            lang = result.scalar_one_or_none() or "en_US"
            
        i18n_data = load_flattened_i18n(asset_dir, lang)
        
        # 核心改动：直接 set，不保存 token，不进行 reset。
        # Python 的协程隔离机制会保证其在当前事件处理流中有效，流转结束后随上下文自动销毁。
        current_i18n_data.set(i18n_data)
        return i18n_data

    return Depends(i18n_dependency)


# --- 纯同步极简回复函数 ---
def reply(dot_key: str, **kwargs) -> str:
    """纯同步回复函数：安全格式化，免传参"""
    try:
        i18n_data = current_i18n_data.get()
    except LookupError:
        i18n_data = {}
        
    val = i18n_data.get(dot_key)
    if val is None:
        return dot_key

    if isinstance(val, list):
        text = random.choice(val)
    else:
        text = str(val)
        
    return safe_formatter.format(text, **kwargs)


# --- 全局语言切换指令 ---
set_language = on_regex(r"^(切换语言|set_lang|lang)\s+([a-zA-Z_0-9\-]+)$", priority=4, block=False)

_i18n = use_i18n(INTERNAL_ASSETS)

@set_language.handle()
async def set_language_handled(
    bot: Bot, 
    event: Event, 
    matcher: Matcher, 
    _ = _i18n,
    groups: tuple = RegexGroup()
):
    _, lang_code = groups
    lang_code = lang_code.strip()
    
    platform = bot.adapter.get_name()
    user_id = str(event.get_user_id())
    
    async with get_session() as session:
        # 1. 查库并更新
        stmt = select(User).where(User.platform == platform, User.user_id == user_id)
        res = await session.execute(stmt)
        user_lang_obj = res.scalar_one_or_none()
        
        if not user_lang_obj:
            user_lang_obj = User(platform=platform, user_id=user_id, language=lang_code)
            session.add(user_lang_obj)
        else:
            user_lang_obj.language = lang_code
            
        await session.commit()

    # 2. 动态读取新语言的名称
    target_lang_data = load_flattened_i18n(INTERNAL_ASSETS, lang_code)
    current_i18n_data.set(target_lang_data) # 👈 手动刷新当前上下文为新语言包

    friendly_lang_name = target_lang_data.get("language_name", lang_code)

    # 3. 此时 reply 就能完美拿到刚刷新的 target_lang_data 里的 "set_language.success" 了
    await matcher.finish(reply("set_language.success", language=friendly_lang_name))