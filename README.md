# 🎓 대진대학교 초고속 실시간 수강신청 옵저버 & 자동화 스위트 (Daejin Sugang Suite)

대진대학교(`dreams2.daejin.ac.kr`) 수강신청 시스템을 위한 **초고속 실시간 잔여석 모니터링(SSE 스트림 웹 대시보드)** 및 **직접 패킷 인젝션 기반 자동 수강신청/취소표 스나이핑 스위트**입니다.

---

## 🌐 1. 실시간 웹 옵저버 대시보드 (`https://daejin.qucord.com`)

브라우저 DOM 및 자바스크립트 렌더링 오버헤드 없이 백그라운드에서 병렬 스크래핑한 실시간 잔여석 데이터를 웹으로 제공합니다.

- 🌐 **공용 배포 주소**: **[https://daejin.qucord.com](https://daejin.qucord.com)**
- ⚡ **단방향 SSE (Server-Sent Events) 스트림 (`/api/stream`)**:
  - 클라이언트가 무겁게 전체 JSON을 폴링하지 않고 연결을 유지하다가, **빈자리 변동 발생 시 0.01초 만에 Diff 패킷만 실시간 푸시**.
  - 네트워크 단절 시 자동 폴링 폴백(Fallback) 및 자동 재연결 지원.
- 🎯 **광범위한 모니터링 영역 (총 510+ 과목 상시 감시)**:
  - 1전공 (스마트융합보안학과 전공)
  - 타전공 (경영학과 전공 등)
  - 교양필수 (사고와표현, 영어읽기와토론, 대순사상과상생윤리, AI시대의컴퓨팅사고 등 전 분반)
  - 교양선택 1~6영역 (인간과소통, 사회와경제, 과학과기술, 예술과문화, 융합과혁신, AI·디지털리터러시) 및 7~C영역 전체
  - 교직 및 일반선택 강좌
- 📊 **다채로운 정렬(Sort) 및 필터 기능**:
  - **드롭다운 및 열 헤더 1클릭 정렬**: 여석 많은 순(기본), 여석 적은 순(마감임박 줍기용), 과목명순, 학수번호순, 교수명순, 신청자순.
  - **카테고리별 분리**: 스마트융합보안, 경영학과, 교필, 교선 1~6영역별 전용 필터.
  - **빈자리만 보기 토글**: 마감된 과목 제외하고 즉시 들어갈 수 있는 과목만 확인.
- 🔔 **취소표 오디오 알림 & 티커 피드**:
  - 마감 과목에 빈자리 발생 시 실시간 `삐-` 사운드 알림 및 상단 티커 피드 갱신.
- 📋 **학수번호 1클릭 복사**:
  - 우측 복사 버튼 클릭 시 `과목번호-분반`이 클립보드에 복사되어 빠른 수강신청 창에 `Ctrl+V` 가능.

---

## 🛠 2. 통합 CLI 마스터 도구 (`sugang.py`)

터미널에서 수강신청 상태 조회, 과목 검색, 즉시 신청, 서버 시간 동기화 등을 원클릭으로 실행할 수 있습니다.

```bash
# 확정 수강신청 내역 및 취득/신청 가능 학점 확인
python3 sugang.py status

# 예비수강 장바구니 목록 및 실시간 잔여석 조회
python3 sugang.py cart

# 실시간 과목 검색 (과목명, 교수명, 학수번호, 강의시간)
python3 sugang.py search "회계원리"
python3 sugang.py search "김자원"

# 현재 빈자리(여석 > 0) 있는 과목만 조회 (카테고리 필터 가능)
python3 sugang.py open
python3 sugang.py open "경영"

# 특정 학과 개설 전공강좌 실시간 잔여석 조회
python3 sugang.py dept 경영학과
python3 sugang.py dept 컴공
python3 sugang.py dept 보안

# 단일 과목 즉시 초고속 수강신청 (패킷 직전송)
python3 sugang.py apply 121001 01

# 대진대 서버 정밀 시계 오차(Offset) 및 네트워크 RTT 측정
python3 sugang.py sync
```

---

## 🚀 3. 자동 수강신청 & 취소표 스나이퍼 모듈

### 🎯 1) 본 수강신청 10:00:00 정각 스나이퍼 (`packet_sniper.py`)
- **방식**: 브라우저를 띄우지 않고 HTTP POST(`/sugang/NSugangWlsn0410`)를 직접 쏘는 방식 (과목당 ~0.005초 소요).
- **특징**:
  - 대진대 서버 `Date` 헤더 기반 마이크로초 단위 네트워크 지연시간(RTT) 보정.
  - 10:00:00 정각 세션 획득 후 담아둔 과목 목록을 멀티스레드로 동시 사출.
  - 마감 시 2지망 분반으로 5ms 안에 자동 스위칭(Fallback Chain).

```bash
# config.json에 등록된 장바구니/목표 과목을 10:00:00 정각에 자동 신청
python3 packet_sniper.py config.json
```

### 🏹 2) 24시간 취소표 자동 주워담기 (`vacancy_hunter.py`)
- **방식**: 마감된 목표 과목들의 잔여석을 백그라운드에서 고속 폴링하다가, 누군가 수강을 취소하는 즉시 0.01초 만에 신청 패킷을 전송해 낚아챔.
- **특징**: 세션 만료 시 자동 재로그인(Keep-Alive), 성공 시 디스코드 DM 즉시 알림.

```bash
python3 vacancy_hunter.py config.json
```

### 🔄 3) 원자적 수강 교체 스와퍼 (`atomic_swapper.py`)
- **방식**: 수강신청 학점이 꽉 찬 상태에서, 목표 과목에 자리가 나는 순간 **기존 수강과목을 취소(Drop)함과 동시에 목표과목을 신청(Apply)**하는 원자적 교환기.

```bash
# [버릴과목] 927430-25 (대순사상) -> [잡을과목] 922613-01 (AI와스마트라이프)
python3 atomic_swapper.py config.json
```

---

## ⚙️ 4. 설정 파일 및 모듈별 `config.json` 스키마 가이드

모든 자동화 도구(`packet_sniper.py`, `vacancy_hunter.py`, `atomic_swapper.py`, `sugang.py`)는 동일한 `config.json` 파일을 공유하며, 각 모듈에 필요한 블록만 채워 넣으면 바로 작동합니다.

### 📋 통합 `config.json` 전체 템플릿
```json
{
  "stdNo": "20261236",
  "passwd": "YOUR_PORTAL_PASSWORD",
  "user_flag": "1",
  "discord_bot_token": "",
  "discord_channel_id": "",

  "target_time": "10:00:00",
  "courses": [
    {
      "name": "자바프로그래밍언어",
      "code": "576006",
      "bun": "01",
      "fallback_bun": ["02", "03"]
    },
    {
      "name": "대순사상과상생윤리",
      "code": "927430",
      "bun": "15",
      "fallback_bun": ["19", "18", "21", "22", "03"]
    }
  ],

  "hunter_poll_interval": 1.5,
  "hunter_targets": [
    {
      "name": "대순사상과상생윤리 (03분반 꿀교수)",
      "code": "927430",
      "bun": "03"
    },
    {
      "name": "영어읽기와토론 (12분반)",
      "code": "927284",
      "bun": "12"
    }
  ],

  "swap_targets": {
    "drop_course": {
      "name": "대순사상과상생윤리 (현재 보유 분반)",
      "code": "927430",
      "bun": "25"
    },
    "wanted_courses": [
      {
        "name": "1순위: AI기반프로그래밍입문",
        "code": "922605",
        "bun": "01"
      },
      {
        "name": "2순위: AI시대의콘텐츠크리에이션",
        "code": "922616",
        "bun": "02"
      }
    ],
    "rollback_course": {
      "name": "롤백용 안전 대안과목",
      "code": "927430",
      "bun": "25"
    }
  }
}
```

---

### 🔍 모듈별 필수 스키마 상세 설명

#### 1) 공통 설정 (Common)
| 필드명 | 타입 | 필수 여부 | 설명 |
|---|---|---|---|
| `stdNo` | `string` | **필수** | 대진대학교 포털 학번 8자리 (예: `"20261236"`) |
| `passwd` | `string` | **필수** | 대진대학교 포털 비밀번호 |
| `user_flag` | `string` | 선택 (기본 `"1"`) | 재학생 구분 플래그 (`"1"`: 학부생) |
| `discord_bot_token` | `string` | 선택 | 성공 알림 전송용 디스코드 봇 토큰 (미사용 시 `""`) |
| `discord_channel_id` | `string` | 선택 | 알림 수신할 디스코드 채널 ID (미사용 시 `""`) |

---

#### 2) `packet_sniper.py` (정각 10:00:00 일괄 스나이퍼) 스키마
10시 정각 수강신청 오픈과 동시에 멀티스레드로 쏠 과목 목록과 분반 마감 시 대체할 2지망 체인을 설정합니다.

| 필드명 | 타입 | 설명 |
|---|---|---|
| `target_time` | `string` | 발사 목표 시각 (KST, 형식: `"10:00:00"`) |
| `courses` | `array` | 동시 신청할 1지망 과목 객체 배열 |
| `courses[].code` | `string` | 6자리 과목번호 (예: `"576006"`) |
| `courses[].bun` | `string` | 2자리 분반 (예: `"01"`) |
| `courses[].name` | `string` | 식별용 과목명 |
| `courses[].fallback_bun` | `array[string]` | **1지망 마감 시 5ms 내 즉시 순차 시도할 대체 분반 목록** (예: `["02", "03"]`) |

---

#### 3) `vacancy_hunter.py` (24시간 백그라운드 취소표 헌터) 스키마
누군가 취소하여 빈자리가 나는 순간 즉시 주워담을 목표 과목들을 설정합니다.

| 필드명 | 타입 | 설명 |
|---|---|---|
| `hunter_poll_interval` | `float` | 잔여석 감시 폴링 주기 초 단위 (기본: `1.5`초) |
| `hunter_targets` | `array` | 빈자리 발생 시 즉시 낚아챌 목표 과목 객체 배열 |
| `hunter_targets[].code` | `string` | 6자리 과목번호 (예: `"927430"`) |
| `hunter_targets[].bun` | `string` | 2자리 분반 (예: `"03"`) |
| `hunter_targets[].name` | `string` | 식별용 과목명 |

---

#### 4) `atomic_swapper.py` (학점 한도 초과 방지 원자적 맞교환기) 스키마
학점(18학점)이 가득 차 있어 신규 신청이 불가능할 때, 목표 과목에 자리가 생기는 순간 **기존 과목 드랍 ➔ 신규 과목 신청**을 10ms 만에 원자적으로 맞바꿉니다.

| 필드명 | 타입 | 설명 |
|---|---|---|
| `swap_targets.drop_course` | `object` | **자리가 났을 때 버릴(취소할) 현재 보유 과목** (`code`, `bun`, `name`) |
| `swap_targets.wanted_courses` | `array` | **감시할 희망 과목 목록 (우선순위 순서대로 배치)** (`code`, `bun`, `name`) |
| `swap_targets.rollback_course` | `object` | **교체 신청이 찰나에 실패했을 때 안전하게 원상복구할 백업 과목** |

---

### `targets.json` (웹 옵저버 모니터링 대상 - 핫 리로드 지원)
서버 재시작 없이 `targets.json`에 학과/영역 URL을 추가하면 옵저버가 실시간으로 자동 감지하여 모니터링에 반영합니다.

```json
[
  { "type": "major", "url": "https://dreams2.daejin.ac.kr/sugang/new/sugang_wlsn0417_3.jsp", "name": "스마트융합보안학과 전공" },
  { "type": "major", "url": "https://dreams2.daejin.ac.kr/sugang/new/sugang_wlsn0417_1.jsp?ic_kwa=B41005&ic_kwa_1=AA0242", "name": "경영학과 전공" }
]
```

---

## 🖥 5. 서버 백그라운드 데몬 관리 (Systemd)

웹 옵저버는 라즈베리파이 백그라운드 서비스(`daejin-observer.service`)로 24시간 풀가동됩니다.

```bash
# 서비스 상태 확인
sudo systemctl status daejin-observer.service

# 서비스 재시작 (디스크 캐시 기반 0초 복구)
sudo systemctl restart daejin-observer.service

# 실시간 로그 모니터링
journalctl -u daejin-observer.service -f
```

---

## 📡 6. REST & SSE API 엔드포인트

| 엔드포인트 | 메서드 | 설명 |
|---|---|---|
| `GET /` | HTML | 반응형 실시간 옵저버 웹 대시보드 |
| `GET /api/stream` | SSE | 실시간 잔여석 변동 및 취소표 스트림 (`EventSource`) |
| `GET /api/data` | JSON | 전체 510개 강좌 및 실시간 상태 스냅샷 (Zero-Copy 메모리 캐시) |
| `POST /api/reload_targets` | JSON | `targets.json` 모니터링 대상 즉시 리로드 |

---

## 🤖 7. CI/CD 자동 빌드 & 릴리즈 파이프라인 (GitHub Actions)

로컬 머신에서 바이너리를 직접 빌드/배포하지 않고, GitHub Actions CI/CD를 통해 버전 태그 푸시 시 자동으로 Windows 및 macOS(Apple Silicon) 단일 실행 파일이 빌드 및 릴리즈됩니다.

### 📦 지원 OS 및 산출물
- **Windows (x64)**: `DaejinSugangSuite-Windows-x64.exe` (독립 실행 파일)
- **macOS (Apple Silicon M1/M2/M3/M4)**: `DaejinSugangSuite-macOS-AppleSilicon.zip` (`.app` 번들)

### 🚀 새 버전 릴리즈 방법
```bash
# 1. 버전 태그 생성 (예: v1.0.1)
git tag v1.0.1

# 2. 태그 푸시 -> GitHub Actions가 자동으로 Windows & macOS 빌드 후 Releases에 업로드
git push origin v1.0.1
```

- **워크플로우 파일**: `.github/workflows/release.yml`
- **동작**: `windows-latest` 및 `macos-latest` 환경에서 각각 독립 실행 앱을 패키징하여 GitHub Releases에 자동 등록.


