#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Daejin University Smart Asymmetric Course Swapper
=================================================
Logic:
  1. Currently held: 922616-01 (화 15:30~17:30)
  2. Monitored targets:
     - Target A: 922605-01 (AI기반프로그래밍입문 / 화 15:30) -> Ultimate Goal
     - Target B: 922616-02 (AI시대의콘텐츠크리에이션 02분반 / 목 15:30) -> Safe Intermediate
  3. Actions on vacancy:
     - Case 1: 922616-02 opens up while holding 922616-01:
       * Try direct apply 922616-02 FIRST without dropping 01분반.
       * If successful -> Drop 922616-01 immediately, update held to 922616-02.
       * If direct apply blocked by duplicate check -> Atomic swap (drop 01 -> apply 02 -> rollback to 01 on fail).
       * After switching to 922616-02, CONTINUE monitoring for 922605-01!
     - Case 2: 922605-01 opens up (whether holding 01분반 or 02분반):
       * Drop currently held course (01 or 02) -> Apply 922605-01.
       * If successful -> Mission Complete! Alert Discord and finish.
       * If failed -> Instant rollback to currently held course.
"""

import os
import sys
import time
import json
import re
import random
import logging
import datetime
import requests

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s][%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("SmartSwapper")

KST = datetime.timezone(datetime.timedelta(hours=9))

BASE_URL = "https://dreams2.daejin.ac.kr"
LOGIN_API_URL = f"{BASE_URL}/sugang/NLoginB"
APPLY_API_URL = f"{BASE_URL}/sugang/NSugangWlsn0410"
QUERY_URL = f"{BASE_URL}/sugang/new/sugang_wlsn0417_2.jsp?ic_kwa=B41002&ic_kwa_1=B42006&ppage=1"


class DaejinSmartSwapper:
    def __init__(self, config_path="config.json"):
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)

        self.std_no = self.config.get("stdNo")
        self.passwd = self.config.get("passwd")
        self.user_flag = self.config.get("user_flag", "1")
        self.discord_bot_token = self.config.get("discord_bot_token", "")
        self.discord_channel_id = self.config.get("discord_channel_id", "")

        # Course definitions
        self.course_616_01 = {
            "name": "AI시대의콘텐츠크리에이션(01분반)",
            "code": "922616",
            "bun": "01",
            "full_code": "92261601"
        }
        self.course_616_02 = {
            "name": "AI시대의콘텐츠크리에이션(02분반)",
            "code": "922616",
            "bun": "02",
            "full_code": "92261602"
        }
        self.course_605_01 = {
            "name": "AI기반프로그래밍입문(01분반)",
            "code": "922605",
            "bun": "01",
            "full_code": "92260501"
        }

        # Track currently held course
        self.currently_held = self.course_616_01

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Referer": f"{BASE_URL}/sugang/new/main.jsp",
            "Origin": BASE_URL
        })
        self.last_login_time = 0

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
                logger.info(f"✅ Login successful for ID: {self.std_no}")
                return True
            logger.error(f"❌ Login failed: {text[:200]}")
            return False
        except Exception as e:
            logger.error(f"❌ Login error: {e}")
            return False

    def ensure_session(self):
        if time.time() - self.last_login_time > 600:
            logger.info("🔄 Refreshing session token...")
            self.login()

    def check_seats(self):
        """Passively checks seats for 922605-01 and 922616-02 in a single request."""
        try:
            r = self.session.get(QUERY_URL, timeout=4)
            html = r.content.decode("euc-kr", "replace")
            
            results = {}
            for key in ["92260501", "92261602"]:
                m = re.search(rf'class=[\"\']seat[\"\'][^>]*data-key=[\"\']{key}[\"\'][^>]*>(\d+)<', html)
                if m:
                    results[key] = int(m.group(1))
                else:
                    results[key] = 0
            return results
        except Exception as e:
            logger.warning(f"Seat query error: {e}")
            return {}

    def drop_course(self, course_info):
        payload = {
            "cmd": "cancle",
            "urltype": "page",
            "cousNm": course_info["name"].encode("euc-kr"),
            "jsg_subcd": course_info["full_code"]
        }
        try:
            r = self.session.post(APPLY_API_URL, data=payload, timeout=3)
            text = r.content.decode("euc-kr", "replace")
            logger.info(f"🗑️ [Drop Request] {course_info['name']} ({course_info['full_code']})")
            return "삭제" in text or "완료" in text or r.status_code == 200
        except Exception as e:
            logger.error(f"Drop error: {e}")
            return False

    def apply_course(self, course_info):
        payload = {
            "dir": "1",
            "cmd": "aply",
            "urltype": "direct",
            "getsbjt_no": course_info["code"],
            "getclss_no": course_info["bun"],
            "ic_sbjcd": course_info["full_code"]
        }
        try:
            r = self.session.post(APPLY_API_URL, data=payload, timeout=3)
            text = r.content.decode("euc-kr", "replace")
            alert_msg = ""
            for line in text.split("\n"):
                if "alert(" in line:
                    start_idx = line.find("alert(") + 6
                    end_idx = line.rfind(")")
                    alert_msg = line[start_idx:end_idx].strip("'\"")
                    break
            
            success = "완료" in alert_msg or "정상" in alert_msg or "신청되었습니다" in alert_msg
            return success, alert_msg
        except Exception as e:
            return False, f"Apply error: {e}"

    def send_discord_alert(self, msg):
        if not self.discord_bot_token or not self.discord_channel_id:
            return
        url = f"https://discord.com/api/v10/channels/{self.discord_channel_id}/messages"
        headers = {"Authorization": f"Bot {self.discord_bot_token}"}
        try:
            requests.post(url, headers=headers, json={"content": msg}, timeout=5)
        except Exception:
            pass

    def handle_616_02_opened(self):
        """Case B: 922616-02 opens while holding 922616-01."""
        logger.info("⚡ [616-02 VACANCY DETECTED] Attempting direct application for 616-02 first...")
        
        # Step 1: Try direct apply 616-02
        t0 = time.perf_counter()
        applied, alert = self.apply_course(self.course_616_02)
        t_apply = (time.perf_counter() - t0) * 1000
        logger.info(f"   ↳ Direct Apply 616-02: {t_apply:.1f}ms | Success={applied} | Alert='{alert}'")

        if applied:
            logger.info("🎉 616-02 신청 성공! 기존 01분반 정리 진행...")
            self.drop_course(self.course_616_01)
            self.currently_held = self.course_616_02
            self.send_discord_alert(
                f"🎉 **[중간 분반 교체 성공]** 616-01 ➡️ **616-02(목15:30)** 교체 완료!\n"
                f"👉 605-01(AI프로그래밍입문) 취소표 계속 감시 진행 중!"
            )
            return True

        # If direct apply failed due to duplicate check or capacity
        if "이미" in alert or "중복" in alert:
            logger.info("ℹ️ 동일과목 중복 차단 감지 -> 01분반 취소 후 02분반 스왑 시도...")
            self.drop_course(self.course_616_01)
            applied2, alert2 = self.apply_course(self.course_616_02)
            if applied2:
                logger.info("🎉 01분반 취소 후 616-02 스왑 성공!")
                self.currently_held = self.course_616_02
                self.send_discord_alert(
                    f"🎉 **[중간 분반 교체 성공]** **616-02(목15:30)** 확보 완료!\n"
                    f"👉 605-01(AI프로그래밍입문) 취소표 계속 감시 진행 중!"
                )
                return True
            else:
                logger.warning("⚠️ 616-02 스왑 실패, 01분반 롤백 복구 시도...")
                self.apply_course(self.course_616_01)
                return False
        return False

    def handle_605_01_opened(self):
        """Case A: 922605-01 opens (Ultimate Target)."""
        logger.info(f"🚨 [605-01 VACANCY DETECTED] Dropping currently held ({self.currently_held['name']}) and sniping 605-01...")
        
        # Step 1: Drop currently held course
        t0 = time.perf_counter()
        dropped = self.drop_course(self.currently_held)
        t_drop = (time.perf_counter() - t0) * 1000
        logger.info(f"   ↳ Drop {self.currently_held['name']}: {t_drop:.1f}ms | Success={dropped}")

        # Step 2: Apply 605-01
        t1 = time.perf_counter()
        applied, alert = self.apply_course(self.course_605_01)
        t_apply = (time.perf_counter() - t1) * 1000
        logger.info(f"   ↳ Apply 605-01: {t_apply:.1f}ms | Success={applied} | Alert='{alert}'")

        if applied:
            logger.info("🎉🎉🎉 [FINAL GOAL ACHIEVED] Successfully enrolled into 922605-01 AI기반프로그래밍입문!")
            self.send_discord_alert(
                f"🎉🎉 **[최종 목표 달성! 수강신청 교체 완료]** 🎉🎉\n"
                f"👤 **학번**: `{self.std_no}`\n"
                f"✅ **최종 확정**: **AI기반프로그래밍입문 (922605-01)** (화 15:30)\n"
                f"🗑️ **기존 취소**: **{self.currently_held['name']}**\n"
                f"⚡ **스왑 소요 시간**: `{t_drop + t_apply:.1f}ms`\n"
                f"👉 꿀과목으로 최종 교체 완료했습니다!"
            )
            return True
        else:
            logger.warning(f"⚠️ 605-01 신청 실패 ({alert}). 들고 있던 과목({self.currently_held['name']}) 즉시 롤백 복구...")
            rb_success, rb_alert = self.apply_course(self.currently_held)
            if rb_success:
                logger.info("🛡️ [ROLLBACK COMPLETE] 기존 과목 무손실 안전 복구 완료.")
            else:
                logger.warning("⚠️ 기존 과목 복구 실패 -> 반대쪽 616 분반 비상 신청 시도...")
                alt_616 = self.course_616_02 if self.currently_held == self.course_616_01 else self.course_616_01
                self.apply_course(alt_616)
            return False

    def run(self):
        logger.info("=" * 70)
        logger.info("🛡️ Daejin University Smart Asymmetric Course Swapper")
        logger.info(f"🔄 Currently Held: {self.currently_held['name']}")
        logger.info("🎯 Targets:")
        logger.info(f"  • 605-01 (AI기반프로그래밍입문) -> [최종 목표: 잡히면 616 정리 후 즉시 종료]")
        logger.info(f"  • 616-02 (콘텐츠 02분반 / 목15:30) -> [중간 안전 확보: 선신청 후 01분반 취소]")
        logger.info("=" * 70)

        if not self.login():
            return

        loop = 0
        while True:
            loop += 1
            self.ensure_session()
            
            seat_map = self.check_seats()
            s_605_01 = seat_map.get("92260501", 0)
            s_616_02 = seat_map.get("92261602", 0)

            if loop % 25 == 0:
                logger.info(f"⏳ [감시 #{loop}] 605-01 여석: {s_605_01} | 616-02 여석: {s_616_02} | 보유과목: {self.currently_held['name']}")

            # Priority 1: 605-01 opens -> Final Swap!
            if s_605_01 > 0:
                logger.info(f"🔥 [최종 목표 발견] 605-01 여석 {s_605_01}개 발생!")
                final_success = self.handle_605_01_opened()
                if final_success:
                    break
                time.sleep(1.0)

            # Priority 2: 616-02 opens while holding 616-01 -> Safe Shift!
            elif s_616_02 > 0 and self.currently_held == self.course_616_01:
                logger.info(f"🔥 [중간 분반 발견] 616-02 여석 {s_616_02}개 발생!")
                self.handle_616_02_opened()
                time.sleep(1.0)

            # Sleep with jitter
            jitter = random.uniform(-0.15, 0.15)
            time.sleep(max(0.6, 1.1 + jitter))


if __name__ == "__main__":
    cfg_file = sys.argv[1] if len(sys.argv) > 1 else "config.json"
    swapper = DaejinSmartSwapper(cfg_file)
    swapper.run()
