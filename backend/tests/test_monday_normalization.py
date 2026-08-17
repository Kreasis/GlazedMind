import unittest

from app.services.monday import _normalize


class MondayNormalizationTests(unittest.TestCase):
    def test_fc_code_is_store_metadata_not_ticket_identity(self) -> None:
        item = {
            "id": "12780591911",
            "name": "FC1515",
            "group": {"title": "Open Tickets"},
            "column_values": [
                {"id": "status", "text": "In Progress", "column": {"title": "Status"}},
                {"id": "description", "text": "Change the glazed donut price", "column": {"title": "Description"}},
            ],
        }
        ticket = _normalize(item)
        self.assertEqual(ticket["id"], "12780591911")
        self.assertEqual(ticket["store_code"], "FC1515")
        self.assertEqual(ticket["ticket_number"], "FC1515")

    def test_store_code_is_normalized_from_a_longer_ticket_title(self) -> None:
        item = {
            "id": "2",
            "name": "FC 1515 - New POS installation",
            "group": {"title": "Open Tickets"},
            "column_values": [],
        }
        self.assertEqual(_normalize(item)["store_code"], "FC1515")


if __name__ == "__main__":
    unittest.main()
