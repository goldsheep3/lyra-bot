from __future__ import annotations

import unittest
from datetime import datetime
from unittest.mock import patch

import nonebot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


class B50RefactoringTest(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        try:
            nonebot.get_driver()
        except ValueError:
            nonebot.init()

        plugin = nonebot.get_plugin("maib") or nonebot.load_plugin("plugins.maib")
        if plugin is None:
            raise RuntimeError("failed to load plugins.maib")

        from plugins.maib import utils
        from plugins.maib.image_gen._components import b50_board
        from plugins.maib.services.models import MaiChart, MaiChartAch, MaiData, MaiUser, Model
        from plugins.maib.services.refactoring import b50
        from plugins.maib.utils.enums import Server, ServerScope

        cls.b50 = b50
        cls.b50_board = b50_board
        cls.utils = utils
        cls.MaiChart = MaiChart
        cls.MaiChartAch = MaiChartAch
        cls.MaiData = MaiData
        cls.MaiUser = MaiUser
        cls.Model = Model
        cls.Server = Server
        cls.ServerScope = ServerScope

    async def asyncSetUp(self) -> None:
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        async with self.engine.begin() as connection:
            await connection.run_sync(self.Model.metadata.create_all)
        self.session_patch = patch.object(self.b50, "get_session", self.sessions)
        self.session_patch.start()

        async with self.sessions() as session:
            session.add(
                self.MaiUser(
                    qq=10001,
                    username="Player",
                    cn_update_at=datetime(2026, 11, 19, 12, 0, 0),
                )
            )
            for shortid, version_cn in ((1, 2024), (2, 2025)):
                session.add(
                    self.MaiData(
                        shortid=shortid,
                        title=f"Song {shortid}",
                        bpm=180,
                        artist="Artist",
                        genre=1,
                        cabinet="DX",
                        version_jp=23,
                        version_cn=version_cn,
                        provider="provider-a",
                        img_path=f"covers/{shortid}.png",
                        charts=[
                            self.MaiChart(
                                shortid=shortid,
                                difficulty=5,
                                lv_jp=13.0,
                                lv_cn=13.0,
                            )
                        ],
                    )
                )
            await session.commit()

            charts = list(
                (await session.execute(select(self.MaiChart))).scalars().all()
            )
            for chart in charts:
                session.add(
                    self.MaiChartAch(
                        chart_id=chart.id,
                        shortid=chart.shortid,
                        difficulty=chart.difficulty,
                        server=self.Server.CN,
                        provider="diving-fish",
                        qq=10001,
                        achievement=1_000_000,
                        dxrating_cache=100 + chart.shortid,
                    )
                )
                session.add(
                    self.MaiChartAch(
                        chart_id=chart.id,
                        shortid=chart.shortid,
                        difficulty=chart.difficulty,
                        server=self.Server.CN,
                        provider="provider-alt",
                        qq=10001,
                        achievement=900_000,
                        dxrating_cache=1,
                    )
                )
            await session.commit()

    async def asyncTearDown(self) -> None:
        self.session_patch.stop()
        await self.engine.dispose()

    async def test_get_b50_data_returns_provider_filtered_utils_entries(self) -> None:
        data = await self.b50.get_b50_data(
            10001,
            self.ServerScope.CN,
            current_version=2025,
        )

        self.assertIsInstance(data, self.utils.B50Data)
        self.assertEqual(data.provider, "diving-fish")
        self.assertEqual(data.current_version, 2025)
        self.assertEqual([song.shortid for song, _ in data.b35], [1])
        self.assertEqual([song.shortid for song, _ in data.b15], [2])
        self.assertEqual(data.dxrating, 203)
        self.assertIn("2026.11.19 12:00:00", data.update_at)
        for song, difficulty in (*data.b35, *data.b15):
            chart = song.get_chart(difficulty)
            assert chart is not None
            self.assertEqual(chart.get_ach(self.Server.CN).achievement, 100.0)

    async def test_get_b50_data_allows_explicit_provider(self) -> None:
        data = await self.b50.get_b50_data(
            10001,
            self.ServerScope.CN,
            provider="provider-alt",
            current_version=2025,
        )

        self.assertEqual(data.provider, "provider-alt")
        self.assertEqual(data.dxrating, 2)

    async def test_get_b50_data_rejects_all_scope(self) -> None:
        with self.assertRaises(ValueError):
            await self.b50.get_b50_data(10001, self.ServerScope.ALL)

    def test_b50_data_single_scope_properties_and_draw_adapter(self) -> None:
        data = self.utils.B50Data(
            dxrating=123,
            current_version=2025,
            scope=self.ServerScope.CN,
            all_update_at={"JP": "JP time", "CN": "CN time"},
        )
        sentinel = object()
        with patch.object(self.b50_board, "draw_b50_board", return_value=sentinel) as draw:
            result = self.b50_board.draw_b50_data(data, username="Player")

        self.assertIs(result, sentinel)
        self.assertEqual(data.provider, "diving-fish")
        self.assertEqual(data.update_at, "CN time")
        self.assertEqual(draw.call_args.kwargs["updated"], "CN time")
        self.assertEqual(draw.call_args.kwargs["server"], self.Server.CN)

    def test_b50_data_all_scope_has_no_single_provider_or_update_time(self) -> None:
        data = self.utils.B50Data(
            dxrating=0,
            current_version=2025,
            scope=self.ServerScope.ALL,
        )
        with self.assertRaises(ValueError):
            _ = data.provider
        with self.assertRaises(ValueError):
            _ = data.update_at
        with self.assertRaises(ValueError):
            self.b50_board.draw_b50_data(data)


if __name__ == "__main__":
    unittest.main()
