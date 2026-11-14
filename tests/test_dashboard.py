import io
import gc
import json
import sqlite3
import tempfile
import unittest
import warnings
from contextlib import closing
from pathlib import Path

from dashboard import create_app
from generate import load_config


class DashboardReadOnlyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = staticmethod(create_app(Path(__file__).parent.parent / "data" / "teacher_burnout.db"))

    def request(self, path, method="GET", app=None):
        environ = {
            "REQUEST_METHOD": method,
            "PATH_INFO": path.split("?", 1)[0],
            "QUERY_STRING": path.split("?", 1)[1] if "?" in path else "",
            "SERVER_PORT": "8080",
            "wsgi.url_scheme": "http",
            "wsgi.input": io.BytesIO(b""),
            "CONTENT_LENGTH": "0",
        }
        captured = {}

        def start_response(status, headers):
            captured["status"] = status
            captured["headers"] = dict(headers)

        body = b"".join((app or self.app)(environ, start_response))
        return captured, body

    def test_summary_reports_panel_counts_without_hidden_truth(self):
        response, body = self.request("/api/summary")
        data = json.loads(body)

        self.assertEqual(response["status"], "200 OK")
        self.assertEqual(data["teacher_count"], 300)
        self.assertEqual(data["panel_rows"], 10761)
        self.assertNotIn("_gen_teacher_truth", body.decode())

    def test_summary_includes_school_count(self):
        response, body = self.request("/api/summary")
        data = json.loads(body)

        self.assertEqual(response["status"], "200 OK")
        self.assertEqual(data["school_count"], 12)

    def test_summary_returns_db_backed_phase_cards_and_header_metadata(self):
        response, body = self.request("/api/summary")
        data = json.loads(body)

        self.assertEqual(response["status"], "200 OK")
        self.assertEqual(data["report_date"], "2026-04-20")
        self.assertEqual(data["forecast_to"], "2026-05-18")
        self.assertEqual(data["forecast_week_dates"], ["2026-04-27", "2026-05-04", "2026-05-11", "2026-05-18"])
        self.assertEqual(data["location_label"], "Свердловская область")
        self.assertEqual(
            [(stage["level"], stage["name"], stage["count"], stage["percent"]) for stage in data["stages"]],
            [(1, "Напряженность", 80, 27), (2, "Истощение", 28, 9), (3, "Бессилие", 20, 7)],
        )
        self.assertEqual(len(data["stages"][0]["history"]), 9)
        self.assertNotIn("model_accuracy", data)

    def test_default_generator_config_uses_canonical_burnout_levels(self):
        cfg = load_config([], [])

        self.assertEqual(
            [(item["type"], item["level"]) for item in cfg["survey"]["burnout_types"]],
            [("Нет признаков", 0), ("Напряженность", 1), ("Истощение", 2), ("Бессилие", 3)],
        )

    def test_database_dictionary_and_survey_use_canonical_burnout_names(self):
        db_path = Path(__file__).parent.parent / "data" / "teacher_burnout.db"
        db_uri = f"file:{db_path.resolve().as_posix()}?mode=ro"
        with closing(sqlite3.connect(db_uri, uri=True)) as connection:
            dictionary = connection.execute(
                "SELECT burnout_type, burnout_level FROM burnout_type_dic ORDER BY burnout_level"
            ).fetchall()
            survey_types = {
                row[0] for row in connection.execute("SELECT DISTINCT burnout_type FROM survey_act")
            }

        self.assertEqual(
            dictionary,
            [("Нет признаков", 0), ("Напряженность", 1), ("Истощение", 2), ("Бессилие", 3)],
        )
        self.assertEqual(
            survey_types,
            {"Нет признаков", "Напряженность", "Истощение", "Бессилие"},
        )

    def test_summary_provides_school_stage_counts_and_monthly_history(self):
        response, body = self.request("/api/summary")
        data = json.loads(body)

        self.assertEqual(response["status"], "200 OK")
        self.assertEqual(len(data["schools"]), data["school_count"])
        self.assertEqual(data["trend_months"][0], "2025-09")
        self.assertEqual(data["trend_months"][-1], "2026-05")
        self.assertEqual(len(data["trend_months"]), 9)

        current_totals = {stage["level"]: 0 for stage in data["stages"]}
        for school in data["schools"]:
            self.assertGreater(school["teacher_count"], 0)
            self.assertEqual(len(school["stages"]), len(data["stages"]))
            for stage in school["stages"]:
                current_totals[stage["level"]] += stage["count"]
                self.assertEqual(len(school["monthly_counts"][str(stage["level"])]), 9)

        self.assertEqual(current_totals, {stage["level"]: stage["count"] for stage in data["stages"]})
        for month_index, stage in enumerate(data["stages"][0]["history"]):
            school_total = sum(school["monthly_counts"]["1"][month_index] for school in data["schools"])
            self.assertEqual(school_total, stage)

    def test_ranking_fact_and_forecast_snapshots_use_distinct_counts(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            database = Path(temporary_directory) / "forecast.db"
            with closing(sqlite3.connect(database)) as connection:
                connection.executescript("""
                    CREATE TABLE user_dic (user_id INTEGER, user_nm TEXT);
                    CREATE TABLE school_dic (school_id INTEGER, school_nm TEXT);
                    CREATE TABLE user_act_schedule (user_id INTEGER, school_id INTEGER, dttm_from TEXT, dttm_to TEXT, act_participants_cnt INTEGER);
                    CREATE TABLE user_activity_log (user_id INTEGER, activity_dttm TEXT);
                    CREATE TABLE burnout_type_dic (burnout_type TEXT, burnout_level INTEGER);
                    CREATE TABLE survey_act (survey_id INTEGER, user_id INTEGER, calendar_dt TEXT, burnout_type TEXT);
                    CREATE TABLE teacher_burnout_panel (
                        user_id INTEGER, week_dt TEXT, event_hours REAL, activity_hours REAL,
                        act_avg_participants_per_hour REAL, burnout_level INTEGER
                    );
                    INSERT INTO user_dic VALUES (1, 'Педагог 1'), (2, 'Педагог 2');
                    INSERT INTO school_dic VALUES (7, 'Школа');
                    INSERT INTO user_act_schedule VALUES (1, 7, '2026-04-27 09:00:00', '2026-04-27 10:00:00', 1), (2, 7, '2026-04-27 09:00:00', '2026-04-27 10:00:00', 1);
                    INSERT INTO survey_act VALUES (1, 1, '2026-05-04', 'Истощение'), (2, 2, '2026-04-27', 'Истощение');
                    INSERT INTO burnout_type_dic VALUES
                        ('Нет признаков', 0), ('Напряженность', 1),
                        ('Истощение', 2), ('Бессилие', 3);
                    INSERT INTO teacher_burnout_panel VALUES
                        (1, '2026-04-27', 10, 2, 3, 1),
                        (1, '2026-05-04', 10, 2, 3, 2),
                        (1, '2026-05-11', 10, 2, 3, 3),
                        (1, '2026-05-18', 10, 2, 3, NULL),
                        (2, '2026-04-27', 10, 2, 3, 2),
                        (2, '2026-05-04', 10, 2, 3, NULL),
                        (2, '2026-05-11', 10, 2, 3, NULL),
                        (2, '2026-05-18', 10, 2, 3, NULL),
                        (2, '2026-05-25', 10, 2, 3, NULL);
                """)
                connection.commit()

            response, body = self.request("/api/summary", app=create_app(database, fact_through="2026-05-04"))
            data = json.loads(body)
            school = data["schools"][0]
            forecast_stage = next(stage for stage in school["stages"] if stage["level"] == 3)
            fact_stage = next(stage for stage in school["fact_stages"] if stage["level"] == 2)
            projected_stage = next(stage for stage in school["forecast_stages"] if stage["level"] == 3)
            carried_fact = next(stage for stage in school["forecast_stages"] if stage["level"] == 2)

            self.assertEqual(response["status"], "200 OK")
            self.assertEqual(data["report_date"], "2026-05-04")
            self.assertEqual(data["forecast_week_dates"], ["2026-05-11", "2026-05-18", "2026-05-25"])
            self.assertEqual(data["ranking_fact_to"], "2026-05-04")
            self.assertEqual(data["ranking_forecast_from"], "2026-05-11")
            self.assertEqual(data["ranking_forecast_to"], "2026-05-25")
            self.assertEqual(data["forecast_months"], [])
            self.assertEqual(data["monthly_counts"]["3"][-1], 1)
            self.assertEqual(forecast_stage["count"], 1)
            self.assertEqual(forecast_stage["forecast_count"], 1)
            self.assertEqual(fact_stage["count"], 2)
            self.assertEqual(projected_stage["count"], 1)
            self.assertEqual(projected_stage["forecast_count"], 1)
            self.assertEqual(carried_fact["count"], 1)
            self.assertEqual(carried_fact["forecast_count"], 0)

    def test_mixed_month_is_not_marked_wholly_as_forecast(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            database = Path(temporary_directory) / "mixed-forecast.db"
            with closing(sqlite3.connect(database)) as connection:
                connection.executescript("""
                    CREATE TABLE user_dic (user_id INTEGER, user_nm TEXT);
                    CREATE TABLE school_dic (school_id INTEGER, school_nm TEXT);
                    CREATE TABLE user_act_schedule (user_id INTEGER, school_id INTEGER, dttm_from TEXT, dttm_to TEXT, act_participants_cnt INTEGER);
                    CREATE TABLE user_activity_log (user_id INTEGER, activity_dttm TEXT);
                    CREATE TABLE burnout_type_dic (burnout_type TEXT, burnout_level INTEGER);
                    CREATE TABLE survey_act (survey_id INTEGER, user_id INTEGER, calendar_dt TEXT, burnout_type TEXT);
                    CREATE TABLE teacher_burnout_panel (
                        user_id INTEGER, week_dt TEXT, event_hours REAL, activity_hours REAL,
                        act_avg_participants_per_hour REAL, burnout_level INTEGER
                    );
                    INSERT INTO user_dic VALUES (1, 'Педагог 1'), (2, 'Педагог 2');
                    INSERT INTO school_dic VALUES (7, 'Школа');
                    INSERT INTO user_act_schedule VALUES (1, 7, '2026-04-27 09:00:00', '2026-04-27 10:00:00', 1), (2, 7, '2026-04-27 09:00:00', '2026-04-27 10:00:00', 1);
                    INSERT INTO survey_act VALUES (1, 1, '2026-05-04', 'Истощение'), (2, 2, '2026-04-27', 'Истощение');
                    INSERT INTO burnout_type_dic VALUES
                        ('Нет признаков', 0), ('Напряженность', 1),
                        ('Истощение', 2), ('Бессилие', 3);
                    INSERT INTO teacher_burnout_panel VALUES
                        (1, '2026-05-04', 10, 2, 3, 1),
                        (1, '2026-05-11', 10, 2, 3, 2),
                        (1, '2026-05-18', 10, 2, 3, 3),
                        (2, '2026-05-04', 10, 2, 3, 1),
                        (2, '2026-05-11', 10, 2, 3, NULL),
                        (2, '2026-05-18', 10, 2, 3, NULL);
                """)
                connection.commit()

            response, body = self.request("/api/summary", app=create_app(database, fact_through="2026-05-04"))
            data = json.loads(body)

            self.assertEqual(response["status"], "200 OK")
            self.assertEqual(data["forecast_months"], [])
            self.assertEqual(data["monthly_counts"]["1"][-1], 1)
            self.assertEqual(data["monthly_counts"]["3"][-1], 1)
            self.assertEqual(data["schools"][0]["forecast_months"], [])

    def test_reference_header_and_kpi_row_replaces_internal_panel_metrics(self):
        response, body = self.request("/")
        page = body.decode("utf-8")

        self.assertEqual(response["status"], "200 OK")
        for marker in (
            'class="dashboard-topbar"',
            'id="report-date"',
            'id="forecast-to"',
            "Прогноз до:",
            'id="location-label"',
            'class="kpi-grid"',
            'id="stage-cards"',
            'id="model-accuracy"',
            "Overview",
            "Школа",
        ):
            self.assertIn(marker, page)
        self.assertNotIn("Строк панели", page)
        self.assertNotIn('id="panel-rows"', page)

    def test_lower_report_contains_school_ranking_and_burnout_trend(self):
        response, body = self.request("/")
        page = body.decode("utf-8")

        self.assertEqual(response["status"], "200 OK")
        for marker in (
            "Антирейтинг школ",
            'id="ranking-snapshot-toggle"',
            'name="ranking-snapshot"',
            'id="ranking-snapshot-note"',
            'id="ranking-fact-to"',
            'id="ranking-forecast-from"',
            'class="ranking-columns"',
            'class="ranking-school-heads"',
            'class="ranking-metric-heads"',
            'id="ranking-rows"',
            'id="ranking-level-filters"',
            'data-default-unchecked-level="1"',
            "Категории выгоревших:",
            "Процент выгоревших",
            "selected-count-cell",
            "function updateRankingMetrics",
            "Динамика выгорания",
            'id="school-filter"',
            'id="trend-level-filters"',
            'id="trend-level-filters" data-default-unchecked-level="1"',
            'id="trend-period"',
            'id="trend-chart"',
            ".trend-chart .forecast-line{stroke-dasharray:",
            ".teacher-load-chart .forecast-line{stroke-dasharray:",
            "fact_stages",
            "forecast_stages",
        ):
            self.assertIn(marker, page)
        self.assertNotIn("forecast-segment", page)
        self.assertNotIn("forecast-legend-swatch", page)
        self.assertNotIn("forecastCounts", page)
        self.assertIn("composite-bar", page)
        ranking_section = page.split('<section class="report-panel ranking-panel"', 1)[1].split("</section>", 1)[0]
        self.assertNotIn("<table", ranking_section.lower())
        self.assertNotIn("Категории для антирейтинга:", page)
        self.assertNotIn("Доля выбранных", page)
        self.assertNotIn("Доля выгоревших", page)
        self.assertNotIn("Недельные данные", page)
        self.assertIn("показаны тестовые данные, не прогноз модели", page)
        self.assertIn('id="forecast-disclaimer"', page)
        self.assertNotIn("после апреля метки", page)

    def test_page_has_teacher_card_and_school_count_targets(self):
        response, body = self.request("/")
        page = body.decode("utf-8")

        self.assertEqual(response["status"], "200 OK")
        self.assertIn('class="kpi-card teacher-card"', page)
        self.assertIn('id="teacher-count"', page)
        self.assertIn('id="school-count"', page)

    def test_teacher_navigation_opens_dossier_with_separate_load_charts(self):
        response, body = self.request("/")
        page = body.decode("utf-8")

        self.assertEqual(response["status"], "200 OK")
        self.assertRegex(page, r'<button[^>]*id="teacher-tab"')
        self.assertIn('id="overview-tab"', page)
        self.assertIn('id="teacher-view"', page)
        self.assertIn('id="school-select"', page)
        self.assertIn('id="teacher-select"', page)
        self.assertLess(page.index('id="school-select"'), page.index('id="teacher-select"'))
        self.assertIn('id="teacher-name"', page)
        self.assertIn('id="teacher-current-stage"', page)
        self.assertIn('id="teacher-burnout-chart"', page)
        self.assertIn("drawTeacherBurnoutChart", page)
        self.assertIn('id="teacher-event-hours-chart"', page)
        self.assertIn('id="teacher-activity-hours-chart"', page)
        self.assertIn('id="teacher-survey-list"', page)
        self.assertIn("Последние опросы", page)
        self.assertNotIn('id="teacher-message-count-chart"', page)
        self.assertNotIn('id="teacher-participants-chart"', page)
        self.assertNotIn('<span class="nav-tab">Школа</span>', page)

    def test_teacher_directory_returns_school_first_selection_fields_only(self):
        response, body = self.request("/api/teachers")
        data = json.loads(body)

        self.assertEqual(response["status"], "200 OK")
        self.assertTrue(data["schools"])
        self.assertEqual(len(data["teachers"]), 300)
        for school in data["schools"]:
            self.assertIn("school_id", school)
            self.assertTrue(school["name"])
        for teacher in data["teachers"]:
            self.assertTrue(teacher["user_id"] > 0)
            self.assertTrue(teacher["name"])
            self.assertIn("school_id", teacher)
            self.assertIn("school", teacher)
            self.assertNotIn("current_stage", teacher)
            self.assertNotIn("history", teacher)

    def test_teacher_dossier_returns_current_stage_and_ordered_weekly_load(self):
        directory_response, directory_body = self.request("/api/teachers")
        teacher = json.loads(directory_body)["teachers"][0]
        response, body = self.request(f"/api/teacher?user_id={teacher['user_id']}")
        dossier = json.loads(body)

        self.assertEqual(directory_response["status"], "200 OK")
        self.assertEqual(response["status"], "200 OK")
        self.assertEqual(dossier["user_id"], teacher["user_id"])
        self.assertEqual(dossier["name"], teacher["name"])
        self.assertEqual(dossier["report_date"], "2026-04-20")
        self.assertIsNone(dossier["forecast_to"])
        self.assertEqual(dossier["forecast_week_dates"], [])
        self.assertEqual(
            dossier["burnout_stages"],
            [
                {"level": 0, "name": "Нет признаков"},
                {"level": 1, "name": "Напряженность"},
                {"level": 2, "name": "Истощение"},
                {"level": 3, "name": "Бессилие"},
            ],
        )
        self.assertIn(dossier["current_stage"]["level"], [None, 0, 1, 2, 3])
        self.assertIn("name", dossier["current_stage"])
        self.assertTrue(dossier["history"])
        weeks = [row["week_dt"] for row in dossier["history"]]
        self.assertEqual(weeks, sorted(weeks))
        self.assertTrue(all(week <= dossier["report_date"] for week in weeks))
        self.assertLessEqual(dossier["latest_week"], dossier["report_date"])
        for row in dossier["history"]:
            self.assertIn("event_hours", row)
            self.assertIn("activity_hours", row)
            self.assertIn("act_avg_participants_per_hour", row)
        self.assertNotIn("act_msg_cnt", dossier["history"][0])
        self.assertGreater(dossier["survey_count"], 0)
        self.assertTrue(dossier["surveys"])
        survey_dates = [survey["survey_dt"] for survey in dossier["surveys"]]
        self.assertEqual(survey_dates, sorted(survey_dates, reverse=True))
        self.assertTrue(all(survey_date <= dossier["report_date"] for survey_date in survey_dates))
        for survey in dossier["surveys"]:
            self.assertIn(survey["burnout_level"], [0, 1, 2, 3])
            self.assertTrue(survey["burnout_type"])
        self.assertEqual(
            dossier["current_stage"]["survey_dt"],
            dossier["surveys"][0]["survey_dt"],
        )
        self.assertEqual(
            dossier["current_stage"]["level"],
            dossier["surveys"][0]["burnout_level"],
        )

    def test_teacher_dossier_rejects_invalid_or_unknown_teacher_id(self):
        invalid_response, _ = self.request("/api/teacher?user_id=not-an-id")
        missing_response, _ = self.request("/api/teacher?user_id=999999")

        self.assertEqual(invalid_response["status"], "400 Bad Request")
        self.assertEqual(missing_response["status"], "404 Not Found")

    def test_dossier_has_no_data_before_first_fact(self):
        database = Path(__file__).parent.parent / "data" / "teacher_burnout.db"
        app = create_app(database, fact_through="2025-01-01")
        _, directory = self.request("/api/teachers", app=app)
        teacher_id = json.loads(directory)["teachers"][0]["user_id"]
        _, body = self.request(f"/api/teacher?user_id={teacher_id}", app=app)
        dossier = json.loads(body)
        self.assertIsNone(dossier["current_stage"]["level"])
        self.assertIsNone(dossier["latest_week"])
        self.assertIsNone(dossier["latest_load"])
        self.assertEqual(dossier["history"], [])
        self.assertEqual(dossier["surveys"], [])

    def test_teacher_without_surveys_has_no_current_stage_or_survey_rows(self):
        database = Path(__file__).parent.parent / "data" / "teacher_burnout.db"
        uri = f"file:{database.resolve().as_posix()}?mode=ro"
        with closing(sqlite3.connect(uri, uri=True)) as connection:
            row = connection.execute(
                "SELECT user_id FROM user_dic "
                "WHERE user_id NOT IN (SELECT user_id FROM survey_act) "
                "ORDER BY user_id LIMIT 1"
            ).fetchone()
        self.assertIsNotNone(row)

        response, body = self.request(f"/api/teacher?user_id={row[0]}")
        dossier = json.loads(body)

        self.assertEqual(response["status"], "200 OK")
        self.assertEqual(dossier["current_stage"]["name"], "Нет данных")
        self.assertIsNone(dossier["current_stage"]["level"])
        self.assertEqual(dossier["survey_count"], 0)
        self.assertEqual(dossier["surveys"], [])

    def test_teacher_card_keeps_reference_compact_proportions(self):
        _, body = self.request("/")
        page = body.decode("utf-8")

        self.assertIn("min-height:82px", page)
        self.assertIn("width:38px;height:38px;flex:0 0 38px", page)

    def test_model_accuracy_is_shown_as_an_uncomputed_placeholder(self):
        _, body = self.request("/")
        page = body.decode("utf-8")

        self.assertIn("Оценочная точность модели", page)
        self.assertIn('id="model-accuracy"', page)
        self.assertIn("Будет доступна после подключения модели", page)

    def test_accuracy_card_matches_teacher_card_composition(self):
        _, body = self.request("/")
        page = body.decode("utf-8")

        self.assertIn('class="accuracy-icon"', page)
        self.assertIn(".accuracy-card{display:flex;min-height:82px", page)
        self.assertLess(page.index('class="accuracy-icon"'), page.index('id="model-accuracy"'))

    def test_kpi_grid_uses_five_columns_and_collapses_on_smaller_screens(self):
        _, body = self.request("/")
        page = body.decode("utf-8")

        self.assertIn('class="kpi-grid"', page)
        self.assertIn(".kpi-grid{display:grid;grid-template-columns:repeat(5", page)
        self.assertIn(".kpi-grid{grid-template-columns:repeat(2", page)
        self.assertIn(".kpi-grid{grid-template-columns:1fr", page)

    def test_panel_endpoint_returns_rows_with_bounded_limit(self):
        response, body = self.request("/api/panel?limit=5")
        data = json.loads(body)

        self.assertEqual(response["status"], "200 OK")
        self.assertEqual(len(data["rows"]), 5)
        self.assertEqual(data["limit"], 5)
        self.assertNotIn("act_msg_cnt", data["rows"][0])

    def test_panel_endpoint_rejects_invalid_limit(self):
        response, body = self.request("/api/panel?limit=not-a-number")

        self.assertEqual(response["status"], "400 Bad Request")
        self.assertEqual(json.loads(body)["error"], "invalid limit")

    def test_non_get_requests_are_rejected(self):
        response, _ = self.request("/api/summary", method="POST")
        self.assertEqual(response["status"], "405 Method Not Allowed")

    def test_app_initialization_closes_the_read_only_database(self):
        database = Path(__file__).parent.parent / "data" / "teacher_burnout.db"
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", ResourceWarning)
            create_app(database)
            gc.collect()

        leaked_connections = [
            warning for warning in caught
            if issubclass(warning.category, ResourceWarning) and "unclosed database" in str(warning.message)
        ]
        self.assertEqual(leaked_connections, [])


if __name__ == "__main__":
    unittest.main()
