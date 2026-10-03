# 글별 동적 썸네일

일반 블로그의 새 글은 제목·정보성 소제목·본문 일부를 읽어 Codex의 native ImageGen으로
주제별 그림을 생성한다. 폐 질환·위 질환·엑셀·제품 비교 등은 서로 다른 장면을 요청한다.
글마다 생성되지만 같은 글의 재시도는 제목·전체 본문·디자인 버전·모델을 묶은 캐시를 사용한다.
기존 글의 이미지나 예약 시간은 변경하지 않는다.

생성된 배경 위에 번들 한글 폰트로 제목을 합성한다. 원문 제목의 앞부분만 사용하며
42자를 넘으면 생략 표시를 한다. 원본은 1200×900 JPG이고 제목은 중앙 정사각형 크롭 안에 둔다.
그림에 글자를 직접 맡기지 않아 한글 오탈자 위험을 줄인다. 일러스트임을 표시하며
치료 효과·실제 제품 사양·인증을 꾸며 내는 장면은 요청하지 않는다.

## 실행 경로

`pipeline` → `create_editorial_thumbnail` → `create_dynamic_thumbnail` →
`CodexSubscriptionClient.generate_image` → JPG 합성 → 기존 WordPress 미디어 업로드.

- 기본 `BLOG_THUMBNAIL_PROVIDER=codex`; 일반·큐 발행 workflow에 명시한다.
- 인증은 기존 전용 `BLOG_CODEX_HOME/auth.json`을 사용한다. 이미지 호출도 구독 한도를 사용하며
  별도 OpenAI API 키나 Gemini 과금으로 자동 전환하지 않는다.
- 이미지 호출에서는 shell·앱·브라우저·다중 에이전트·웹 검색을 끈다. WordPress/API 비밀을 전달하지 않는다.
- CLI의 `thread.started` 이벤트로 현재 생성 폴더를 찾는다. 모델이 출력한 파일 경로나 URL은 믿지 않는다.
  심볼릭 링크·복수 결과·너무 큰 파일·깨진 이미지·잘못된 가로세로 비율은 거부한다.
- 이미지 생성은 최대 240초 한 번만 요청한다. 실패하면 기존 도형 썸네일로 발행을 이어가며
  `provider=editorial_fallback`, 분류된 실패 사유를 기록한다. 대체 결과를 동적 생성 성공으로 보고하지 않는다.
- `data/generated-thumbnails/*.json`에 공급자·버전·이미지/본문/프롬프트 해시를 기록하고
  일반·큐 발행의 로그 artifact에도 이 JSON을 포함한다. 인증 파일은 포함하지 않는다.
- `BLOG_THUMBNAIL_PROVIDER=editorial`은 명시적 오프라인/장애 대응용이다.
- `BLOG_CODEX_IMAGE_MODEL`은 선택적 Codex 주 모델 지정값이다. 이미지 API 모델명과 혼동하지 않는다.

## 검증과 적용

로컬 기본 미리보기는 오프라인이다. `--provider codex`는 실제 구독 호출이므로 전용 인증이 필요하다.

```sh
python scripts/preview_editorial_thumbnails.py --provider codex --sample lung --output "$PREVIEW_OUTPUT"
```

`Dynamic Thumbnail Check` workflow는 운영과 동일한 CLI 버전·구독 인증·동시 실행 그룹으로
한 장을 생성한다. 글을 만들거나 WordPress에 접속하지 않으며, 대체 이미지로 끝나면 실패 처리한다.
머지 후 main에서 이 workflow를 실행해 artifact와 `codex_imagegen` 기록을 확인한 다음
실제 자동 발행 글의 대표 이미지와 본문 상단 이미지까지 확인한다.

구현 시 관련 회귀 테스트 407개 통과, 변경 모듈 커버리지 95.22%, 새 모듈·테스트 Ruff 검사와
`git diff --check` 통과를 확인했다. 건강·엑셀 주제의 실제 ImageGen 그림과 합성 결과도 육안 검증했다. 시각 검증용 그림은 대화 내 내장 도구로 생성했으며, CI의 Codex exec 연결 성공 증거와는 다르다.
2026-10-04 KST 사용자 승인으로 PR #82를 main에 머지했다
(`76f249ff4eed57464c26f9498d62c55337e4770e`). 이후 운영 인증을 사용하는
`Dynamic Thumbnail Check` 두 실행이 모두 성공했다.

- [건강/폐암 생성 실행](https://github.com/hhj4861/wp-auto-blog/actions/runs/37163170347):
  폐 모형 그림, `provider=codex_imagegen`, 1200×900 JPG.
- [생산성/엑셀 생성 실행](https://github.com/hhj4861/wp-auto-blog/actions/runs/37163283872):
  조건별 셀 강조 그림, `provider=codex_imagegen`, 1200×900 JPG.

두 실행의 이미지·본문·프롬프트 해시가 서로 다르고, 이미지 해시는 내려받은 실제 파일과 일치한다.
최종 JPG를 직접 열어 주제별 그림과 한글 제목을 확인했다. 두 실행 모두 인증 복원·생성·artifact 업로드·
인증 갱신 저장과 정리가 성공했다. 실패 대체 썸네일을 성공으로 처리한 결과가 아니다.
운영 main 및 일반·큐 자동 포스팅에 적용됐으며 다음 새 글부터 사용한다.
이번 검증은 이미지 생성 전용으로 새 글을 발행하거나 기존 글의 대표 이미지를 수정하지 않았다.
새 방식의 WordPress 업로드·공개 페이지 반영은 이후 실제 자동 발행에서 확인할 항목이다.

구현 근거: [Codex CLI 공식 문서](https://learn.chatgpt.com/docs/developer-commands),
[운영 버전의 native ImageGen 계약](https://github.com/openai/codex/blob/rust-v0.153.0/codex-rs/ext/image-generation/imagegen_description.md),
[이미지 파일 저장 검증](https://github.com/openai/codex/blob/rust-v0.153.0/codex-rs/app-server/tests/suite/v2/imagegen_extension.rs).
