-- Схема БД (SQLite). Порядок создания учитывает внешние ключи.
PRAGMA foreign_keys = ON;

DROP VIEW  IF EXISTS teacher_burnout_panel;
DROP TABLE IF EXISTS user_activity_log;
DROP TABLE IF EXISTS user_act_schedule;
DROP TABLE IF EXISTS survey_act;
DROP TABLE IF EXISTS burnout_type_dic;
DROP TABLE IF EXISTS class_dic;
DROP TABLE IF EXISTS event_dic;
DROP TABLE IF EXISTS user_dic;
DROP TABLE IF EXISTS school_dic;
DROP VIEW  IF EXISTS teacher_burnout_panel_ext;
DROP TABLE IF EXISTS user_absence;
DROP TABLE IF EXISTS _gen_teacher_truth;
DROP TABLE IF EXISTS _gen_teacher_week_truth;

-- Справочник школ
CREATE TABLE school_dic (
    school_id   INTEGER PRIMARY KEY,
    school_nm   TEXT NOT NULL,
    school_adr  TEXT
);

-- Справочник пользователей (учителей)
CREATE TABLE user_dic (
    user_id  INTEGER PRIMARY KEY,
    user_nm  TEXT NOT NULL
);

-- Справочник классов
CREATE TABLE class_dic (
    class_id   INTEGER PRIMARY KEY,
    class_nm   TEXT NOT NULL,
    school_id  INTEGER NOT NULL REFERENCES school_dic(school_id)
);

-- Справочник мероприятий
CREATE TABLE event_dic (
    event_id  INTEGER PRIMARY KEY,
    event_nm  TEXT NOT NULL
);

-- Вспомогательный справочник: тип выгорания -> числовой уровень (для таргета)
CREATE TABLE burnout_type_dic (
    burnout_type   TEXT PRIMARY KEY,
    burnout_level  INTEGER NOT NULL
);

-- Активность в инструментах учителя
CREATE TABLE user_activity_log (
    activity_id       INTEGER PRIMARY KEY,
    user_id           INTEGER NOT NULL REFERENCES user_dic(user_id),
    activity_type     TEXT NOT NULL,
    act_msg_cnt       INTEGER NOT NULL DEFAULT 0,
    act_msg_char_cnt  INTEGER NOT NULL DEFAULT 0,
    activity_desc     TEXT,
    activity_dttm     TEXT NOT NULL            -- 'YYYY-MM-DD HH:MM:SS'
);

-- Фактический календарь
CREATE TABLE user_act_schedule (
    schedule_id           INTEGER PRIMARY KEY,
    user_id               INTEGER NOT NULL REFERENCES user_dic(user_id),
    school_id             INTEGER NOT NULL REFERENCES school_dic(school_id),
    event_id              INTEGER NOT NULL REFERENCES event_dic(event_id),
    dttm_from             TEXT NOT NULL,
    dttm_to               TEXT NOT NULL,
    class_id              INTEGER REFERENCES class_dic(class_id),   -- NULL для общешкольных (педсовет, дежурство)
    act_participants_cnt  INTEGER
);

-- Результаты опросов
CREATE TABLE survey_act (
    survey_id     INTEGER PRIMARY KEY,
    user_id       INTEGER NOT NULL REFERENCES user_dic(user_id),
    calendar_dt   TEXT NOT NULL,               -- 'YYYY-MM-DD'
    burnout_type  TEXT NOT NULL REFERENCES burnout_type_dic(burnout_type)
);

-- ДОП. таблица (вне исходного ТЗ): отсутствия из HR-системы
CREATE TABLE user_absence (
    absence_id    INTEGER PRIMARY KEY,
    user_id       INTEGER NOT NULL REFERENCES user_dic(user_id),
    date_from     TEXT NOT NULL,
    date_to       TEXT NOT NULL,
    absence_type  TEXT NOT NULL              -- 'Больничный'
);

-- Служебные таблицы с «истиной» генератора (для отладки/анализа, НЕ использовать как признаки)
CREATE TABLE _gen_teacher_truth (
    user_id         INTEGER PRIMARY KEY,
    school_id       INTEGER,
    teacher_kind    TEXT,      -- primary / subject
    stavka          REAL,
    profile         TEXT,      -- healthy / healthy_high_load / burnout_overload / burnout_disengaged
    w_overload      REAL,
    w_disengaged    REAL,
    expression      REAL,
    onset_week      INTEGER,
    ramp_weeks      INTEGER,
    peak_level      REAL,
    recovers        INTEGER,
    hire_week       INTEGER,
    quit_week       INTEGER
);

CREATE TABLE _gen_teacher_week_truth (
    user_id      INTEGER,
    week_dt      TEXT,
    latent       REAL,         -- латентный уровень, из которого снимается опрос
    burn         REAL,         -- компонент выгорания
    overload     REAL,         -- интенсивность перегрузки 0..1
    employed     INTEGER,
    PRIMARY KEY (user_id, week_dt)
);
