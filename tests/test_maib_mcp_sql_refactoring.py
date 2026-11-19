from __future__ import annotations

import unittest
from unittest.mock import patch

import nonebot
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


class McpSqlRefactoringTest(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        try:
            nonebot.get_driver()
        except ValueError:
            nonebot.init()

        plugin = nonebot.get_plugin("maib") or nonebot.load_plugin("plugins.maib")
        if plugin is None:
            raise RuntimeError("failed to load plugins.maib")

        from plugins.maib.services.models import MaiData, Model
        from plugins.maib.services.refactoring import mcp_sql

        cls.MaiData = MaiData
        cls.Model = Model
        cls.mcp_sql = mcp_sql

    async def asyncSetUp(self) -> None:
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        async with self.engine.begin() as connection:
            await connection.run_sync(self.Model.metadata.create_all)
        self.session_patch = patch.object(self.mcp_sql, "get_session", self.sessions)
        self.session_patch.start()

        async with self.sessions() as session:
            session.add(
                self.MaiData(
                    shortid=1,
                    title="Song",
                    bpm=180,
                    artist="Artist",
                    genre=1,
                    cabinet="DX",
                    version_jp=25,
                    version_cn=None,
                    provider="provider-a",
                    img_path="covers/song.png",
                )
            )
            await session.commit()

    async def asyncTearDown(self) -> None:
        self.session_patch.stop()
        await self.engine.dispose()

    async def test_sql_query_owns_session_and_returns_json_rows(self) -> None:
        result = await self.mcp_sql.sql_query(
            "SELECT shortid, title FROM MaiData ORDER BY shortid"
        )

        self.assertTrue(result["default_limit_applied"])
        self.assertEqual(result["columns"], ["shortid", "title"])
        self.assertEqual(result["rows"], [{"shortid": 1, "title": "Song"}])

    async def test_sql_query_rejects_mutation_and_unknown_tables(self) -> None:
        with self.assertRaises(self.mcp_sql.ReadOnlySqlError):
            await self.mcp_sql.sql_query("DELETE FROM MaiData")
        with self.assertRaises(self.mcp_sql.ReadOnlySqlError):
            await self.mcp_sql.sql_query("SELECT * FROM maib_maiusers")

    def test_normalize_sql_caps_explicit_limit(self) -> None:
        normalized, applied_limit = self.mcp_sql.normalize_readonly_sql(
            "SELECT * FROM MaiChart LIMIT 999"
        )

        self.assertEqual(applied_limit, 0)
        self.assertIn("LIMIT 200", normalized)


if __name__ == "__main__":
    unittest.main()
