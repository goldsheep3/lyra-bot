from .tool import request_json


BASE_URL = "https://maimai.lxns.net/api/v0/maimai"


class Lxns:
    @staticmethod
    async def lx_alias_list() -> dict | None:
        """`~/alias/list`"""
        return await request_json(
            BASE_URL + "/alias/list", 
            project_name="lxns*/alias/list"
        )
