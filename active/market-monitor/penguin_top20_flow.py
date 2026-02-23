#!/usr/bin/env python3
import base64
import struct
import time
import requests

RPC = "https://mainnet.helius-rpc.com/?api-key=5073f9a7-2c12-4d66-b2c7-74246ee06129"
MINT = "8Jx8AAHj86wbQgUTjGuj6GTTL5Ps3cqxKRTvpaJApump"
TOKEN2022 = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"
WINDOW_SEC = 6 * 3600
MAX_SIG_PER_OWNER = 30

ALPH = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def b58(b: bytes) -> str:
    n = int.from_bytes(b, "big")
    s = ""
    while n > 0:
        n, r = divmod(n, 58)
        s = ALPH[r] + s
    pad = 0
    for x in b:
        if x == 0:
            pad += 1
        else:
            break
    return "1" * pad + (s or "1")


s = requests.Session()


def rpc(method, params):
    for i in range(8):
        j = s.post(RPC, json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params}, timeout=60).json()
        if "error" in j:
            if j["error"].get("code") in (429, -32429):
                time.sleep(0.2 * (i + 1))
                continue
            raise RuntimeError(j["error"])
        return j["result"]
    raise RuntimeError("rate-limited")


def main():
    since = int(time.time()) - WINDOW_SEC
    sup = rpc("getTokenSupply", [MINT])["value"]
    dec = int(sup["decimals"])
    supply = float(sup["uiAmount"])

    res = rpc("getProgramAccounts", [TOKEN2022, {
        "encoding": "base64",
        "filters": [{"memcmp": {"offset": 0, "bytes": MINT}}],
        "dataSlice": {"offset": 0, "length": 72}
    }])

    owner_amt = {}
    for a in res:
        raw = base64.b64decode(a["account"]["data"][0])
        if len(raw) < 72:
            continue
        owner = b58(raw[32:64])
        amt = struct.unpack("<Q", raw[64:72])[0]
        if amt == 0:
            continue
        owner_amt[owner] = owner_amt.get(owner, 0) + amt

    top20 = sorted(owner_amt.items(), key=lambda kv: kv[1], reverse=True)[:20]

    rows = []
    for owner, raw_amt in top20:
        sigs = rpc("getSignaturesForAddress", [owner, {"limit": MAX_SIG_PER_OWNER}])
        net = 0.0
        for sg in sigs:
            bt = sg.get("blockTime") or 0
            if bt < since:
                continue
            tx = rpc("getTransaction", [sg["signature"], {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}])
            if not tx:
                continue
            pre = (tx.get("meta") or {}).get("preTokenBalances") or []
            post = (tx.get("meta") or {}).get("postTokenBalances") or []
            pa = po = 0.0
            touched = False
            for b in pre:
                if b.get("mint") == MINT and b.get("owner") == owner:
                    pa += float((b.get("uiTokenAmount") or {}).get("uiAmount") or 0)
                    touched = True
            for b in post:
                if b.get("mint") == MINT and b.get("owner") == owner:
                    po += float((b.get("uiTokenAmount") or {}).get("uiAmount") or 0)
                    touched = True
            if touched:
                d = po - pa
                if abs(d) > 1e-9:
                    net += d
        pct = (raw_amt / (10 ** dec)) / supply * 100
        rows.append((owner, pct, net))

    neg = sum(1 for _, _, n in rows if n < 0)
    pos = sum(1 for _, _, n in rows if n > 0)
    total = sum(n for _, _, n in rows)
    print(f"window=6h top20 neg={neg} pos={pos} sum_net={total:,.2f}")
    print("top outflow")
    for o, p, n in sorted(rows, key=lambda x: x[2])[:8]:
        print(o, f"pct={p:.3f}", f"net={n:,.2f}")
    print("top inflow")
    for o, p, n in sorted(rows, key=lambda x: x[2], reverse=True)[:8]:
        print(o, f"pct={p:.3f}", f"net=+{n:,.2f}")


if __name__ == "__main__":
    main()
