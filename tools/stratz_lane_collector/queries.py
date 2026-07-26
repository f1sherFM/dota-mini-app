"""GraphQL operations used by the STRATZ lane collector."""

from __future__ import annotations


LANE_OUTCOME_QUERY = """
query LoadLaneOutcomes($week: Long!, $isWith: Boolean!) {
  heroStats {
    laneOutcome(
      week: $week
      isWith: $isWith
      positionIds: [POSITION_1, POSITION_2, POSITION_3, POSITION_4, POSITION_5]
    ) {
      heroId1
      heroId2
      position
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
