def lnc_agent_senders() -> list[str]:
    return [f"agent{i}@ogenies.com" for i in range(1, 101)]


def choose_sender_email(prospect_id: str) -> str:
    """
    Deterministic sender rotation.
    Keeps a stable mapping prospect -> sender without DB state.
    """
    senders = lnc_agent_senders()
    idx = abs(hash(prospect_id)) % len(senders)
    return senders[idx]
