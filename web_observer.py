#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Daejin University Real-time Course Vacancy Observer (대진대 수강신청 실시간 빈자리 옵저버)
=======================================================================================
- Features:
  1. Automated high-speed background scraper for all Major and General Education courses.
  2. Live In-Memory Course State & Vacancy Change Event History.
  3. Web UI Dashboard with real-time search, filters, vacancy sound alerts, and 1-click code copying.
  4. REST API (/api/data, /api/events, /api/status).
"""

import os
import sys
import time
import json
import re
import random
import logging
import threading
import datetime
import requests

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

from flask import Flask, jsonify, render_template_string, request

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s][%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("WebObserver")

KST = datetime.timezone(datetime.timedelta(hours=9))

BASE_URL = "https://dreams2.daejin.ac.kr"
LOGIN_API_URL = f"{BASE_URL}/sugang/NLoginB"
GE_QUERY_URL = f"{BASE_URL}/sugang/new/sugang_wlsn0417_2.jsp"
MAJOR_QUERY_URL = f"{BASE_URL}/sugang/new/sugang_wlsn0417_3.jsp"

app = Flask(__name__)

# Global In-Memory Store
course_db = {}
event_history = []
stats = {
    "total_courses": 0,
    "open_courses": 0,
    "events_count": 0,
    "last_scraped_at": "-",
    "scrape_latency_ms": 0,
    "status": "Initializing"
}
db_lock = threading.Lock()


class CourseCrawler(threading.Thread):
    def __init__(self, config_path="config.json"):
        super().__init__(daemon=True)
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)

        self.std_no = self.config.get("stdNo")
        self.passwd = self.config.get("passwd")
        self.user_flag = self.config.get("user_flag", "1")

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Referer": f"{BASE_URL}/sugang/new/main.jsp",
            "Origin": BASE_URL
        })
        self.last_login_time = 0

        # Categories to scrape
        self.ge_categories = [
            {"kwa": "B41001", "name": "교양필수 (사고와표현/영읽토/대순/AI컴퓨팅)"},
            {"kwa": "B41002", "name": "AI·디지털리터러시 & 교양선택"},
            {"kwa": "B41003", "name": "인간과사회 (교선)"},
            {"kwa": "B41004", "name": "과학과기술 (교선)"},
            {"kwa": "B41005", "name": "예술과체육 (교선)"},
            {"kwa": "B41006", "name": "글로벌과세계 (교선)"},
            {"kwa": "B41007", "name": "융복합과진로 (교선)"}
        ]

    def login(self):
        login_data = {
            "stdNo": self.std_no,
            "passwd": self.passwd,
            "user_flag": self.user_flag
        }
        try:
            r = self.session.post(LOGIN_API_URL, data=login_data, timeout=5)
            text = r.content.decode("euc-kr", "replace")
            if "main.jsp" in text or "location.href" in text or r.status_code == 200:
                self.last_login_time = time.time()
                logger.info("✅ Scraper session active.")
                return True
            return False
        except Exception as e:
            logger.error(f"Login error: {e}")
            return False

    def ensure_session(self):
        if time.time() - self.last_login_time > 600:
            self.login()

    def parse_table_html(self, html, category_name):
        courses = []
        if BeautifulSoup:
            soup = BeautifulSoup(html, "html.parser")
            for tr in soup.find_all("tr"):
                row = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
                if len(row) >= 10 and "-" in row[1] and len(row[1]) == 9:
                    code_parts = row[1].split("-")
                    code = code_parts[0]
                    bun = code_parts[1]
                    full_code = f"{code}{bun}"

                    enrolled = int(row[7]) if row[7].isdigit() else 0
                    seats = int(row[8]) if row[8].isdigit() else 0
                    credits_val = row[9] if len(row) > 9 else "2"
                    room = row[10] if len(row) > 10 else ""
                    remarks = row[11] if len(row) > 11 else ""

                    courses.append({
                        "full_code": full_code,
                        "code": code,
                        "bun": bun,
                        "name": row[3],
                        "prof": row[4],
                        "time": row[5],
                        "type": row[6] if len(row) > 6 else "",
                        "enrolled": enrolled,
                        "seats": seats,
                        "credits": credits_val,
                        "room": room,
                        "remarks": remarks,
                        "category": category_name,
                        "status": "OPEN" if seats > 0 else "FULL"
                    })
        else:
            # Pure regex table row parsing
            rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL)
            for tr in rows:
                cols = [re.sub(r'<[^>]+>', '', c).strip() for c in re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', tr, re.DOTALL)]
                if len(cols) >= 10 and "-" in cols[1] and len(cols[1]) == 9:
                    code_parts = cols[1].split("-")
                    code = code_parts[0]
                    bun = code_parts[1]
                    full_code = f"{code}{bun}"

                    enrolled = int(cols[7]) if cols[7].isdigit() else 0
                    seats = int(cols[8]) if cols[8].isdigit() else 0
                    credits_val = cols[9] if len(cols) > 9 else "2"
                    room = cols[10] if len(cols) > 10 else ""
                    remarks = cols[11] if len(cols) > 11 else ""

                    courses.append({
                        "full_code": full_code,
                        "code": code,
                        "bun": bun,
                        "name": cols[3],
                        "prof": cols[4],
                        "time": cols[5],
                        "type": cols[6] if len(cols) > 6 else "",
                        "enrolled": enrolled,
                        "seats": seats,
                        "credits": credits_val,
                        "room": room,
                        "remarks": remarks,
                        "category": category_name,
                        "status": "OPEN" if seats > 0 else "FULL"
                    })
        return courses

    def scrape_cycle(self):
        self.ensure_session()
        t0 = time.perf_counter()
        scraped_courses = []

        # 1. Scrape Major Courses (Smart Convergence Security)
        try:
            r = self.session.get(MAJOR_QUERY_URL, timeout=4)
            html = r.content.decode("euc-kr", "replace")
            major_courses = self.parse_table_html(html, "스마트융합보안학과 전공")
            scraped_courses.extend(major_courses)
        except Exception as e:
            logger.warning(f"Major scrape error: {e}")

        # 2. Scrape General Education Categories
        for cat in self.ge_categories:
            try:
                url = f"{GE_QUERY_URL}?ic_kwa={cat['kwa']}&ppage=1"
                r = self.session.get(url, timeout=4)
                html = r.content.decode("euc-kr", "replace")
                ge_courses = self.parse_table_html(html, cat["name"])
                scraped_courses.extend(ge_courses)
            except Exception as e:
                logger.warning(f"GE scrape error ({cat['name']}): {e}")

        elapsed_ms = (time.perf_counter() - t0) * 1000

        # Update Course DB and detect vacancy changes
        now_str = datetime.datetime.now(KST).strftime("%H:%M:%S")
        open_count = 0

        with db_lock:
            for c in scraped_courses:
                key = c["full_code"]
                prev = course_db.get(key)
                
                # Check for vacancy change event (e.g. 0 -> 1+ seats or seats increased)
                if prev:
                    if prev["seats"] == 0 and c["seats"] > 0:
                        event_msg = f"🔥 [빈자리 발생!] {c['name']} ({c['code']}-{c['bun']}) {c['seats']}석 오픈! (교수: {c['prof']} / 시간: {c['time']})"
                        event_history.insert(0, {
                            "time": now_str,
                            "type": "VACANCY_OPEN",
                            "code": c["code"],
                            "bun": c["bun"],
                            "name": c["name"],
                            "seats": c["seats"],
                            "msg": event_msg
                        })
                        logger.info(event_msg)
                    elif prev["seats"] > 0 and c["seats"] == 0:
                        event_history.insert(0, {
                            "time": now_str,
                            "type": "VACANCY_FILLED",
                            "code": c["code"],
                            "bun": c["bun"],
                            "name": c["name"],
                            "seats": 0,
                            "msg": f"⏳ [마감] {c['name']} ({c['code']}-{c['bun']}) 잔여석 소진 (마감)"
                        })
                
                c["last_updated"] = now_str
                course_db[key] = c
                if c["seats"] > 0:
                    open_count += 1

            # Keep only last 50 events
            if len(event_history) > 50:
                event_history[:] = event_history[:50]

            stats["total_courses"] = len(course_db)
            stats["open_courses"] = open_count
            stats["events_count"] = len(event_history)
            stats["last_scraped_at"] = now_str
            stats["scrape_latency_ms"] = round(elapsed_ms, 1)
            stats["status"] = "Live Monitoring"

    def run(self):
        logger.info("🚀 Course Crawler background thread started.")
        self.login()
        while True:
            try:
                self.scrape_cycle()
            except Exception as e:
                logger.error(f"Crawler cycle exception: {e}")
            time.sleep(2.5) # Fast 2.5s scrape interval


# ==============================================================================
# Web Routes & REST API
# ==============================================================================

@app.route("/api/data")
def get_data():
    with db_lock:
        courses_list = list(course_db.values())
        events_list = list(event_history[:15])
        current_stats = dict(stats)
    return jsonify({
        "stats": current_stats,
        "events": events_list,
        "courses": courses_list
    })


@app.route("/")
def index():
    html = """
