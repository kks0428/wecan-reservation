#!/usr/bin/env python3
"""
PENGUIN (Solana) monitor
- 가격/유동성/거래량/매수매도 트렌드 감시
- 급락/유동성 급감/매도 우위 경고 출력

Usage:
  python3 penguin_monitor.py --once
  python3 penguin_monitor.py --interval 600
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shlex
import subprocess
import time
from pathlib import Path

import requests

TOKEN = "8Jx8AAHj86wbQgUTjGuj6GTTL5Ps3cqxKRTvpaJApump"
CHAIN = "solana"
API = "https://api.dexscreener.com"
STATE_FILE = Path("/home/kspoopoo/.openclaw/workspace/.penguin_state.json")
OPENCLAW_BIN = "node /home/kspoopoo/openclaw/dist/index.js"
TG_TARGET_DEFAULT = "497612383"


THRESHOLDS = {
    "drop_1h_pct": -5.0,        # 1h 하락이 -5% 이하
    "drop_5m_pct": -2.5,        # 5m 급락
    "liq_drop_pct": -12.0,      # 직전 대비 유동성 -12% 이하
    "sell_bias_ratio": 1.35,    # sells > buys * 1.35
}


def now_kst() -> str:
    return (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=9)).strftime("%Y-%m-%d %H:%M:%S KST")


def fetch_top_pair() -> dict:
    r = requests.get(f"{API}/token-pairs/v1/{CHAIN}/{TOKEN}", timeout=20)
    r.raise_for_status()
    arr = r.json()
    if not isinstance(arr, list) or not arr:
        raise RuntimeError("No pair data")
    arr.sort(key=lambda p: float((p.get("liquidity") or {}).get("usd") or 0), reverse=True)
    return arr[0]


def load_state() -> dict:
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text())
    except Exception:
        return {}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2))


def analyze(cur: dict, prev: dict) -> list[str]:
    alerts: list[str] = []

    ch = cur.get("priceChange") or {}
    tx = cur.get("txns") or {}
    liq = float((cur.get("liquidity") or {}).get("usd") or 0)

    m5 = float(ch.get("m5") or 0)
    h1 = float(ch.get("h1") or 0)

    if h1 <= THRESHOLDS["drop_1h_pct"]:
        alerts.append(f"⚠️ 1h 급락: {h1:.2f}%")
    if m5 <= THRESHOLDS["drop_5m_pct"]:
        alerts.append(f"⚠️ 5m 급락: {m5:.2f}%")

    h1tx = tx.get("h1") or {}
    buys = int(h1tx.get("buys") or 0)
    sells = int(h1tx.get("sells") or 0)
    if buys > 0 and sells > buys * THRESHOLDS["sell_bias_ratio"]:
        alerts.append(f"⚠️ 매도 우위: h1 buys/sells={buys}/{sells}")

    prev_liq = float(prev.get("liq") or 0)
    if prev_liq > 0:
        liq_delta = (liq - prev_liq) / prev_liq * 100
        if liq_delta <= THRESHOLDS["liq_drop_pct"]:
            alerts.append(f"⚠️ 유동성 급감: {liq_delta:.2f}% (prev ${prev_liq:,.0f} -> now ${liq:,.0f})")

    return alerts


def snapshot_line(cur: dict) -> str:
    ch = cur.get("priceChange") or {}
    tx = cur.get("txns") or {}
    vol = cur.get("volume") or {}
    liq = float((cur.get("liquidity") or {}).get("usd") or 0)

    return (
        f"[{now_kst()}] {cur.get('dexId')} price=${cur.get('priceUsd')} "
        f"chg(m5/h1/h24)={ch.get('m5')}/{ch.get('h1')}/{ch.get('h24')}% "
        f"liq=${liq:,.0f} vol(h1/h24)={vol.get('h1')}/{vol.get('h24')} "
        f"tx_h1={tx.get('h1')}"
    )


def send_telegram(msg: str) -> None:
    target = os.getenv("PENGUIN_TG_TARGET", TG_TARGET_DEFAULT).strip()
    if not target:
        return
    cmd = (
        f"{OPENCLAW_BIN} message send --channel telegram "
        f"--target {shlex.quote(target)} --message {shlex.quote(msg)}"
    )
    subprocess.run(cmd, shell=True, check=False)


def run_once(notify: bool = False) -> int:
    cur = fetch_top_pair()
    prev = load_state()

    line = snapshot_line(cur)
    print(line)
    alerts = analyze(cur, prev)
    for a in alerts:
        print(a)

    if notify and alerts:
        send_telegram("[PENGUIN ALERT]\n" + line + "\n" + "\n".join(alerts))

    save_state(
        {
            "ts": int(time.time()),
            "liq": float((cur.get("liquidity") or {}).get("usd") or 0),
            "price": float(cur.get("priceUsd") or 0),
            "pair": cur.get("pairAddress"),
            "dex": cur.get("dexId"),
        }
    )
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", type=int, default=0, help="seconds; 0 means run once")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--notify", action="store_true", help="send Telegram alert when thresholds hit")
    args = ap.parse_args()

    if args.once or args.interval <= 0:
        return run_once(notify=args.notify)

    while True:
        try:
            run_once(notify=args.notify)
        except Exception as e:
            print(f"[{now_kst()}] ERROR: {e}")
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
