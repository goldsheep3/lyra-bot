from __future__ import annotations

import asyncio
import unittest
from pathlib import Path

import nonebot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


class MaibBaselineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        nonebot.init()
        plugin = nonebot.load_plugin("plugins.maib")
        if plugin is None:
            raise RuntimeError("failed to load plugins.maib")

        from plugins.maib import services, utils
        from plugins.maib.services.models import MaiAlias, MaiChart, MaiData, Model

        cls.services = services
        cls.utils = utils
        cls.MaiAlias = MaiAlias
        cls.MaiChart = MaiChart
        cls.MaiData = MaiData
        cls.Model = Model

    def _maidata(self, *, title: str = "Song", img_path: str = "covers/song.png"):
        chart = self.utils.MaiChart(
            shortid=1,
            difficulty=5,
            lv_jp=13.7,
            lv_cn=13.6,
            lv_fit=13.65,
            des="Designer",
        )
        maidata = self.utils.MaiData(
            shortid=1,
            title=title,
            bpm=180,
            artist="Artist",
            genre=1,
            cabinet="DX",
            version=25,
            version_cn=2025,
            converter="provider-a",
            img_path=Path(img_path),
        )
        maidata.set_chart(chart)
        return maidata

    def test_plugin_exports_current_models(self) -> None:
        self.assertTrue(hasattr(self.services, "MaiSync"))
        self.assertTrue(hasattr(self.services, "MaiLxns"))
        self.assertFalse(hasattr(self.services, "MaiSyncPairingCode"))
        self.assertFalse(hasattr(self.services, "MaiSyncToken"))

    def test_maidata_preserves_img_path(self) -> None:
        model = self.MaiData.from_utils(self._maidata(img_path="covers/custom.png"))
        result = model.to_utils()
        self.assertEqual(result.img_path.name, "custom.png")
        self.assertEqual(result.img_path.parent.name, "covers")

    def test_alias_and_song_update_use_current_columns(self) -> None:
        asyncio.run(self._test_alias_and_song_update_use_current_columns())

    async def _test_alias_and_song_update_use_current_columns(self) -> None:
        from plugins.maib.services.alias import add_ma, add_ma_batch
        from plugins.maib.services.fetch import sync_mdt_list

        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with engine.begin() as connection:
                await connection.run_sync(self.Model.metadata.create_all)

            async with session_factory() as session:
                initial = self.MaiData.from_utils(self._maidata())
                await sync_mdt_list([initial], session=session)
                await session.flush()

                self.assertTrue(
                    await add_ma(1, "alias-one", 10001, session=session)
                )
                await add_ma_batch(
                    [(1, "alias-one"), (1, "alias-two")],
                    10001,
                    session=session,
                )

                updated_data = self._maidata(
                    title="Updated Song",
                    img_path="covers/updated.png",
                )
                updated_data.version = 26
                updated_data.converter = "provider-b"
                updated_chart = updated_data.get_chart(5)
                assert updated_chart is not None
                updated_chart.des = "Updated Designer"

                await sync_mdt_list(
                    [self.MaiData.from_utils(updated_data)],
                    session=session,
                )
                await session.flush()

                song = (
                    await session.execute(
                        select(self.MaiData).where(self.MaiData.shortid == 1)
                    )
                ).scalar_one()
                chart = (
                    await session.execute(
                        select(self.MaiChart).where(
                            self.MaiChart.shortid == 1,
                            self.MaiChart.difficulty == 5,
                        )
                    )
                ).scalar_one()
                aliases = set(
                    (
                        await session.execute(
                            select(self.MaiAlias.name).where(
                                self.MaiAlias.shortid == 1
                            )
                        )
                    ).scalars()
                )

                self.assertEqual(song.title, "Updated Song")
                self.assertEqual(song.version_jp, 26)
                self.assertEqual(song.provider, "provider-b")
                self.assertEqual(Path(song.img_path), Path("covers/updated.png"))
                self.assertEqual(chart.designer, "Updated Designer")
                self.assertEqual(aliases, {"alias-one", "alias-two"})
        finally:
            await engine.dispose()


if __name__ == "__main__":
    unittest.main()
