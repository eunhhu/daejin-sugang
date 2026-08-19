# Daejin Sugang Automation (대진대학교 초고속 수강신청 자동화 도구)

> ⚡ **Daejin University Course Registration Sniper Suite**  
> 대진대학교 종합정보시스템(`dreams2.daejin.ac.kr`)의 수강신청 엔드포인트 역공학 분석을 바탕으로 제작된 **초정밀 수강신청 자동화 스나이퍼 & 취소표 줍기 도구**입니다.

---

## 📌 주요 모듈 및 3가지 실행 엔진

### 1. 🚀 Direct Packet Sniper (`packet_sniper.py`) - **[정각 올클리어 추천]**
* **방식**: 순수 HTTP/Requests 및 멀티스레드 기반 다이렉트 패킷 인젝션
* **응답 속도**: 과목당 **`~0.005초`** (DOM 렌더링, 브라우저 자바스크립트 실행 오버헤드 0%)
* **핵심 기능**:
  - 대진대 서버 시계 오차(ms) 및 편도 네트워크 Ping(RTT/2) 실시간 자동 역산
  - 10:00:00.000 정각 1ms 도달 즉시 고속 로그인 버스트(`NLoginB`)
  - 신청 API(`/sugang/NSugangWlsn0410`)로 directForm 규격 패킷 연속 사출
  - **초고속 서브 분반 Fallback 체인**: 1순위 분반 마감 시 **0.005초 만에 2순위/3순위 예비 분반으로 즉시 전환 신청**
  - EUC-KR 응답 Alert 실시간 파싱 및 디스코드 DM 브리핑 자동 전송

### 2. 🎯 Vacancy Hunter (`vacancy_hunter.py`) - **[취소표 무한 줍기 스나이퍼]**
* **방식**: 실시간 백그라운드 폴링 & 빈자리 발생 즉시 0.005초 낚아채기
* **핵심 기능**:
  - 마감된 인기 분반을 백그라운드에서 실시간 모니터링
  - **누군가 수강을 취소하는 그 찰나(0.01초)**에 다이렉트 신청 패킷을 꽂아 넣어 빈자리 가로채기
  - **세션 자동 유지(Keep-Alive)**: 10분마다 세션을 자동 갱신하여 튕김 없이 24시간 감시 가능
  - **스마트 지터(Jitter)**: 랜덤 딜레이(±0.2초)를 주어 서버 차단(IP Ban) 및 이상 트래픽 탐지 우회
  - 획득 성공 시 Discord DM으로 즉시 축하 알림 발송 및 자동 종료

### 3. 🌐 Playwright Browser Sniper (`browser_sniper.py`)
* **방식**: Chromium 헤드리스/헤드풀 브라우저 DOM 자동화
* **핵심 기능**:
  - 실제 브라우저 환경 및 대진대 공식 자바스크립트 이벤트 완벽 에뮬레이션
  - **튕김/새로고침 방어 가드 (`add_init_script`)**: 서버 조기 튕김 시 폼 초기화(`$("#stdNo").val("")`)를 백그라운드 20ms 간격으로 무력화하고 학번/비밀번호 강제 유지
  - **논블로킹 비동기 다이얼로그 리스너 (`page.on("dialog")`)**: Alert 팝업 발생 시 0.0001초 만에 자동 수락
  - 메인 화면 및 최종 신청 완료 화면 자동 스크린샷 캡처 및 디스코드 첨부 전송

---

## 🛠️ 수강신청 엔드포인트 & 프로토콜 분석 (Reverse-Engineered)

