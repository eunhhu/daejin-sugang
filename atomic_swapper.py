#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Daejin University 18-Credit Hard Limit Safe Atomic Swapper
=========================================================
Facts:
  - Current Credits: 17
  - Max Allowed Credits: 18 (Hard Server Limit)
  - Target Courses: 2 credits each (922605-01 or 922616-02)
  - 17 + 2 = 19 > 18 -> Direct apply WITHOUT drop is REJECTED by server.

Atomic Protocol:
  1. Passive Watchdog: Continuously check remaining seats for:
     - Target 1: 922605-01 (AI기반프로그래밍입문 / 화 15:30) [Priority 1]
     - Target 2: 922616-02 (AI시대의콘텐츠크리에이션 02분반 / 목 15:30) [Priority 2]
  2. While seats == 0: NEVER touch currently held course (100% safe).
  3. The moment seats > 0 for either target:
     - Step 1: Drop currently held course in ~10ms (Credits drop: 17 -> 15)
     - Step 2: Apply opened target in ~10ms (Credits become: 15 + 2 = 17)
     - Step 3 (Verification):
         * If Success:
             - If 922605-01 secured -> Mission Complete! Discord alert & exit.
             - If 922616-02 secured -> Update held to 922616-02, continue monitoring for 922605-01!
         * If Fail (sniped by someone else in that 10ms window):
             - Instant Rollback Step A: Re-apply originally held course in ~10ms
             - Instant Rollback Step B: If Step A fails, apply alternative 616 section in ~10ms
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
logger = logging.getLogger("CreditAwareSwapper")

KST = datetime.timezone(datetime.timedelta(hours=9))

BASE_URL = "https://dreams2.daejin.ac.kr"
LOGIN_API_URL = f"{BASE_URL}/sugang/NLoginB"
APPLY_API_URL = f"{BASE_URL}/sugang/NSugangWlsn0410"
QUERY_URL = f"{BASE_URL}/sugang/new/sugang_wlsn0417_2.jsp?ic_kwa=B41002&ic_kwa_1=B42006&ppage=1"
CONFIRMED_URL = f"{BASE_URL}/sugang/new/sugang_wlsn04110.jsp"


