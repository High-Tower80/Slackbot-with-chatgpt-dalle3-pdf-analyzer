import unittest

import wiki


SAMPLE_PAGES = [
    {
        "id": "ab62a17c-7172-46d5-af08-0e27d9f83cdc",
        "title": "Wifi Login Info",
        "tags": ["wifi", "internet", "password", "ssid", "login", "renzei", "5g"],
        "stored_url": "https://wiki.intertrendhub.com/Wifi-Login-Info-ab62a17c717246d5af080e27d9f83cdc?pvs=4",
    },
    {
        "id": "06b4bd3e-1703-4c28-b1ed-2e4df82cf6c4",
        "title": "PTO Instructions",
        "tags": ["pto", "time off", "adp", "vacation", "hr"],
        "stored_url": "https://wiki.intertrendhub.com/PTO-Instructions-06b4bd3e17034c28b1ed2e4df82cf6c4?pvs=4",
    },
    {
        "id": "7193cd1c-556c-484d-bcf3-887239dbbb12",
        "title": "Human Resources",
        "tags": ["benefits", "classpass", "pto", "hr"],
        "stored_url": "https://wiki.intertrendhub.com/PTO-Instructions-06b4bd3e17034c28b1ed2e4df82cf6c4?pvs=4",
    },
    {
        "id": "34950071-c89b-80f8-a6dd-f2d234666d00",
        "title": "ADP Open Enrollment",
        "tags": ["adp", "enrollment", "benefits", "healthcare"],
    },
    {
        "id": "e708aa6d-d762-485a-ae18-63b0af5b1522",
        "title": "Holidays",
        "tags": ["holidays", "time off", "benefits"],
        "stored_url": "https://wiki.intertrendhub.com/Holidays-e708aa6dd762485aae1863b0af5b1522?pvs=4",
    },
    {
        "id": "86777021-0657-4579-bbc5-4cfce462c5a4",
        "title": "Subscriptions",
        "tags": ["resources", "publications", "login"],
        "stored_url": "https://wiki.intertrendhub.com/Pubs-Subs-8677702106574579bbc54cfce462c5a4?pvs=4",
    },
    {
        "id": "15950071-c89b-808f-a2c1-fcad50397188",
        "title": "Tutorial: Start Saving Time",
        "tags": ["timesheet", "time off", "entry"],
    },
    {
        "id": "13e50071-c89b-80a6-b116-d787f0ebf9c0",
        "title": "Phishing Alert Guide",
        "tags": ["scam", "phishing", "alert", "security"],
        "stored_url": "https://wiki.intertrendhub.com/Phishing-Alert-Guide-13e50071c89b80a6b116d787f0ebf9c0?pvs=4",
    },
]


def load_index():
    index = wiki.WikiIndex(token="")
    index.load_pages(SAMPLE_PAGES)
    return index


class WikiLinkFormattingTests(unittest.TestCase):
    def test_prefers_stored_public_url_and_strips_tracking(self):
        url = wiki.format_public_wiki_url(
            "Wifi Login Info",
            "ab62a17c-7172-46d5-af08-0e27d9f83cdc",
            stored_url="https://wiki.intertrendhub.com/Wifi-Login-Info-ab62a17c717246d5af080e27d9f83cdc?pvs=4",
        )
        self.assertEqual(
            url,
            "https://wiki.intertrendhub.com/Wifi-Login-Info-ab62a17c717246d5af080e27d9f83cdc",
        )

    def test_keeps_custom_slug_when_stored_url_is_same_page(self):
        url = wiki.format_public_wiki_url(
            "Subscriptions",
            "86777021-0657-4579-bbc5-4cfce462c5a4",
            stored_url="https://wiki.intertrendhub.com/Pubs-Subs-8677702106574579bbc54cfce462c5a4?pvs=4",
        )
        self.assertEqual(
            url,
            "https://wiki.intertrendhub.com/Pubs-Subs-8677702106574579bbc54cfce462c5a4",
        )

    def test_ignores_stored_url_that_points_at_a_different_page(self):
        url = wiki.format_public_wiki_url(
            "Human Resources",
            "7193cd1c-556c-484d-bcf3-887239dbbb12",
            stored_url="https://wiki.intertrendhub.com/PTO-Instructions-06b4bd3e17034c28b1ed2e4df82cf6c4?pvs=4",
        )
        self.assertEqual(
            url,
            "https://wiki.intertrendhub.com/Human-Resources-7193cd1c556c484dbcf3887239dbbb12",
        )

    def test_slugifies_punctuation_in_title(self):
        url = wiki.format_public_wiki_url(
            "Tutorial: Start Saving Time",
            "15950071c89b808fa2c1fcad50397188",
        )
        self.assertEqual(
            url,
            "https://wiki.intertrendhub.com/Tutorial-Start-Saving-Time-15950071c89b808fa2c1fcad50397188",
        )

    def test_slack_link_uses_formatted_url(self):
        link = wiki.format_slack_link(
            "Wifi Login Info",
            "https://wiki.intertrendhub.com/Wifi-Login-Info-ab62a17c717246d5af080e27d9f83cdc",
        )
        self.assertEqual(
            link,
            "<https://wiki.intertrendhub.com/Wifi-Login-Info-ab62a17c717246d5af080e27d9f83cdc|Wifi Login Info>",
        )


