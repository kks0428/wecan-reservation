#!/usr/bin/env python3
from __future__ import annotations
import os, time, datetime as dt, json
import requests

MINT = "8Jx8AAHj86wbQgUTjGuj6GTTL5Ps3cqxKRTvpaJApump"
RPC = os.getenv("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")
DAYS = int(os.getenv("PENGUIN_DAYS", "14"))
TOP_N = int(os.getenv("PENGUIN_TOPN", "8"))
MAX_SIGS = int(os.getenv("PENGUIN_MAXSIGS", "350"))

s = requests.Session()


def rpc(method, params):
    for i in range(8):
        r = s.post(RPC, json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params}, timeout=45)
        j = r.json()
        if "error" in j:
            code = j["error"].get("code")
            if code == 429:
                time.sleep(0.6 * (i + 1))
                continue
            raise RuntimeError(j["error"])
        return j["result"]
    raise RuntimeError("rate-limited")


def token_acc_owner(token_acc: str) -> str:
    info = rpc("getAccountInfo", [token_acc, {"encoding": "jsonParsed"}])
    v = (info or {}).get("value") or {}
    data = (v.get("data") or {}).get("parsed") or {}
    return ((data.get("info") or {}).get("owner") or "")


def get_top_token_accounts():
    supply = float(rpc("getTokenSupply", [MINT])["value"]["uiAmount"])
    la = rpc("getTokenLargestAccounts", [MINT])["value"][:TOP_N]
    out = []
    for i, x in enumerate(la, 1):
        amt = float(x["uiAmount"])
        ta = x["address"]
        owner = token_acc_owner(ta)
        out.append({
            "rank": i,
            "tokenAccount": ta,
            "owner": owner,
            "amount": amt,
            "pct": amt / supply * 100,
        })
    return supply, out


def get_signatures(addr: str, since_ts: int):
    out = []
    before = None
    while len(out) < MAX_SIGS:
        cfg = {"limit": 100}
        if before:
            cfg["before"] = before
        arr = rpc("getSignaturesForAddress", [addr, cfg])
        if not arr:
            break
        stop = False
        for a in arr:
            bt = a.get("blockTime") or 0
            if bt and bt < since_ts:
                stop = True
                break
            out.append(a["signature"])
        if stop:
            break
        before = arr[-1]["signature"]
        if len(arr) < 100:
            break
    return out[:MAX_SIGS]


def net_flow_for_owner(owner_wallet: str, mint: str, since_ts: int):
    # owner wallet 기준으로 관련 tx를 훑고 pre/post token balance 변화로 순유출입 계산
    sigs = get_signatures(owner_wallet, since_ts)
    net = 0.0
    inflow = 0.0
    outflow = 0.0
    tx_count = 0
    for sig in sigs:
        tx = rpc("getTransaction", [sig, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}])
        if not tx:
            continue
        bt = tx.get("blockTime") or 0
        if bt < since_ts:
            continue
        meta = tx.get("meta") or {}
        pre = meta.get("preTokenBalances") or []
        post = meta.get("postTokenBalances") or []
        pre_amt = 0.0
        post_amt = 0.0
        touched = False
        for b in pre:
            if b.get("mint") == mint and b.get("owner") == owner_wallet:
                pre_amt += float((b.get("uiTokenAmount") or {}).get("uiAmount") or 0)
                touched = True
        for b in post:
            if b.get("mint") == mint and b.get("owner") == owner_wallet:
                post_amt += float((b.get("uiTokenAmount") or {}).get("uiAmount") or 0)
                touched = True
        if not touched:
            continue
        d = post_amt - pre_amt
        if abs(d) < 1e-9:
            continue
        tx_count += 1
        net += d
        if d > 0:
            inflow += d
        else:
            outflow += -d
    return {
        "owner": owner_wallet,
        "txCount": tx_count,
        "net": net,
        "inflow": inflow,
        "outflow": outflow,
        "sigsScanned": len(sigs),
    }


def main():
    now = int(time.time())
    since = now - DAYS * 86400
    supply, top = get_top_token_accounts()

    results = []
    for row in top:
        owner = row["owner"]
        if not owner:
            continue
        try:
            flow = net_flow_for_owner(owner, MINT, since)
        except Exception as e:
            flow = {"owner": owner, "error": str(e)}
        row2 = {**row, **flow}
        results.append(row2)

    report = {
        "generatedAtUTC": dt.datetime.now(dt.timezone.utc).isoformat(),
        "rpc": RPC,
        "days": DAYS,
        "supply": supply,
        "top": results,
    }

    p = "/home/kspoopoo/.openclaw/workspace/penguin_14d_report.json"
    with open(p, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print("saved", p)
    for r in results:
        if r.get("error"):
            print(r["rank"], r["owner"][:8], "ERR", r["error"])
        else:
            print(
                f"#{r['rank']} owner={r['owner'][:8]}... pct={r['pct']:.2f}% tx={r['txCount']} net={r['net']:+,.2f} in={r['inflow']:,.2f} out={r['outflow']:,.2f} scanned={r['sigsScanned']}"
            )


if __name__ == "__main__":
    main()
