"""Unit tests for WaitableSlot and wait_until."""
import asyncio
import pytest

from pyquotex._api._waits import WaitableSlot, wait_until


@pytest.mark.asyncio
async def test_slot_resolves_with_set_value():
    slot: WaitableSlot[int] = WaitableSlot()

    async def setter():
        await asyncio.sleep(0.01)
        slot.set(42)

    asyncio.create_task(setter())
    assert await slot.wait(timeout=1.0) == 42


@pytest.mark.asyncio
async def test_slot_times_out_when_never_set():
    slot: WaitableSlot[int] = WaitableSlot()
    with pytest.raises(asyncio.TimeoutError):
        await slot.wait(timeout=0.05)


@pytest.mark.asyncio
async def test_slot_can_be_cleared_and_reused():
    slot: WaitableSlot[str] = WaitableSlot()
    slot.set("first")
    assert await slot.wait(timeout=0.1) == "first"
    slot.clear()
    with pytest.raises(asyncio.TimeoutError):
        await slot.wait(timeout=0.05)
    slot.set("second")
    assert await slot.wait(timeout=0.1) == "second"


@pytest.mark.asyncio
async def test_slot_set_before_wait_resolves_immediately():
    slot: WaitableSlot[int] = WaitableSlot()
    slot.set(7)
    assert await slot.wait(timeout=0.1) == 7


@pytest.mark.asyncio
async def test_wait_until_resolves_when_predicate_true():
    counter = {"n": 0}

    async def increment():
        await asyncio.sleep(0.01)
        counter["n"] = 5

    asyncio.create_task(increment())
    await wait_until(lambda: counter["n"] >= 5, timeout=1.0)
    assert counter["n"] == 5


@pytest.mark.asyncio
async def test_wait_until_times_out():
    with pytest.raises(asyncio.TimeoutError):
        await wait_until(lambda: False, timeout=0.05)


from pyquotex._api._waits import SlotRegistry


def test_slot_registry_has_named_slots():
    reg = SlotRegistry()
    assert reg.balance is not None
    assert reg.balance_update is not None
    assert reg.candle_v2_ready is not None
    assert reg.historical_ready is not None
    assert reg.pending_confirm is not None
    assert reg.sold_option_confirm is not None
    assert reg.training_balance_edit is not None
    assert reg.auth_status is not None


def test_slot_registry_keyed_slots_create_on_access():
    reg = SlotRegistry()
    slot_a = reg.order_confirm("req-1")
    slot_b = reg.order_confirm("req-1")
    slot_c = reg.order_confirm("req-2")
    assert slot_a is slot_b  # same key returns same slot
    assert slot_a is not slot_c  # different key returns different slot


def test_slot_registry_keyed_slot_release():
    reg = SlotRegistry()
    slot = reg.order_confirm("req-1")
    slot.set({"id": 1})
    reg.release_order_confirm("req-1")
    new_slot = reg.order_confirm("req-1")
    assert new_slot is not slot
