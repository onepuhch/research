# V1 구현 결과 — 알림 답장으로 사용자 판단 기록 (2026-10-11)

작성: Claude, 2026-10-11. 지시: [V 검토·구현 지시](v_interaction_review_2026-10-11.md)(Codex). 실제 Telegram 발송·모델 호출 없이 가짜 업데이트와 가짜 전송으로만 검증했다. V2(명령 확인 간격)·V3(자유 질문)는 손대지 않았다. 타이머·워크플로·토큰도 바꾸지 않았다.

## 바뀐 것

| 파일 | 내용 |
|---|---|
| `scripts/candidate_feedback.py` (새 파일) | 낱말 → action 매핑, 답장 대상 알림 찾기, 추가 전용 원장, 카드 한 줄, 보고 집계 |
| `scripts/telegram_cmd.py` | 수신 시 답장 정보를 큐에 저장(원문 없음), `handle_reply`, 추적 결과의 구조화, `--dry-run --reply-to` |
| `scripts/promote.py` | `Refused`(거절 사유 코드, ValueError의 하위 클래스), `active_candidate_idea`, `track_candidate`(success/already_tracked/rejected). 기존 `promote_candidate`의 동작과 메시지는 그대로다 |
| `scripts/candidates.py` | 카드 meta 줄 아래에 최신 사용자 판단 표시 |
| `scripts/discovery_timing.py` | 보고 끝에 '사용자 반응·활용' 절 추가 |
| `scripts/persist_state.py`, `scripts/context_verify.py` | 새 원장을 CI 상태 커밋 목록과 검증 실행 보호 목록에 추가 |
| `config/schema.json` | `json_records.candidate_feedback_event` 필수 필드 |
| `README.md` | 알림 답장 문단 |
| `tests/test_v1_feedback.py` | 시험 23개 |

## 지시서가 정하지 않아 구현자가 정한 것(검토 요청)

1. **같은 메시지인지 확인.** message_id가 한 건만 맞아도, 답장 대상 메시지가 봇이 보낸 것이 아니거나(`from.is_bot=false`), 텔레그램이 준 메시지 시각이 영수증 시각과 10분(`MATCH_WINDOW_S`) 넘게 다르면 연결하지 않는다(모호로 처리). 영수증에 채팅 ID가 없어서, 허용 채팅을 바꾼 뒤 번호가 겹치는 경우에 대비한 것이다.
2. **재처리 때 결과 보존.** 추적 답장의 판단 이벤트에 처리 전 '이미 추적 중이던 idea'(`tracked_before`)를 함께 저장한다. 추적 원장 저장 뒤 결과 저장 전에 멈췄다가 다시 처리해도 결과가 `already_tracked`로 바뀌지 않고 `success`로 남는다. 처음 구현에서는 이 경우를 시험이 잡아냈고, 고쳤다.
3. **불일치 알림의 추적 답장.** 판단 이벤트(action track, disputed_source 붙음)는 남기고, 결과 이벤트는 `rejected / disputed_source`로 남긴다. 그래서 보고의 불일치 알림(별도) 칸에서는 최신 판단이 '추적'으로 셀 수 있다. 실제 등록 수에는 들어가지 않는다.
4. **지원 알림 범위.** candidate_id가 있는 sent 이벤트면 재검토 변화 알림(material_update, 예: 163 PBF)도 포함된다. 지시서의 'candidate_id가 있는 sent 이벤트'를 그대로 따랐다.
5. **손상 파일 처리.** 처리 중 JSON 손상(`JSONDecodeError`)이 생기면, 모든 명령을 '입력 오류' 회신으로 끝내지 않고 재시도 대상으로 남기도록 바꿨다. 기존에는 ValueError로 묶여 '명령을 처리할 수 없습니다' 회신으로 완료됐다. 원장 손상을 실패로 남기라는 지시를 큐 전체에 적용한 것이다.
6. **도움말.** `/help` 끝에 '후보 알림에 답장: 추적 · 관심없음 · 보류 · 자세히 (한 낱말만)' 한 줄을 넣었다.
7. **완료된 큐 항목.** 완료 뒤에는 기존처럼 text를 지우고, action도 지운다. 답장 대상 message_id·시각·봇 여부는 참조라서 남긴다.
8. **추적 함수의 다른 ValueError.** 거절 코드가 없는 ValueError는 답장 경로에서 `rejected / invalid_record`로 기록한다. 일반 `/track` 경로는 기존처럼 '식별·통화 확인 부족' 회신이다.

