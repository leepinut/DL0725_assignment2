# LMS Assignment to Google Calendar Sync

## 📖 프로젝트 개요

이 프로젝트는 명지대학교 LMS에서 과제 정보를 자동으로 가져와 Google Calendar에 직접 동기화하는 프로그램입니다.

평소 LMS에서 직접 과제를 확인하기보다는 캘린더를 통해 마감 일정을 관리하는 경우가 많아, 매번 수동으로 일정을 옮기는 과정이 번거로웠습니다. 이를 해결하기 위해 자동으로 LMS 과제 정보를 크롤링하여 Google Calendar API를 통해 바로 일정으로 등록하도록 구현했습니다.

---

## ✨ 주요 기능

- **LMS 자동 로그인**: Selenium을 이용해 LMS에 자동으로 로그인합니다.
- **과제 정보 수집**: 과목명, 과제명, 마감일을 자동으로 수집합니다.
- **Google Calendar 연동**: Google Calendar API를 이용해 수집된 과제를 일정으로 자동 등록합니다.
- **중복 방지 및 업데이트**: 이미 등록된 과제는 중복 생성하지 않으며, 마감일 등 변경된 내용이 있다면 기존 일정을 자동으로 업데이트합니다.

---

## ⚙️ 설치 방법

#### 1. 저장소 클론 (Clone)
```bash
git clone https://github.com/leepinut/DL0725_assignment2.git
cd DL0725_assignment2
```

#### 2. 필요 라이브러리 설치
```bash
pip install -r requirements.txt
```

#### 3. Google Calendar API 설정
1.  **[Google Cloud Console](https://console.cloud.google.com/flows/enableapi?apiid=calendar-json.googleapis.com)** 에 접속하여 새 프로젝트를 생성하고 **Google Calendar API를 활성화**합니다.
2.  `사용자 인증 정보` > `+ 사용자 인증 정보 만들기` > `OAuth 클라이언트 ID`를 선택합니다.
3.  애플리케이션 유형을 **"데스크톱 앱"**으로 선택하고 클라이언트 ID를 생성합니다.
4.  생성된 ID 옆의 다운로드 버튼을 눌러 `credentials.json` 파일을 다운로드한 후, 프로젝트 폴더 최상단(`lms-calendar-sync` 폴더 안)에 저장합니다.

> ✅ **참고**: 민감한 정보가 담긴 `credentials.json` 파일은 `.gitignore`에 이미 등록되어 있어, 실수로 GitHub에 업로드되지 않도록 안전하게 처리되어 있습니다.

---

## 🚀 사용 방법

#### 1. LMS 계정 정보 입력
프로젝트 폴더에 `config.json` 파일을 생성하고 아래와 같이 LMS 로그인 정보를 입력합니다.

```json
{
  "LMS_URL": "https://lms.mju.ac.kr",
  "USERNAME": "YourUsername",
  "PASSWORD": "YourPassword"
}
```

#### 2. 스크립트 실행
터미널에서 아래 명령어를 실행합니다.
```bash
python main.py
```

#### 3. 최초 실행 시 구글 인증
- 스크립트를 처음 실행하면, 웹 브라우저가 자동으로 열리며 Google 계정 인증 화면이 나타납니다.
- 캘린더에 접근할 본인 계정을 선택하고, 권한을 **"허용"**합니다.
- 인증이 완료되면 `token.pickle` 파일이 생성되며, 다음 실행부터는 이 과정을 자동으로 처리합니다.

---

## 📄 결과물

- 스크립트 실행이 완료되면, LMS의 새로운 과제나 변경된 과제들이 자동으로 Google Calendar에 반영됩니다.
- **과제 제목**: `[과목명] 과제명` 형식으로 등록됩니다.
- **이벤트 날짜**: 과제 마감일에 맞추어 종일 이벤트로 생성됩니다.
- **설명**: LMS 페이지로 바로 갈 수 있는 링크가 포함됩니다.

> **팁**: Windows의 `작업 스케줄러`나 macOS/Linux의 `cron`을 사용하면, 매일 특정 시간에 이 스크립트를 자동으로 실행하여 동기화를 완벽하게 자동화할 수 있습니다.