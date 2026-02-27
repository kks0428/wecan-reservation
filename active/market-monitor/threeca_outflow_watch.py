#!/usr/bin/env python3
import json
import subprocess
import time
from pathlib import Path

import requests

RPC = "https://mainnet.helius-rpc.com/?api-key=5073f9a7-2c12-4d66-b2c7-74246ee06129"
MINT = "8Jx8AAHj86wbQgUTjGuj6GTTL5Ps3cqxKRTvpaJApump"
OWNER = "3caFdfwp2LQ93cTENzGm7T7SRSZHXiuWTB22gDQ2UBSy"
THRESHOLD = 300_000.0
STATE = Path("/home/kspoopoo/.openclaw/workspace/state/threeca_outflow_watch.json")
OPENCLAW_BIN = "node /home/kspoopoo/openclaw/dist/index.js"
TARGET = "497612383"

s = requests.Session()


def rpc(method: str, params: list):
    for i in range(8):
        j = s.post(RPC, json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params}, timeout=45).json()
        if "error" in j:
            code = (j["error"] or {}).get("code")
            if code in (429, -32429):
                time.sleep(0.2 * (i + 1))
                continue
            raise RuntimeError(j["error"])
        return j["result"]
    raise RuntimeError("rpc rate-limited")


def load_state():
    if not STATE.exists():
        return {"seen": []}
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:
        return {"seen": []}


def save_state(st):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")


def owner_delta(tx: dict) -> float:
    pre = (tx.get("meta") or {}).get("preTokenBalances") or []
    post = (tx.get("meta") or {}).get("postTokenBalances") or []
    pa = po = 0.0
    touched = False
    for b in pre:
        if b.get("mint") == MINT and b.get("owner") == OWNER:
            pa += float((b.get("uiTokenAmount") or {}).get("uiAmount") or 0)
            touched = True
    for b in post:
        if b.get("mint") == MINT and b.get("owner") == OWNER:
            po += float((b.get("uiTokenAmount") or {}).get("uiAmount") or 0)
            touched = True
    return (po - pa) if touched else 0.0


def send(msg: str):
    subprocess.run(
        f"{OPENCLAW_BIN} message send --channel telegram --target {TARGET} --message {json.dumps(msg)}",
        shell=True,
        check=False,
    )


def main():
    st = load_state()
    seen = set(st.get("seen", []))

    sigs = rpc("getSignaturesForAddress", [OWNER, {"limit": 25}])
    alerts = []

    for sg in sigs:
        sig = sg.get("signature")
        if not sig or sig in seen:
            continue
        tx = rpc("getTransaction", [sig, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}])
        if not tx:
            continue
        d = owner_delta(tx)
        if d <= -THRESHOLD:
            bt = sg.get("blockTime") or 0
            alerts.append((sig, bt, d))
        seen.add(sig)

    if alerts:
        alerts.sort(key=lambda x: x[1])
        lines = ["🚨 3ca 대량 유출 감지"]
        for sig, bt, d in alerts:
            lines.append(f"- {d:,.0f} PENGUIN | sig: {sig[:12]}...")
        send("\n".join(lines))

    st["seen"] = list(seen)[-400:]
    save_state(st)


if __name__ == "__main__":
    main()
