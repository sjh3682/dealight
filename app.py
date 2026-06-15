# -*- coding: utf-8 -*-
"""
Dealight - 중고거래 가격 비교 · 적정가 판단 도구
-------------------------------------------------
물건 이름과 상태를 입력하면, 이미 올라와 있는 매물과 가격을 보여주고
지금 시세가 얼마인지(그리고 내가 생각한 가격이 비싼지/싼지) 알려준다.

데이터는 data/listings.csv (generate_data.py 로 만든 가상 매물)에서 읽는다.

실행:
    pip install flask
    python generate_data.py     # 데이터가 없다면 먼저 생성
    python app.py
    브라우저에서 http://127.0.0.1:5000 접속
"""

import csv
import os
import statistics
from collections import OrderedDict
from flask import Flask, render_template, request

app = Flask(__name__)

DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "listings.csv")

# 상태 등급(화면 표시 순서) — generate_data.py 와 동일하게 맞춘다
CONDITIONS = [
    "미사용",
    "사용감 거의 없음",
    "눈에 띄는 흔적 없음",
    "사용감 있음",
    "사용감 심함",
]

# 상태별 가격 배수(기준 1.00 = '눈에 띄는 흔적 없음')
# 상태가 섞인 매물들을 같은 기준으로 비교하기 위해 사용한다.
CONDITION_FACTOR = {
    "미사용": 1.18,
    "사용감 거의 없음": 1.08,
    "눈에 띄는 흔적 없음": 1.00,
    "사용감 있음": 0.85,
    "사용감 심함": 0.68,
}


