from __future__ import annotations

import unittest
from unittest.mock import patch

import nonebot
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


class AimeRefactoringTest(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        nonebot.init()
        plugin = nonebot.load_plugin("plugins.maib")
        if plugin is None:
            raise RuntimeError("failed to load plugins.maib")

        from plugins.maib.services.models import Maime, MaiUser, Model
        from plugins.maib.services.refactoring import aime

        cls.aime = aime
        cls.Maime = Maime
        cls.MaiUser = MaiUser
        cls.Model = Model

    async def asyncSetUp(self) -> None:
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        async with self.engine.begin() as connection:
            await connection.run_sync(self.Model.metadata.create_all)
        self.session_patch = patch.object(self.aime, "get_session", self.sessions)
        self.session_patch.start()

    async def asyncTearDown(self) -> None:
        self.session_patch.stop()
        await self.engine.dispose()

    async def test_link_normalizes_and_reports_current_owner(self) -> None:
        await self.aime.link("0001-0002 0003-0004 5678", qq=10001)

        cards = await self.aime.get_aimes(qq=10001)
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["access"], "00010002000300045678")
        with self.assertRaises(self.aime.AimeAlreadyLinkedSelfError):
            await self.aime.link("00010002000300045678", qq=10001)
        with self.assertRaises(self.aime.AimeAlreadyLinkedError):
            await self.aime.link("00010002000300045678", qq=10002)

    async def test_unlinked_is_hidden_from_full_but_found_by_suffix(self) -> None:
        access = "11112222333344445555"
        await self.aime.link(access, qq=10001)

        with self.assertRaises(self.aime.AimeNotOwnerError):
            await self.aime.unlink(access, qq=10002)
        await self.aime.unlink(access, qq=10001)

        self.assertIsNone(await self.aime.find_aime(access))
        with self.assertRaises(self.aime.AimeNotLinkedError):
            await self.aime.find_aime_by_access4("5555")
        self.assertEqual(await self.aime.get_aimes(qq=10001), [])

        await self.aime.link(access, qq=10002)
        rebound = await self.aime.find_aime_by_access4("5555")
        self.assertEqual(rebound["access"], access)
        self.assertEqual(rebound["qq"], 10002)

    async def test_suffix_considers_bound_and_unbound_history_for_ambiguity(self) -> None:
        unbound = "11112222333344449999"
        bound = "55556666777788889999"
        await self.aime.link(unbound, qq=10001)
        await self.aime.unlink(unbound, qq=10001)
        await self.aime.link(bound, qq=10002)

        with self.assertRaises(self.aime.AimeMultipleFoundError):
            await self.aime.find_aime_by_access4("9999")

    async def test_find_uses_temporary_default_hint(self) -> None:
        access = "12345678901234560001"
        await self.aime.link(access, qq=10001)

        suffix_result = await self.aime.find_aime_by_access4("0001")
        full_result = await self.aime.find_aime(access)
        assert full_result is not None

        self.assertEqual(suffix_result["hint"], "Target QQ: 10001")
        self.assertEqual(full_result["hint"], "Target QQ: 10001")


if __name__ == "__main__":
    unittest.main()
