# -*- coding: utf-8 -*-
"""
Dealight - 중고 매물 가상 데이터 생성기
-------------------------------------------------
실제 사이트를 크롤링하지 않고, 실제 시세를 참고해 '그럴듯한' 중고 매물
데이터를 만들어 data/listings.csv 로 저장한다.
카테고리: 전자기기 / 가전 / 생활·레저 / 화장품·향수 / 명품

실행:  python generate_data.py
"""

import csv
import os
import random
from datetime import datetime, timedelta

random.seed(42)  # 실행할 때마다 같은 데이터가 나오도록 고정

# ---------------------------------------------------------------------------
# 1) 상태 등급과 가격 배수 (기준 1.00 = '눈에 띄는 흔적 없음')
# ---------------------------------------------------------------------------
CONDITIONS = [
    "미사용",
    "사용감 거의 없음",
    "눈에 띄는 흔적 없음",
    "사용감 있음",
    "사용감 심함",
]
CONDITION_FACTOR = {
    "미사용": 1.18,
    "사용감 거의 없음": 1.08,
    "눈에 띄는 흔적 없음": 1.00,
    "사용감 있음": 0.85,
    "사용감 심함": 0.68,
}
CONDITION_WEIGHT = [0.10, 0.22, 0.30, 0.26, 0.12]

# ---------------------------------------------------------------------------
# 2) 품목 목록: (카테고리, 상품명, 기준가)
#    기준가 = '눈에 띄는 흔적 없음' 상태의 대략적인 중고 시세(원)
# ---------------------------------------------------------------------------
PRODUCTS = [
    # ---- 전자기기 ----
    ("전자기기", "아이폰 13", 450_000),
    ("전자기기", "아이폰 14", 600_000),
    ("전자기기", "아이폰 15", 780_000),
    ("전자기기", "갤럭시 S23", 450_000),
    ("전자기기", "갤럭시 S24", 660_000),
    ("전자기기", "갤럭시 Z플립5", 600_000),
    ("전자기기", "에어팟 프로 2", 180_000),
    ("전자기기", "에어팟 4", 120_000),
    ("전자기기", "갤럭시 버즈3", 95_000),
    ("전자기기", "아이패드 9세대", 230_000),
    ("전자기기", "아이패드 에어 5", 480_000),
    ("전자기기", "맥북 에어 M2", 950_000),
    ("전자기기", "애플워치 SE 2세대", 230_000),
    ("전자기기", "닌텐도 스위치 OLED", 280_000),
    ("전자기기", "플레이스테이션 5", 480_000),
    ("전자기기", "로지텍 MX 마스터 3", 70_000),
    # ---- 가전 ----
    ("가전", "다이슨 청소기 V11", 320_000),
    ("가전", "발뮤다 토스터", 180_000),
    ("가전", "LG 스타일러", 700_000),
    ("가전", "삼성 비스포크 큐브 냉장고", 250_000),
    # ---- 생활·레저 ----
    ("생활·레저", "헬리녹스 체어원", 90_000),
    ("생활·레저", "스탠리 텀블러", 25_000),
    ("생활·레저", "삼천리 하이브리드 자전거", 150_000),
    # ---- 화장품·향수 ----
    ("화장품·향수", "샤넬 No.5 오 드 퍼퓸 100ml", 130_000),
    ("화장품·향수", "조 말론 우드세이지 앤 씨솔트 100ml", 130_000),
    ("화장품·향수", "디올 소바쥬 오 드 뚜왈렛 100ml", 90_000),
    ("화장품·향수", "디올 어딕트 립 글로우", 35_000),
    ("화장품·향수", "에스티로더 더블웨어 파운데이션", 45_000),
    ("화장품·향수", "맥 립스틱 루비우", 18_000),
    ("화장품·향수", "설화수 자음생크림", 120_000),
    ("화장품·향수", "헤라 블랙쿠션", 35_000),
    ("화장품·향수", "SK-II 페이셜 트리트먼트 에센스 230ml", 150_000),
    ("화장품·향수", "입생로랑 루쥬 볼립테 립스틱", 30_000),
    ("화장품·향수", "톰포드 립스틱", 48_000),
    ("화장품·향수", "나스 래디언트 크리미 컨실러", 25_000),
    ("화장품·향수", "랑콤 제니피끄 세럼 50ml", 90_000),
    # ---- 명품 ----
    ("명품", "루이비통 네버풀 MM", 1_500_000),
    ("명품", "샤넬 클래식 미디움 플랩백", 9_500_000),
    ("명품", "구찌 마몽 숄더백", 1_300_000),
    ("명품", "에르메스 가든파티 36", 2_800_000),
    ("명품", "프라다 사피아노 토트백", 1_600_000),
    ("명품", "디올 레이디백 미디움", 4_500_000),
    ("명품", "셀린느 트리오페백", 2_200_000),
    ("명품", "생로랑 루루백", 1_700_000),
    ("명품", "발렌시아가 시티백", 900_000),
    ("명품", "롤렉스 데이트저스트 36", 9_800_000),
    ("명품", "까르띠에 러브링", 1_900_000),
    ("명품", "티파니 1837 목걸이", 450_000),
]

