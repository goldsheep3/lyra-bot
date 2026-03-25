import json
from pathlib import Path
from nonebot import logger
from openai import AsyncOpenAI

DEFAULT = {"contains_alcohol": False, "score": 3, "reason": ""}

# 初始化阶段由 __init__.py 传入配置
API_URL: str = ""
API_MODEL: str = ""
API_KEY: str = ""

_ai_service_instance: "AIService | None" = None

def get_ai_service() -> "AIService":
    global _ai_service_instance
    if _ai_service_instance is None:
        _ai_service_instance = AIService(API_URL, API_MODEL, API_KEY)
    return _ai_service_instance

def get_prompt_from_path(prompt_path: Path, user_input: str = "") -> str:
    """从指定路径加载 prompt 模板"""
    try:
        prompt = prompt_path.read_text(encoding="utf-8")
        if user_input:
            return prompt.replace("{{user_input}}", user_input)
        return prompt
    except Exception as e:
        logger.error(f"加载 prompt 模板失败: {e}")
        return ""

class AIService:

    def __init__(self, api_url, api_model, api_key, prompt_dir: Path = (Path(__file__).parent / "prompt")):
        # 初始化异步客户端
        api_url = api_url or API_URL
        api_model = api_model or API_MODEL
        api_key = api_key or API_KEY
        self.enabled = all([api_url, api_model, api_key])
        self.api_model = api_model
        self.client = AsyncOpenAI(api_key=api_key, base_url=api_url)
        self.prompt_dir = prompt_dir

    async def request_ai(self, prompt: str, **kwargs) -> str | None:
        """通用的 AI 请求逻辑"""
        
        if not self.enabled:
            return None
        try:
            response = await self.client.chat.completions.create(
                model=self.api_model,
                messages=[{"role": "user", "content": prompt}],
                **kwargs
            )
            content = response.choices[0].message.content
            return content
        except Exception as e:
            logger.error(f"AI API 核心调用失败: {e}")
            return None

    async def analyze_food(self, name: str) -> dict:
        """分析餐点，返回包含是否含酒精、评分和理由的字典"""
        
        if not self.enabled:
            return DEFAULT

        prompt = get_prompt_from_path(self.prompt_dir / "food_analysis.md", user_input=name)

        result = await self.request_ai(prompt)
        if not result:
            return DEFAULT

        result = json.loads(result)

        # 提取字段
        alcohol = result.get("contains_alcohol", False)
        common = result.get("is_common", True)
        tasty = result.get("is_tasty", True)
        normal = result.get("is_normal_food", True)
        vulgar = result.get("is_vulgar_or_troll", False)
        reason = result.get("reason", "No reason provided")

        # 标签生成逻辑
        tags = [common, tasty, normal, vulgar]
        result_tag = ''.join('T' if t else 'F' for t in tags)

        score = 2.4
        if common:  # 常见性
            score += 0.4
        if tasty:  # 美味程度
            score += 0.8
        if not normal:  # 是否正常食物
            score -= 0.4
        if vulgar:  # 是否低俗或恶搞
            score -= 0.8
        score = round(score)

        return {
            "contains_alcohol": alcohol,  # 酒精状态
            "score": max(1, min(score, 5)),
            "reason": f'{result_tag}|{reason}'
        }

    async def parse_user_preference(self, user_input: str) -> float | None:
        """解析用户偏好，返回一个偏好分数"""
        if not self.enabled:
            return None

        prompt = get_prompt_from_path(self.prompt_dir / "preference_analysis.md", user_input=user_input)

        result = await self.request_ai(prompt)
        if not result:
            return None

        try:
            score = float(result)
            return score
        except ValueError:
            logger.error(f"AI 返回的用户偏好无法转换为数字: {result}")
            return None