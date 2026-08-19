#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Daejin University Multi-Target Safe Course Swapper
=================================================
Strategy:
  1. Simultaneously monitor:
     - Target A: 922605-01 (AI기반프로그래밍입문)
     - Target B: 922616-02 (AI시대의콘텐츠크리에이션 02분반)
  2. While both have 0 seats:
     - Keep existing 922616-01 (01분반) completely safe and intact.
  3. When Target A or Target B opens up (seats > 0):
     - Step 1: Drop existing 922616-01 (10ms)
     - Step 2: Grab the opened target (10ms)
     - Step 3: If apply fails:
         a) Instantly re-grab 922616-01 (10ms)
         b) If that fails too, instantly grab 922616-02 (10ms)
  4. Send Discord DM ONLY upon final confirmed success.
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
logger = logging.getLogger("MultiTargetSwapper")

KST = datetime.timezone(datetime.timedelta(hours=9))

BASE_URL = "https://dreams2.daejin.ac.kr"
LOGIN_API_URL = f"{BASE_URL}/sugang/NLoginB"
APPLY_API_URL = f"{BASE_URL}/sugang/NSugangWlsn0410"
QUERY_URL = f"{BASE_URL}/sugang/new/sugang_wlsn0417_2.jsp?ic_kwa=B41002&ic_kwa_1=B42006&ppage=1"


