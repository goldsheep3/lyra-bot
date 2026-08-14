"""utils/simai.py 谱面内容解析器"""
# 有 bug，但是修这个的优先级太低太低（
import re


__all__ = [
    "SimaiNoteCount",
]


class SimaiNoteCount:
    """Simai 音符计数器"""

    def __init__(self, simai_text: str = ""):
        self.raw_text = simai_text
        self.tokens: list[str] = []
        self.counts: dict[str, list[str]] = {"tap": [], "hold": [], "slide": [], "touch": [], "break": []}

    def _extract_tokens(self) -> list[str]:
        text = self.raw_text.strip()
        if not text:
            return []
        text = re.sub(r'[\n\r\s]', '', text)
        text = text[:-1] if text.endswith('E') else text
        text = re.sub(r'\([^)]*\)', '', text)
        text = re.sub(r'\{[^}]*}', '', text)
        text = text.replace('/', ',')
        self.tokens = [t for t in text.split(',') if t.strip()]
        return self.tokens

    def process(self, simai_text: str | None = None) -> 'SimaiNoteCount':
        if simai_text is not None:
            self.raw_text = simai_text
        self.counts = {k: [] for k in self.counts}
        tokens = self._extract_tokens()
        for token in tokens:
            if 'h' in token:
                (self.counts["break"] if 'b' in token else self.counts["hold"]).append(token)
            elif any(c in token for c in "BCEAD"):
                (self.counts["break"] if 'b' in token else self.counts["touch"]).append(token)
            elif '[' in token:
                prefix, suffix = token[:3], token[3:]
                (self.counts["break"] if 'b' in prefix else self.counts["tap"]).append(prefix)
                for s in suffix.split('*'):
                    (self.counts["break"] if 'b' in s else self.counts["slide"]).append(s)
            else:
                for unit in re.findall(r'[1-8][a-z]*', token):
                    (self.counts["break"] if 'b' in unit else self.counts["tap"]).append(unit)
        return self

    @property
    def statistics(self) -> dict[str, int]:
        return {k: len(v) for k, v in self.counts.items()}

    def to_tuple(self) -> tuple[int, int, int, int, int]:
        s = self.statistics
        return (s.get("tap", 0), s.get("hold", 0), s.get("slide", 0), s.get("touch", 0), s.get("break", 0))
