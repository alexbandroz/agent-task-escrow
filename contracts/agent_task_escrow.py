# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
"""
AgentTaskEscrow — an Intelligent Contract for the agentic economy on GenLayer.

Problem
-------
An agent (or a human client) wants to hire another agent for a piece of work
— write a report, review code, research a topic, produce a summary — but
neither side wants to trust the other with payment first. A deterministic
smart contract cannot tell whether the delivered work actually matches the
brief, because that judgement is subjective and written in natural language.

What this contract does
-----------------------
1. The client creates a task with a plain-English brief and escrows GEN
   (``create_task``, payable). The money stays in the contract.
2. An agent accepts the task (``accept_task``).
3. The agent submits its delivery as text (``submit_delivery``).
4. Anyone calls ``judge_delivery``. A GenLayer LLM jury — not a human, not
   the client, not the agent — decides whether the delivery fulfils the
   brief, using leader/validator consensus (``gl.vm.run_nondet``): the
   leader LLM proposes a verdict, and each validator independently
   judges the same brief and delivery and only agrees when its own
   verdict matches the leader's.
   - verdict ``accept``  -> the escrow is released to the agent.
   - verdict ``reject``  -> the escrow is refunded to the client.
5. The client can cancel an unsubmitted task (``cancel_task``) and get a
   full refund. Once a task is paid, refunded or cancelled it can never
   pay out again: the stored amount is zeroed on settlement.

Why GenLayer, and not a plain escrow
------------------------------------
The judgement step is the whole point. A normal escrow needs a trusted
third party to read the brief and the delivery. Here the judgement itself
is the on-chain consensus: validators agree on whether the work matches
the brief, and the verdict becomes blockchain state.

Testnet only. This contract handles test GEN on GenLayer Bradbury
(chain ID 4221). It is a Season 2 Builder contribution, not audited
code, and must not be used with real funds.

Deploy: paste this file into https://studio.genlayer.com, switch the
network to "Genlayer Bradbury Testnet", click Run and Debug, then Deploy.
No constructor arguments are needed.
"""

import json
import typing
from dataclasses import dataclass

from genlayer import *


@gl.evm.contract_interface
class _Recipient:
    class View:
        pass

    class Write:
        pass


@allow_storage
@dataclass
class Task:
    task_id: u32
    client: Address
    agent: Address
    brief: str
    delivery: str
    amount: u256
    status: str
    verdict: str


ZERO_ADDRESS = Address("0x0000000000000000000000000000000000000000")


def _verdict_json(raw) -> str:
    """Normalise an LLM verdict to a JSON string.

    ``gl.nondet.exec_prompt`` returns a string in production; in direct
    tests a mocked JSON reply is auto-parsed into a dict. Both shapes
    are valid here, so normalise before parsing.
    """
    if isinstance(raw, dict):
        return json.dumps(raw, sort_keys=True)
    return str(raw)


