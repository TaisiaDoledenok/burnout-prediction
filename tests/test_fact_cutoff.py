import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from dashboard import create_app

ROOT = Path(__file__).resolve().parent.parent


class FactCutoffTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / 'test.db'
        with sqlite3.connect(self.db) as db:
            db.executescript((ROOT / 'sql/schema.sql').read_text())
            db.executescript((ROOT / 'sql/views.sql').read_text())
            db.executescript("""
                INSERT INTO user_dic VALUES (1, 'Teacher');
                INSERT INTO school_dic (school_id, school_nm) VALUES (1, 'Past'), (2, 'Future');
                INSERT INTO event_dic VALUES (1, 'Event');
                INSERT INTO burnout_type_dic VALUES ('Low', 1), ('High', 3);
                INSERT INTO user_act_schedule (user_id, school_id, event_id, dttm_from, dttm_to, act_participants_cnt) VALUES
                (1, 1, 1, '2026-04-20 09:00:00', '2026-04-20 10:00:00', 10),
                (1, 1, 1, '2026-04-22 09:00:00', '2026-04-22 11:00:00', 20),
                (1, 2, 1, '2026-04-23 09:00:00', '2026-04-23 15:00:00', 30),
                (1, 2, 1, '2026-04-24 09:00:00', '2026-04-24 15:00:00', 30),
                (1, 2, 1, '2026-04-27 09:00:00', '2026-04-27 15:00:00', 30);
                INSERT INTO user_activity_log (user_id, activity_type, activity_dttm) VALUES
                (1, 'x', '2026-04-22 09:00:00'), (1, 'x', '2026-04-23 10:00:00');
                INSERT INTO survey_act (user_id, calendar_dt, burnout_type) VALUES
                (1, '2026-04-22', 'Low'), (1, '2026-04-23', 'High');
            """)

    def request(self, path, cutoff='2026-04-22'):
        app = create_app(self.db, fact_through=cutoff)
        env = {'REQUEST_METHOD': 'GET', 'PATH_INFO': path.split('?')[0], 'QUERY_STRING': path.partition('?')[2],
               'SERVER_PORT': '80', 'wsgi.url_scheme': 'http', 'wsgi.input': io.BytesIO(), 'CONTENT_LENGTH': '0'}
        return json.loads(b''.join(app(env, lambda status, headers: None)))

    def test_partial_week_includes_cutoff_day_not_later_days(self):
        data = self.request('/api/teacher?user_id=1')
        self.assertEqual(data['latest_week'], '2026-04-20')
        self.assertEqual(data['latest_load']['event_hours'], 3)
        self.assertEqual(data['latest_load']['activity_hours'], 1)
        self.assertAlmostEqual(data['history'][-1]['act_avg_participants_per_hour'], 16.67)
        self.assertEqual(data['current_stage']['level'], 1)
        self.assertEqual(len(data['surveys']), 1)
        monday = self.request('/api/teacher?user_id=1', '2026-04-20')
        self.assertEqual(monday['latest_load']['event_hours'], 1)
        self.assertEqual(monday['latest_load']['activity_hours'], 0)

    def test_event_spanning_midnight_stops_at_end_of_cutoff_day(self):
        with sqlite3.connect(self.db) as db:
            db.execute("INSERT INTO user_act_schedule (user_id, school_id, event_id, dttm_from, dttm_to, act_participants_cnt) VALUES (1, 1, 1, '2026-04-22 23:00:00', '2026-04-23 02:00:00', 10)")
        self.assertEqual(self.request('/api/teacher?user_id=1')['latest_load']['event_hours'], 4)

    def test_school_and_fact_ranking_ignore_future_assignments_and_surveys(self):
        data = self.request('/api/teacher?user_id=1')
        self.assertEqual(data['school_id'], 1)
        summary = self.request('/api/summary')
        schools = {s['school_id']: s for s in summary['schools']}
        self.assertEqual(schools[1]['fact_teacher_count'], 1)
        self.assertEqual(schools[2]['fact_teacher_count'], 0)
        self.assertEqual({x['level']: x['count'] for x in schools[1]['fact_stages']}, {1: 1, 3: 0})
        self.assertEqual(schools[1]['fact_stages'][0]['percent'], 100)
        self.assertEqual({x['level']: x['count'] for x in schools[2]['fact_stages']}, {1: 0, 3: 0})
        self.assertEqual({x['level']: x['count'] for x in schools[2]['forecast_stages']}, {1: 0, 3: 1})

    def test_future_only_school_assignment_is_listed_as_unknown(self):
        directory = self.request('/api/teachers', '2026-04-19')
        self.assertIsNone(directory['teachers'][0]['school_id'])
        self.assertTrue(any(s['school_id'] is None for s in directory['schools']))