class DaejinCreditAwareSwapper:
    def __init__(self, config_path="config.json"):
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)

        self.std_no = self.config.get("stdNo")
        self.passwd = self.config.get("passwd")
        self.user_flag = self.config.get("user_flag", "1")
        self.discord_bot_token = self.config.get("discord_bot_token", "")
        self.discord_channel_id = self.config.get("discord_channel_id", "")

        self.c_616_01 = {
            "name": "AI시대의콘텐츠크리에이션(01분반)",
            "code": "922616",
            "bun": "01",
            "full_code": "92261601",
            "credits": 2
        }
        self.c_616_02 = {
            "name": "AI시대의콘텐츠크리에이션(02분반)",
            "code": "922616",
            "bun": "02",
            "full_code": "92261602",
            "credits": 2
        }
        self.c_605_01 = {
            "name": "AI기반프로그래밍입문(01분반)",
            "code": "922605",
            "bun": "01",
            "full_code": "92260501",
            "credits": 2
        }

        # Track currently held course
        self.currently_held = self.c_616_01

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

    def sync_actual_held(self):
        try:
            r = self.session.get(CONFIRMED_URL, timeout=4)
            html = r.content.decode("euc-kr", "replace")
            if "922616-02" in html:
                self.currently_held = self.c_616_02
            elif "922616-01" in html:
                self.currently_held = self.c_616_01
            elif "922605-01" in html:
                self.currently_held = self.c_605_01
            logger.info(f"📋 Enrolled course verified: {self.currently_held['name']}")
        except Exception as e:
            logger.warning(f"Sync error: {e}")

    def ensure_session(self):
        if time.time() - self.last_login_time > 600:
            logger.info("🔄 Refreshing session token...")
            self.login()

    def check_seats(self):
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

    def perform_atomic_swap(self, target_course):
        old = self.currently_held
        logger.info(f"🚨 [ATOMIC SWAP TRIGGERED] Dropping {old['name']} -> Sniping {target_course['name']}...")
        
        # Step 1: Drop old course (17 -> 15 credits)
        t0 = time.perf_counter()
        dropped = self.drop_course(old)
        t_drop = (time.perf_counter() - t0) * 1000
        logger.info(f"   ↳ Step 1 (Drop Old): {t_drop:.1f}ms | Success={dropped}")

        # Step 2: Apply new course (15 -> 17 credits)
        t1 = time.perf_counter()
        applied, alert = self.apply_course(target_course)
        t_apply = (time.perf_counter() - t1) * 1000
        logger.info(f"   ↳ Step 2 (Apply New): {t_apply:.1f}ms | Success={applied} | Alert='{alert}'")

        if applied:
            logger.info(f"🎉🎉 [SWAP SUCCESSFUL] Successfully enrolled into {target_course['name']}!")
            self.currently_held = target_course
            
            # If 605-01 secured -> Final Mission Finished!
            if target_course["code"] == "922605":
                self.send_discord_alert(
                    f"🎉🎉 **[최종 목표 달성! 수강신청 교체 완료]** 🎉🎉\n"
                    f"👤 **학번**: `{self.std_no}`\n"
                    f"✅ **최종 확정**: **AI기반프로그래밍입문 (922605-01)** (화 15:30)\n"
                    f"🗑️ **기존 취소**: **{old['name']}**\n"
                    f"⚡ **스왑 소요 시간**: `{t_drop + t_apply:.1f}ms`\n"
                    f"👉 꿀과목으로 최종 교체 완료했습니다!"
                )
                return True, True # (success, is_final)
            else:
                # 616-02 secured -> intermediate step!
                self.send_discord_alert(
                    f"🎉 **[중간 분반 교체 성공]** {old['name']} ➡️ **616-02(목15:30)** 교체 완료!\n"
                    f"👉 605-01(AI프로그래밍입문) 취소표 계속 감시 진행 중!"
                )
                return True, False

        else:
            logger.warning(f"⚠️ [APPLY FAILED] Reason: {alert}. Initiating instant rollback to {old['name']}...")
            # Step 3: Rollback to old course
            t2 = time.perf_counter()
            rb_success, rb_alert = self.apply_course(old)
            t_rb = (time.perf_counter() - t2) * 1000
            logger.info(f"   ↳ Step 3 (Rollback Old): {t_rb:.1f}ms | Success={rb_success} | Alert='{rb_alert}'")

            if rb_success:
                logger.info(f"🛡️ [ROLLBACK COMPLETE] {old['name']} 안전하게 원상복구 완료.")
            else:
                # Step 3.5: Emergency backup to other 616 section
                backup = self.c_616_02 if old == self.c_616_01 else self.c_616_01
                logger.warning(f"⚠️ 원래 과목 복구 실패 -> {backup['name']} 즉시 비상 낚아채기...")
                t3 = time.perf_counter()
                bk_success, bk_alert = self.apply_course(backup)
                t_bk = (time.perf_counter() - t3) * 1000
                logger.info(f"   ↳ Step 3.5 (Emergency Backup): {t_bk:.1f}ms | Success={bk_success} | Alert='{bk_alert}'")
                if bk_success:
                    self.currently_held = backup
                    logger.info(f"🛡️ {backup['name']}으로 대체 복구 성공!")
                else:
                    logger.error("🚨 [CRITICAL ALERT] All rollbacks failed!")
                    self.send_discord_alert(
                        f"🚨🚨 **[긴급 수동 확인 요망]** 스왑 및 롤백 실패 경보 발생! 즉시 수강신청 확인/취소 메뉴를 확인해주세요!"
                    )
            return False, False

    def run(self):
        logger.info("=" * 70)
        logger.info("🛡️ Daejin University 18-Credit Hard Limit Safe Swapper")
        logger.info("=" * 70)

        if not self.login():
            return

        self.sync_actual_held()

        loop = 0
        while True:
            loop += 1
            self.ensure_session()
            
            seat_map = self.check_seats()
            s_605_01 = seat_map.get("92260501", 0)
            s_616_02 = seat_map.get("92261602", 0)

            if loop % 25 == 0:
                logger.info(f"⏳ [감시 #{loop}] 605-01 여석: {s_605_01} | 616-02 여석: {s_616_02} | 현재보유: {self.currently_held['name']}")

            # Priority 1: 605-01 opens -> Final Swap!
            if s_605_01 > 0:
                logger.info(f"🔥 [최종 목표 발견] 605-01 여석 {s_605_01}개 발생!")
                success, is_final = self.perform_atomic_swap(self.c_605_01)
                if is_final:
                    break
                time.sleep(1.0)

            # Priority 2: 616-02 opens while holding 616-01 -> Shift to 616-02!
            elif s_616_02 > 0 and self.currently_held == self.c_616_01:
                logger.info(f"🔥 [중간 분반 발견] 616-02 여석 {s_616_02}개 발생!")
                self.perform_atomic_swap(self.c_616_02)
                time.sleep(1.0)

            # Sleep 1.1s with random jitter
            jitter = random.uniform(-0.15, 0.15)
            time.sleep(max(0.6, 1.1 + jitter))


if __name__ == "__main__":
    cfg_file = sys.argv[1] if len(sys.argv) > 1 else "config.json"
    swapper = DaejinCreditAwareSwapper(cfg_file)
    swapper.run()
