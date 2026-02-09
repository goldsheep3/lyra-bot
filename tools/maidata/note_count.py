import re
from typing import List, Dict


def extract_note_tokens(simai_text: str) -> List[str]:
    """
    从 simai 文本中提取最小音符 token 列表
    不做任何音符类型判断，仅做结构展开
    """

    simai_text = simai_text.strip()
    tokens: List[str] = []

    if not simai_text:
        return tokens

    if any(c in simai_text for c in ' \n\r'):
        # 大概是未经处理的多行，需要先处理
        # 如果为 tools/maidata 中调用，大概是不会进入该处理段
        metadata = re.findall(r'&inote_[0-9]=', simai_text)
        if metadata and len(metadata) > 2:
            raise ValueError("simai 文本包含过多谱面数据")
        simai_text = re.sub(r'&[a-z]=.*?\n', '', simai_text)
        simai_text = simai_text.replace('\n', '').replace('\r', '').replace(' ', '')

    # 删除结尾 E
    simai_text = simai_text[:-1] if simai_text.endswith('E') else simai_text
    # 删除 () 标记
    simai_text = re.sub(r'\([^)]*\)', '', simai_text)
    # 删除 {} 标记
    simai_text = re.sub(r'\{[^}]*\}', '', simai_text)
    # 将同位叠加符号 / 视作并列 ,
    simai_text = simai_text.replace('/', ',')
    # 按 , 拆分
    parts = simai_text.split(',')

    for part in parts:
        token = part.strip()
        if token:
            tokens.append(token)

    return tokens


def count_notes(tokens: List[str]) -> Dict[str, List[str]]:
    """
    对音符 token 进行数量统计
    根据提供的判定规则，将音符分类为 TAP, HOLD, SLIDE, TOUCH, BREAK
    """

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


def analyze_simai(simai_text: str) -> Dict[str, List[str]]:
    """
    主入口函数：
    simai 文本 -> 音符数量统计结果
    """
    tokens = extract_note_tokens(simai_text)
    return count_notes(tokens)


