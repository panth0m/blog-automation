#!/usr/bin/env python3
"""키워드 레이더: 네이버 공식 API로 분야별 블로그 주제 순위를 만든다.

필요한 환경변수 (GitHub 저장소 Settings → Secrets → Actions 에 등록)
  NAVER_AD_API_KEY, NAVER_AD_SECRET, NAVER_AD_CUSTOMER_ID   검색광고 API (월 검색수, 연관 키워드)
  NAVER_CLIENT_ID, NAVER_CLIENT_SECRET                      개발자센터 앱 (블로그 검색 + 데이터랩)

출력: <out>/radar.json  (분야별 순위 + 내 글 순위)
표준 라이브러리만 쓴다.
"""
import argparse
import base64
import datetime as dt
import hashlib
import hmac
import json
import math
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

KST = dt.timezone(dt.timedelta(hours=9))
AD_BASE = "https://api.searchad.naver.com"
OPEN_BASE = "https://openapi.naver.com"

# 사진·영상이 잘 어울리는 주제인지 (영상감). 단순한 단어 규칙이다.
VISUAL_UP = ["맛집", "카페", "여행", "코디", "인테리어", "레시피", "요리", "디저트", "베이커리", "호캉스",
             "캠핑", "전시", "팝업", "네일", "헤어", "후기", "리뷰", "뷰", "풍경", "단풍", "축제", "꽃",
             "강아지", "고양이", "룩", "메이크업", "오마카세", "브런치", "케이크", "차박", "숙소", "펜션"]
VISUAL_DOWN = ["방법", "뜻", "신청", "조건", "계산", "서류", "자격", "기간", "세금", "정책", "보험", "연말정산",
               "청약", "금리", "대출", "지원금", "환급", "규정", "법", "증명서"]


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def need_env(names):
    missing = [n for n in names if not os.environ.get(n)]
    if missing:
        log("다음 시크릿이 없어요: " + ", ".join(missing))
        sys.exit(2)


def http(req, tries=3):
    for i in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")[:300]
            if e.code in (429, 500, 502, 503) and i < tries - 1:
                time.sleep(2 * (i + 1))
                continue
            raise RuntimeError(f"HTTP {e.code} {req.full_url[:120]} {body}")
        except urllib.error.URLError:
            if i < tries - 1:
                time.sleep(2 * (i + 1))
                continue
            raise


# ---------- 검색광고 API ----------

def ad_headers(method, uri):
    ts = str(int(time.time() * 1000))
    msg = f"{ts}.{method}.{uri}".encode()
    sig = base64.b64encode(hmac.new(os.environ["NAVER_AD_SECRET"].encode(), msg, hashlib.sha256).digest()).decode()
    return {
        "X-Timestamp": ts,
        "X-API-KEY": os.environ["NAVER_AD_API_KEY"],
        "X-Customer": os.environ["NAVER_AD_CUSTOMER_ID"],
        "X-Signature": sig,
    }


def to_int(v):
    if isinstance(v, (int, float)):
        return int(v)
    s = str(v).strip()
    if s.startswith("<"):
        return 5
    try:
        return int(float(s.replace(",", "")))
    except ValueError:
        return 0


def related_keywords(hints):
    """힌트 키워드(최대 5개)의 연관 키워드와 월 검색수."""
    uri = "/keywordstool"
    q = urllib.parse.urlencode({"hintKeywords": ",".join(h.replace(" ", "") for h in hints), "showDetail": "1"})
    req = urllib.request.Request(f"{AD_BASE}{uri}?{q}", headers=ad_headers("GET", uri))
    data = http(req)
    out = []
    for k in data.get("keywordList", []):
        pc, mo = to_int(k.get("monthlyPcQcCnt")), to_int(k.get("monthlyMobileQcCnt"))
        out.append({"keyword": k.get("relKeyword", ""), "pc": pc, "mobile": mo, "volume": pc + mo,
                    "comp": k.get("compIdx", "")})
    return out


# ---------- 개발자센터 API ----------

def open_headers():
    return {"X-Naver-Client-Id": os.environ["NAVER_CLIENT_ID"],
            "X-Naver-Client-Secret": os.environ["NAVER_CLIENT_SECRET"]}


def blog_search(query, display=1, start=1, sort="sim"):
    q = urllib.parse.urlencode({"query": query, "display": display, "start": start, "sort": sort})
    return http(urllib.request.Request(f"{OPEN_BASE}/v1/search/blog.json?{q}", headers=open_headers()))


def blog_doc_count(query):
    return int(blog_search(query).get("total", 0))


def datalab(keywords, start, end):
    """키워드마다 일별 상대 검색량. 한 번에 5개까지."""
    body = {"startDate": start, "endDate": end, "timeUnit": "date",
            "keywordGroups": [{"groupName": k, "keywords": [k]} for k in keywords]}
    h = open_headers()
    h["Content-Type"] = "application/json"
    req = urllib.request.Request(f"{OPEN_BASE}/v1/datalab/search", data=json.dumps(body).encode(), headers=h,
                                 method="POST")
    data = http(req)
    out = {}
    for r in data.get("results", []):
        out[r["title"]] = {d["period"]: d["ratio"] for d in r.get("data", [])}
    return out


# ---------- 점수 ----------

def clamp(x):
    return max(0, min(100, round(x)))


def series(daymap, start_day, days):
    return [float(daymap.get((start_day + dt.timedelta(days=i)).isoformat(), 0.0)) for i in range(days)]


