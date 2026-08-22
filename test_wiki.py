import os
import unittest
from unittest import mock

import wiki


SAMPLE_PAGES = [
    {
        "id": "ab62a17c-7172-46d5-af08-0e27d9f83cdc",
        "title": "Wifi Login Info",
        "tags": ["wifi", "internet", "password", "ssid", "login", "campus", "5g"],
        "stored_url": "https://wiki.example.com/Wifi-Login-Info-ab62a17c717246d5af080e27d9f83cdc?pvs=4",
    },
    {
        "id": "06b4bd3e-1703-4c28-b1ed-2e4df82cf6c4",
        "title": "PTO Instructions",
        "tags": ["pto", "time off", "adp", "vacation", "hr"],
        "stored_url": "https://wiki.example.com/PTO-Instructions-06b4bd3e17034c28b1ed2e4df82cf6c4?pvs=4",
    },
    {
        "id": "7193cd1c-556c-484d-bcf3-887239dbbb12",
        "title": "Human Resources",
        "tags": ["benefits", "classpass", "pto", "hr"],
        "stored_url": "https://wiki.example.com/PTO-Instructions-06b4bd3e17034c28b1ed2e4df82cf6c4?pvs=4",
    },
    {
        "id": "34950071-c89b-80f8-a6dd-f2d234666d00",
        "title": "ADP Open Enrollment",
        "tags": ["adp", "enrollment", "benefits", "healthcare"],
        "snippet": "Pro tip: Use Gemini to ask questions directly about the PDF",
    },
    {
        "id": "e708aa6d-d762-485a-ae18-63b0af5b1522",
        "title": "Holidays",
        "tags": ["holidays", "time off", "benefits"],
        "stored_url": "https://wiki.example.com/Holidays-e708aa6dd762485aae1863b0af5b1522?pvs=4",
    },
    {
        "id": "86777021-0657-4579-bbc5-4cfce462c5a4",
        "title": "Subscriptions",
        "tags": ["resources", "publications", "login"],
        "stored_url": "https://wiki.example.com/Pubs-Subs-8677702106574579bbc54cfce462c5a4?pvs=4",
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
        "stored_url": "https://wiki.example.com/Phishing-Alert-Guide-13e50071c89b80a6b116d787f0ebf9c0?pvs=4",
    },
    {
        "id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeee1",
        "title": "Training Hub",
        "tags": ["trakstar", "onboarding", "training"],
        "snippet": "Make sure you log your training hours.",
    },
    {
        "id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeee2",
        "title": "Conference Room Availability",
        "tags": ["calendar", "schedule"],
    },
    {
        "id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeee3",
        "title": "Employee Handbook",
        "tags": ["handbook", "benefits"],
        "snippet": "Click the Gemini logo and ask it anything.",
    },
    {
        "id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeee4",
        "title": "Watch and Learn Library",
        "tags": ["training", "AI and Advertising", "Webinar"],
        "snippet": "AI Agents Prompt Library",
    },
    {
        "id": "18250071-c89b-807d-ac9b-e3392929d461",
        "title": "Google Gemini",
        "tags": ["ai", "gemini", "google", "tutorial"],
        "description": "Google’s flagship AI built into company tools",
        "snippet": "Use Gemini to rewrite this email.",
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
            stored_url="https://wiki.example.com/Wifi-Login-Info-ab62a17c717246d5af080e27d9f83cdc?pvs=4",
        )
        self.assertEqual(
            url,
            "https://wiki.example.com/Wifi-Login-Info-ab62a17c717246d5af080e27d9f83cdc",
        )

    def test_keeps_custom_slug_when_stored_url_is_same_page(self):
        url = wiki.format_public_wiki_url(
            "Subscriptions",
            "86777021-0657-4579-bbc5-4cfce462c5a4",
            stored_url="https://wiki.example.com/Pubs-Subs-8677702106574579bbc54cfce462c5a4?pvs=4",
        )
        self.assertEqual(
            url,
            "https://wiki.example.com/Pubs-Subs-8677702106574579bbc54cfce462c5a4",
        )

    def test_ignores_stored_url_that_points_at_a_different_page(self):
        url = wiki.format_public_wiki_url(
            "Human Resources",
            "7193cd1c-556c-484d-bcf3-887239dbbb12",
            stored_url="https://wiki.example.com/PTO-Instructions-06b4bd3e17034c28b1ed2e4df82cf6c4?pvs=4",
        )
        self.assertEqual(
            url,
            "https://wiki.example.com/Human-Resources-7193cd1c556c484dbcf3887239dbbb12",
        )

    def test_slugifies_punctuation_in_title(self):
        url = wiki.format_public_wiki_url(
            "Tutorial: Start Saving Time",
            "15950071c89b808fa2c1fcad50397188",
        )
        self.assertEqual(
            url,
            "https://wiki.example.com/Tutorial-Start-Saving-Time-15950071c89b808fa2c1fcad50397188",
        )

    def test_slack_link_uses_formatted_url(self):
        link = wiki.format_slack_link(
            "Wifi Login Info",
            "https://wiki.example.com/Wifi-Login-Info-ab62a17c717246d5af080e27d9f83cdc",
        )
        self.assertEqual(
            link,
            "<https://wiki.example.com/Wifi-Login-Info-ab62a17c717246d5af080e27d9f83cdc|Wifi Login Info>",
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
        self.assertTrue(results[0].page.url.startswith("https://wiki.example.com/Wifi-Login-Info-"))

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

    def test_ai_does_not_match_substring_titles(self):
        titles = [result.page.title for result in self.index.search("ai")]
        self.assertNotIn("Training Hub", titles)
        self.assertNotIn("Conference Room Availability", titles)
        self.assertNotIn("Employee Handbook", titles)
        self.assertIn("Google Gemini", titles)
        self.assertIn("Watch and Learn Library", titles)
        self.assertEqual(titles[0], "Google Gemini")

    def test_gemini_uses_title_not_body_mentions(self):
        titles = [result.page.title for result in self.index.search("gemini")]
        self.assertEqual(titles[0], "Google Gemini")
        self.assertNotIn("ADP Open Enrollment", titles)
        self.assertNotIn("Employee Handbook", titles)

    def test_prefix_still_finds_phishing(self):
        titles = [result.page.title for result in self.index.search("phish")]
        self.assertIn("Phishing Alert Guide", titles)


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
        self.assertIn("wiki.example.com/Phishing-Alert-Guide-", payload["text"])
        self.assertTrue(payload["blocks"])
        self.assertEqual(payload["blocks"][1]["accessory"]["url"].startswith("https://wiki.example.com/"), True)

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
                    "url": "https://wiki.example.com/Holidays-e708aa6dd762485aae1863b0af5b1522?pvs=4",
                },
            },
        }
        page = wiki.parse_notion_page(raw)
        self.assertIsNotNone(page)
        self.assertEqual(page.title, "Holidays")
        self.assertEqual(page.tags, ["holidays", "time off"])
        self.assertEqual(
            page.url,
            "https://wiki.example.com/Holidays-e708aa6dd762485aae1863b0af5b1522",
        )