class DaejinMultiTargetSwapper:
    def __init__(self, config_path="config.json"):
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)

        self.std_no = self.config.get("stdNo")
        self.passwd = self.config.get("passwd")
        self.user_flag = self.config.get("user_flag", "1")
        self.discord_bot_token = self.config.get("discord_bot_token", "")
        self.discord_channel_id = self.config.get("discord_channel_id", "")

        # Current course to drop
        self.old_course = {
            "name": "AI시대의콘텐츠크리에이션(01분반)",
            "code": "922616",
            "bun": "01",
            "full_code": "92261601"
        }

        # Desired targets to watch
        self.targets = [
            {
                "name": "AI기반프로그래밍입문",
                "code": "922605",
                "bun": "01",
                "full_code": "92260501",
                "priority": 1
            },
            {
                "name": "AI시대의콘텐츠크리에이션(02분반)",
                "code": "922616",
                "bun": "02",
                "full_code": "92261602",
                "priority": 2
            }
        ]

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
        """Passively checks seats for all target courses in a single request."""
        try:
            r = self.session.get(QUERY_URL, timeout=4)
            html = r.content.decode("euc-kr", "replace")
            
            results = {}
            for t in self.targets:
                key = t["full_code"]
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

    def perform_swap(self, chosen_target):
        logger.info(f"🚨 [SWAP TRIGGERED] Target seat vacancy in {chosen_target['name']} ({chosen_target['full_code']})!")
        
        # Step 1: Drop old course
        t0 = time.perf_counter()
        dropped = self.drop_course(self.old_course)
        t_drop = (time.perf_counter() - t0) * 1000
        logger.info(f"   ↳ Step 1 (Drop Old 01분반): {t_drop:.1f}ms | Success={dropped}")

        # Step 2: Grab the new chosen target
        t1 = time.perf_counter()
        applied, alert = self.apply_course(chosen_target)
        t_apply = (time.perf_counter() - t1) * 1000
        logger.info(f"   ↳ Step 2 (Apply New {chosen_target['name']}): {t_apply:.1f}ms | Success={applied} | Alert='{alert}'")

        if applied:
            logger.info(f"🎉🎉 [SWAP SUCCESSFUL] Successfully enrolled into {chosen_target['name']}!")
            self.send_discord_alert(
                f"🎉🎉 **[수강신청 과목 교체 성공!]** 🎉🎉\n"
                f"👤 **학번**: `{self.std_no}`\n"
                f"✅ **신규 확정**: **{chosen_target['name']}** (`{chosen_target['full_code']}`)\n"
                f"🗑️ **기존 취소**: **{self.old_course['name']}** (`{self.old_course['full_code']}`)\n"
                f"⚡ **스왑 소요 시간**: `{t_drop + t_apply:.1f}ms`\n"
                f"👉 원하는 과목으로 교체 성공했습니다!"
            )
            return True
        else:
            logger.warning(f"⚠️ [APPLY FAILED] Reason: {alert}. Initiating instant rollback chain...")
            # Step 3: Rollback to original 01분반
            t2 = time.perf_counter()
            rolled_back, rb_alert = self.apply_course(self.old_course)
            t_rb = (time.perf_counter() - t2) * 1000
            logger.info(f"   ↳ Step 3 (Rollback Old 01분반): {t_rb:.1f}ms | Success={rolled_back} | Alert='{rb_alert}'")

            if rolled_back:
                logger.info("🛡️ [ROLLBACK COMPLETE] Safely recovered existing 01분반 course. No loss.")
            else:
                # Step 3.5: Fallback to the OTHER target if 01분반 is lost
                other_target = self.targets[1] if chosen_target == self.targets[0] else self.targets[0]
                logger.warning(f"⚠️ 01분반 복구 실패! 대체 과목 {other_target['name']} 비상 신청...")
                t3 = time.perf_counter()
                alt_success, alt_alert = self.apply_course(other_target)
                t_alt = (time.perf_counter() - t3) * 1000
                logger.info(f"   ↳ Step 3.5 (Grab Alternative {other_target['name']}): {t_alt:.1f}ms | Success={alt_success} | Alert='{alt_alert}'")
                
                if alt_success:
                    logger.info(f"🎉 [ALTERNATIVE SECURED] {other_target['name']} 확보 완료!")
                    self.send_discord_alert(
                        f"🎉 **[대체 과목 확보 성공]** 원래 과목 대신 **{other_target['name']}**으로 확보되었습니다!"
                    )
                else:
                    logger.error("🚨 [CRITICAL ALERT] All recovery attempts failed! Check manually!")
                    self.send_discord_alert(
                        f"🚨🚨 **[긴급 수동 확인 요망]** 스왑 및 복구 실패 경보 발생! 즉시 수강신청 확인/취소 메뉴를 확인해주세요!"
                    )
            return False

    def run(self):
        logger.info("=" * 70)
        logger.info("🛡️ Daejin University Multi-Target Course Swapper")
        logger.info(f"🔄 Current Held: {self.old_course['name']} ({self.old_course['full_code']})")
        logger.info("🎯 Targets Monitored (Either one opens -> Swap):")
        for t in self.targets:
            logger.info(f"  • {t['name']} ({t['full_code']}) [우선순위 {t['priority']}]")
        logger.info("🛡️ Safety: Current course NEVER dropped until a target has seats > 0.")
        logger.info("=" * 70)

        if not self.login():
            return

        loop = 0
        while True:
            loop += 1
            self.ensure_session()
            
            seat_map = self.check_seats()
            
            # Sort candidates: 605-01 first, then 616-02
            opened_target = None
            for t in self.targets:
                if seat_map.get(t["full_code"], 0) > 0:
                    opened_target = t
                    break

            if loop % 25 == 0:
                s1 = seat_map.get("92260501", 0)
                s2 = seat_map.get("92261602", 0)
                logger.info(f"⏳ [감시 #{loop}] 922605-01 여석: {s1} | 922616-02 여석: {s2} | 기존 616-01 안전 유지 중")

            if opened_target:
                logger.info(f"🔥 빈자리 발견! {opened_target['name']} ({opened_target['full_code']}) 여석 발생")
                success = self.perform_swap(opened_target)
                if success:
                    break
                else:
                    time.sleep(1.0)

            # Sleep 1.1s with random jitter
            jitter = random.uniform(-0.15, 0.15)
            time.sleep(max(0.6, 1.1 + jitter))


if __name__ == "__main__":
    cfg_file = sys.argv[1] if len(sys.argv) > 1 else "config.json"
    swapper = DaejinMultiTargetSwapper(cfg_file)
    swapper.run()
