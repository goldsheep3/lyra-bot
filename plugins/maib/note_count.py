import re


async def extract_note_tokens(simai_text: str) -> list[str]:
    """
    从 simai 文本中提取最小音符 token 列表
    不做任何音符类型判断，仅做结构展开
    """

    simai_text = simai_text.strip()
    tokens: list[str] = []

    if not simai_text:
        return tokens

    # 删除所有空白字符（包括换行、回车、空格等）
    simai_text = simai_text.replace('\n', '').replace('\r', '').replace(' ', '')
    # 删除结尾 E
    simai_text = simai_text[:-1] if simai_text.endswith('E') else simai_text
    # 删除 () 标记
    simai_text = re.sub(r'\([^)]*\)', '', simai_text)
    # 删除 {} 标记
    simai_text = re.sub(r'\{[^}]*}', '', simai_text)
    # 将同位叠加符号 / 视作并列 ,
    simai_text = simai_text.replace('/', ',')
    # 按 , 拆分
    parts = simai_text.split(',')

    for part in parts:
        token = part.strip()
        if token:
            tokens.append(token)

    return tokens


async def count_notes(tokens: str | list[str]) -> dict[str, list[str]]:
    """
    对音符 token 进行数量统计
    根据提供的判定规则，将音符分类为 TAP, HOLD, SLIDE, TOUCH, BREAK
    """

    if isinstance(tokens, str):
        # 如果输入是字符串，先提取 token 列表
        tokens = await extract_note_tokens(tokens)

    result = {
        "TAP": [],
        "HOLD": [],
        "SLIDE": [],
        "TOUCH": [],
        "BREAK": [],
    }

    for token in tokens:
        if 'h' in token:  # 包含 h - HOLD 或 TOUCH HOLD
            if 'b' in token:
                result["BREAK"].append(token)
            else:
                result["HOLD"].append(token)
        elif any(c in token for c in "BCEAD"):  # 包含判定区字母 - TOUCH
            # 这里能且只能假设 TOUCH 书写时均有 / 隔开，不存在`3B2`的描述……
            if 'b' in token:
                # 目前官谱还没有 BREAK TOUCH，只有烟花（
                result["BREAK"].append(token)
            else:
                result["TOUCH"].append(token)
        elif '[' in token:  # 包含 [ - SLIDE
            prefix = token[:3]  # 切前面3个字符
            suffix = token[3:]  # 切后面部分

            if 'b' in prefix:
                result["BREAK"].append(prefix)
            else:
                result["TAP"].append(prefix)

            for s in suffix.split('*'):
                if 'b' in s:
                    result["BREAK"].append(s)
                else:
                    result["SLIDE"].append(s)
        else:  # TAP 或双押 TAP
            note_units = re.findall(r'[1-8][a-z]*', token)
            
            for unit in note_units:
                if 'b' in unit:
                    result["BREAK"].append(unit)
                else:
                    result["TAP"].append(unit)

    return result


async def note_count_values(counts: dict[str, list[str]]) -> dict[str, int]:
    """从统计结果中提取各类型音符的数量"""
    return {k: len(v) for k, v in counts.items()}


async def count_note_values(simai_text: str) -> dict[str, int]:
    """直接从 simai 文本中统计各类型音符的数量"""
    tokens = await extract_note_tokens(simai_text)
    counts = await count_notes(tokens)
    return await note_count_values(counts)


async def count_to_tuple(simai_text: str) -> tuple[int, int, int, int, int]:
    """将统计结果转换为元组形式，顺序为 (TAP, HOLD, SLIDE, TOUCH, BREAK)"""
    counts = await count_note_values(simai_text)
    return (
        counts.get("TAP", 0),
        counts.get("HOLD", 0),
        counts.get("SLIDE", 0),
        counts.get("TOUCH", 0),
        counts.get("BREAK", 0),
    )
