# Daejin Sugang Automation (대진대학교 초고속 수강신청 자동화 도구)

> ⚡ **Daejin University Course Registration Sniper Suite & Live Web Observer**  
> 대진대학교 종합정보시스템(`dreams2.daejin.ac.kr`)의 수강신청 엔드포인트 역공학 분석을 바탕으로 제작된 **초정밀 수강신청 자동화 스나이퍼 & 실시간 웹 옵저버**입니다.

🌐 **실시간 웹 옵저버 배포 주소**: **[https://daejin.qucord.com](https://daejin.qucord.com)**

---

## 📌 주요 모듈 및 4가지 실행 엔진

### 1. 🌐 Real-time Web Observer (`web_observer.py`) - **[전과목 실시간 옵저버 웹사이트]**
* **배포 링크**: `https://daejin.qucord.com` (Cloudflare Tunnel HTTPS)
* **기능**:
  - 전공 및 교양 전 영역 148개+ 전 강좌의 잔여석을 2.5초 주기로 초고속 백그라운드 스크래핑
  - **🔥 실시간 취소표 발생 피드 스트림**: 취소표가 발생하는 즉시 상단 티커에 과목명/시간/잔여석 브리핑
  - **🔔 사운드 비프 알림**: 화면 켜두고 다른 작업 중에도 취소표 발생 시 알림음 재생
  - **🔍 스마트 검색 및 "빈자리만 보기" 토글** & 학수번호 1클릭 복사

### 2. 🚀 Direct Packet Sniper (`packet_sniper.py`) - **[정각 올클리어]**
* **방식**: 순수 HTTP/Requests 및 멀티스레드 기반 다이렉트 패킷 인젝션
* **응답 속도**: 과목당 **`~0.005초`** (DOM 렌더링, 브라우저 자바스크립트 실행 오버헤드 0%)
* **핵심 기능**:
  - 대진대 서버 시계 오차(ms) 및 편도 네트워크 Ping(RTT/2) 실시간 자동 역산
  - 10:00:00.000 정각 1ms 도달 즉시 고속 로그인 버스트(`NLoginB`)
  - 신청 API(`/sugang/NSugangWlsn0410`)로 directForm 규격 패킷 연속 사출
  - **초고속 서브 분반 Fallback 체인**: 1순위 분반 마감 시 **0.005초 만에 2순위/3순위 예비 분반으로 즉시 전환 신청**

### 3. 🛡️ Credit-Aware Atomic Course Swapper (`atomic_swapper.py`) - **[18학점 하드제한 대응 아토믹 스왑]**
* **방식**: 18학점 제한 시스템에서 기존 과목을 날리지 않고 원하는 과목으로 초고속 맞바꿔치기
* **핵심 기능**:
  - 목표 과목 잔여석 0석인 동안 기존 과목 100% 안전 유지
  - 빈자리 감지 즉시 **기존 과목 취소(9ms) ➡️ 목표 과목 낚아채기(9ms) ➡️ 실패 시 0.005초 즉시 롤백 복구**

### 4. 🎯 Vacancy Hunter (`vacancy_hunter.py`) - **[취소표 무한 줍기 스나이퍼]**
* **방식**: 실시간 백그라운드 폴링 & 빈자리 발생 즉시 0.005초 낚아채기
* **핵심 기능**:
  - 세션 자동 유지(Keep-Alive) & 스마트 지터(Anti-Ban Jitter)
  - 획득 성공 시 Discord DM 축하 알림 발송 및 자동 종료

---

## 🛠️ 수강신청 엔드포인트 & 프로토콜 분석 (Reverse-Engineered)

| 기능 | HTTP Method | URL 엔드포인트 | 주요 파라미터 규격 |
| :--- | :--- | :--- | :--- |
| **로그인 인증** | `POST` | `/sugang/NLoginB` | `stdNo` (학번), `passwd` (비밀번호), `user_flag` (1: 학부생) |
| **빠른 수강신청** | `POST` | `/sugang/NSugangWlsn0410` | `dir=1`, `cmd=aply`, `urltype=direct`, `getsbjt_no` (6자리), `getclss_no` (2자리), `ic_sbjcd` (8자리) |
| **수강 취소/삭제** | `POST` | `/sugang/NSugangWlsn0410` | `cmd=cancle`, `urltype=page`, `cousNm` (과목명), `jsg_subcd` (8자리) |
| **신청 확인/취소** | `GET` | `/sugang/new/sugang_wlsn04110.jsp` | 확정 신청 내역 및 총 취득학점 테이블 파싱 |
| **장바구니 조회** | `GET` | `/sugang/new/sugang_wlsn04120.jsp` | 예비수강신청 과목 목록 및 여석 조회 |
| **전공강좌 조회** | `GET` | `/sugang/new/sugang_wlsn0417_3.jsp` | 스마트융합보안학과 개설 강좌 및 실시간 잔여석 |
| **교양강좌 조회** | `GET` | `/sugang/new/sugang_wlsn0417_2.jsp` | `ic_kwa` (영역코드), `ic_kwa_1` (세부영역) |

---

## 🚀 빠른 시작 (Quick Start)

```bash
# 1. 패키지 설치
pip install -r requirements.txt

# 2. 웹 옵저버 실행
python3 web_observer.py

# 3. 브라우저에서 https://daejin.qucord.com 접속
```
