"""GraphQL operations used by the STRATZ lane collector."""

from __future__ import annotations


LANE_ALIASES = {
    "safe": "SAFE",
    "mid": "MID",
    "off": "OFF",
}


LANE_OUTCOME_QUERY = """
query LoadLaneOutcomes($week: Long!, $isWith: Boolean!) {
  heroStats {
    safe: laneOutcome(
      week: $week
      isWith: $isWith
      positionIds: [POSITION_1, POSITION_5]
    ) {
      heroId1
      heroId2
      matchCount
      drawCount
      winCount
      lossCount
      stompWinCount
      stompLossCount
      matchWinCount
      csCount
      week
      bracketBasicIds
    }
    mid: laneOutcome(
      week: $week
      isWith: $isWith
      positionIds: [POSITION_2]
    ) {
      heroId1
      heroId2
      matchCount
      drawCount
      winCount
      lossCount
      stompWinCount
      stompLossCount
      matchWinCount
      csCount
      week
      bracketBasicIds
    }
    off: laneOutcome(
      week: $week
      isWith: $isWith
      positionIds: [POSITION_3, POSITION_4]
    ) {
      heroId1
      heroId2
      matchCount
      drawCount
      winCount
      lossCount
      stompWinCount
      stompLossCount
      matchWinCount
      csCount
      week
      bracketBasicIds
    }
  }
}
"""
