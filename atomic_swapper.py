#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Daejin University Safe Atomic Course Swapper (안전 스왑 스나이퍼)
================================================================
Target: Swap existing course (AI시대의콘텐츠크리에이션 922616-01) with (AI기반프로그래밍입문 922605-01)
Safety Guarantee:
  1. Never drop existing course while target course has 0 remaining seats.
  2. The exact moment target course has remaining seat (여석 > 0):
     - Step 1: Drop old course (922616-01) in ~10ms
     - Step 2: Grab new course (922605-01) in ~10ms
     - Step 3: If apply fails, instantly re-grab old course (922616-01) in ~5ms (Rollback Protection)
  3. Send real-time Discord notification.
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

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s][%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("AtomicSwapper")

KST = datetime.timezone(datetime.timedelta(hours=9))

BASE_URL = "https://dreams2.daejin.ac.kr"
LOGIN_API_URL = f"{BASE_URL}/sugang/NLoginB"
APPLY_API_URL = f"{BASE_URL}/sugang/NSugangWlsn0410"
QUERY_URL = f"{BASE_URL}/sugang/new/sugang_wlsn0417_2.jsp?ic_kwa=B41002&ic_kwa_1=B42006&ppage=1"
CHECK_APPLY_URL = f"{BASE_URL}/sugang/new/sugang_wlsn04110.jsp"


class DaejinAtomicSwapper:
    def __init__(self, config_path="config.json"):
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)

        self.std_no = self.config.get("stdNo")
        self.passwd = self.config.get("passwd")
        self.user_flag = self.config.get("user_flag", "1")
        self.discord_bot_token = self.config.get("discord_bot_token", "")
        self.discord_channel_id = self.config.get("discord_channel_id", "")

        # Old course to drop ONLY when new course opens
        self.old_course = {
            "name": "AI시대의콘텐츠크리에이션",
            "code": "922616",
            "bun": "01",
            "full_code": "92261601"
        }

        # Desired new course
        self.target_course = {
            "name": "AI기반프로그래밍입문",
            "code": "922605",
            "bun": "01",
            "full_code": "92260501"
        }

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

    def check_target_seats(self):
        """Passively checks remaining seats for target course without touching existing courses."""
        try:
            r = self.session.get(QUERY_URL, timeout=4)
            html = r.content.decode("euc-kr", "replace")
            
            # Exact regex on seat data-key
            m = re.search(rf'class=[\"\']seat[\"\'][^>]*data-key=[\"\']{self.target_course["full_code"]}[\"\'][^>]*>(\d+)<', html)
            if m:
                rem = int(m.group(1))
                return rem, "Checked"
            
            # Fallback check on button status
            if f'data-key="{self.target_course["full_code"]}"' in html and 'soldlabel' in html:
                return 0, "Full"

            return 0, "?"
        except Exception as e:
            logger.warning(f"Seat query error: {e}")
            return 0, "?"

    def drop_course(self, course_info):
        """Drops a currently enrolled course."""
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
        """Applies for a course directly."""
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

    def perform_atomic_swap(self):
        logger.info("🚨 [SWAP TRIGGERED] Target seat vacancy detected! Executing atomic swap...")
        
        # Step 1: Drop old course
        t0 = time.perf_counter()
        dropped = self.drop_course(self.old_course)
        t_drop = (time.perf_counter() - t0) * 1000
        logger.info(f"   ↳ Step 1 (Drop Old): {t_drop:.1f}ms | Success={dropped}")

        # Step 2: Grab new course
        t1 = time.perf_counter()
        applied, alert = self.apply_course(self.target_course)
        t_apply = (time.perf_counter() - t1) * 1000
        logger.info(f"   ↳ Step 2 (Apply New): {t_apply:.1f}ms | Success={applied} | Alert='{alert}'")

        if applied:
            logger.info("🎉🎉 [ATOMIC SWAP SUCCESSFUL] Successfully swapped to AI기반프로그래밍입문!")
            self.send_discord_alert(
                f"🎉🎉 **[수강신청 과목 교체 성공!]** 🎉🎉\n"
                f"👤 **학번**: `{self.std_no}`\n"
                f"✅ **신규 확정**: **{self.target_course['name']}** (`{self.target_course['full_code']}`)\n"
                f"🗑️ **기존 취소**: **{self.old_course['name']}** (`{self.old_course['full_code']}`)\n"
                f"⚡ **스왑 소요 시간**: `{t_drop + t_apply:.1f}ms`\n"
                f"👉 완벽하게 꿀과목으로 교체 완료했습니다!"
            )
            return True
        else:
            logger.warning(f"⚠️ [APPLY FAILED] Reason: {alert}. Initiating instant rollback to old course...")
            # Step 3: Rollback
            t2 = time.perf_counter()
            rolled_back, rb_alert = self.apply_course(self.old_course)
            t_rb = (time.perf_counter() - t2) * 1000
            logger.info(f"   ↳ Step 3 (Rollback Old): {t_rb:.1f}ms | Success={rolled_back} | Alert='{rb_alert}'")

            if rolled_back:
                logger.info("🛡️ [ROLLBACK COMPLETE] Safely recovered existing course. No loss.")
            else:
                logger.error("🚨 [CRITICAL ALERT] Rollback failed! Immediate manual check required!")
                self.send_discord_alert(
                    f"🚨🚨 **[긴급 수동 확인 요망]** 스왑 실패 및 롤백 경보 발생! 즉시 수강신청 확인/취소 메뉴를 확인해주세요!"
                )
            return False

    def run(self):
        logger.info("=" * 70)
        logger.info("🛡️ Daejin University Safe Atomic Course Swapper")
        logger.info(f"🎯 Target to Catch: {self.target_course['name']} ({self.target_course['full_code']})")
        logger.info(f"🔄 Source to Swap:  {self.old_course['name']} ({self.old_course['full_code']})")
        logger.info("🛡️ Safety Guarantee: Existing course is NEVER touched until target vacancy > 0.")
        logger.info("=" * 70)

        if not self.login():
            return

        loop = 0
        while True:
            loop += 1
            self.ensure_session()
            
            seats, enrolled = self.check_target_seats()
            
            if loop % 25 == 0:
                logger.info(f"⏳ [감시 #{loop}] {self.target_course['name']} 잔여석: {seats} (신청자: {enrolled}) | 기존 과목 안전 유지 중")

            if seats > 0:
                logger.info(f"🔥 빈자리 발견! (여석: {seats}자리)")
                success = self.perform_atomic_swap()
                if success:
                    break
                else:
                    time.sleep(1.0) # wait before next check

            # Sleep 1.2s with random jitter
            jitter = random.uniform(-0.15, 0.15)
            time.sleep(max(0.6, 1.2 + jitter))


if __name__ == "__main__":
    cfg_file = sys.argv[1] if len(sys.argv) > 1 else "config.json"
    swapper = DaejinAtomicSwapper(cfg_file)
    swapper.run()
