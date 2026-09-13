"""
simulator 패키지 골격 (3단계 Day 8).

순수 도메인(Clock / Weather / InitialState)은
backend `app.domain.simulation` 에 두고, 이 패키지는 이후
runner·상태전이·센서 noise 를 붙일 worker 진입점이다.

실행 (backend 패키지가 PYTHONPATH 에 있을 때):
    python -m app.demo_clock
"""