def score_row(row):
    vol, docs, s = row["volume"], row["docs"], row.get("trend") or []
    attention = clamp(100 * math.log10(max(vol, 1)) / 5)  # 10만 회 = 100
    if len(s) >= 35:
        recent, before = sum(s[-7:]) / 7, sum(s[-35:-7]) / 28
        ratio = (recent + 0.5) / (before + 0.5)
    else:
        ratio = 1.0
    rising = clamp(50 + 50 * math.log2(ratio) / 1.5)  # 2.8배 = 100, 0.35배 = 0
    gap_ratio = vol / max(docs, 1)
    gap = clamp(50 + 25 * math.log10(max(gap_ratio, 1e-4)))  # 문서 1개당 검색 1회 = 50, 100회 = 100
    kw = row["keyword"]
    visual = 50 + 15 * sum(w in kw for w in VISUAL_UP) - 15 * sum(w in kw for w in VISUAL_DOWN)
    visual = clamp(visual)
    total = clamp(0.3 * attention + 0.25 * rising + 0.35 * gap + 0.1 * visual)
    row.update({"attention": attention, "rising": rising, "gap": gap, "visual": visual, "total": total,
                "trend_ratio": round(ratio, 2), "gap_ratio": round(gap_ratio, 3)})
    # 화면용으로 최근 28일만 정수로
    row["spark"] = [round(v) for v in s[-28:]]
    row.pop("trend", None)
    return row


# ---------- 내 글 순위 ----------

def find_rank(keyword, blog_ids, depth):
    ids = [b.lower() for b in blog_ids if b]
    if not ids:
        return None
    for start in range(1, min(depth, 1000) + 1, 100):
        res = blog_search(keyword, display=100, start=start)
        items = res.get("items", [])
        for i, it in enumerate(items):
            hay = (it.get("link", "") + " " + it.get("bloggerlink", "")).lower()
            if any(b in hay for b in ids):
                title = it.get("title", "").replace("<b>", "").replace("</b>", "")
                return {"rank": start + i, "title": title, "link": it.get("link", "")}
        if len(items) < 100:
            break
        time.sleep(0.15)
    return {"rank": None}


# ---------- 실행 ----------

def build(cfg, only=None):
    today = dt.datetime.now(KST).date()
    end = today - dt.timedelta(days=1)
    start = end - dt.timedelta(days=34)
    out = {"generated_at": dt.datetime.now(KST).isoformat(timespec="minutes"), "categories": [], "rank": [],
           "errors": []}
    for cat in cfg["categories"]:
        if only and cat["id"] not in only:
            continue
        log(f"[{cat['name']}] 연관 키워드 모으는 중")
        pool = {}
        seeds = cat["seeds"]
        for i in range(0, len(seeds), 5):
            try:
                for k in related_keywords(seeds[i:i + 5]):
                    if cfg["min_volume"] <= k["volume"] <= cfg["max_volume"]:
                        pool.setdefault(k["keyword"], k)
            except Exception as e:  # 한 분야가 실패해도 나머지는 계속
                out["errors"].append(f"{cat['id']} keywordstool: {e}")
            time.sleep(0.3)
        # 검색수 상위 후보만 정밀 계산 (API 한도 보호)
        cands = sorted(pool.values(), key=lambda r: -r["volume"])[: cfg["per_category"] * 2]
        for r in cands:
            try:
                r["docs"] = blog_doc_count(r["keyword"])
            except Exception as e:
                r["docs"] = 0
                out["errors"].append(f"{r['keyword']} docs: {e}")
            time.sleep(0.12)
        for i in range(0, len(cands), 5):
            chunk = cands[i:i + 5]
            try:
                trends = datalab([r["keyword"] for r in chunk], start.isoformat(), end.isoformat())
                for r in chunk:
                    r["trend"] = series(trends.get(r["keyword"], {}), start, 35)
            except Exception as e:
                out["errors"].append(f"{cat['id']} datalab: {e}")
            time.sleep(0.2)
        rows = sorted((score_row(r) for r in cands), key=lambda r: -r["total"])[: cfg["per_category"]]
        out["categories"].append({"id": cat["id"], "name": cat["name"], "rows": rows})
        log(f"[{cat['name']}] {len(rows)}개")
    blogs = cfg.get("my_blogs", [])
    for w in cfg.get("rank_watch", []):
        kw = w["keyword"] if isinstance(w, dict) else str(w)
        ids = [w["blog"]] if isinstance(w, dict) and w.get("blog") else blogs
        try:
            r = find_rank(kw, ids, cfg.get("rank_depth", 300)) or {"rank": None}
        except Exception as e:
            r = {"rank": None, "error": str(e)[:200]}
        out["rank"].append({"keyword": kw, "blogs": ids, **r, "checked_at": out["generated_at"]})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=os.path.join(os.path.dirname(__file__), "config.json"))
    ap.add_argument("--out", default="out")
    ap.add_argument("--only", nargs="*", help="이 분야 id만 (테스트용)")
    a = ap.parse_args()
    need_env(["NAVER_AD_API_KEY", "NAVER_AD_SECRET", "NAVER_AD_CUSTOMER_ID", "NAVER_CLIENT_ID",
              "NAVER_CLIENT_SECRET"])
    with open(a.config, encoding="utf-8") as f:
        cfg = json.load(f)
    data = build(cfg, a.only)
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "radar.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    n = sum(len(c["rows"]) for c in data["categories"])
    log(f"완료: 분야 {len(data['categories'])}개, 주제 {n}개, 순위 {len(data['rank'])}개, 오류 {len(data['errors'])}개")
    for e in data["errors"][:20]:
        log("  -", e)
    if n == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
