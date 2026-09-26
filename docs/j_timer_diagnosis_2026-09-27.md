# J2 PC 타이머 진단 (Claude, 2026-09-27 00:40 KST 무렵)

조회만 했다. 예약 작업·스크립트·전원 설정은 바꾸지 않았고, 작업 실행이나 dispatch도 하지 않았다. token.txt는 열지 않았다. 시각은 모두 KST다(UTC는 괄호 안에 적었다).

## 결론

- **확정 원인**: PC가 9/26 01:00:15에 종료됐고 22:25:48에 다시 시작됐다(System 로그 Kernel-General 13/12, EventLog 6006/6005, User32 1074).
  - 그 사이 정시 4번이 모두 PC가 꺼져 있어 실행되지 않았다: 03:23 명령, 09:17 auto, 15:23 명령, 21:23 명령.
  - 타이머 설정·경로·토큰 오류는 아니다.
- **지연 실행**: 일간 작업(StartWhenAvailable=true)은 부팅 뒤 22:29:29에 뒤늦게 실행됐다.
  - dispatch.log 22:29:58 `auto ok`와 GitHub run [36245371318](https://github.com/onepuhch/research/actions/runs/36245371318)(workflow_dispatch, 생성 13:30:05Z = 22:30:05)의 시각 차이는 7초다.
  - 그래서 이 run이 타이머의 지연 auto로 보인다. 다만 목록 API는 입력 mode를 주지 않는다.
  - 이 run은 당시 테스트 날짜 버그로 테스트 단계에서 실패했다. `ok`는 GitHub가 요청을 접수했다는 뜻일 뿐, 일간 작업이 성공했다는 뜻이 아니다.
- **명령 작업 0x800710E0**(ERROR_REQUEST_REFUSED, "요청 거부"): 같은 22:29:29에 기록됐다.
  - 스크립트는 실행되지 않았다. dispatch.log에 commands 줄이 없고, 13:29Z 부근 두 번째 dispatch run도 없다.
  - 이 작업은 StartWhenAvailable=false라서 놓친 실행을 부팅 뒤 시작하지 않는 것이 설정상 정상 동작이다. 거부 코드는 그 놓친 실행을 기록한 것으로 **추정**한다.
  - Task Scheduler Operational 로그가 꺼져 있어 확정할 수 없다. 로그를 켜는 것은 시스템 설정 변경이라 하지 않았다.
- **이전 기록 정정**: [장애 기록](incident_2026-09-26_date_test.md)과 [I 인수인계](i_handoff_2026-09-27.md)에 쓴 "9/26 PC 타이머 dispatch 없음"은 틀렸다.
  - 정시 dispatch가 없었던 것이다(PC 꺼짐).
  - 22:29에 지연 auto dispatch 1건이 있었다. 두 문서에 정정 문구를 달았다.

## 설정 (변경 없음)

| 작업 | 트리거 | StartWhenAvailable | WakeToRun | 실행 계정 방식 | 제한 |
|---|---|---|---|---|---|
| Research daily run | 매일 09:17 | true | false | Interactive(로그온 시), Limited | 5분, IgnoreNew |
| Research command check | 매일 03:23, 15:23, 21:23 | false | false | Interactive, Limited | 5분, IgnoreNew |

- 동작: `dispatch.ps1 -Mode auto|commands` → GitHub `workflow_dispatch`(ref=main) → dispatch.log에 `ok` 또는 `FAILED`를 한 줄 남긴다.
- **09:23 명령 트리거가 없는 이유**: 09:17 auto 실행이 명령 단계도 처리한다(workflow 순서 migrate → commands → plan → steps). README의 "03:23/09:23/15:23/21:23"은 GitHub 6시간 예약(`23 */6 * * *`) 기준이다. PC 타이머는 09:17 auto에 03:23·15:23·21:23 명령 3번을 더한다. README에 이 차이를 적었다.

## 보완 여부

바꾸지 않았다. 이유는 다음과 같다.

- 원인이 PC 전원 꺼짐이다. WakeToRun은 절전에서 깨우는 기능이라 완전 종료된 PC에는 효과가 없다. 전원 정책 변경은 지시서의 기본 해법에서 제외돼 있다.
- 명령 작업의 StartWhenAvailable을 켜면 부팅 직후 auto와 commands가 같이 dispatch된다. auto가 이미 명령을 처리하므로 중복일 뿐이다. 지시서의 "중복 trigger 자동 추가 금지"에도 가깝다.
- PC가 꺼진 날에는 GitHub 대체 예약만 남는다. 9/26에 실측한 지연은 아래와 같다. **대체 실행은 정시가 아니며, 3~5시간 늦을 수 있다.**

| 예약(cron, UTC) | 예정 시각 KST | 실제 생성 KST | 지연 |
|---|---|---|---|
| `23 */6` 12:23Z | 9/25 21:23 | 9/26 02:19 (17:19Z) | 약 4시간 56분 |
| `23 */6` 18:23Z | 9/26 03:23 | 9/26 06:40 (21:40Z) | 약 3시간 17분 |
| `17 0` 00:17Z / `23 */6` 00:23Z | 9/26 09:17 / 09:23 | 9/26 14:07, 14:08 (05:07Z, 05:08Z) | 약 4시간 50분 |
| `23 */6` 06:23Z | 9/26 15:23 | 9/26 20:33 (11:33Z) | 약 5시간 10분 |

어느 행이 어느 cron에서 나왔는지는 생성 시각으로 추정한 것이다(GitHub는 늦게 실행할 뿐 먼저 실행하지 않는다는 전제). 9/26 21:23 예약은 15:00Z까지 run이 없었다.

## 다음 자연 실행에서 확인할 것

PC가 켜져 있으면 다음 실행은 9/27 03:23 commands와 09:17 auto다. 요청을 보내지 않고 아래를 읽기만 한다.

```powershell
Get-Content "$env:USERPROFILE\.research-timer\dispatch.log" -Tail 5
Get-ScheduledTask -TaskName 'Research daily run','Research command check' | Get-ScheduledTaskInfo | Select-Object TaskName, LastRunTime, LastTaskResult, NextRunTime
```

- dispatch.log의 각 줄과 GitHub workflow_dispatch run의 생성 시각이 맞는지 대조한다.
- 명령 작업의 LastTaskResult가 0으로 돌아오는지 본다(0x800710E0이 반복되는지).
- 확인 결과는 J 인수인계에 적는다.