if __name__ == "__main__":
    # 简单测试
    test_simai = """
(70){1},
{4}1>6[4:1],7,8<3[4:1],2,
{4}1>6[4:1],6,7h[4:1],5,
{4}8<3[4:1],2,1>6[4:1],7,
{12}8<3[4:1],,,3,,,2,2,8,8<5[12:1],,5,
{12}4>1[12:1],,6,6<1[12:1],,2,3-7[12:1],4,4,5-8[12:1],,1,
{12}2-8[12:1],3,4,5-3[12:1],6,7,8-6[12:1],2,2,1w5[12:1],,,
{1},
{24}3<6[12:1],,2,2,,7,7,,8,,8,,3>1[12:1],,,4,4,,5,,,,5,,
{24}4/6>3[12:1],,7,7,,2,2-6[12:1],,1,,1,,2<7[12:1]*>5[12:1],,,,8,,,,,,,,
{24}6>3[12:1],,7,7,,2,2,,1,,1,,6<8[12:1],,,,4,,5,,5,,4,,
{24}3<6[12:1],,2,,2,,7-3[12:1],,8,,8,,3,,,2,2h[12:1],,C1f/B4/B5,,,,,,
{24}2/8,2/8,,3/7,,4/6,4/6h[6:1],,5,,8,,1/7,1/7,,2/6,,3/5,3h[6:1]/5,,4,,1,,
{24}2/8,2/8,,3/7,,4/6,6h[12:1]/4-8[8:1],,5,,3,,1>5[8:1],,1,,1,,6,,,,,,
{24}7>2[12:1],,5,5,,3,3,,4,,5,,7<5[12:1],,8,8,,3,3-7[8:1],,4,,4,,
{12},5,5,6-2[12:1],7,7,6>3[12:1]*<1[12:1],,5,,,,
{24}2<7[12:1],,,4,4,,6,,,,4,,2>4[12:1],,,6,6,,7,,8,,8,,
{24}7-2[12:1],,,5,5,,3>4[4:1],,4,,5,,5,,,,,,,,,,,,
{24}4/6,4/6,,3/7,,,2h[6:1]/8,,4,,4,,3/5,3/5,,2/6,,,1/7h[6:1],,5,,3,,
{24}1b/8b,,,2b/3b,,,4b/5b,,,6b/7b,,,1/8,1/8,,B2/B3/B6/B7,,4x/5x,5x/4x>1[12:1],4x/5x,,,6,,
{24}4b<7[12:1],,5,5,5,,4qq1[4:1],,1,,3,,5-8[12:1],,8,,6,,5b>2[12:1],,3,,3,,
{12}5<8[12:1],8,6,5/1pp4[4:1],2,2,8,7,6,5<8[12:1],6,3,
{24}5>2[12:1],,4,4,4,,5pp8[4:1],,8,,6,,4-1[12:1],,1,,3,,4b<7[12:1],,6,,6,,
{12}4>1[12:1],3,3,4/5pp4[4:1],6,6,1pp8[4:1],,,,,,
{12}6-4[12:1],5,5,2-8[12:1],3,3,5p4[4:1],4,4,6,,,
(70){12},3/6,4/5,4>1[12:1]/5<8[12:1],3/6,3/6,4-8[12:1]/5-1[12:1],,,4>5[4:1]/5<4[4:1],,,
{12}4x/5x,,,,,,1-4[12:1],1-6[12:1],3/7,,,5-2[12:1],
{12}5-8[12:1],5-1[12:1],,,,8-5[12:1],8-3[12:1],2/6,,,4>8[8:1]*<8[8:1],2/6,
{12}2/6,,,,8-5[12:1],8-3[12:1],2/6,,,4-1[12:1],4-7[12:1],4-8[12:1],
{12},,,1-6[12:1],1-4[12:1],3/7,,,5-2[12:1],5-8[12:1],5-1[12:1],,
{12},,8>3[12:1],8<5[12:1],8-4[12:1],,,,,,C1h[4:1],,
{1},
{24},,C1/B7/E7/B8/E8,,,B1/E1/B2/E2/E3,,,B3/B4/E4/B5/E5/B6/E6,,,C1f,,,2x/7x,2x/7x,,3/6,,1/8,1/8<5[12:1],,4/5,,
{24}2,,8b>3[12:1],,1,1,1,,8qq5[4:1],,7,,7,,4-1[12:1],,1,,3,,4b<7[12:1],,6,,
{24}6,,4>1[12:1],,2,2,2,,4/5pp8[4:1],,7,,7,,4,,3,,2,,1>4[12:1],,2/7,,
{24}2/7,,1<6[12:1],,8,8,8,,1pp4[4:1],,3,,3,,5-8[12:1],,8,,6,,5b>2[12:1],,3,,
{24}3,,5<8[12:1],,7,7,7,,5/1pp8[4:1],,2,,2,,5pp4[4:1],,,,,,,,,,
{24},,2-8[12:1],,1,1,1,,6-4[12:1],,7,7,7,,1p8[4:1],,8,8,8,,2,,,,
{12},,2/7,1/8,1>4[12:1]/8<5[12:1],2/7,2/7,1-5[12:1]/8-4[12:1],,,1>8[4:1]/8<1[4:1],,
{24},,1x/8x,,,,,,,,,,,,3qq4[4:1],,4,4,,6,6,,5,,
{24}6,,7pp5[4:1],,5,5,,3,3,,4,,3,,3pp2[4:1],,4,4,,6,6<1[12:1],,7,,
{24}7,,6-3[12:1],,5,,5,,1,,1,,1,,6pp5[4:1],,5,5,,3,3,,4,,
{24}3,,2qq4[4:1],,4,4,,6,6,,5,,6,,6qq7[4:1],,5,5,,3,3>8[12:1],,2,,
{12}2,3V51[6:1],6,6,8,7,6,3V51[6:1],1,1,8,7,
{12}6,5w1[1:1],4/6,2/8,5b,,,,,,,,
{1},
{1},
{1},
E
"""
    tokens = extract_note_tokens(test_simai)
    counts = count_notes(tokens)
    print({k: len(v) for k, v in counts.items()})
    # print(counts)
