"""애플리케이션 서비스 패키지 (2단계 Day 7+ / 3단계 Day 11).

routers 는 HTTP 경계만, 비즈니스 조회/쓰기·시뮬 스텝은 services 에 둔다.
- farm: 농장 snapshot/state/readings 조회
- simulation: run 수명주기 + step 폐쇄 루프(외기→참값→측정)
"""
