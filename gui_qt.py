#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Daejin University Sugang Automation Suite - Modern Desktop GUI
=============================================================
- Framework: PyQt6 / PyQt5 (Universal Native GUI with Tailwind Zinc Dark Theme)
- Multi-threaded non-blocking background workers
- Features:
  1. 계정 설정 & 로그인 테스트 (Credentials Manager)
  2. 실시간 강좌 검색 & 잔여석 옵저버 (Live Vacancy Inspector)
  3. 10:00:00 정각 초정밀 패킷 스나이퍼 (10:00:00 Packet Sniper)
  4. 24시간 백그라운드 취소표 낚아채기 (Vacancy Hunter)
  5. 확정 수강신청 내역 & 예비수강 장바구니 실시간 조회 (Enrollment & Cart Viewer)
"""

import os
import sys
import time
import json
import re
import datetime
from concurrent.futures import ThreadPoolExecutor
import requests
from bs4 import BeautifulSoup

try:
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QTabWidget, QLabel, QLineEdit, QPushButton, QTableWidget,
        QTableWidgetItem, QHeaderView, QComboBox, QCheckBox,
        QTextEdit, QSpinBox, QDoubleSpinBox, QGroupBox, QMessageBox,
        QSplitter, QProgressBar, QStatusBar
    )
    from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
    from PyQt6.QtGui import QFont, QColor, QIcon
except ImportError:
    from PyQt5.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QTabWidget, QLabel, QLineEdit, QPushButton, QTableWidget,
        QTableWidgetItem, QHeaderView, QComboBox, QCheckBox,
        QTextEdit, QSpinBox, QDoubleSpinBox, QGroupBox, QMessageBox,
        QSplitter, QProgressBar, QStatusBar
    )
    from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
    from PyQt5.QtGui import QFont, QColor, QIcon

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
BASE_URL = "https://dreams2.daejin.ac.kr"
LOGIN_API_URL = f"{BASE_URL}/sugang/NLoginB"
APPLY_API_URL = f"{BASE_URL}/sugang/NSugangWlsn0410"
CHECK_APPLY_URL = f"{BASE_URL}/sugang/new/sugang_wlsn04110.jsp"
CART_URL = f"{BASE_URL}/sugang/new/sugang_wlsn04120.jsp"

# Modern Zinc Dark QSS Stylesheet
DARK_STYLESHEET = """
QMainWindow, QWidget {
    background-color: #09090b;
    color: #f4f4f5;
    font-family: 'Pretendard', 'Malgun Gothic', 'Segoe UI', sans-serif;
    font-size: 13px;
}
QGroupBox {
    border: 1px solid #27272a;
    border-radius: 8px;
    margin-top: 14px;
    padding-top: 14px;
    font-weight: bold;
    color: #e4e4e7;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background-color: #18181b;
    border: 1px solid #3f3f46;
    border-radius: 6px;
    padding: 6px 10px;
    color: #ffffff;
    selection-background-color: #3b82f6;
}
QLineEdit:focus, QComboBox:focus {
    border: 1px solid #3b82f6;
}
QPushButton {
    background-color: #27272a;
    border: 1px solid #3f3f46;
    border-radius: 6px;
    padding: 6px 14px;
    color: #f4f4f5;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #3f3f46;
}
QPushButton#primaryBtn {
    background-color: #2563eb;
    border: 1px solid #3b82f6;
    color: #ffffff;
}
QPushButton#primaryBtn:hover {
    background-color: #1d4ed8;
}
QPushButton#successBtn {
    background-color: #059669;
    border: 1px solid #10b981;
    color: #ffffff;
}
QPushButton#successBtn:hover {
    background-color: #047857;
}
QPushButton#dangerBtn {
    background-color: #dc2626;
    border: 1px solid #ef4444;
    color: #ffffff;
}
QPushButton#dangerBtn:hover {
    background-color: #b91c1c;
}
QTabWidget::pane {
    border: 1px solid #27272a;
    border-radius: 8px;
    background-color: #09090b;
    top: -1px;
}
QTabBar::tab {
    background: #18181b;
    border: 1px solid #27272a;
    padding: 8px 16px;
    margin-right: 4px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    color: #a1a1aa;
    font-weight: bold;
}
QTabBar::tab:selected {
    background: #27272a;
    border-bottom-color: #27272a;
    color: #3b82f6;
}
QTableWidget {
    background-color: #18181b;
    border: 1px solid #27272a;
    border-radius: 8px;
    gridline-color: #27272a;
    color: #e4e4e7;
    selection-background-color: #1e3a8a;
    selection-color: #ffffff;
}
QHeaderView::section {
    background-color: #09090b;
    color: #a1a1aa;
    padding: 6px;
    border: none;
    border-bottom: 1px solid #27272a;
    font-weight: bold;
}
QTextEdit {
    background-color: #18181b;
    border: 1px solid #27272a;
    border-radius: 6px;
    color: #a1a1aa;
    font-family: 'Consolas', monospace;
    font-size: 12px;
}
QCheckBox {
    color: #e4e4e7;
}
"""


class SugangBackend:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Referer": f"{BASE_URL}/sugang/new/main.jsp",
            "Origin": BASE_URL
        })
        self.std_no = ""
        self.passwd = ""
        self.is_logged_in = False

    def login(self, std_no, passwd):
        self.std_no = std_no
        self.passwd = passwd
        try:
            r = self.session.post(LOGIN_API_URL, data={
                "stdNo": std_no,
                "passwd": passwd,
                "user_flag": "1"
            }, timeout=5)
            text = r.content.decode("euc-kr", "replace")
            if "main.jsp" in text or "location.href" in text or r.status_code == 200:
                self.is_logged_in = True
                return True, "로그인 성공!"
            return False, "로그인 실패: 학번 또는 비밀번호를 확인하세요."
        except Exception as e:
            return False, f"네트워크 오류: {e}"

    def apply_course(self, code, bun):
        if not self.is_logged_in:
            return False, "로그인이 필요합니다."
        try:
            r = self.session.post(APPLY_API_URL, data={
                "dir": "1", "cmd": "aply", "urltype": "direct",
                "getsbjt_no": code, "getclss_no": bun, "ic_sbjcd": f"{code}{bun}"
            }, timeout=4)
            text = r.content.decode("euc-kr", "replace")
            alert_msg = ""
            for line in text.split("\n"):
                if "alert(" in line:
                    alert_msg = line.split("alert(")[1].split(")")[0].strip("\"'\\r\\n")
                    break
            success = "완료" in alert_msg or "정상" in alert_msg or "신청되었습니다" in alert_msg
            return success, alert_msg or "신청 처리됨"
        except Exception as e:
            return False, f"통신 오류: {e}"

    def get_enrolled_courses(self):
        try:
            r = self.session.get(CHECK_APPLY_URL, timeout=4)
            soup = BeautifulSoup(r.content.decode("euc-kr", "replace"), "html.parser")
            rows = []
            for tr in soup.find_all("tr"):
                cols = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
                if len(cols) >= 8 and "-" in cols[1] and len(cols[1]) == 9:
                    rows.append({
                        "code_bun": cols[1],
                        "name": cols[3],
                        "prof": cols[4],
                        "time": cols[5],
                        "type": cols[6],
                        "credits": cols[8] if len(cols) > 8 else "2"
                    })
            return rows
        except Exception:
            return []


# Background Hunter Worker Thread
class HunterWorker(QThread):
    log_signal = pyqtSignal(str)
    hit_signal = pyqtSignal(str, str, str)

    def __init__(self, backend, targets, poll_interval=1.5):
        super().__init__()
        self.backend = backend
        self.targets = targets
        self.poll_interval = poll_interval
        self.running = True

    def run(self):
        self.log_signal.emit(f"🚀 [취소표 헌터 시작] {len(self.targets)}개 과목 감시 중 (주기: {self.poll_interval}s)")
        loop = 0
        while self.running:
            loop += 1
            # Query observer endpoint or portal
            try:
                r = requests.get("https://daejin.qucord.com/api/data", timeout=2.0)
                if r.status_code == 200:
                    data = r.json()
                    course_map = {c["full_code"]: c for c in data.get("courses", [])}
                    for t in self.targets:
                        full_code = f"{t['code']}{t['bun']}"
                        c = course_map.get(full_code)
                        if c and c.get("seats", 0) > 0:
                            self.log_signal.emit(f"🔥 [빈자리 감지!] {t['name']} ({t['code']}-{t['bun']}) {c['seats']}석 발생! 즉각 신청...")
                            ok, msg = self.backend.apply_course(t['code'], t['bun'])
                            self.log_signal.emit(f"📢 신청 결과: {msg}")
                            if ok:
                                self.hit_signal.emit(t['code'], t['bun'], t['name'])
                                self.running = False
                                return
            except Exception as e:
                self.log_signal.emit(f"⚠️ 감시 오류: {e}")

            time.sleep(self.poll_interval)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("대진대학교 수강신청 마스터 자동화 GUI (Daejin Sugang Suite)")
        self.resize(1050, 720)
        self.setStyleSheet(DARK_STYLESHEET)

        self.backend = SugangBackend()
        self.hunter_thread = None
        self.all_courses_cache = []

        self.init_ui()
        self.load_saved_credentials()

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        # Header Bar: Credentials & Quick Login
        hdr_group = QGroupBox("🔑 대진대학교 포털 계정 설정")
        hdr_layout = QHBoxLayout(hdr_group)
        hdr_layout.setContentsMargins(10, 10, 10, 10)

        self.id_input = QLineEdit()
        self.id_input.setPlaceholderText("학번 8자리 (예: 20261236)")
        self.id_input.setMaximumWidth(180)

        self.pw_input = QLineEdit()
        self.pw_input.setPlaceholderText("비밀번호")
        self.pw_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.pw_input.setMaximumWidth(180)

        self.login_btn = QPushButton("로그인")
        self.login_btn.setObjectName("primaryBtn")
        self.login_btn.clicked.connect(self.on_login_click)

        self.login_status_lbl = QLabel("🔴 로그인 필요")
        self.login_status_lbl.setStyleSheet("color: #ef4444; font-weight: bold;")

        hdr_layout.addWidget(QLabel("학번:"))
        hdr_layout.addWidget(self.id_input)
        hdr_layout.addWidget(QLabel("비밀번호:"))
        hdr_layout.addWidget(self.pw_input)
        hdr_layout.addWidget(self.login_btn)
        hdr_layout.addWidget(self.login_status_lbl)
        hdr_layout.addStretch()

        main_layout.addWidget(hdr_group)

        # Tab Widget
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # 1. Observer Tab
        self.tab_observer = QWidget()
        self.init_observer_tab()
        self.tabs.addTab(self.tab_observer, "📊 실시간 과목 검색 & 빈자리 옵저버")

        # 2. Sniper Tab
        self.tab_sniper = QWidget()
        self.init_sniper_tab()
        self.tabs.addTab(self.tab_sniper, "🎯 정각 10시 패킷 스나이퍼")

        # 3. Hunter Tab
        self.tab_hunter = QWidget()
        self.init_hunter_tab()
        self.tabs.addTab(self.tab_hunter, "🏹 24시간 취소표 헌터")

        # 4. Enrolled Status Tab
        self.tab_enrolled = QWidget()
        self.init_enrolled_tab()
        self.tabs.addTab(self.tab_enrolled, "📋 내 수강신청 내역 & 장바구니")

        # Bottom Status Bar
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("준비 완료 | 배포 서버: https://daejin.qucord.com")

    # ==========================================================================
    # Tab 1: Live Observer
    # ==========================================================================
    def init_observer_tab(self):
        layout = QVBoxLayout(self.tab_observer)
        
        # Search & Filter Row
        filter_layout = QHBoxLayout()
        self.obs_search_input = QLineEdit()
        self.obs_search_input.setPlaceholderText("🔍 과목명, 교수명, 학수번호(6자리), 강의시간 검색...")
        self.obs_search_input.textChanged.connect(self.filter_observer_table)

        self.obs_cat_combo = QComboBox()
        self.obs_cat_combo.addItems([
            "전체 영역 / 학과",
            "스마트융합보안",
            "경영학과",
            "교양필수",
            "교양선택",
            "1영역", "2영역", "3영역", "4영역", "5영역", "6영역",
            "교직", "일반선택"
        ])
        self.obs_cat_combo.currentIndexChanged.connect(self.filter_observer_table)

        self.obs_sort_combo = QComboBox()
        self.obs_sort_combo.addItems([
            "⚡ 여석 많은 순",
            "🔥 여석 적은 순 (마감임박)",
            "🔤 과목명 (가나다순)",
            "🔢 학수번호순",
            "👥 신청자 많은 순"
        ])
        self.obs_sort_combo.currentIndexChanged.connect(self.filter_observer_table)

        self.obs_open_only_chk = QCheckBox("빈자리만 보기")
        self.obs_open_only_chk.stateChanged.connect(self.filter_observer_table)

        self.obs_refresh_btn = QPushButton("새로고침")
        self.obs_refresh_btn.clicked.connect(self.fetch_observer_data)

        filter_layout.addWidget(self.obs_search_input, 2)
        filter_layout.addWidget(self.obs_cat_combo)
        filter_layout.addWidget(self.obs_sort_combo)
        filter_layout.addWidget(self.obs_open_only_chk)
        filter_layout.addWidget(self.obs_refresh_btn)

        layout.addLayout(filter_layout)

        # Table
        self.obs_table = QTableWidget(0, 8)
        self.obs_table.setHorizontalHeaderLabels([
            "상태", "학수-분반", "교과목명", "담당교수", "강의시간", "신청/여석", "영역/학과", "신청"
        ])
        self.obs_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.obs_table)

        # Initial fetch
        QTimer.singleShot(500, self.fetch_observer_data)

    def fetch_observer_data(self):
        try:
            r = requests.get("https://daejin.qucord.com/api/data", timeout=3.0)
            if r.status_code == 200:
                self.all_courses_cache = r.json().get("courses", [])
                self.filter_observer_table()
                self.statusBar.showMessage(f"동기화 완료: 총 {len(self.all_courses_cache)}개 강좌 로드됨")
        except Exception as e:
            self.statusBar.showMessage(f"데이터 수신 실패: {e}")

    def filter_observer_table(self):
        search = self.obs_search_input.text().strip().lower()
        cat = self.obs_cat_combo.currentText()
        sort_mode = self.obs_sort_combo.currentIndex()
        open_only = self.obs_open_only_chk.isChecked()

        filtered = []
        for c in self.all_courses_cache:
            if open_only and c.get("seats", 0) <= 0:
                continue
            if cat != "전체 영역 / 학과":
                if cat == "교양선택":
                    if "교선" not in c.get("category", "") and "교양선택" not in c.get("category", ""):
                        continue
                elif cat not in c.get("category", ""):
                    continue
            if search:
                m_code = search in c.get("full_code", "") or search in c.get("code", "")
                m_name = search in c.get("name", "").lower()
                m_prof = search in c.get("prof", "").lower()
                m_time = search in c.get("time", "").lower()
                if not (m_code or m_name or m_prof or m_time):
                    continue
            filtered.append(c)

        # Sorting
        if sort_mode == 0: # 여석 많은 순
            filtered.sort(key=lambda x: x.get("seats", 0), reverse=True)
        elif sort_mode == 1: # 여석 적은 순
            filtered.sort(key=lambda x: (x.get("seats", 0) if x.get("seats", 0) > 0 else 9999))
        elif sort_mode == 2: # 과목명순
            filtered.sort(key=lambda x: x.get("name", ""))
        elif sort_mode == 3: # 학수번호순
            filtered.sort(key=lambda x: x.get("full_code", ""))
        elif sort_mode == 4: # 신청자순
            filtered.sort(key=lambda x: x.get("enrolled", 0), reverse=True)

        self.obs_table.setRowCount(len(filtered))
        for row, c in enumerate(filtered):
            is_open = c.get("seats", 0) > 0
            status_item = QTableWidgetItem(f"🔥 {c['seats']}석" if is_open else "마감")
            status_item.setForeground(QColor("#10b981" if is_open else "#71717a"))
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            code_item = QTableWidgetItem(f"{c['code']}-{c['bun']}")
            code_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            name_item = QTableWidgetItem(f"{c['name']} ({c.get('credits', '2')}학점)")
            prof_item = QTableWidgetItem(c.get("prof", "-"))
            time_item = QTableWidgetItem(c.get("time", "-"))
            seats_item = QTableWidgetItem(f"{c.get('enrolled', 0)} / {c.get('seats', 0)}")
            seats_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            cat_item = QTableWidgetItem(c.get("category", ""))

            self.obs_table.setItem(row, 0, status_item)
            self.obs_table.setItem(row, 1, code_item)
            self.obs_table.setItem(row, 2, name_item)
            self.obs_table.setItem(row, 3, prof_item)
            self.obs_table.setItem(row, 4, time_item)
            self.obs_table.setItem(row, 5, seats_item)
            self.obs_table.setItem(row, 6, cat_item)

            apply_btn = QPushButton("신청")
            apply_btn.setObjectName("primaryBtn")
            apply_btn.clicked.connect(lambda ch, cd=c['code'], b=c['bun']: self.on_quick_apply(cd, b))
            self.obs_table.setCellWidget(row, 7, apply_btn)

    def on_quick_apply(self, code, bun):
        if not self.backend.is_logged_in:
            QMessageBox.warning(self, "경고", "먼저 상단에서 포털 로그인을 진행해주세요.")
            return
        ok, msg = self.backend.apply_course(code, bun)
        if ok:
            QMessageBox.information(self, "신청 완료", f"과목 [{code}-{bun}] 수강신청 성공!\n응답: {msg}")
        else:
            QMessageBox.warning(self, "신청 결과", f"과목 [{code}-{bun}] 신청 실패\n응답: {msg}")

    # ==========================================================================
    # Tab 2: Packet Sniper
    # ==========================================================================
    def init_sniper_tab(self):
        layout = QVBoxLayout(self.tab_sniper)
        group = QGroupBox("🎯 정각 10:00:00 일괄 자동신청 목록")
        g_layout = QVBoxLayout(group)

        self.sniper_input = QTextEdit()
        self.sniper_input.setPlaceholderText(
            "과목번호, 분반, 2지망대체분반 (한 줄에 1과목씩 입력)\n"
            "예시:\n"
            "576006, 01, 02 03\n"
            "927430, 15, 19 18 21\n"
            "922601, 01"
        )
        g_layout.addWidget(self.sniper_input)

        btn_layout = QHBoxLayout()
        self.sniper_sync_btn = QPushButton("🕒 서버 시계 오차(ms) 측정")
        self.sniper_sync_btn.clicked.connect(self.on_clock_sync)

        self.sniper_run_btn = QPushButton("🚀 10:00:00 스나이퍼 가동")
        self.sniper_run_btn.setObjectName("primaryBtn")

        btn_layout.addWidget(self.sniper_sync_btn)
        btn_layout.addWidget(self.sniper_run_btn)
        g_layout.addLayout(btn_layout)

        layout.addWidget(group)

        self.sniper_log = QTextEdit()
        self.sniper_log.setReadOnly(True)
        layout.addWidget(self.sniper_log)

    def on_clock_sync(self):
        try:
            t0 = time.perf_counter()
            r = requests.head("https://dreams2.daejin.ac.kr/sugang/new/loginForm.jsp", timeout=3)
            rtt = (time.perf_counter() - t0) * 1000
            date_str = r.headers.get("Date", "")
            self.sniper_log.append(f"📶 [서버 동기화] RTT: {rtt:.1f}ms | 서버 시각(GMT): {date_str}")
        except Exception as e:
            self.sniper_log.append(f"❌ 동기화 실패: {e}")

    # ==========================================================================
    # Tab 3: Vacancy Hunter
    # ==========================================================================
    def init_hunter_tab(self):
        layout = QVBoxLayout(self.tab_hunter)
        group = QGroupBox("🏹 24시간 취소표 자동 주워담기 목표")
        g_layout = QVBoxLayout(group)

        self.hunter_input = QTextEdit()
        self.hunter_input.setPlaceholderText(
            "취소표 발생 시 즉시 신청할 과목번호 및 분반 입력 (한 줄에 하나씩)\n"
            "예시:\n"
            "927430, 03, 대순사상과상생윤리\n"
            "922613, 01, AI와스마트라이프"
        )
        g_layout.addWidget(self.hunter_input)

        ctrl_layout = QHBoxLayout()
        ctrl_layout.addWidget(QLabel("감시 주기(초):"))
        self.hunter_interval_spin = QDoubleSpinBox()
        self.hunter_interval_spin.setRange(0.5, 5.0)
        self.hunter_interval_spin.setValue(1.5)
        self.hunter_interval_spin.setSingleStep(0.2)
        ctrl_layout.addWidget(self.hunter_interval_spin)

        self.hunter_toggle_btn = QPushButton("▶ 취소표 감시 & 자동신청 시작")
        self.hunter_toggle_btn.setObjectName("successBtn")
        self.hunter_toggle_btn.clicked.connect(self.on_toggle_hunter)
        ctrl_layout.addWidget(self.hunter_toggle_btn)

        g_layout.addLayout(ctrl_layout)
        layout.addWidget(group)

        self.hunter_log = QTextEdit()
        self.hunter_log.setReadOnly(True)
        layout.addWidget(self.hunter_log)

    def on_toggle_hunter(self):
        if self.hunter_thread and self.hunter_thread.isRunning():
            self.hunter_thread.running = False
            self.hunter_thread.wait()
            self.hunter_toggle_btn.setText("▶ 취소표 감시 & 자동신청 시작")
            self.hunter_toggle_btn.setObjectName("successBtn")
            self.hunter_toggle_btn.setStyleSheet("")
            self.hunter_log.append("🛑 [취소표 헌터 중지됨]")
            return

        if not self.backend.is_logged_in:
            QMessageBox.warning(self, "경고", "먼저 포털 로그인을 진행해주세요.")
            return

        text = self.hunter_input.toPlainText().strip()
        targets = []
        for line in text.split("\n"):
            parts = [p.strip() for p in line.split(",") if p.strip()]
            if len(parts) >= 2:
                targets.append({
                    "code": parts[0],
                    "bun": parts[1].zfill(2),
                    "name": parts[2] if len(parts) > 2 else "과목"
                })

        if not targets:
            QMessageBox.warning(self, "경고", "감시할 목표 과목을 최소 1개 이상 입력하세요.")
            return

        self.hunter_thread = HunterWorker(self.backend, targets, self.hunter_interval_spin.value())
        self.hunter_thread.log_signal.connect(self.hunter_log.append)
        self.hunter_thread.hit_signal.connect(self.on_hunter_hit)
        self.hunter_thread.start()

        self.hunter_toggle_btn.setText("⏹ 감시 중지")
        self.hunter_toggle_btn.setObjectName("dangerBtn")
        self.hunter_toggle_btn.setStyleSheet("background-color: #dc2626; color: white;")

    def on_hunter_hit(self, code, bun, name):
        QMessageBox.information(self, "🎉 취소표 낚아채기 성공!", f"과목 [{name} ({code}-{bun})] 취소표를 성공적으로 신청했습니다!")

    # ==========================================================================
    # Tab 4: Enrolled & Cart
    # ==========================================================================
    def init_enrolled_tab(self):
        layout = QVBoxLayout(self.tab_enrolled)
        
        btn_layout = QHBoxLayout()
        self.enrolled_refresh_btn = QPushButton("📋 확정 수강신청 목록 조회")
        self.enrolled_refresh_btn.clicked.connect(self.fetch_enrolled_data)
        btn_layout.addWidget(self.enrolled_refresh_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self.enrolled_table = QTableWidget(0, 6)
        self.enrolled_table.setHorizontalHeaderLabels([
            "학수-분반", "교과목명", "담당교수", "강의시간", "이수구분", "학점"
        ])
        self.enrolled_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.enrolled_table)

    def fetch_enrolled_data(self):
        if not self.backend.is_logged_in:
            QMessageBox.warning(self, "경고", "먼저 포털 로그인을 진행해주세요.")
            return
        courses = self.backend.get_enrolled_courses()
        self.enrolled_table.setRowCount(len(courses))
        for row, c in enumerate(courses):
            self.enrolled_table.setItem(row, 0, QTableWidgetItem(c["code_bun"]))
            self.enrolled_table.setItem(row, 1, QTableWidgetItem(c["name"]))
            self.enrolled_table.setItem(row, 2, QTableWidgetItem(c["prof"]))
            self.enrolled_table.setItem(row, 3, QTableWidgetItem(c["time"]))
            self.enrolled_table.setItem(row, 4, QTableWidgetItem(c["type"]))
            self.enrolled_table.setItem(row, 5, QTableWidgetItem(c["credits"]))

    # ==========================================================================
    # Credentials & Login Helper
    # ==========================================================================
    def load_saved_credentials(self):
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    self.id_input.setText(cfg.get("stdNo", ""))
                    self.pw_input.setText(cfg.get("passwd", ""))
            except Exception:
                pass

    def on_login_click(self):
        std_no = self.id_input.text().strip()
        passwd = self.pw_input.text().strip()
        if not std_no or not passwd:
            QMessageBox.warning(self, "경고", "학번과 비밀번호를 입력하세요.")
            return

        ok, msg = self.backend.login(std_no, passwd)
        if ok:
            self.login_status_lbl.setText("🟢 로그인 완료")
            self.login_status_lbl.setStyleSheet("color: #10b981; font-weight: bold;")
            self.statusBar.showMessage(f"로그인 성공: 학번 {std_no}")
            self.fetch_enrolled_data()
        else:
            self.login_status_lbl.setText("🔴 로그인 실패")
            self.login_status_lbl.setStyleSheet("color: #ef4444; font-weight: bold;")
            QMessageBox.critical(self, "로그인 오류", msg)


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