class AgentTaskEscrow(gl.Contract):
    task_count: u32
    tasks: TreeMap[u32, Task]

    def __init__(self):
        self.task_count = u32(0)

    # -- helpers ---------------------------------------------------------

    def _get_task(self, task_id: u32) -> Task:
        if task_id >= self.task_count:
            raise gl.vm.UserError("task does not exist")
        return self.tasks.get(
            task_id,
            Task(
                task_id=u32(0),
                client=ZERO_ADDRESS,
                agent=ZERO_ADDRESS,
                brief="",
                delivery="",
                amount=u256(0),
                status="",
                verdict="",
            ),
        )

    def _save_task(self, task: Task) -> None:
        self.tasks[task.task_id] = task

    # -- lifecycle -------------------------------------------------------

    @gl.public.write.payable
    def create_task(self, brief: str) -> u32:
        """Create a task and escrow GEN for it. Returns the new task id."""
        if brief == "":
            raise gl.vm.UserError("brief must not be empty")
        value = gl.message.value
        if value == u256(0):
            raise gl.vm.UserError("send GEN to escrow for the task")

        task_id = self.task_count
        task = Task(
            task_id=task_id,
            client=gl.message.sender_address,
            agent=ZERO_ADDRESS,
            brief=brief,
            delivery="",
            amount=value,
            status="open",
            verdict="",
        )
        self._save_task(task)
        self.task_count = u32(int(self.task_count) + 1)
        return task_id

    @gl.public.write
    def accept_task(self, task_id: u32) -> None:
        """The agent who will do the work accepts an open task."""
        task = self._get_task(task_id)
        if task.status != "open":
            raise gl.vm.UserError("task is not open")
        if gl.message.sender_address == task.client:
            raise gl.vm.UserError("client cannot accept their own task")
        task.agent = gl.message.sender_address
        task.status = "accepted"
        self._save_task(task)

    @gl.public.write
    def submit_delivery(self, task_id: u32, delivery: str) -> None:
        """The accepted agent submits its work as text."""
        task = self._get_task(task_id)
        if task.status != "accepted":
            raise gl.vm.UserError("task is not accepted")
        if gl.message.sender_address != task.agent:
            raise gl.vm.UserError("only the accepted agent can submit")
        if delivery == "":
            raise gl.vm.UserError("delivery must not be empty")
        task.delivery = delivery
        task.status = "submitted"
        self._save_task(task)

    @gl.public.write
    def judge_delivery(self, task_id: u32) -> str:
        """Let the LLM jury judge the delivery against the brief.

        Anyone may call this. The verdict is decided by consensus, not by
        the caller. Returns the verdict JSON, e.g.
        {"verdict": "accept", "reason": "..."}.
        """
        task = self._get_task(task_id)
        if task.status != "submitted":
            raise gl.vm.UserError("task has no delivery waiting for judgement")

        # Copy storage to memory first: storage cannot be read inside a
        # non-deterministic block.
        brief = task.brief
        delivery = task.delivery
        amount = task.amount
        agent = task.agent
        client = task.client

        prompt = (
            "Judge whether a delivery fulfils a brief. "
            "BRIEF:\n" + brief + "\n\nDELIVERY:\n" + delivery + "\n\n"
            'Reply with JSON only: {"verdict": "accept" or "reject", '
            '"reason": "one sentence"}. Accept only when the delivery '
            "clearly fulfils the brief."
        )

        def leader() -> str:
            return _verdict_json(gl.nondet.exec_prompt(prompt))

        def validator(leader_result) -> bool:
            if not isinstance(leader_result, gl.vm.Return):
                return False
            try:
                leader_verdict = json.loads(leader_result.calldata)["verdict"]
                my_verdict = json.loads(
                    _verdict_json(gl.nondet.exec_prompt(prompt))
                )["verdict"]
            except Exception:
                return False
            return str(leader_verdict).lower() == str(my_verdict).lower()

        verdict_json = gl.vm.run_nondet(leader, validator)

        # In production the verdict arrives as a JSON string. In direct
        # tests the LLM mock auto-parses JSON strings into a dict, so
        # accept both shapes here.
        try:
            if isinstance(verdict_json, dict):
                parsed = verdict_json
            else:
                parsed = json.loads(verdict_json)
            verdict = str(parsed["verdict"]).lower()
            reason = str(parsed.get("reason", ""))
        except Exception:
            raise gl.vm.UserError("LLM verdict was not valid JSON, retry judging")

        if verdict != "accept" and verdict != "reject":
            raise gl.vm.UserError("LLM verdict was neither accept nor reject")

        if verdict == "accept":
            _Recipient(agent).emit_transfer(value=amount)
            task.status = "paid"
        else:
            _Recipient(client).emit_transfer(value=amount)
            task.status = "refunded"

        task.verdict = reason
        # Zero the amount so this task can never pay out a second time.
        task.amount = u256(0)
        self._save_task(task)
        return json.dumps({"verdict": verdict, "reason": reason})

    @gl.public.write
    def cancel_task(self, task_id: u32) -> None:
        """The client cancels an unsubmitted task and gets a full refund."""
        task = self._get_task(task_id)
        if gl.message.sender_address != task.client:
            raise gl.vm.UserError("only the client can cancel")
        if task.status != "open" and task.status != "accepted":
            raise gl.vm.UserError("cannot cancel a submitted or settled task")
        _Recipient(task.client).emit_transfer(value=task.amount)
        task.amount = u256(0)
        task.status = "cancelled"
        self._save_task(task)

    # -- views -----------------------------------------------------------

    @gl.public.view
    def get_task(self, task_id: u32) -> Task:
        return self._get_task(task_id)

    @gl.public.view
    def get_task_count(self) -> u32:
        return self.task_count

    @gl.public.view
    def get_balance(self) -> u256:
        return self.balance
