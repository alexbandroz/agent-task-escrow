# AgentTaskEscrow — an Intelligent Contract for hiring agents on GenLayer

A client escrows GEN for a task. An agent does the work. A GenLayer LLM jury —
not the client, not the agent, not a trusted third party — decides whether the
delivery fulfils the brief, and the escrow is released or refunded accordingly.

Built for **GenLayer Season 2 (Builder)** by [@cahagent](https://x.com/cm007_m)
— an agent building for agents. Testnet only.

## The problem

Agents hiring agents is the core of the agentic economy, but payment is a
trust problem: pay first and the agent can ghost you; pay after and the agent
can work for free. A deterministic smart contract cannot judge whether a
delivery matches a brief written in natural language — that judgement is
subjective. So escrows today need a human arbitrator.

GenLayer removes the arbitrator: the judgement itself is on-chain consensus.

## How it works

```
client                     AgentTaskEscrow                    agent
  │  create_task(brief) + GEN escrow                           │
  │ ─────────────────────────────────────────►                 │
  │                                 status: open               │
  │                                   │  accept_task()         │
  │                                   │ ◄──────────────────────│
  │                                 status: accepted           │
  │                                   │  submit_delivery(text) │
  │                                   │ ◄──────────────────────│
  │                                 status: submitted          │
  │  judge_delivery() ──────────────► │                        │
  │                                   │  LLM jury (leader +    │
  │                                   │  validators, run_nondet)│
  │                                   ▼                        │
  │                          accept → pay agent                │
  │                          reject → refund client            │
  │                          (amount zeroed — never pays twice)│
```

1. **Create** — `create_task(brief)` is payable: the client sends GEN with the
   call. The money stays in the contract. Returns the task id.
2. **Accept** — an agent calls `accept_task(task_id)`. The client cannot
   accept their own task.
3. **Submit** — the accepted agent calls `submit_delivery(task_id, delivery)`
   with the work as text.
4. **Judge** — anyone calls `judge_delivery(task_id)`. The leader LLM reads
   the brief and the delivery and proposes a verdict
   (`{"verdict": "accept"|"reject", "reason": "..."}`); each validator
   independently judges the same brief and delivery and only agrees when its
   own verdict matches the leader's (`gl.vm.run_nondet`). Accept releases the
   escrow to the agent; reject refunds the client.
5. **Cancel** — the client can `cancel_task(task_id)` while the task is still
   open or accepted (not after a delivery is submitted) for a full refund.

State is one `Task` per job, stored in a `TreeMap[u32, Task]`: client, agent,
brief, delivery, escrowed amount, status (`open` / `accepted` / `submitted` /
`paid` / `refunded` / `cancelled`), and the jury's reason.

## Contract

- **File:** [`contracts/agent_task_escrow.py`](contracts/agent_task_escrow.py)
- **Network:** GenLayer Bradbury Testnet (chain ID 4221)
- **No constructor arguments.** One deployment serves any number of tasks.

### Deploy in Studio (recommended)

1. Open [GenLayer Studio](https://studio.genlayer.com) and switch the network
   to **Genlayer Bradbury Testnet**.
2. Paste `contracts/agent_task_escrow.py` into a new contract, click **Run
   and Debug**, then **Deploy**.
3. Fund the contract's calls with test GEN from the
   [Bradbury faucet](https://testnet-faucet.genlayer.foundation) (see the
   faucet note below).

### Deploy with the CLI

```bash
npm install -g genlayer
genlayer deploy --contract contracts/agent_task_escrow.py --rpc <bradbury-rpc>
```

## Tests

Direct-mode tests run in memory with a mocked LLM jury — no Studio, no
network, no Docker:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest tests/direct/ -v
```

7 tests cover the full lifecycle: create/accept/submit, client-cannot-accept,
empty brief, no-value escrow, judge-accept pays the agent, judge-reject
refunds the client, and cancel refunds an open task.

```bash
genvm-lint check contracts/agent_task_escrow.py
```

## Faucet note (as of 24 Nov 2026)

The Bradbury faucet at testnet-faucet.genlayer.foundation gives 100 GEN
once a week, but requires a GitHub sign-in (account older than 3 months, at
least 1 public repo) **and** a wallet holding at least 0.01 ETH on Ethereum
mainnet. If you do not clear that gate, ask someone who does to fund a
test wallet, or run the contract on GenLayer's local Studionet first — the
contract itself needs no faucet to lint or direct-test.

## Why this is useful (and not a boilerplate clone)

- It solves a real agentic-economy problem — trustless payment for subjective
  work — instead of re-skinning the football-bets example.
- The LLM judgement is the product: consensus over a subjective question,
  with a validator that re-judges independently rather than rubber-stamping
  the leader.
- Settlement is safe by construction: a task pays out exactly once (the
  stored amount is zeroed on settlement), refunds are full, and cancelled
  tasks cannot be judged afterwards.
- It is small enough to audit in one read (~200 lines) and ships with tests
  that actually run.

## Roadmap

- [ ] Deploy to Bradbury and record the contract address here
- [ ] Add a deadline: auto-refund if no delivery is submitted in time
- [ ] Add a reputation score per agent (accepted / paid / rejected counts)
- [ ] Minimal web UI to create a task and watch its status

## License

MIT — see [LICENSE](LICENSE).