<!DOCTYPE html>
<html lang="ko" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>대진대 수강신청 실시간 빈자리 옵저버</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <script>
    tailwind.config = {
      darkMode: 'class',
      theme: {
        extend: {
          colors: {
            brand: '#3b82f6',
            brandDark: '#1e3a8a',
            surface: '#18181b',
            surfaceCard: '#27272a',
            surfaceBorder: '#3f3f46'
          }
        }
      }
    }
  </script>
  <style>
    @keyframes pulse-fast { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
    .live-dot { animation: pulse-fast 1.5s cubic-bezier(0.4, 0, 0.6, 1) infinite; }
  </style>
</head>
<body class="bg-zinc-950 text-zinc-100 min-h-screen font-sans antialiased selection:bg-blue-500 selection:text-white">

  <!-- Header -->
  <header class="border-b border-zinc-800 bg-zinc-900/80 backdrop-blur sticky top-0 z-50">
    <div class="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
      <div class="flex items-center gap-3">
        <div class="w-9 h-9 rounded-xl bg-blue-600/20 border border-blue-500/30 flex items-center justify-center text-blue-400">
          <i class="fa-solid fa-radar text-lg"></i>
        </div>
        <div>
          <h1 class="text-lg font-bold flex items-center gap-2">
            대진대 수강신청 실시간 옵저버
            <span class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 live-dot"></span> LIVE
            </span>
          </h1>
          <p class="text-xs text-zinc-400">실시간 강좌 잔여석 및 취소표 감지 시스템</p>
        </div>
      </div>
      
      <div class="flex items-center gap-3 text-xs">
        <div class="hidden sm:flex items-center gap-2 bg-zinc-800/60 px-3 py-1.5 rounded-lg border border-zinc-700/50">
          <i class="fa-solid fa-server text-zinc-400"></i>
          <span class="text-zinc-400">서버 갱신:</span>
          <span id="lastUpdated" class="font-mono text-zinc-200">-</span>
          <span class="text-zinc-500">|</span>
          <span id="scrapeLatency" class="font-mono text-blue-400">-ms</span>
        </div>
        <button id="soundToggle" onclick="toggleSound()" class="px-3 py-1.5 rounded-lg bg-zinc-800 border border-zinc-700 hover:bg-zinc-700 transition flex items-center gap-1.5 text-zinc-300">
          <i id="soundIcon" class="fa-solid fa-bell"></i>
          <span id="soundLabel">알림음 ON</span>
        </button>
      </div>
    </div>
  </header>

  <main class="max-w-7xl mx-auto px-4 py-6 space-y-6">

    <!-- KPI Metric Cards -->
    <div class="grid grid-cols-2 sm:grid-cols-4 gap-4">
      <div class="bg-zinc-900 border border-zinc-800 p-4 rounded-2xl">
        <div class="text-xs text-zinc-400 font-medium mb-1">총 모니터링 강좌</div>
        <div id="statTotal" class="text-2xl font-bold text-zinc-100 font-mono">0</div>
        <div class="text-[11px] text-zinc-500 mt-1">전공 + 교양 전 영역</div>
      </div>
      <div class="bg-zinc-900 border border-zinc-800 p-4 rounded-2xl relative overflow-hidden">
        <div class="absolute right-3 top-3 w-8 h-8 rounded-full bg-emerald-500/10 flex items-center justify-center text-emerald-400 text-xs font-bold">
          <i class="fa-solid fa-door-open"></i>
        </div>
        <div class="text-xs text-emerald-400 font-medium mb-1">현재 빈자리 강좌</div>
        <div id="statOpen" class="text-2xl font-bold text-emerald-400 font-mono">0</div>
        <div class="text-[11px] text-zinc-500 mt-1">즉시 신청 가능한 강좌</div>
      </div>
      <div class="bg-zinc-900 border border-zinc-800 p-4 rounded-2xl">
        <div class="text-xs text-zinc-400 font-medium mb-1">취소표 감지 피드</div>
        <div id="statEvents" class="text-2xl font-bold text-amber-400 font-mono">0</div>
        <div class="text-[11px] text-zinc-500 mt-1">오늘 감지된 변동 건수</div>
      </div>
      <div class="bg-zinc-900 border border-zinc-800 p-4 rounded-2xl">
        <div class="text-xs text-zinc-400 font-medium mb-1">모니터링 상태</div>
        <div id="statStatus" class="text-lg font-bold text-blue-400 truncate">정상 가동</div>
        <div class="text-[11px] text-zinc-500 mt-1">2.5초 주기 실시간 갱신</div>
      </div>
    </div>

    <!-- Live Vacancy Alert Feed Ticker -->
    <div class="bg-zinc-900/90 border border-zinc-800 rounded-2xl p-4">
      <div class="flex items-center justify-between mb-2">
        <h2 class="text-sm font-bold flex items-center gap-2 text-zinc-200">
          <i class="fa-solid fa-bolt text-amber-400"></i> 실시간 취소표 발생 피드
        </h2>
        <span class="text-[11px] text-zinc-500">최근 15건 실시간 스트림</span>
      </div>
      <div id="eventsContainer" class="space-y-1.5 max-h-32 overflow-y-auto pr-1 text-xs font-mono">
        <div class="text-zinc-500 italic py-2 text-center">아직 감지된 취소표 이벤트가 없습니다. 실시간 감시 중...</div>
      </div>
    </div>

    <!-- Filter & Search Controls -->
    <div class="bg-zinc-900 border border-zinc-800 p-4 rounded-2xl space-y-3">
      <div class="flex flex-col md:flex-row gap-3">
        <!-- Search Input -->
        <div class="relative flex-1">
          <i class="fa-solid fa-magnifying-glass absolute left-3.5 top-3 text-zinc-500 text-sm"></i>
          <input id="searchInput" type="text" placeholder="과목명, 교수명, 학수번호(6자리) 검색..." 
                 class="w-full pl-10 pr-4 py-2 bg-zinc-950 border border-zinc-800 rounded-xl text-sm text-zinc-200 placeholder-zinc-500 focus:outline-none focus:border-blue-500 transition"
                 oninput="renderCourses()">
        </div>

        <!-- Category Dropdown -->
        <select id="categoryFilter" onchange="renderCourses()"
                class="bg-zinc-950 border border-zinc-800 rounded-xl px-3 py-2 text-sm text-zinc-200 focus:outline-none focus:border-blue-500">
          <option value="ALL">전체 영역 / 학과</option>
          <option value="스마트융합보안">스마트융합보안학과 전공</option>
          <option value="교양필수">교양필수 (사표/영읽토/대순)</option>
          <option value="AI·디지털">AI·디지털리터러시</option>
          <option value="인간과사회">인간과사회</option>
          <option value="과학과기술">과학과기술</option>
          <option value="예술과체육">예술과체육</option>
        </select>

        <!-- Toggle Open Only -->
        <label class="flex items-center gap-2 cursor-pointer bg-zinc-950 border border-zinc-800 px-4 py-2 rounded-xl text-sm font-medium hover:bg-zinc-800/50 transition select-none">
          <input id="openOnlyToggle" type="checkbox" onchange="renderCourses()" class="w-4 h-4 rounded text-emerald-500 focus:ring-0 bg-zinc-900 border-zinc-700">
          <span class="text-emerald-400 flex items-center gap-1.5">
            <i class="fa-solid fa-sparkles"></i> 빈자리만 보기
          </span>
        </label>
      </div>
    </div>

    <!-- Courses Table -->
    <div class="bg-zinc-900 border border-zinc-800 rounded-2xl overflow-hidden">
      <div class="px-4 py-3 border-b border-zinc-800 flex items-center justify-between text-xs text-zinc-400">
        <span id="filteredCount">0개 강좌 표시 중</span>
        <span>클릭하여 학수번호-분반 복사</span>
      </div>

      <div class="overflow-x-auto">
        <table class="w-full text-left text-sm">
          <thead class="bg-zinc-950/70 text-zinc-400 text-xs uppercase border-b border-zinc-800">
            <tr>
              <th class="py-3 px-4">상태</th>
              <th class="py-3 px-4">학수-분반</th>
              <th class="py-3 px-4">교과목명</th>
              <th class="py-3 px-4">담당교수</th>
              <th class="py-3 px-4">강의시간</th>
              <th class="py-3 px-4">신청/여석</th>
              <th class="py-3 px-4">영역/학과</th>
              <th class="py-3 px-4 text-right">복사</th>
            </tr>
          </thead>
          <tbody id="courseTableBody" class="divide-y divide-zinc-800/60 font-sans">
            <tr>
              <td colspan="8" class="text-center py-8 text-zinc-500">데이터를 불러오는 중입니다...</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

  </main>

  <audio id="alertAudio" src="https://assets.mixkit.co/active_storage/sfx/2869/2869-preview.mp3" preload="auto"></audio>

  <script>
    let allCourses = [];
    let soundEnabled = true;
    let knownOpenKeys = new Set();

    function toggleSound() {
      soundEnabled = !soundEnabled;
      document.getElementById('soundIcon').className = soundEnabled ? 'fa-solid fa-bell' : 'fa-solid fa-bell-slash';
      document.getElementById('soundLabel').innerText = soundEnabled ? '알림음 ON' : '알림음 OFF';
    }

    function playBeep() {
      if (!soundEnabled) return;
      const audio = document.getElementById('alertAudio');
      if (audio) {
        audio.currentTime = 0;
        audio.play().catch(() => {});
      }
    }

    function copyToClipboard(text, btn) {
      navigator.clipboard.writeText(text).then(() => {
        const oldHtml = btn.innerHTML;
        btn.innerHTML = '<i class="fa-solid fa-check text-emerald-400"></i>';
        setTimeout(() => { btn.innerHTML = oldHtml; }, 1200);
      });
    }

    async function fetchData() {
      try {
        const res = await fetch('/api/data');
        const data = await res.json();

        // Update Stats
        document.getElementById('statTotal').innerText = data.stats.total_courses;
        document.getElementById('statOpen').innerText = data.stats.open_courses;
        document.getElementById('statEvents').innerText = data.stats.events_count;
        document.getElementById('statStatus').innerText = data.stats.status;
        document.getElementById('lastUpdated').innerText = data.stats.last_scraped_at;
        document.getElementById('scrapeLatency').innerText = data.stats.scrape_latency_ms + 'ms';

        // Check for new vacancies and play sound
        let hasNewVacancy = false;
        data.courses.forEach(c => {
          if (c.seats > 0 && !knownOpenKeys.has(c.full_code)) {
            knownOpenKeys.add(c.full_code);
            hasNewVacancy = true;
          } else if (c.seats === 0 && knownOpenKeys.has(c.full_code)) {
            knownOpenKeys.delete(c.full_code);
          }
        });

        if (hasNewVacancy) {
          playBeep();
        }

        // Update Events Feed
        renderEvents(data.events);

        // Update Courses
        allCourses = data.courses;
        renderCourses();

      } catch (err) {
        console.error('Fetch error:', err);
      }
    }

    function renderEvents(events) {
      const container = document.getElementById('eventsContainer');
      if (!events || events.length === 0) {
        container.innerHTML = '<div class="text-zinc-500 italic py-2 text-center">아직 감지된 취소표 이벤트가 없습니다. 실시간 감시 중...</div>';
        return;
      }

      container.innerHTML = events.map(e => {
        const isOpen = e.type === 'VACANCY_OPEN';
        return `
          <div class="flex items-center justify-between py-1 px-2.5 rounded-lg ${isOpen ? 'bg-emerald-500/10 border border-emerald-500/20 text-emerald-300' : 'bg-zinc-800/40 text-zinc-400'}">
            <div class="flex items-center gap-2 truncate">
              <span class="text-zinc-500 font-mono text-[10px]">[${e.time}]</span>
              <span class="font-bold ${isOpen ? 'text-emerald-400' : 'text-zinc-400'}">${e.name} (${e.code}-${e.bun})</span>
              <span>${isOpen ? '🔥 ' + e.seats + '자리 발생!' : '마감'}</span>
            </div>
            <button onclick="copyToClipboard('${e.code}${e.bun}', this)" class="text-[10px] px-2 py-0.5 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-300 transition">
              복사
            </button>
          </div>
        `;
      }).join('');
    }

    function renderCourses() {
      const search = document.getElementById('searchInput').value.trim().toLowerCase();
      const cat = document.getElementById('categoryFilter').value;
      const openOnly = document.getElementById('openOnlyToggle').checked;

      const filtered = allCourses.filter(c => {
        if (openOnly && c.seats <= 0) return false;
        if (cat !== 'ALL' && !c.category.includes(cat)) return false;
        if (search) {
          const matchCode = c.full_code.toLowerCase().includes(search) || c.code.toLowerCase().includes(search);
          const matchName = c.name.toLowerCase().includes(search);
          const matchProf = c.prof.toLowerCase().includes(search);
          const matchTime = c.time.toLowerCase().includes(search);
          if (!matchCode && !matchName && !matchProf && !matchTime) return false;
        }
        return true;
      });

      // Sort: Open seats first, then by code
      filtered.sort((a, b) => b.seats - a.seats || a.code.localeCompare(b.code));

      document.getElementById('filteredCount').innerText = `${filtered.length}개 강좌 표시 중`;

      const tbody = document.getElementById('courseTableBody');
      if (filtered.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="text-center py-8 text-zinc-500">조건에 맞는 강좌가 없습니다.</td></tr>';
        return;
      }

      tbody.innerHTML = filtered.map(c => {
        const isOpen = c.seats > 0;
        return `
          <tr class="hover:bg-zinc-800/40 transition border-b border-zinc-800/40 ${isOpen ? 'bg-emerald-950/20' : ''}">
            <td class="py-3 px-4 whitespace-nowrap">
              ${isOpen 
                ? `<span class="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                     <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 live-dot"></span> ${c.seats}석 오픈!
                   </span>`
                : `<span class="inline-flex items-center px-2 py-0.5 rounded text-xs text-zinc-500 bg-zinc-800/50">마감</span>`
              }
            </td>
            <td class="py-3 px-4 font-mono font-bold text-zinc-200 whitespace-nowrap">
              ${c.code}-${c.bun}
            </td>
            <td class="py-3 px-4 font-medium text-zinc-100">
              ${c.name}
              <span class="text-xs text-zinc-500 block sm:inline">(${c.credits}학점)</span>
            </td>
            <td class="py-3 px-4 text-zinc-300 whitespace-nowrap">${c.prof || '-'}</td>
            <td class="py-3 px-4 text-zinc-400 font-mono text-xs whitespace-nowrap">${c.time || '-'}</td>
            <td class="py-3 px-4 whitespace-nowrap font-mono text-xs">
              <span class="text-zinc-400">${c.enrolled}</span>
              <span class="text-zinc-600">/</span>
              <span class="${isOpen ? 'text-emerald-400 font-bold text-sm' : 'text-zinc-500'}">${c.seats}</span>
            </td>
            <td class="py-3 px-4 text-xs text-zinc-400 truncate max-w-xs">${c.category}</td>
            <td class="py-3 px-4 text-right whitespace-nowrap">
              <button onclick="copyToClipboard('${c.code}${c.bun}', this)" 
                      title="학수번호 ${c.code}${c.bun} 복사"
                      class="px-2.5 py-1 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-xs text-zinc-300 transition border border-zinc-700/60 flex items-center gap-1 ml-auto">
                <i class="fa-regular fa-copy"></i>
                <span>${c.code}</span>
              </button>
            </td>
          </tr>
        `;
      }).join('');
    }

    // Polling loop every 2 seconds
    fetchData();
    setInterval(fetchData, 2000);
  </script>
</body>
</html>
    """
    return render_template_string(html)


def main():
    cfg_path = sys.argv[1] if len(sys.argv) > 1 else "config.json"
    crawler = CourseCrawler(cfg_path)
    crawler.start()
    
    port = int(os.environ.get("PORT", 8888))
    logger.info(f"🌐 Daejin Sugang Web Observer starting on http://0.0.0.0:{port}...")
    app.run(host="0.0.0.0", port=port, debug=False)


if __name__ == "__main__":
    main()
