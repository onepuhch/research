# 현재 운영 상태 — 2026-09-07

개선 코드 e081317을 원격 main에 배포하고 실제 운영 실행을 끝까지 확인했다. Telegram 추적 보고서 실발송도 API 성공 응답(message_id 119)으로 확인했다. 사용자 열람 여부는 확인할 수 없다.

## 검증 결과

- [운영 실행 34128208623](https://github.com/onepuhch/research/actions/runs/34128208623): 수집·추출·명령 처리·알림 처리·보고서 생성·상태 저장·산출물 보관 성공.
- EPS 수집 단계는 HTTP 402로 실패했다. 따라서 전체 workflow 결론은 failure이며 모든 연결이 정상이라는 의미로 해석하면 안 된다.
- Import AI RSS는 GitHub 실행 환경에서 HTTP 403이다. 다른 소스의 수집과 후속 처리는 계속된다.
- [Windows/Linux 테스트 34128209167](https://github.com/onepuhch/research/actions/runs/34128209167): 각 38개 테스트 통과.
- 운영에서 추가된 기존 872개 신호를 보존했다. CRDO 근거는 SIG-0873/0874, 실제 모델 추출 관망 신호는 SIG-0875다.
- 활성 CRDO 1건, 실적·가이던스 관측 14개, 다음 점검일 2026-09-13. 컨센서스는 미확보다.

## 설정 및 한계

GitHub에 누락됐던 FMP_API_KEY는 암호화해 Repository Secret에 등록했다. 보유 키의 API 접근 제한은 별도 문제이며 요금제 구매는 수행하지 않았다. 정기 운영은 KST 09:17 연구 처리, 03:23/09:23/15:23/21:23 명령 처리다.

로직 종합 재점검은 docs/logic_review_2026-09-07.md, 기계 판독 운영 증거는 docs/deployment_verification_2026-09-07.json을 참조한다. 기존 verification_2026-09-07.json은 최초 로컬 검증 당시의 기록이다.

미완료: FMP 접근 권한, 일부 RSS 접근, 평가 표본 판정과 실제 성과 복기, Google Sheets 실제 배포. 로직·운영 검증과 투자 성과 검증을 구분한다.