# 용량(GB)을 제목에 붙일 전자기기
STORAGE_ITEMS = {
    "아이폰 13", "아이폰 14", "아이폰 15",
    "갤럭시 S23", "갤럭시 S24", "갤럭시 Z플립5",
    "아이패드 9세대", "아이패드 에어 5",
}
STORAGE_OPTIONS = ["128GB", "256GB", "512GB"]

REGIONS = [
    "서울 강남구", "서울 마포구", "서울 송파구", "경기 성남시", "경기 수원시",
    "경기 안성시", "인천 부평구", "부산 해운대구", "대구 수성구", "대전 유성구",
    "광주 서구", "경기 고양시", "서울 노원구", "경기 용인시", "서울 강서구",
]

# 카테고리별 제목 꼬리표
TAGS_COMMON = ["급처", "직거래 환영", "택포", "에누리가능", "쿨거래시 네고"]
TAGS_LUX = ["정품", "더스트백 포함", "보증서 O", "풀구성", "정품 영수증 有", "감정 가능"]
TAGS_COSMETIC = ["미개봉", "잔량 90%+", "1~2회 사용", "정품 백화점 구매", "선물받은 새것"]


def round_price(price):
    """가격대에 따라 반올림 단위를 다르게(명품은 만원, 일반은 천원, 저가는 백원)."""
    if price >= 1_000_000:
        step = 10_000
    elif price >= 100_000:
        step = 1_000
    else:
        step = 100
    return int(round(price / step) * step)


def make_price(base, condition):
    price = base * CONDITION_FACTOR[condition]
    price *= random.uniform(0.92, 1.10)           # ±10% 개인차/흥정폭
    if random.random() < 0.06:                    # 가끔 급처 떨이
        price *= random.uniform(0.78, 0.88)
    return round_price(price)


def make_title(category, name, condition):
    parts = [name]
    if name in STORAGE_ITEMS:
        parts.append(random.choice(STORAGE_OPTIONS))

    if category == "명품":
        if random.random() < 0.8:
            parts.append(random.choice(TAGS_LUX))
        parts.append(random.choice(["판매합니다", "양도합니다", "정리합니다"]))
    elif category == "화장품·향수":
        if condition in ("미사용", "사용감 거의 없음"):
            parts.append(random.choice(TAGS_COSMETIC))
        parts.append(random.choice(["판매해요", "양도해요", "정리합니다"]))
    else:
        if condition in ("미사용", "사용감 거의 없음"):
            parts.append(random.choice(["S급", "미개봉급", "거의새것"]))
        parts.append(random.choice(["판매합니다", "팝니다", "내놓아요", "정리합니다"]))
        if random.random() < 0.45:
            parts.append(f"({random.choice(TAGS_COMMON)})")

    return " ".join(parts)


def main():
    today = datetime(2026, 6, 16)
    rows = []
    listing_id = 1000

    for category, name, base in PRODUCTS:
        count = random.randint(16, 30)         # 품목마다 매물 수를 다르게
        for _ in range(count):
            condition = random.choices(CONDITIONS, weights=CONDITION_WEIGHT)[0]
            price = make_price(base, condition)
            date = (today - timedelta(days=random.randint(0, 45))).strftime("%Y-%m-%d")
            rows.append({
                "id": listing_id,
                "category": category,
                "item_name": name,
                "title": make_title(category, name, condition),
                "condition": condition,
                "price": price,
                "region": random.choice(REGIONS),
                "date": date,
            })
            listing_id += 1

    random.shuffle(rows)

    out_path = os.path.join(os.path.dirname(__file__), "data", "listings.csv")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["id", "category", "item_name", "title",
                        "condition", "price", "region", "date"],
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"총 {len(rows)}건 / {len(PRODUCTS)}개 품목 데이터를 생성했습니다 -> {out_path}")


if __name__ == "__main__":
    main()
