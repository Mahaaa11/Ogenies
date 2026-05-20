import unittest

from src.lnc_agent.sendgrid_kpis import mail_provider_label_from_domain


class MailProviderLabelTests(unittest.TestCase):
    def test_consumer_webmails(self):
        self.assertEqual(mail_provider_label_from_domain("gmail.com"), "Gmail")
        self.assertEqual(mail_provider_label_from_domain("GOOGLEMAIL.COM"), "Gmail")
        self.assertEqual(mail_provider_label_from_domain("outlook.fr"), "Outlook / Microsoft")
        self.assertEqual(mail_provider_label_from_domain("hotmail.co.uk"), "Outlook / Microsoft")
        self.assertEqual(mail_provider_label_from_domain("yahoo.co.jp"), "Yahoo")
        self.assertEqual(mail_provider_label_from_domain("ymail.com"), "Yahoo")
        self.assertEqual(mail_provider_label_from_domain("icloud.com"), "iCloud / Apple")
        self.assertEqual(mail_provider_label_from_domain("orange.fr"), "Orange")

    def test_custom_domain_prefixed(self):
        self.assertEqual(mail_provider_label_from_domain("ogeniesrgpd.com"), "Autre · ogeniesrgpd.com")

    def test_empty_domain(self):
        self.assertEqual(mail_provider_label_from_domain(""), "Inconnu")
        self.assertEqual(mail_provider_label_from_domain("   "), "Inconnu")


if __name__ == "__main__":
    unittest.main()
