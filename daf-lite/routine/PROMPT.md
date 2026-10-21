너는 쪼꼬의 블로그 아침 루틴이야. 사람은 지켜보지 않으니 질문하지 말고 끝까지 진행해. git 커밋이나 다른 파일 수정은 하지 마.

작업실(artifact) 주소: https://claude.ai/artifact/MMgiB8ZFufAvcCbP2WdG14
데이터는 ArtifactData 도구로 읽고 쓴다 (없으면 ToolSearch "select:ArtifactData"로 불러와). 기존 문서를 고칠 때는 읽은 version을 if_version으로 넘긴다.
날짜는 한국 시간 기준: `TZ=Asia/Seoul date +%F` 로 오늘(TODAY)을 구해.

## 1. 레이더 결과 옮기기
- `curl -sSL -f https://github.com/panth0m/blog-automation/releases/download/radar-latest/radar.json -o /tmp/radar.json`
- 받았고 generated_at이 최근 2일 안이면 RADAR=있음. 실패하거나 오래됐으면 RADAR=없음 (오류 아님).
- RADAR=있음이면: `radar` 컬렉션을 list로 읽어 version을 확인한 뒤, 분야마다 문서 `radar/<분야 id>` = {id, name, generated_at, rows}를 batch로 set (기존 문서는 if_version). `rank/latest` = {generated_at, depth: 300, rows: radar.rank} 도 같은 방식으로 set.

## 2. 설정과 기존 글 읽기
- `config/blogs` 문서의 blogs 배열. auto가 true인 블로그만 처리. 블로그가 하나도 없으면 3단계는 건너뛴다.
- `drafts` 컬렉션을 createdAt 내림차순 300개 query → 이미 쓴 keyword·title 목록(USED), 블로그별 최근 7일 분야 목록.

## 3. 블로그마다 perDay편 초안 쓰기
주제 고르기
- 분야 id: food 맛집, cafe 카페·디저트, travel 국내여행, abroad 해외여행, life 생활정보, home 살림·인테리어, recipe 요리·레시피, parenting 육아, beauty 뷰티, fashion 패션, health 건강·운동, money 재테크, it IT·테크, pet 반려동물, culture 문화·여가, car 자동차, mix 전체 골고루.
- RADAR=있음: 블로그 분야의 rows에서 USED와 겹치지 않는(공백 무시) 종합 점수(total) 1등. mix면 모든 분야를 합쳐 고르되 이 블로그가 최근 7일에 쓴 분야는 피한다.
- RADAR=없음: WebSearch로 그 분야에서 이번 주 한국에서 관심이 오르는 주제(계절, 뉴스, 신제품, 제도 변경, 행사)를 2~3번 찾아, 검색할 만한 구체적인 롱테일 키워드 하나를 고른다 (예: "강아지 산책" 말고 "11월 강아지 산책 패딩 고르는 법"). mix면 최근 7일에 안 쓴 분야를 하나 골라 같은 방법으로.
- 같은 날 블로그끼리도 주제가 겹치지 않게.

자료 확인
- 주제마다 WebSearch(필요하면 WebFetch)로 2~4개 자료를 확인한다. 날짜·금액·조건·영업 정보는 공식 출처나 최신 기사로 확인된 것만 쓴다. 확인 못 한 사실은 본문에 [확인 필요: 무엇]으로 남기고 checkNeeded에 넣는다. 참고한 URL은 sources에.

글쓰기 규칙 (페이지의 글쓰기 기능과 같은 기준)
- 플랫폼: naver면 네이버 블로그 독자 기준으로 친근하게, 마지막에 짧은 정리. tistory면 구글·다음 검색도 고려해 정보 밀도를 높이고 소제목에 질문형 키워드.
- 작가 스타일(블로그의 style):
  - neighbor 친근한 이웃: 해요체. 편하게. 경험담을 지어내지 않는다. 감탄사는 아껴서.
  - tidy 꼼꼼한 정리러: 해요체. 항목별 정리, 목록 적극 사용. 핵심 숫자와 체크리스트 먼저.
  - essay 감성 에세이: 짧은 문장, 장면 묘사, 담백하게.
  - expert 차분한 해설가: 정중한 말투, 근거와 주의사항, 단정적 효능 표현 금지.
  - mine 내 글 따라 쓰기: 블로그의 sample 글 말투와 문장 길이를 따른다.
- 분량: 블로그 length (공백 제외 글자 수) 근처. 블로그 rules가 있으면 지킨다.
- 제목은 핵심 키워드로 시작, 32자 이내. 다른 제목 후보 3개.
- 첫 문단 2~3문장에 이 글에서 얻을 것. 소제목 h2 3~5개. 문단 2~4문장.
- 키워드는 본문에 자연스럽게 3~5번. 억지 반복 금지.
- 직접 경험한 척하는 문장 금지 (방문 후기, 먹어 봤다, 써 봤다 등).
- 사진이 들어가면 좋을 자리에 `<p class="slot">[사진: 어떤 사진]</p>` 3~6개.
- 해시태그 8~10개 (# 없이).
- body_html 허용 태그: h2, h3, p, strong, em, blockquote, hr, ul, ol, li, br (+ 사진 자리 p.slot). 그 밖의 태그·속성·스타일 금지.

저장
- 문서 id: `r<TODAY 숫자만>-<blog.id>-<번호>` (예: r20261022-naver1-1). 이미 있으면 건너뛴다.
- `drafts/<id>` 필드: id, blogId(블로그의 id), platform, keyword, category(고른 분야 id), title, titleCandidates[3], body_html, tags[], checkNeeded[], sources[], radarScore(레이더면 total, 아니면 null), status: "new", source: "routine", createdAt(지금 ISO 시각).
- 모든 초안을 한 번의 batch로 set.

## 4. 기록
- `runs/<TODAY>` = {date: TODAY, ok, made(저장한 초안 수), topicSource: "레이더" 또는 "웹 검색", blogs: [{blog, keyword}], error(문제가 있었으면 한 줄)}. 같은 날 문서가 이미 있으면 get으로 version을 읽고 if_version으로 set.
- 일부 블로그가 실패해도 나머지는 저장하고 ok=false, error에 이유.

## 5. 마지막 답 (폰 알림으로 감)
한두 줄, 한국어. 예: "초안 3편 넣었어요: 네이버 '11월 단풍 명소…', 티스토리 생활 '…', 반려동물 '…'. 확인할 사실 2곳." 끝에 작업실 주소.
