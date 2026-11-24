# Deploying AgentTaskEscrow to Bradbury

## 1. Get test GEN

Faucet: https://testnet-faucet.genlayer.foundation — 100 GEN once a week.
Gate (verified live 24 Nov 2026): GitHub sign-in (account > 3 months old,
>= 1 public repo) **and** a wallet holding >= 0.01 ETH on Ethereum mainnet.
If you fail the gate, use Studionet (local) first — see step 2.

## 2. Deploy via Studio

1. https://studio.genlayer.com → network: **Genlayer Bradbury Testnet**
   (chain ID 4221). For a first run without faucet funds, use the local
   Studionet network instead.
2. New contract → paste `contracts/agent_task_escrow.py` → **Run and Debug**.
   Known Studio quirk (24 Nov 2026): on Bradbury the Run and Debug panel
   sometimes shows "Could not load contract schema" with no Deploy button.
   If that happens, retry on Studionet, or deploy with the CLI below.
3. **Deploy.** No constructor arguments. Save the contract address.

## 3. Deploy via CLI

```bash
npm install -g genlayer
genlayer network   # pick bradbury
genlayer deploy --contract contracts/agent_task_escrow.py
```

## 4. Exercise it (example flow, amounts in wei, 1 GEN = 10^18)

1. Client: `create_task("Write a 200-word summary of GenLayer")` with
   value `1000000000000000000` (1 GEN) → returns task id `0`.
2. Agent: `accept_task(0)`.
3. Agent: `submit_delivery(0, "<the summary text>")`.
4. Anyone: `judge_delivery(0)` → verdict JSON; check `get_task(0)` —
   status `paid` (agent got the GEN) or `refunded` (client got it back).

## 5. Submit to the Season 2 Portal

Portal: https://portal.genlayer.foundation — Builder path. Connect GitHub
and link this repo as your contribution; the deployed contract address
goes in the submission notes. Points are converted every Sunday, with no
guarantee of token conversion.
