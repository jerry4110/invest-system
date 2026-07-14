"""테스트 공통: 백그라운드(감시·스케줄러·배치 보정) 비활성 — 네트워크 격리·결정성."""
import os

os.environ["INVEST_DISABLE_BACKGROUND"] = "1"