## 검증(완료 기준 대응)

- 시험 23개(`tests/test_v1_feedback.py`)와 전체 시험이 통과했다. 실제 Telegram 요청은 막은 상태다.

| 기준 | 시험 |
|---|---|
| 1. 네 낱말·명령형, 유일 연결, 알림 아님·ID 없음·uncertain 거절 | `ReplyWordsTest` 6개(봇 아님, 시각 불일치, 번호 중복 포함) |
| 2. track→detail 판단 유지, track→dismiss 판단 변경과 추적 유지, detail만은 무판단+조회 | `VerdictTest` 4개 |
| 3. 성공·이미 추적·상한·오래됨·불일치 구분, 연구 판정·승격 없음 | `TrackReplyTest` 5개(분류 불변, review 이벤트 없음 확인) |
| 4. 같은 업데이트 재입력·큐 저장 후 중단·추적 저장 후 중단·회신 실패에도 중복 0, 손상·dry-run·원문 미저장 | `RetryTest` 6개, `test_no_chat_text_is_stored_anywhere` |
| 5. 카드·보고의 분모·버전·무응답·detail 집계 | `ViewsTest` 2개 |

- 대표 가짜 입력·회신·결과 JSON(임시 데이터 폴더, 네트워크 없음): [`data/eval/v1_2026-10-11/reply_feedback_fake_run.json`](../data/eval/v1_2026-10-11/reply_feedback_fake_run.json). 만든 스크립트도 같은 폴더에 두었다.

| 가짜 입력(답장 대상) | 회신 요지 | 저장 |
|---|---|---|
| 관심없음 (501, AAA 알림) | 판단 기록: AAA · 관심없음. 추적 등록과 알림 예약은 바꾸지 않습니다 | reply/dismiss |
| 자세히 (501) | 알림 당시 버전 · 최신 카드 버전 (변화 없음) + 기존 상세 카드 | reply/detail |
| 추적 (501) | 추적 등록 완료: AAA → IDEA-0001 | reply/track + track_result success |
| 추적 (502, 불일치 표시 BBB) | 답장으로는 추적 등록하지 않음, `/candidate`·`/track ID` 안내 | reply/track(disputed) + track_result rejected/disputed_source |
| 보류 (168, 정정 안내) | 후보 알림에 대한 답장이 아니어서 기록하지 않음 | 없음 |
| 이 회사 좋네 (501) | /help 목록 | 없음(큐에도 원문 없음) |

- 실제 원장 읽기 전용 dry-run(쓰기 없음, `git status` 변화 없음 확인)

| 답장 가정 | 결과 |
|---|---|
| 163에 관심없음 | PBF 재검토 변화 알림, 기록 예정 |
| 165에 추적 | DHT 알림, 제공처 값 불일치 PI-20261010-yahoo-eps 표시 |
| 168에 보류 | 후보 알림 아님, 안내만 |
| 164에 자세히 | VSEC 알림, 기록 예정 |

- 실제 데이터 보고 절(지금은 답장 0건): 후보 ID가 있는 발송 알림은 21건이다. 일반 18건(기업 18곳)은 모두 무판단이고, 불일치 알림 3건은 별도로 센다.

## 한계

- **회신 전달.** 회신은 기존 reply_pending 큐로 보낸다. 네트워크 응답을 모르면 같은 회신이 두 번 갈 수 있다(기존 한계). 판단·추적 기록은 중복되지 않는다.
- **응답 시각.** 명령은 지금처럼 PC 타이머(03:23·15:23·21:23 KST)와 일간·예약 실행 때만 처리하므로 회신이 몇 시간 늦을 수 있다(V2 범위 밖).
- **실제 운영 검증.** 아직 하지 않았다. 사용자가 실제 알림에 답장한 뒤 다음 commands 실행에서 확인해야 한다.
