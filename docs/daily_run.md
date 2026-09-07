# v2 운영 절차

## 매일

1. gen_report.py health에서 수집·추출·EPS·명령 처리의 마지막 성공 시각과 실패 원인을 확인한다.
2. gen_report.py board에서 기한 도래, 지표 부족, 반증 조건 발동을 먼저 검토한다.
3. 신규 후보는 원문에서 기업·사건·기간·수치를 확인하고 최대 3건을 검토한다. 대형 고객 발표는 공급자 가설의 수요 근거로 연결한다.
4. 등록 시 기업 식별자와 thesis_key를 지정한다. 새 뉴스가 같은 가설이면 기존 idea_id에 근거를 추가한다.
5. 연구자의 판단 변경은 add_entry로 이유와 다음 점검일을 입력한다. 신호 추가만으로 최근 점검일을 갱신하지 않는다.

## 수동 컨센서스 관측

FMP HTTP 402 해결 전에는 이용 권한이 있는 출처에서 동일 회계기간 추정치와 시점을 확인하여 입력한다. 아래는 형식 설명이며 실제 값으로 채운 후 실행한다. 서로 다른 제공자를 하나의 시계열로 합치지 않는다.

```json
{
  "target_table": "metric_log",
  "data": {
    "종목/업종": "CRDO",
    "entity_id": "NASDAQ:CRDO",
    "지표명": "EPS consensus",
    "as_of": "실제 관측일 YYYY-MM-DD",
    "period_end": "확인된 대상 회계연도 종료일 YYYY-MM-DD",
    "fiscal_period": "annual",
    "metric_kind": "consensus",
    "단위": "per share",
    "통화": "USD",
    "회계기준": "provider-defined",
    "출처": "실제 제공자명",
    "출처URL": "해당 자료 URL",
    "현재값": "확인된 수치",
    "data_quality": "live"
  }
}
```

같은 날 값이 바뀌면 timezone이 포함된 실제 as_of 시각을 사용한다. 하루 여러 관측은 일별 마지막 값 하나로 리비전을 계산한다. 같은 관측을 다시 넣으면 같은 ID를 반환하며 값이 충돌하면 거부한다. 유지 관측도 정상 기록한다.

## 매주

weekly 보고서에서 강화·약화·자료 부족을 근거 ID와 함께 검토한다. 시계열이 없는 아이디어를 기사량으로 승격하지 않는다. evaluate.py가 만든 티어별 표본을 원문 대조 후 evaluation_log에 별도 등록한다. 판정 전 미확인 행을 통과로 계산하지 않는다. 아직 30/90/180일 수익률 자동 복기는 없다.

## 장애 및 운영 전환

- 402: 현재 공급자 접근 불가. 자동 결제 없이 수동 자료를 사용하거나 계약 권한을 확인한다.
- 429/모델 오류: 추출 재시도 원장을 유지한다. 수집을 다시 실행하면 기한이 된 재시도도 처리한다.
- 손상된 알림 상태: 발송이 중단된다. pushed ID를 백업에서 복원한다.
- 쓰기 중단: migrate_v2.py 또는 다음 원장 읽기에서 pending_tables.json을 복구한다.
- 운영 전환: 로컬 검증 결과를 검토한 뒤 변경을 원격 main에 반영하고 첫 workflow 실행의 health·저장 상태·실제 응답을 확인한다. 2026-09-07 main 전환·메시지 실발송·실제 workflow 검증을 완료했다. 이후 변경에도 같은 확인 절차를 적용한다.

Telegram 명령 처리 주기를 줄여도 외부 스케줄 지연에 따른 유실 위험은 남는다. Telegram 업데이트 보관 제한은 [Bot API](https://core.telegram.org/bots/api#getting-updates), 스케줄 제약은 [GitHub 문서](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)를 확인한다.
