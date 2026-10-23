# KSEcho 연구 자료 — 심초음파 영상 AI

한국심초음파학회(KSEcho) / Journal of Cardiovascular Imaging(JCVI) 투고를 준비하며 만든 슬라이드 덱과 보고서 모음.

- 공개 데이터(PhysioNet MIMIC-IV-ECHO, EchoNet-Dynamic, CAMUS)로 무엇이 가능한지
- 심초음파 영상 AI에서 비어 있는 영역이 어디인지
- 도플러 기반 E/e′ 자동화를 실제로 어떻게 설계하는지

## 보기

| 문서 | 형식 | 내용 |
|---|---|---|
| [ai-tracks.html](ai-tracks.html) | 슬라이드 15장 | 공개 데이터 지형, 트랙 A·B·C, 6개월 일정 |
| [doppler-protocol.html](doppler-protocol.html) | 슬라이드 17장 | 도플러 E/e′ 실험설계, 코호트·평가·킬 스위치 |
| [reports/mimic-open-data.html](reports/mimic-open-data.html) | 스크롤 문서 12p | 데이터 접근 문제, 주제 후보 5개, 12주 계획 |

슬라이드는 키보드 `←`/`→` 로 이동, `f` 전체화면, `n` 발표자 노트.

## 구조

```
pdf/      인쇄·배포용 PDF
notes/    슬라이드별 발표자 노트 (markdown)
source/   덱 소스(JSON) · 테마 토큰(CSS)
reports/  스크롤 보고서
```

## 데이터 출처

- PhysioNet **MIMIC-IV-ECHO** v1.0.1 — 구조화 측정 206,488검사 / 91,372명, 2008–2022 (credentialed access)
- Stanford AIMI **EchoNet-Dynamic** — 10,030 심첨 4방 영상
- **CAMUS** — 500명, 3 view
- PhysioNet **ECHOVIEW** — MIMIC-IV-ECHO 기계 생성 뷰 주석 29,196검사
- 학술지: *Journal of Cardiovascular Imaging* (e-jcvi.org), PubMed·Scopus 색인

## 주의

- 수치는 각 데이터셋 공식 기술 문서 기준이며, 확인하지 못한 값은 문서 안에 "확인 필요"로 표시했다.
- 환자 정보는 포함하지 않는다. MIMIC 데이터는 재배포 금지(DUA)이므로 원자료는 이 저장소에 없다.
- 이 저장소는 연구 계획 문서이며, 임상 판단의 근거로 쓰일 수 없다.
