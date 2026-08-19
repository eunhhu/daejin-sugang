#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Daejin University Course & Remaining Seat Inspector
===================================================
Inspects real-time course openings, remaining seats (여석), and confirmed cart/enrollment.
"""

import sys
import json
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://dreams2.daejin.ac.kr"
LOGIN_API_URL = f"{BASE_URL}/sugang/NLoginB"
CHECK_APPLY_URL = f"{BASE_URL}/sugang/new/sugang_wlsn04110.jsp"
CART_URL = f"{BASE_URL}/sugang/new/sugang_wlsn04120.jsp"


def get_authenticated_session(config_path="config.json"):
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": f"{BASE_URL}/sugang/new/loginForm.jsp"
    })
    
    data = {
        "stdNo": cfg["stdNo"],
        "passwd": cfg["passwd"],
        "user_flag": cfg.get("user_flag", "1")
    }
    r = session.post(LOGIN_API_URL, data=data)
    if "main.jsp" in r.text or "location.href" in r.text or r.status_code == 200:
        return session
    raise RuntimeError("Login failed. Check credentials in config.json")


def inspect_enrolled(session):
    print("\n📋 [현재 실시간 확정 수강신청 목록]")
    r = session.get(CHECK_APPLY_URL)
    soup = BeautifulSoup(r.content.decode("euc-kr", "replace"), "html.parser")
    for tr in soup.find_all("tr"):
        row = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
        if len(row) > 3:
            print(" | ".join(row))


def query_major_courses(session):
    print("\n📚 [스마트융합보안학과 전공과목 개설 및 잔여석]")
    url = f"{BASE_URL}/sugang/new/sugang_wlsn0417_3.jsp"
    r = session.get(url)
    soup = BeautifulSoup(r.content.decode("euc-kr", "replace"), "html.parser")
    for tr in soup.find_all("tr"):
        row = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
        if len(row) > 6:
            print(" | ".join(row))


def query_general_courses(session, area_code="B41001", sub_area=""):
    print(f"\n🎓 [교양과목 개설 및 잔여석 (영역: {area_code} / {sub_area})]")
    url = f"{BASE_URL}/sugang/new/sugang_wlsn0417_2.jsp?ic_kwa={area_code}&ic_kwa_1={sub_area}&ppage=1"
    r = session.get(url)
    soup = BeautifulSoup(r.content.decode("euc-kr", "replace"), "html.parser")
    for tr in soup.find_all("tr"):
        row = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
        if len(row) > 6:
            print(" | ".join(row))


if __name__ == "__main__":
    cfg_file = sys.argv[1] if len(sys.argv) > 1 else "config.json"
    session = get_authenticated_session(cfg_file)
    inspect_enrolled(session)
    query_major_courses(session)
    query_general_courses(session, "B41001") # 교양필수
