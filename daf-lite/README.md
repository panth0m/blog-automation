# 블로그 작업실 (DAF 개인판)

DAF(대한AI팩토리) 블로그 도구를 혼자 쓰려고 PC 없이 도는 구조로 다시 만든 것.

| 부분 | 어디서 | 하는 일 |
|---|---|---|
| 키워드 레이더 | GitHub Actions (`.github/workflows/daf-radar.yml`) | 매일 04:17 KST, 네이버 공식 API로 분야별 주제 점수와 내 글 순위를 계산해 `radar-latest` 릴리스에 `radar.json`으로 올림 |
| 아침 루틴 | Claude 예약 작업 "블로그 아침 초안" (06:52 KST) | 레이더 결과를 작업실로 옮기고, 자동 작성이 켜진 블로그마다 초안을 써서 승인함에 넣음. 폰 알림 |
| 작업실 | claude.ai 아티팩트 (`workroom/index.html`) | 승인함, 레이더, 글쓰기, 사진 글쓰기, 체험단 원고·검수, 이웃 댓글 초안, 순위, 설정 |

작업실 주소: https://claude.ai/artifact/MMgiB8ZFufAvcCbP2WdG14
루틴 지시문 원본: `routine/PROMPT.md` (고치면 예약 작업의 프롬프트도 같이 바꿔야 함)

## 레이더 켜기 (한 번만)

1. **검색광고 API**: https://searchad.naver.com 가입 → 도구 → API 사용 관리 → 라이선스 발급. `API 라이선스`, `비밀키`, `CUSTOMER_ID` 세 개를 받는다.
2. **개발자센터 앱**: https://developers.naver.com/apps → 애플리케이션 등록 → 사용 API에 `검색`과 `데이터랩(검색어 트렌드)` 추가 → `Client ID`, `Client Secret`.
3. GitHub 저장소 → Settings → Secrets and variables → Actions → New repository secret 으로 다섯 개 등록:
   - `NAVER_AD_API_KEY`, `NAVER_AD_SECRET`, `NAVER_AD_CUSTOMER_ID`
   - `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`
4. Actions 탭 → "키워드 레이더" → Run workflow 로 첫 실행. 다음 날 아침 루틴부터 레이더 주제를 쓴다.

키가 없어도 루틴은 웹 검색으로 주제를 골라서 돈다.

## 순위 확인

`radar/config.json`에서
```json
"my_blogs": ["네이버아이디", "티스토리아이디"],
"rank_watch": ["망원동 소금빵", {"keyword": "강아지 패딩", "blog": "티스토리아이디"}]
```
네이버 블로그 검색(정확도순) 300위 안에서 찾는다. 통합검색 화면 위치와는 다를 수 있다.

## 일부러 뺀 것

- **편집기 자동 입력**: 네이버·티스토리 모두 글쓰기 공식 API가 없어서 화면 자동 조작이 필요하고, 화면이 바뀌면 깨진다. 대신 "본문 서식 복사" → 붙여넣기 → 각 플랫폼 예약 발행.
- **이웃 댓글·공감 자동 달기**: 스팸이고 어뷰징 단속 대상. 초안만 만들고 직접 단다.
- **조회수 통계**: 로그인이 필요해서 제외.

## API 한도 (하루)

검색광고 키워드 도구는 분야당 1회, 블로그 검색은 분야당 최대 80회 + 순위 확인 키워드당 3회, 데이터랩은 분야당 16회 정도. 개발자센터 기본 한도(검색 25,000 / 데이터랩 1,000) 안이다.
