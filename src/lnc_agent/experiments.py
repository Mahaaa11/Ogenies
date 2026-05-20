def choose_ab_variant(prospect_id: str) -> str:
    """
    A/B testing assignment.
    Deterministic so the same prospect always gets the same variant.
    """
    return "A" if (abs(hash("ab:" + prospect_id)) % 2 == 0) else "B"

