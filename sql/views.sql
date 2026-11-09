-- Понедельная панель признаков. Одна строка = учитель × неделя (неделя начинается в понедельник).
-- date(x, '-6 days', 'weekday 1') — понедельник недели, в которую попадает x.
-- Сетка недель для учителя: от первой до последней недели, в которой у него есть
-- события календаря или активность (т.е. период работы). Недели без данных внутри
-- периода (больничный, сбой выгрузки) остаются с нулями.
DROP VIEW IF EXISTS teacher_burnout_panel_ext;
DROP VIEW IF EXISTS teacher_burnout_panel;

CREATE VIEW teacher_burnout_panel AS
WITH RECURSIVE
sched AS (
    SELECT user_id,
           date(dttm_from, '-6 days', 'weekday 1')                                         AS week_dt,
           SUM((julianday(dttm_to) - julianday(dttm_from)) * 24.0)                          AS event_hours,
           SUM((julianday(dttm_to) - julianday(dttm_from)) * 24.0 * act_participants_cnt)   AS participant_hours
    FROM user_act_schedule
    GROUP BY 1, 2
),
act AS (
    -- activity_hours = число различных часовых интервалов, в которых была хотя бы одна активность
    SELECT user_id,
           date(activity_dttm, '-6 days', 'weekday 1')            AS week_dt,
           COUNT(DISTINCT strftime('%Y-%m-%d %H', activity_dttm))  AS activity_hours,
           SUM(act_msg_cnt)                                        AS act_msg_cnt,
           SUM(act_msg_char_cnt)                                   AS act_msg_char_cnt
    FROM user_activity_log
    GROUP BY 1, 2
),
surv AS (
    SELECT s.user_id,
           date(s.calendar_dt, '-6 days', 'weekday 1') AS week_dt,
           MAX(d.burnout_level)                         AS burnout_level
    FROM survey_act s
    JOIN burnout_type_dic d ON d.burnout_type = s.burnout_type
    GROUP BY 1, 2
),
emp AS (
    SELECT user_id, MIN(week_dt) AS w_from, MAX(week_dt) AS w_to
    FROM (SELECT user_id, week_dt FROM sched UNION ALL SELECT user_id, week_dt FROM act)
    GROUP BY user_id
),
spine(user_id, week_dt, w_to) AS (
    SELECT user_id, w_from, w_to FROM emp
    UNION ALL
    SELECT user_id, date(week_dt, '+7 days'), w_to FROM spine WHERE week_dt < w_to
)
SELECT sp.user_id,
       sp.week_dt,
       ROUND(COALESCE(sc.event_hours, 0), 2)                                     AS event_hours,
       COALESCE(a.activity_hours, 0)                                             AS activity_hours,
       ROUND(CASE WHEN sc.event_hours > 0
                  THEN sc.participant_hours / sc.event_hours END, 2)             AS act_avg_participants_per_hour,
       COALESCE(a.act_msg_cnt, 0)                                                AS act_msg_cnt,
       COALESCE(a.act_msg_char_cnt, 0)                                           AS act_msg_char_cnt,
       sv.burnout_level                                                          AS burnout_level   -- NULL, если опроса на неделе не было
FROM spine sp
LEFT JOIN sched sc ON sc.user_id = sp.user_id AND sc.week_dt = sp.week_dt
LEFT JOIN act   a  ON a.user_id  = sp.user_id AND a.week_dt  = sp.week_dt
LEFT JOIN surv  sv ON sv.user_id = sp.user_id AND sv.week_dt = sp.week_dt;

-- Расширенная панель (вне ТЗ): + дни больничного на неделе из user_absence
CREATE VIEW teacher_burnout_panel_ext AS
WITH RECURSIVE days(user_id, dt, date_to) AS (
    SELECT user_id, date_from, date_to FROM user_absence WHERE absence_type = 'Больничный'
    UNION ALL
    SELECT user_id, date(dt, '+1 day'), date_to FROM days WHERE dt < date_to
),
sick AS (
    SELECT user_id, date(dt, '-6 days', 'weekday 1') AS week_dt, COUNT(DISTINCT dt) AS sick_days
    FROM days GROUP BY 1, 2
)
SELECT p.*, COALESCE(s.sick_days, 0) AS sick_days
FROM teacher_burnout_panel p
LEFT JOIN sick s ON s.user_id = p.user_id AND s.week_dt = p.week_dt;