| 기능 | HTTP Method | URL 엔드포인트 | 주요 파라미터 규격 |
| :--- | :--- | :--- | :--- |
| **로그인 인증** | `POST` | `/sugang/NLoginB` | `stdNo` (학번), `passwd` (비밀번호), `user_flag` (1: 학부생) |
| **빠른 수강신청** | `POST` | `/sugang/NSugangWlsn0410` | `dir=1`, `cmd=aply`, `urltype=direct`, `getsbjt_no` (6자리), `getclss_no` (2자리), `ic_sbjcd` (8자리) |
| **신청 확인/취소** | `GET` | `/sugang/new/sugang_wlsn04110.jsp` | 확정 신청 내역 및 총 취득학점 테이블 파싱 |
| **장바구니 조회** | `GET` | `/sugang/new/sugang_wlsn04120.jsp` | 예비수강신청 과목 목록 및 여석 조회 |
| **전공강좌 조회** | `GET` | `/sugang/new/sugang_wlsn0417_3.jsp` | 스마트융합보안학과 개설 강좌 및 실시간 잔여석 |
| **교양강좌 조회** | `GET` | `/sugang/new/sugang_wlsn0417_2.jsp` | `ic_kwa` (영역코드: B41001 교필, B41002 교선 등), `ic_kwa_1` (세부영역) |

---

## 🚀 빠른 시작 (Quick Start)

### 1. 필수 패키지 설치
```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. 설정 파일 작성 (`config.json`)
`config.example.json`을 복사하여 `config.json`을 생성하고 본인의 학번, 비밀번호, 목표 과목을 입력합니다:

```json
{
  "stdNo": "20261236",
  "passwd": "your_password",
  "user_flag": "1",
  "target_time": "10:00:00",
  "headless": true,
  "discord_bot_token": "YOUR_DISCORD_BOT_TOKEN",
  "discord_channel_id": "YOUR_CHANNEL_ID",
  "hunter_poll_interval": 1.5,
  "courses": [
    {
      "name": "자바프로그래밍언어",
      "code": "576006",
      "bun": "01",
      "fallback_bun": []
    },
    {
      "name": "대순사상과상생윤리",
      "code": "927430",
      "bun": "15",
      "fallback_bun": ["19", "18", "21", "22", "03"]
    }
  ],
  "hunter_targets": [
    {
      "name": "대순사상과상생윤리 (03분반 꿀교수)",
      "code": "927430",
      "bun": "03"
    }
  ]
}
```

---

## 💻 실행 방법

### 1) [정각 신청] 패킷 직결 스나이퍼 실행
```bash
python3 packet_sniper.py
```

### 2) [취소표 줍기] 실시간 빈자리 주워담기 스나이퍼 실행
```bash
python3 vacancy_hunter.py
```

### 3) [브라우저] 자동화 스나이퍼 실행
```bash
python3 browser_sniper.py
```

### 4) 실시간 개설 강좌 & 잔여석(여석) 조회 유틸리티
```bash
python3 query_courses.py
```

### 5) 대진대 서버 네트워크 지연 시간(Ping) 및 시계 동기화 측정
```bash
python3 latency_sync.py
```

---

## 📋 파일 구조 (Project Structure)

```
daejin-sugang/
├── README.md               # 프로젝트 매뉴얼 및 엔드포인트 역공학 분석 문서
├── config.example.json     # 설정 템플릿
├── requirements.txt        # 의존성 패키지 목록
├── packet_sniper.py        # [엔진 1] 초고속 순수 HTTP 패킷 스나이퍼
├── vacancy_hunter.py       # [엔진 2] 취소표 실시간 감시 및 자동 줍기 스나이퍼
├── browser_sniper.py       # [엔진 3] Playwright 브라우저 자동화 스나이퍼
├── query_courses.py        # 실시간 개설강좌/잔여석/확정내역 조회 도구
├── latency_sync.py         # 대진대 서버 정밀 RTT & 시계 오차 동기화 측정기
└── .gitignore              # 개인정보 및 로그 파일 배제
```

---

## ⚠️ 라이선스 및 면책 조항 (Disclaimer)
* 본 소프트웨어는 대진대학교 학사 행정 시스템 학습 및 연구 목적으로 제작되었습니다.
* 과도한 트래픽 유발을 방지하도록 최적화되어 있으며, 실제 사용에 따른 모든 책임은 사용자 본인에게 있습니다.
