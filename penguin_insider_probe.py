#!/usr/bin/env python3
"""
PENGUIN 2주 내부자 덤핑 정황 탐지기
- SOLANA_RPC_URL 필요 (Helius/QuickNode 등 권장)
- creator + top holders 흐름을 14일 기준으로 스냅샷
"""

from __future__ import annotations
import os, time, datetime as dt, requests

MINT = "8Jx8AAHj86wbQgUTjGuj6GTTL5Ps3cqxKRTvpaJApump"
RPC = os.getenv("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")
DAYS = int(os.getenv("PROBE_DAYS", "14"))

s = requests.Session()

def rpc(method, params):
    for i in range(8):
        r = s.post(RPC, json={"jsonrpc":"2.0","id":1,"method":method,"params":params}, timeout=30)
        j = r.json()
        if "error" in j:
            if j["error"].get("code") == 429:
                time.sleep(1.2 * (i + 1))
                continue
            raise RuntimeError(j["error"])
        return j["result"]
    raise RuntimeError("RPC rate-limited too much")


def main():
    supply = float(rpc("getTokenSupply", [MINT])["value"]["uiAmount"])
    la = rpc("getTokenLargestAccounts", [MINT])["value"]
    print(f"RPC={RPC}")
    print(f"Supply={supply:,.3f}")
    print("Top holders snapshot:")
    for i, x in enumerate(la[:15], 1):
        amt = float(x["uiAmount"])
        print(f"{i:>2}. {x['address']}  {amt:,.3f} ({amt/supply*100:.3f}%)")

    # creator(민트 계정) 메타에서 mintAuthority/updateAuthority를 바로 못 얻는 경우가 있어
    # 간단 버전: 토큰 account 생성/초기 민팅 트랜잭션 추적은 별도 단계로 분리
    print("\nNext step:")
    print("1) 위 상위 주소 중 의심 주소 3~5개 선정")
    print("2) 각 주소 getSignaturesForAddress(limit=1000)로 14일 흐름 수집")
    print("3) CEX/AMM 라벨 주소로 유입량 합산")

if __name__ == "__main__":
    main()