class WikiIndexSearchTests(unittest.TestCase):
    def setUp(self):
        self.index = load_index()

    def test_indexes_sample_pages(self):
        self.assertEqual(len(self.index.pages), len(SAMPLE_PAGES))

    def test_wifi_keyword_hits_title_and_tags(self):
        results = self.index.search("wifi")
        self.assertTrue(results)
        self.assertEqual(results[0].page.title, "Wifi Login Info")
        self.assertIn("tag", results[0].matched_on)
        self.assertTrue(results[0].page.url.startswith("https://wiki.intertrendhub.com/Wifi-Login-Info-"))

    def test_password_tag_finds_wifi_page(self):
        titles = [result.page.title for result in self.index.search("password")]
        self.assertEqual(titles, ["Wifi Login Info"])

    def test_multi_word_query_ranks_open_enrollment(self):
        results = self.index.search("open enrollment")
        self.assertTrue(results)
        self.assertEqual(results[0].page.title, "ADP Open Enrollment")

    def test_hr_tag_returns_people_pages(self):
        titles = [result.page.title for result in self.index.search("hr")]
        self.assertIn("Human Resources", titles)
        self.assertIn("PTO Instructions", titles)

    def test_empty_query_has_no_results(self):
        self.assertEqual(self.index.search("   "), [])


class WikiSlackPayloadTests(unittest.TestCase):
    def test_help_payload_when_query_missing(self):
        index = load_index()
        payload = wiki.build_command_response(index, "")
        self.assertEqual(payload["response_type"], "ephemeral")
        self.assertIn("/wiki", payload["text"])

    def test_unconfigured_index_explains_missing_token(self):
        index = wiki.WikiIndex(token="")
        payload = wiki.build_command_response(index, "wifi")
        self.assertIn("NOTION_TOKEN", payload["text"])

    def test_results_payload_includes_formatted_links(self):
        index = load_index()
        index.token = "test-token"
        index.client = object()
        payload = wiki.build_command_response(index, "phishing")
        self.assertIn("Phishing Alert Guide", payload["text"])
        self.assertIn("wiki.intertrendhub.com/Phishing-Alert-Guide-", payload["text"])
        self.assertTrue(payload["blocks"])
        self.assertEqual(payload["blocks"][1]["accessory"]["url"].startswith("https://wiki.intertrendhub.com/"), True)

    def test_parse_official_notion_page_object(self):
        raw = {
            "id": "e708aa6d-d762-485a-ae18-63b0af5b1522",
            "last_edited_time": "2026-01-01T00:00:00.000Z",
            "properties": {
                "Page": {
                    "type": "title",
                    "title": [{"plain_text": "Holidays"}],
                },
                "Tags": {
                    "type": "multi_select",
                    "multi_select": [{"name": "holidays"}, {"name": "time off"}],
                },
                "URL": {
                    "type": "url",
                    "url": "https://wiki.intertrendhub.com/Holidays-e708aa6dd762485aae1863b0af5b1522?pvs=4",
                },
            },
        }
        page = wiki.parse_notion_page(raw)
        self.assertIsNotNone(page)
        self.assertEqual(page.title, "Holidays")
        self.assertEqual(page.tags, ["holidays", "time off"])
        self.assertEqual(
            page.url,
            "https://wiki.intertrendhub.com/Holidays-e708aa6dd762485aae1863b0af5b1522",
        )


if __name__ == "__main__":
    unittest.main()
