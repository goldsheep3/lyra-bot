from .tool import request_json


BASE_URL = "https://raw.githubusercontent.com"
PROXY_URL = "https://gh-proxy.org/https://raw.githubusercontent.com"

INDEX_ENDPOINT = "/Neskol/Maichart-Converts/refs/heads/master/index.json"


class MaichartConverts:
    @staticmethod
    async def maichart_index() -> dict[str, str] | None:
        """`index.json`"""
        # 尝试直连
        res = await request_json(BASE_URL + INDEX_ENDPOINT, project_name="maichart*/index.json")
        if not res:
            # 尝试代理
            res = await request_json(PROXY_URL + INDEX_ENDPOINT, project_name="maichart_proxy*/index.json")
        return res or {}
