CREATE INDEX IF NOT EXISTS ix_activity_user_dttm ON user_activity_log(user_id, activity_dttm);
CREATE INDEX IF NOT EXISTS ix_schedule_user_dttm ON user_act_schedule(user_id, dttm_from);
CREATE INDEX IF NOT EXISTS ix_survey_user_dt     ON survey_act(user_id, calendar_dt);
CREATE INDEX IF NOT EXISTS ix_class_school       ON class_dic(school_id);
