import unittest

from src.lnc_agent.agent import analyze_campaign
from src.lnc_agent.models import Event, Prospect
from src.lnc_agent.scoring import calculate_interest_score, segment_score


class AgentTests(unittest.TestCase):
    def test_high_engagement_prospect_gets_high_segment(self):
        prospect = Prospect(
            id="P001",
            first_name="Amina",
            last_name="Bennani",
            email="amina@example.com",
            company="Atlas Retail",
            role="Marketing Director",
            industry="Retail",
            provider="Sender",
            status="active",
            last_contacted_day=0,
        )
        events = [
            Event(prospect_id="P001", event_type="open", campaign_step="J0", day=0, hour=9),
            Event(prospect_id="P001", event_type="click", campaign_step="J0", day=0, hour=10),
            Event(prospect_id="P001", event_type="click", campaign_step="J+2", day=2, hour=9),
        ]

        score, reasons = calculate_interest_score(prospect, events)

        self.assertGreaterEqual(score, 75)
        self.assertEqual(segment_score(score), "high")
        self.assertIn("rapid click after an open", reasons)

    def test_unsubscribed_prospect_is_not_contacted(self):
        prospect = Prospect(
            id="P005",
            first_name="Leila",
            last_name="Karim",
            email="leila@example.com",
            company="LearnPro",
            role="Head of Sales",
            industry="Education",
            provider="Brevo",
            status="unsubscribed",
            last_contacted_day=8,
        )

        recommendations, drafts, _dashboard = analyze_campaign([prospect], [])

        self.assertEqual(recommendations[0].next_action, "do_not_contact")
        self.assertEqual(drafts[0].from_email, "")
        self.assertEqual(drafts[0].dynamic_template_data, {})


if __name__ == "__main__":
    unittest.main()