def load_listings():
    """CSV를 읽어 매물 리스트(딕셔너리들)로 반환한다."""
    listings = []
    with open(DATA_PATH, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            row["price"] = int(row["price"])
            listings.append(row)
    return listings


LISTINGS = load_listings()
# 검색 안내에 쓸 '취급 품목' 목록
ALL_ITEMS = sorted({l["item_name"] for l in LISTINGS})

# 카테고리별로 품목을 묶어 둔다(홈 화면 빠른 검색 칩에 사용)
CATEGORY_ORDER = ["전자기기", "가전", "화장품·향수", "명품", "생활·레저"]


def build_items_by_category():
    groups = {}
    for l in LISTINGS:
        groups.setdefault(l.get("category", "기타"), set()).add(l["item_name"])
    ordered = OrderedDict()
    for c in CATEGORY_ORDER:          # 정해둔 순서 먼저
        if c in groups:
            ordered[c] = sorted(groups[c])
    for c in groups:                  # 나머지 카테고리
        if c not in ordered:
            ordered[c] = sorted(groups[c])
    return ordered


ITEMS_BY_CATEGORY = build_items_by_category()


def normalize(text):
    """공백 제거 + 소문자화로 검색 비교를 느슨하게 만든다."""
    return text.replace(" ", "").lower()


def search(query):
    """검색어가 상품명이나 제목에 들어가는 매물을 모두 찾는다."""
    q = normalize(query)
    if not q:
        return []
    found = []
    for l in LISTINGS:
        if q in normalize(l["item_name"]) or q in normalize(l["title"]):
            found.append(l)
    return found


def won(n):
    """숫자를 '1,234,000원' 형태로."""
    return f"{int(round(n)):,}원"


def percentile_rank(value, data):
    """value 가 data 안에서 하위 몇 %인지 0~100 으로 반환."""
    if not data:
        return None
    below = sum(1 for x in data if x < value)
    return round(below / len(data) * 100)


def analyze(matches, condition, my_price):
    """검색 결과를 바탕으로 통계 · 추천 시세 · 가격 진단을 계산한다."""
    prices = [l["price"] for l in matches]

    # 1) 매물 전체의 기본 통계
    stats = {
        "count": len(prices),
        "min": min(prices),
        "max": max(prices),
        "mean": round(statistics.mean(prices)),
        "median": round(statistics.median(prices)),
    }

    # 2) 상태 보정: 각 매물 가격을 '눈에 띄는 흔적 없음' 기준으로 환산
    #    base = price / (그 매물의 상태배수)  →  상태가 섞여 있어도 공정하게 비교
    base_prices = sorted(l["price"] / CONDITION_FACTOR[l["condition"]] for l in matches)
    base_median = statistics.median(base_prices)
    n = len(base_prices)
    p25 = base_prices[int(n * 0.25)]
    p75 = base_prices[min(int(n * 0.75), n - 1)]

    def tidy(v):
        """보기 좋게 반올림(10만원 이상은 천원, 그 아래는 백원 단위)."""
        step = 1000 if v >= 100_000 else 100
        return int(round(v / step) * step)

    factor = CONDITION_FACTOR[condition]
    recommended = tidy(base_median * factor)          # 선택한 상태 기준 추천 시세
    fair_low = tidy(p25 * factor)                     # 적정 가격 범위(하한)
    fair_high = tidy(p75 * factor)                    # 적정 가격 범위(상한)

    # 같은 상태 매물이 실제로 몇 건 있는지(참고용)
    same_condition_count = sum(1 for l in matches if l["condition"] == condition)

    result = {
        "stats": stats,
        "recommended": recommended,
        "fair_low": fair_low,
        "fair_high": fair_high,
        "same_condition_count": same_condition_count,
        "verdict": None,
    }

    # 3) 내가 생각한 가격 진단(입력했을 때만)
    if my_price:
        # 모든 매물을 '내 상태' 기준으로 환산한 분포와 비교
        adjusted = [b * factor for b in base_prices]
        rank = percentile_rank(my_price, adjusted)
        diff = my_price - recommended
        ratio = diff / recommended * 100 if recommended else 0

        if rank <= 20:
            label, tone = "매우 저렴", "blue"
        elif rank <= 40:
            label, tone = "저렴한 편", "blue"
        elif rank <= 60:
            label, tone = "적정 가격", "yellow"
        elif rank <= 80:
            label, tone = "다소 비쌈", "red"
        else:
            label, tone = "비싼 편", "red"

        result["verdict"] = {
            "my_price": my_price,
            "label": label,
            "tone": tone,
            "rank": rank,
            "diff": diff,
            "ratio": round(ratio),
        }

    return result


@app.route("/")
def index():
    return render_template("index.html", conditions=CONDITIONS,
                           items=ALL_ITEMS, items_by_category=ITEMS_BY_CATEGORY)


@app.route("/search")
def search_route():
    query = request.args.get("query", "").strip()
    condition = request.args.get("condition", "눈에 띄는 흔적 없음")
    if condition not in CONDITION_FACTOR:
        condition = "눈에 띄는 흔적 없음"

    # 선택한 가격(선택 입력) — 숫자가 아니면 무시
    my_price_raw = request.args.get("my_price", "").replace(",", "").strip()
    my_price = int(my_price_raw) if my_price_raw.isdigit() else None

    matches = search(query)

    if not matches:
        return render_template(
            "results.html",
            query=query, condition=condition, conditions=CONDITIONS,
            matches=None, items=ALL_ITEMS,
        )

    # 최신순 + 가격순 정렬해서 보여주기 좋게
    matches_sorted = sorted(matches, key=lambda l: (l["date"], -l["price"]), reverse=True)
    matched_items = sorted({l["item_name"] for l in matches})
    result = analyze(matches, condition, my_price)

    return render_template(
        "results.html",
        query=query, condition=condition, conditions=CONDITIONS,
        matches=matches_sorted, matched_items=matched_items,
        multi=len(matched_items) > 1, result=result,
        items=ALL_ITEMS, my_price=my_price,
        won=won,
    )


# 템플릿 안에서 won() 을 쓸 수 있게 등록
app.jinja_env.globals.update(won=won)


if __name__ == "__main__":
    URL = "http://127.0.0.1:5000"

    # 리로더가 코드를 두 번 실행하므로, 최초 실행에서만 안내문을 출력한다.
    if os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        print("\n" + "=" * 50)
        print("  ✅ Dealight 서버가 실행되었습니다!")
        print("  아래 주소로 접속하세요:")
        print(f"\n      👉  {URL}\n")
        print("  종료하려면 이 터미널에서 Ctrl + C 를 누르세요.")
        print("=" * 50 + "\n")

    app.run(host="127.0.0.1", port=5000, debug=True)