class WikiPreviewTests(unittest.TestCase):
    def test_extracts_numbered_and_key_value_facts(self):
        blocks = [
            {"type": "callout", "callout": {"rich_text": [{"plain_text": "triple click to highlight"}]}},
            {"type": "unsupported", "unsupported": {"block_type": "drive"}},
            {"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "SSID: Campus-5G"}]}},
            {"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "Password: hunter2"}]}},
            {"type": "numbered_list_item", "numbered_list_item": {"rich_text": [{"plain_text": "Open the Hub"}]}},
            {"type": "numbered_list_item", "numbered_list_item": {"rich_text": [{"plain_text": "Submit the request"}]}},
        ]
        preview = wiki.extract_preview_from_blocks(blocks)
        self.assertIn("SSID: Campus-5G", preview)
        self.assertIn("Password: hunter2", preview)
        self.assertIn("1. Open the Hub", preview)
        self.assertNotIn("triple click", preview)

    def test_formats_compact_values_like_tags(self):
        rendered = wiki.format_preview_for_slack("SSID: Campus-5G\nPassword: hunter2")
        self.assertIn("*SSID:* `Campus-5G`", rendered)
        self.assertIn("*Password:* `hunter2`", rendered)

    def test_search_payload_includes_digestible_facts(self):
        pages = list(SAMPLE_PAGES)
        pages[0] = dict(pages[0], snippet="SSID: Campus-5G\nPassword: office-wifi")
        index = wiki.WikiIndex(token="test-token")
        index.client = object()
        index.load_pages(pages)
        payload = wiki.build_command_response(index, "wifi")
        body = payload["blocks"][1]["text"]["text"]
        self.assertIn("*SSID:* `Campus-5G`", body)
        self.assertIn("*Password:* `office-wifi`", body)

    def test_custom_wifi_emoji_layout(self):
        rendered = wiki.format_preview_for_slack(
            "Office-5g: office-pass\n"
            "Office Guest Networks: guest-pass"
        )
        self.assertIn("*Office-5g:* `office-pass`", rendered)
        self.assertIn("*Office Guest Networks:* `guest-pass`", rendered)

    def test_skips_empty_or_hint_only_preview(self):

        self.assertFalse(wiki.is_useful_preview("triple click to highlight"))
        self.assertFalse(wiki.is_useful_preview(""))


class WikiSlackOnlyFactsTests(unittest.TestCase):
    def test_env_facts_override_notion_snippet_for_wifi(self):
        pages = list(SAMPLE_PAGES)
        index = wiki.WikiIndex(token="test-token")
        index.client = object()
        index.load_pages(pages)
        env = {
            "WIKI_SLACK_WIFI_SSID": "Campus",
            "WIKI_SLACK_WIFI_PASSWORD": "office-secret",
            "WIKI_SLACK_WIFI_SSID_5G": "Campus-5G",
            "WIKI_SLACK_WIFI_PASSWORD_5G": "office-secret-5g",
        }
        with mock.patch.dict(os.environ, env, clear=False):
            payload = wiki.build_command_response(index, "internet")
        body = payload["blocks"][1]["text"]["text"]
        self.assertIn("*SSID:* `Campus`", body)
        self.assertIn("*Password:* `office-secret`", body)
        self.assertIn("*5G SSID:* `Campus-5G`", body)
        self.assertNotIn("triple click", body)

    def test_non_wifi_pages_do_not_get_wifi_facts(self):
        pages = list(SAMPLE_PAGES)
        pages[1] = dict(pages[1], snippet="GO TO THE HUB")
        index = wiki.WikiIndex(token="test-token")
        index.client = object()
        index.load_pages(pages)
        env = {"WIKI_SLACK_WIFI_SSID": "Campus", "WIKI_SLACK_WIFI_PASSWORD": "office-secret"}
        with mock.patch.dict(os.environ, env, clear=False):
            payload = wiki.build_command_response(index, "pto")
        body = payload["blocks"][1]["text"]["text"]
        self.assertIn("PTO Instructions", body)
        self.assertNotIn("office-secret", body)


class WikiHolidayFactsTests(unittest.TestCase):
    def test_formats_single_and_range_dates(self):
        self.assertEqual(wiki.format_holiday_date("2026-01-01"), "Jan 1, 2026")
        self.assertEqual(wiki.format_holiday_date("2026-11-26", "2026-11-27"), "Nov 26-27, 2026")

    def test_builds_sorted_holiday_list(self):
        rows = [
            {"title": "Thanksgiving", "start": "2026-11-26", "end": "2026-11-27"},
            {"title": "New Year’s Day", "start": "2026-01-01"},
            {"title": "Labor Day", "start": "2026-09-07"},
        ]
        text = wiki.holiday_facts_from_pages(rows)
        self.assertIn("2026 company holidays", text)
        self.assertTrue(text.index("New Year") < text.index("Labor Day") < text.index("Thanksgiving"))
        self.assertIn("Labor Day: Sep 7, 2026", text)

    def test_holidays_query_shows_list_in_slack(self):
        pages = list(SAMPLE_PAGES)
        pages[4] = dict(pages[4], snippet=wiki.holiday_facts_from_pages([
            {"title": "Labor Day", "start": "2026-09-07"},
            {"title": "Thanksgiving", "start": "2026-11-26", "end": "2026-11-27"},
        ]))
        index = wiki.WikiIndex(token="test-token")
        index.client = object()
        index.load_pages(pages)
        payload = wiki.build_command_response(index, "holidays")
        body = payload["blocks"][1]["text"]["text"]
        self.assertIn("Holidays", body)
        self.assertIn("*Labor Day:*", body)
        self.assertIn("`Sep 7, 2026`", body)

    def test_thanksgiving_keyword_injects_holidays_page(self):
        pages = list(SAMPLE_PAGES)
        pages[4] = dict(pages[4], snippet="2026 company holidays\nThanksgiving: Nov 26-27, 2026")
        index = wiki.WikiIndex(token="test-token")
        index.client = object()
        index.load_pages(pages)
        payload = wiki.build_command_response(index, "thanksgiving")
        body = payload["blocks"][1]["text"]["text"]
        self.assertIn("Thanksgiving", body)


if __name__ == "__main__":
    unittest.main()
