import asyncio
import unittest

from app.websocket.connection_manager import ConnectionManager


class ConnectionManagerInterruptTests(unittest.IsolatedAsyncioTestCase):
    async def test_interrupt_cancels_active_turn_and_sets_flag(self):
        manager = ConnectionManager()
        manager.interrupt_event("client")
        started = asyncio.Event()

        async def active_turn():
            started.set()
            await asyncio.Event().wait()

        task = asyncio.create_task(active_turn())
        manager.set_turn_task("client", task)
        await started.wait()

        manager.request_interrupt("client")

        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertTrue(manager.is_interrupted("client"))

    async def test_clear_interrupt_allows_next_turn(self):
        manager = ConnectionManager()
        manager.interrupt_event("client")
        manager.request_interrupt("client")
        self.assertTrue(manager.is_interrupted("client"))

        manager.clear_interrupt("client")

        self.assertFalse(manager.is_interrupted("client"))


if __name__ == "__main__":
    unittest.main()
