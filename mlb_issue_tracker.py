#!/usr/bin/env python3
"""
MLBPARK bullpen "이슈 감지기" (일상 잡담 필터 + 급상승 키워드 탐지)

Usage:
  python3 mlb_issue_tracker.py --target 1200 --recent-min 90 --top 10
"""

from __future__ import annotations

import argparse
import collections
import math
import re
from dataclasses import dataclass
from typing import List

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://mlbpark.donga.com/mp/b.php?b=bullpen&p={page}"
HEADERS = {"User-Agent": "Mozilla/5.0"}

NOISE_CATEGORIES = {
    "뻘글",
    "질문",
    "개선요청",
    "주번나",
}

SPORTS_LIVE_CATEGORIES = {"해축", "축구"}

STOPWORDS = {
    "오늘", "진짜", "그냥", "이거", "저거", "관련", "대한", "근데", "하면", "에서", "으로",
    "입니다", "있나요", "없나요", "무엇", "뭔가", "왜", "후기", "영상", "사진", "gif", "jpg", "mp4",
    "ㅋㅋ", "ㅎㅎ", "너무", "같은", "바로", "지금", "보니", "정도", "하네요", "아닌가요", "뭐가", "쓰나요",
}

KNOWN_TAGS = {
    "정치", "사회", "경제", "국제", "문화", "연예", "영화", "음악", "스포츠", "야구", "해축", "축구",
    "농구", "배구", "올림픽", "기타스포츠", "게임", "LOL", "군사", "IT", "과학", "질문", "뻘글", "펌글",
    "짤방", "자동차", "요리", "여행", "주식", "코인", "유머", "개선요청", "동물", "역사", "교육", "건강",
    "의학", "방송", "아이돌", "사진", "19금", "고민", "직장", "군대", "주번나",
}


@dataclass
class Post:
    title: str
    category: str
    body: str
    sec: int
    raw_time: str


def parse_title(title: str) -> tuple[str, str]:
    parts = title.split(maxsplit=1)
    if parts and parts[0] in KNOWN_TAGS:
        return parts[0], (parts[1] if len(parts) > 1 else "")
    return "기타", title


def fetch_posts(target: int = 1200, max_pages: int = 100) -> List[Post]:
    posts: List[Post] = []
    page = 1

    while len(posts) < target and page <= max_pages:
        html = requests.get(BASE_URL.format(page=page), headers=HEADERS, timeout=20).text
        soup = BeautifulSoup(html, "html.parser")

        for tr in soup.select("tr"):
            tds = tr.select("td")
            if len(tds) != 5:
                continue

            num = tds[0].get_text(strip=True)
            if num == "공지" or not num.isdigit():
                continue

            title = tds[1].get_text(" ", strip=True)
            raw_time = tds[3].get_text(" ", strip=True)
            if not re.match(r"^\d{2}:\d{2}:\d{2}$", raw_time):
                continue

            h, m, s = map(int, raw_time.split(":"))
            sec = h * 3600 + m * 60 + s

            cat, body = parse_title(title)
            posts.append(Post(title=title, category=cat, body=body, sec=sec, raw_time=raw_time))

            if len(posts) >= target:
                break

        page += 1

    return posts


def tokenize(text: str) -> List[str]:
    text = re.sub(r"\[[^\]]*\]", " ", text.lower())
    tokens = re.findall(r"[가-힣a-zA-Z0-9+#]{2,}", text)
    out = []
    for t in tokens:
        if t in STOPWORDS or t.isdigit():
            continue
        out.append(t)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, default=1200, help="수집 게시글 수")
    ap.add_argument("--recent-min", type=int, default=90, help="급상승 계산용 최근 구간(분)")
    ap.add_argument("--baseline-min", type=int, default=360, help="비교 기준 구간(분)")
    ap.add_argument("--top", type=int, default=10, help="출력 개수")
    args = ap.parse_args()

    posts = fetch_posts(target=args.target)
    if not posts:
        print("게시글을 수집하지 못했습니다.")
        return

    max_sec = max(p.sec for p in posts)
    recent_start = max_sec - args.recent_min * 60
    base_start = max_sec - args.baseline_min * 60

    recent = [p for p in posts if p.sec >= recent_start]
    baseline = [p for p in posts if base_start <= p.sec < recent_start]

    def filtered(items: List[Post]) -> List[Post]:
        out = []
        for p in items:
            if p.category in NOISE_CATEGORIES:
                continue
            if p.category in SPORTS_LIVE_CATEGORIES:
                continue
            out.append(p)
        return out

    recent_f = filtered(recent)
    baseline_f = filtered(baseline)

    rec_kw = collections.Counter()
    base_kw = collections.Counter()

    for p in recent_f:
        rec_kw.update(tokenize(p.body))
    for p in baseline_f:
        base_kw.update(tokenize(p.body))

    scored = []
    for k, rc in rec_kw.items():
        bc = base_kw.get(k, 0)
        # 급상승 점수: 최근빈도 * (최근+1)/(기준+1) 의 로그 스케일
        surge = (rc + 1) / (bc + 1)
        score = rc * math.log2(1 + surge)
        if rc < 3:
            continue
        scored.append((score, k, rc, bc, surge))

    scored.sort(reverse=True)

    cat_recent = collections.Counter(p.category for p in recent_f)

    print("== MLBPARK 이슈 감지 리포트 ==")
    print(f"수집: {len(posts)}개 | 최근구간: {args.recent_min}분 | 기준구간: {args.baseline_min}분")
    print(f"최근 시각 범위: {min(p.raw_time for p in recent)} ~ {max(p.raw_time for p in recent)}")
    print()

    print("[최근(필터 후) 카테고리 TOP]")
    for c, n in cat_recent.most_common(8):
        print(f"- {c}: {n}")
    print()

    print(f"[급상승 키워드 TOP {args.top}]")
    for _, kw, rc, bc, surge in scored[: args.top]:
        print(f"- {kw:12} | 최근 {rc:3d} | 기준 {bc:3d} | 급상승 x{surge:.2f}")


if __name__ == "__main__":
    main()
