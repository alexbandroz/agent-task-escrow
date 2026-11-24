"""Direct-mode tests for AgentTaskEscrow.

Run (no Studio needed, LLM calls are mocked):

    pip install -r requirements.txt
    pytest tests/direct/ -v

Fixtures (direct_vm, direct_deploy, direct_alice, direct_bob) come from
the ``genlayer-test`` pytest plugin. ``direct_vm.value`` sets the GEN
sent with a payable call (in wei, 1 GEN = 10**18); ``direct_vm.mock_llm``
stubs the LLM jury with a regex on the prompt, so judge_delivery() is
deterministic here. On Bradbury the same call uses real consensus.
"""

from tests.direct.conftest import to_hex

ESCROW = 10**18  # 1 GEN in wei


def _as_hex(address):
    return address.as_hex if hasattr(address, "as_hex") else to_hex(address)


def _create_task(direct_vm, contract, sender, brief="Write a 200-word summary of GenLayer"):
    direct_vm.sender = sender
    direct_vm.value = ESCROW
    task_id = contract.create_task(brief)
    direct_vm.value = 0
    return task_id


def test_create_accept_submit(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = direct_deploy("contracts/agent_task_escrow.py")

    task_id = _create_task(direct_vm, contract, direct_alice)
    assert task_id == 0
    assert contract.get_task_count() == 1

    task = contract.get_task(0)
    assert task.status == "open"
    assert task.brief == "Write a 200-word summary of GenLayer"
    assert _as_hex(task.client) == to_hex(direct_alice)
    assert task.amount == ESCROW

    direct_vm.sender = direct_bob
    contract.accept_task(0)
    assert contract.get_task(0).status == "accepted"
    assert _as_hex(contract.get_task(0).agent) == to_hex(direct_bob)

    contract.submit_delivery(0, "GenLayer is an AI consensus chain ...")
    assert contract.get_task(0).status == "submitted"

    # Cancelling a submitted task must fail.
    direct_vm.sender = direct_alice
    with direct_vm.expect_revert("cannot cancel a submitted or settled task"):
        contract.cancel_task(0)


def test_client_cannot_accept_own_task(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy("contracts/agent_task_escrow.py")
    _create_task(direct_vm, contract, direct_alice, "Summarise this repo in one paragraph")
    with direct_vm.expect_revert("client cannot accept their own task"):
        contract.accept_task(0)


def test_empty_brief_is_rejected(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy("contracts/agent_task_escrow.py")
    direct_vm.sender = direct_alice
    direct_vm.value = ESCROW
    with direct_vm.expect_revert("brief must not be empty"):
        contract.create_task("")


def test_create_without_value_is_rejected(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy("contracts/agent_task_escrow.py")
    direct_vm.sender = direct_alice
    direct_vm.value = 0
    with direct_vm.expect_revert("send GEN to escrow for the task"):
        contract.create_task("Write a summary")


def test_judge_accept_pays_agent(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = direct_deploy("contracts/agent_task_escrow.py")
    _create_task(direct_vm, contract, direct_alice)
    direct_vm.sender = direct_bob
    contract.accept_task(0)
    contract.submit_delivery(0, "GenLayer is an AI consensus chain ...")

    direct_vm.mock_llm(
        r".*",
        '{"verdict": "accept", "reason": "Delivery clearly fulfils the brief."}',
    )
    verdict_json = contract.judge_delivery(0)
    assert '"accept"' in verdict_json
    task = contract.get_task(0)
    assert task.status == "paid"
    assert task.amount == 0  # zeroed so it can never pay out twice


def test_judge_reject_refunds_client(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = direct_deploy("contracts/agent_task_escrow.py")
    _create_task(direct_vm, contract, direct_alice)
    direct_vm.sender = direct_bob
    contract.accept_task(0)
    contract.submit_delivery(0, "Unrelated text about football.")

    direct_vm.mock_llm(
        r".*",
        '{"verdict": "reject", "reason": "Delivery does not address the brief."}',
    )
    verdict_json = contract.judge_delivery(0)
    assert '"reject"' in verdict_json
    task = contract.get_task(0)
    assert task.status == "refunded"
    assert task.amount == 0


def test_cancel_open_task_refunds(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy("contracts/agent_task_escrow.py")
    _create_task(direct_vm, contract, direct_alice)
    direct_vm.sender = direct_alice
    contract.cancel_task(0)
    task = contract.get_task(0)
    assert task.status == "cancelled"
    assert task.amount == 0
