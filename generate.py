#!/usr/bin/env python3
"""
Генератор синтетического датасета для модели выгорания учителей (v2).

  python generate.py                                   # default.yaml -> data/teacher_burnout.db
  python generate.py --config config/scenarios/high_burnout.yaml --out data/high.db
  python generate.py --set groups.burnout_share=0.4 --set absence.enabled=false

Сценарные конфиги частичные: накладываются поверх config/default.yaml.
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import sqlite3
from pathlib import Path

import numpy as np
import yaml

from names import STREETS, make_name

ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG = ROOT / "config" / "default.yaml"
DAY_MIN = 24 * 60


# ============================================================================ config
def deep_merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config(paths: list[str], sets: list[str]) -> dict:
    cfg = yaml.safe_load(DEFAULT_CONFIG.read_text(encoding="utf-8"))
    for p in paths:
        cfg = deep_merge(cfg, yaml.safe_load(Path(p).read_text(encoding="utf-8")))
    for s in sets:
        key, val = s.split("=", 1)
        node = cfg
        parts = key.split(".")
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = yaml.safe_load(val)
    return cfg


# ============================================================================ helpers
def d(s: str) -> dt.date:
    return dt.date.fromisoformat(str(s))


def hm(s: str) -> int:
    h, m = str(s).split(":")
    return int(h) * 60 + int(m)


def fmt(day: dt.date, minute: float, sec: int = 0) -> str:
    m = int(min(max(minute, 0), DAY_MIN - 1))
    return f"{day.isoformat()} {m // 60:02d}:{m % 60:02d}:{sec:02d}"


def clip01(x):
    return np.clip(x, 0.0, 1.0)


def smoothstep(x):
    x = clip01(x)
    return x * x * (3 - 2 * x)


def enabled(section: dict | None) -> bool:
    return bool(section) and section.get("enabled", True)


# ============================================================================ generator
class Generator:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.rng = np.random.default_rng(cfg["seed"])
        p = cfg["period"]
        self.start, self.end = d(p["start_date"]), d(p["end_date"])
        self.days = [self.start + dt.timedelta(i) for i in range((self.end - self.start).days + 1)]
        self.n_days = len(self.days)
        self.n_weeks = (self.n_days + 6) // 7
        self.holidays = set()
        for a, b in p["holidays"]:
            x = d(a)
            while x <= d(b):
                self.holidays.add(x)
                x += dt.timedelta(1)
        self._build_calendar_effects()

    def day_idx(self, day: dt.date) -> int:
        return (day - self.start).days

    # ---------------------------------------------------------------- calendar-wide effects
    def _build_calendar_effects(self):
        cfg, rng, n = self.cfg, self.rng, self.n_days
        self.s_ev, self.s_act, self.s_jour, self.s_stress = (np.ones(n), np.ones(n), np.ones(n), np.zeros(n))
        se = cfg.get("seasonality")
        if enabled(se):
            for per in se["periods"]:
                a, b = self.day_idx(d(per["from"])), self.day_idx(d(per["to"]))
                a, b = max(a, 0), min(b, n - 1)
                if a > b:
                    continue
                self.s_ev[a:b + 1] *= per.get("events_mult", 1)
                self.s_act[a:b + 1] *= per.get("activity_mult", 1)
                self.s_jour[a:b + 1] *= per.get("journal_mult", 1)
                self.s_stress[a:b + 1] += per.get("stress", 0)
        self.flu = np.ones(n)
        ab = cfg.get("absence")
        if enabled(ab):
            for fs in ab.get("flu_seasons", []):
                a, b = max(self.day_idx(d(fs["from"])), 0), min(self.day_idx(d(fs["to"])), n - 1)
                if a <= b:
                    self.flu[a:b + 1] *= fs["mult"]
        dq = cfg.get("data_quality")
        self.outage = np.zeros(n, dtype=bool)
        if enabled(dq):
            self.outage = rng.random(n) < dq["outage_day_prob"]
        # недельные средние
        self.w_stress = np.array([self.s_stress[7 * w:7 * w + 7].mean() for w in range(self.n_weeks)])
        self.w_flu = np.array([self.flu[7 * w:7 * w + 7].mean() for w in range(self.n_weeks)])

    # ---------------------------------------------------------------- dictionaries
    def build_dictionaries(self):
        cfg, rng = self.cfg, self.rng
        sc = cfg["scale"]
        self.schools, self.classes = [], []
        self.class_size, self.class_grade, self.class_nm = {}, {}, {}
        self.school_classes = {}
        g_lo, g_hi = sc["grades"]
        combos = [(g, l) for g in range(g_lo, g_hi + 1) for l in sc["class_letters"]]
        kinds = ["МБОУ «СОШ №{n}»"] * 6 + ["МАОУ «Гимназия №{n}»", "МАОУ «Лицей №{n}»"]
        nums = rng.choice(np.arange(1, 150), size=sc["n_schools"], replace=False)
        cs = cfg["class_size"]
        cid = 1
        for sid in range(1, sc["n_schools"] + 1):
            nm = str(rng.choice(kinds)).format(n=int(nums[sid - 1]))
            adr = f"{sc['city']}, ул. {rng.choice(STREETS)}, д. {rng.integers(1, 120)}"
            self.schools.append((sid, nm, adr))
            n_cls = min(int(rng.integers(sc["classes_per_school"][0], sc["classes_per_school"][1] + 1)), len(combos))
            # гарантируем хотя бы по одному классу в каждой параллели
            base = [combos.index((g, sc["class_letters"][0])) for g in range(g_lo, g_hi + 1)]
            rest = [i for i in range(len(combos)) if i not in base]
            extra = list(rng.choice(rest, size=max(0, n_cls - len(base)), replace=False))
            self.school_classes[sid] = []
            for i in sorted(base + extra):
                g, l = combos[i]
                self.classes.append((cid, f"{g}{l}", sid))
                self.class_size[cid] = int(np.clip(rng.normal(cs["mean"], cs["sd"]), cs["min"], cs["max"]))
                self.class_grade[cid] = g
                self.class_nm[cid] = f"{g}{l}"
                self.school_classes[sid].append(cid)
                cid += 1
        self.events = [(i, e["name"]) for i, e in enumerate(cfg["events"], start=1)]
        self.event_id = {e["name"]: i for i, e in enumerate(cfg["events"], start=1)}

    # ---------------------------------------------------------------- school shocks
    def build_school_shocks(self):
        cfg, rng = self.cfg, self.rng
        nW = self.n_weeks
        self.shock = {}
        ss = (cfg.get("seasonality") or {}).get("school_shocks")
        on = enabled(cfg.get("seasonality")) and enabled(ss)
        for sid, *_ in self.schools:
            active = np.zeros(nW, dtype=bool)
            if on:
                w = 0
                while w < nW:
                    if rng.random() < ss["weekly_prob"]:
                        ln = int(rng.integers(ss["duration_weeks"][0], ss["duration_weeks"][1] + 1))
                        active[w:w + ln] = True
                        w += ln
                    w += 1
            self.shock[sid] = dict(
                active=active,
                ev=np.where(active, ss["events_mult"] if on else 1, 1.0),
                act=np.where(active, ss["activity_mult"] if on else 1, 1.0),
                stress=np.where(active, ss["stress"] if on else 0, 0.0),
            )

    # ---------------------------------------------------------------- teachers & latent state
    def build_teachers(self):
        cfg, rng = self.cfg, self.rng
        n, nW = cfg["scale"]["n_teachers"], self.n_weeks
        g, bd, tt = cfg["groups"], cfg["burnout_dynamics"], cfg["timetable"]
        n_burn = int(round(n * g["burnout_share"]))
        n_over = int(round(n_burn * g["burnout_overload_share"]))
        n_hhl = int(round((n - n_burn) * g["healthy_high_load_share"]))
        profiles = (["burnout_overload"] * n_over + ["burnout_disengaged"] * (n_burn - n_over)
                    + ["healthy_high_load"] * n_hhl + ["healthy"] * (n - n_burn - n_hhl))
        rng.shuffle(profiles)
        holiday_weeks = sorted({self.day_idx(h) // 7 for h in self.holidays if self.start <= h <= self.end})
        weeks = np.arange(nW)
        ex = g["behavior_expression"]
        ad = cfg["activity"]
        self.teachers = []
        for i, prof in enumerate(profiles):
            uid = i + 1
            female = rng.random() < 0.82
            sid = int(rng.choice([s[0] for s in self.schools]))
            pool = self.school_classes[sid]
            primary = rng.random() < tt["primary_teacher_share"]
            if primary:
                cand = [c for c in pool if self.class_grade[c] <= 4]
                classes = [int(rng.choice(cand))]
                homeroom = classes[0]
            else:
                cand = [c for c in pool if self.class_grade[c] >= 5]
                k = int(min(len(cand), rng.integers(3, 9)))
                classes = [int(c) for c in rng.choice(cand, size=k, replace=False)]
                homeroom = classes[0] if rng.random() < cfg["homeroom_share_subject"] else None
            t = dict(
                user_id=uid, name=make_name(rng, female), school_id=sid, primary=primary,
                classes=classes, homeroom=homeroom, profile=prof,
                stavka=float(rng.choice(tt["stavka_options"], p=tt["stavka_probs"])),
                six_day=bool(rng.random() < cfg["period"]["work_saturday_share"]),
                bg_actions=max(2.0, rng.normal(ad["background_actions_per_workday"]["mean"],
                                               ad["background_actions_per_workday"]["sd"])),
                chars_per_msg=max(30.0, rng.normal(ad["chars_per_msg"]["mean"], ad["chars_per_msg"]["sd"])),
                attendance=float(np.clip(rng.normal(cfg["attendance_rate"]["mean"], cfg["attendance_rate"]["sd"]), 0.6, 1.0)),
                offset=rng.normal(0, bd["baseline_level_sd"]),
                w_o=0.0, w_d=0.0, expression=0.0,
                onset=None, ramp=None, peak=0.0, lead=0, recovers=False,
            )
            burn, over = np.zeros(nW), np.zeros(nW)
            if prof.startswith("burnout"):
                dom = rng.uniform(1 - g["type_mixing"], 1)
                t["w_o"], t["w_d"] = (dom, 1 - dom) if prof == "burnout_overload" else (1 - dom, dom)
                t["expression"] = float(np.clip(rng.normal(ex["mean"], ex["sd"]), ex["min"], ex["max"]))
                rr = bd["initial_onset_week_range"] if rng.random() < bd["initial_share"] else bd["onset_week_range"]
                t["onset"] = int(rng.integers(rr[0], rr[1] + 1))
                t["ramp"] = int(rng.integers(bd["ramp_weeks_range"][0], bd["ramp_weeks_range"][1] + 1))
                t["peak"] = float(rng.uniform(*bd["peak_level_range"]))
                t["lead"] = int(rng.integers(bd["overload_lead_weeks"][0], bd["overload_lead_weeks"][1] + 1))
                t["recovers"] = bool(rng.random() < bd["recovery_prob"])
                trend = t["peak"] * smoothstep((weeks - t["onset"]) / t["ramp"])
                rw = np.zeros(nW)
                for w in range(1, nW):
                    rw[w] = 0.85 * rw[w - 1] + rng.normal(0, bd["trajectory_noise_sd"])
                burn = np.where(trend > 0, np.maximum(0, trend + rw * np.minimum(1, trend)), 0.0)
                over = smoothstep((weeks - (t["onset"] - t["lead"])) / (t["ramp"] + t["lead"]))
                if t["recovers"]:
                    after = [w for w in holiday_weeks if w > max(t["onset"], 0) + 1]
                    if after:
                        w0 = after[0] + 1
                        burn[w0:] = np.maximum(0, burn[w0:] - bd["recovery_drop"])
                        over[w0:] *= 0.5
            noise = np.zeros(nW)
            for w in range(1, nW):
                noise[w] = 0.6 * noise[w - 1] + rng.normal(0, bd["weekly_noise_sd"])
            t["burn"], t["bnorm"], t["over"] = burn, burn / 3.0, over
            t["latent"] = np.clip(t["offset"] + burn + noise + self.w_stress + self.shock[sid]["stress"], 0, 3.4)
            self._employment(t)
            self._sick_leave(t)
            self._templates(t)
            self.teachers.append(t)

    def _employment(self, t):
        cfg, rng, nW = self.cfg, self.rng, self.n_weeks
        ch = cfg.get("churn")
        t["hire_week"], t["quit_week"] = 0, None
        if enabled(ch):
            if rng.random() < ch["late_hire_share"]:
                t["hire_week"] = int(rng.integers(4, max(5, nW - 8)))
            for w in range(t["hire_week"] + 1, nW):
                lat = min(max(t["latent"][w], 0), 3) / 3
                if rng.random() < ch["quit_weekly_base"] * (1 + (ch["quit_burnout_mult"] - 1) * lat):
                    t["quit_week"] = w
                    break
        last = t["quit_week"] if t["quit_week"] is not None else nW
        t["employed"] = np.array([t["hire_week"] <= w < last for w in range(nW)])

    def _sick_leave(self, t):
        cfg, rng = self.cfg, self.rng
        ab = cfg.get("absence")
        t["sick"] = set()
        t["absences"] = []
        if not enabled(ab):
            return
        w = 0
        while w < self.n_weeks:
            if t["employed"][w]:
                lat = min(max(t["latent"][w], 0), 3) / 3
                p = ab["sick_weekly_prob"] * (1 + (ab["sick_burnout_mult"] - 1) * lat) * self.w_flu[w]
                if rng.random() < p:
                    a = self.start + dt.timedelta(7 * w + int(rng.integers(0, 5)))
                    ln = int(rng.integers(ab["sick_days"][0], ab["sick_days"][1] + 1))
                    b = min(a + dt.timedelta(ln - 1), self.end)
                    if a <= self.end:
                        t["absences"].append((a, b))
                        x = a
                        while x <= b:
                            t["sick"].add(x)
                            x += dt.timedelta(1)
                        w = self.day_idx(b) // 7 + 1
                        continue
            w += 1

    def _templates(self, t):
        """Шаблон недельного расписания на каждое полугодие: список (weekday, slot, class_id)."""
        cfg, rng, tt = self.cfg, self.rng, self.cfg["timetable"]
        n_wd = 6 if t["six_day"] else 5
        bounds = [self.start] + sorted(d(x) for x in tt.get("rebuild_dates", [])) + [self.end + dt.timedelta(1)]
        t["templates"] = []
        hhl = t["profile"] == "healthy_high_load"
        for a, b in zip(bounds[:-1], bounds[1:]):
            if t["primary"]:
                hours = int(round(rng.normal(21, 1.0)))
                max_slot = 5
            else:
                hours = int(round(t["stavka"] * tt["hours_per_stavka"] + rng.normal(0, tt["hours_noise_sd"])))
                max_slot = tt["max_lessons_per_day"]
            if hhl:
                hours = int(round(hours * 1.1))
            pos = [(wd, s) for wd in range(n_wd) for s in range(max_slot)]
            wts = np.array([(0.5 if wd == 5 else 1.0) * [1, 1, 1, 1, 0.85, 0.6, 0.4, 0.3][s] for wd, s in pos])
            hours = min(hours, len(pos))
            idx = rng.choice(len(pos), size=hours, replace=False, p=wts / wts.sum())
            cls = [t["classes"][j % len(t["classes"])] for j in range(hours)]
            rng.shuffle(cls)
            t["templates"].append((a, b, [(pos[k][0], pos[k][1], int(c)) for k, c in zip(idx, cls)]))

    # ---------------------------------------------------------------- multipliers
    def mults(self, t, w):
        ld, ad = self.cfg["load"], self.cfg["activity"]
        io = t["w_o"] * t["expression"] * t["over"][w]
        idg = t["w_d"] * t["expression"] * t["bnorm"][w]
        ic = t["expression"] * t["bnorm"][w]
        hhl = t["profile"] == "healthy_high_load"
        return dict(
            events=(1 + (ld["overload_events_mult"] - 1) * io) * (1 + (ld["disengaged_events_mult"] - 1) * idg)
                   * (ld["healthy_high_load_mult"] if hhl else 1),
            subs=(1 + (ld["overload_substitutions_mult"] - 1) * io) * (ld["healthy_high_load_substitutions_mult"] if hhl else 1),
            parts=1 + (ld["overload_participants_mult"] - 1) * io,
            actions=(1 + (ad["overload_actions_mult"] - 1) * io) * (1 + (ad["disengaged_actions_mult"] - 1) * idg)
                    * (ad["healthy_high_load_actions_mult"] if hhl else 1),
            msgs=1 + (ad["disengaged_msg_mult"] - 1) * idg,
            after_lesson=1 + (ad["disengaged_after_lesson_mult"] - 1) * idg,
            chars=1 + (ad["burnout_chars_mult"] - 1) * ic,
            evening=float(np.clip(ad["evening_share"] + (ad["overload_evening_share"] - ad["evening_share"]) * io, 0, 0.9)),
        )

    # ---------------------------------------------------------------- schedule + activity for one teacher
    def gen_teacher(self, t, sched_rows, act_rows):
        cfg, rng = self.cfg, self.rng
        tt, ad = cfg["timetable"], cfg["activity"]
        dq = cfg.get("data_quality") if enabled(cfg.get("data_quality")) else {}
        les_dur, brk, t0 = tt["lesson_duration_min"], tt["break_min"], hm(tt["first_lesson_time"])
        lesson_eid = self.event_id["Урок"]
        n_wd = 6 if t["six_day"] else 5
        sid = t["school_id"]
        shock = self.shock[sid]
        extra = []
        for e in cfg["events"]:
            if e.get("kind") == "lesson":
                continue
            f = e.get("for", "any")
            if (f == "primary" and not t["primary"]) or (f == "subject" and t["primary"]):
                continue
            if e.get("homeroom_only") and t["homeroom"] is None:
                continue
            if e.get("need_grades") and not any(self.class_grade[c] in e["need_grades"] for c in t["classes"]):
                continue
            extra.append(e)
        other_classes = [c for c in self.school_classes[sid] if c not in t["classes"]] or t["classes"]
        cls_names = [self.class_nm[c] for c in t["classes"]]
        bg_types = ad["types"]
        bg_p = np.array([x["prob"] for x in bg_types], float)
        bg_p /= bg_p.sum()
        day_hours = np.arange(7, 19)
        day_w = np.array([1, 2, 2, 2, 2, 2, 2, 3, 4, 4, 3, 2], float); day_w /= day_w.sum()
        eve_hours = np.array([19, 20, 21, 22, 23])
        eve_w = np.array([4, 4, 3, 2, 1], float); eve_w /= eve_w.sum()
        al = ad["after_lesson"]
        gap_p = dq.get("teacher_gap_weekly_prob", 0)
        miss_p = dq.get("schedule_missing_prob", 0)
        dup_p = dq.get("activity_duplicate_prob", 0)

        def add_sched(day, st, en, eid, cl, parts):
            if rng.random() < miss_p:
                return
            sched_rows.append((t["user_id"], sid, eid, fmt(day, st), fmt(day, en), cl, parts))

        def add_act(day, minute, tp, k, chars, desc):
            row = (t["user_id"], tp, k, chars, desc, fmt(day, minute, int(rng.integers(0, 60))))
            act_rows.append(row)
            if rng.random() < dup_p:
                act_rows.append(row)

        def msg_chars(k, m):
            mean = t["chars_per_msg"] * m["chars"]
            return int(max(ad["chars_per_msg"]["min"] * k, rng.normal(mean * k, ad["chars_per_msg"]["sd"] * np.sqrt(k))))

        for w in range(self.n_weeks):
            if not t["employed"][w]:
                continue
            m = self.mults(t, w)
            week_days = [self.start + dt.timedelta(7 * w + k) for k in range(7)]
            week_days = [x for x in week_days if x <= self.end]
            workdays = [x for x in week_days if x.weekday() < n_wd and x not in self.holidays and x not in t["sick"]]
            wi = [self.day_idx(x) for x in week_days]
            s_ev_w = float(np.mean(self.s_ev[wi])) * shock["ev"][w]
            lesson_ends = {x: [] for x in week_days}
            busy = {x: set() for x in workdays}
            # ---- уроки по шаблону
            tpl = next(lst for a, b, lst in t["templates"] if a <= week_days[0] < b or a <= week_days[-1] < b)
            for wd, slot, cl in tpl:
                day = self.start + dt.timedelta(7 * w + wd)
                if day not in busy or rng.random() < tt["cancel_prob"]:
                    continue
                st = t0 + slot * (les_dur + brk)
                att = t["attendance"] * (1 - 0.08 * (self.flu[self.day_idx(day)] - 1))
                add_sched(day, st, st + les_dur, lesson_eid, cl, int(rng.binomial(self.class_size[cl], att)))
                busy[day].add(slot)
                lesson_ends[day].append((st + les_dur, cl))
            # ---- замены
            if workdays:
                frac = len(workdays) / n_wd
                for _ in range(int(rng.poisson(tt["substitutions_per_week"] * m["subs"] * s_ev_w * frac))):
                    day = workdays[int(rng.integers(len(workdays)))]
                    free = [s for s in range(tt["max_lessons_per_day"]) if s not in busy[day]]
                    if not free:
                        continue
                    slot = int(rng.choice(free))
                    cl = int(rng.choice(other_classes))
                    st = t0 + slot * (les_dur + brk)
                    parts = int(rng.binomial(self.class_size[cl], t["attendance"]) * m["parts"])
                    add_sched(day, st, st + les_dur, lesson_eid, cl, parts)
                    busy[day].add(slot)
                    lesson_ends[day].append((st + les_dur, cl))
                # ---- внеурочные мероприятия
                cursor = {x: (t0 + (max(busy[x]) + 1) * (les_dur + brk) if busy[x] else hm("13:30"))
                          + int(rng.integers(10, 40)) for x in workdays}
                fixed_used = set()
                for e in extra:
                    rate = e["rate"] * frac * (m["events"] if e["overload_sensitive"] else 1.0) * s_ev_w
                    for _ in range(int(rng.poisson(rate))):
                        day = workdays[int(rng.integers(len(workdays)))]
                        dur = int(rng.integers(e["duration"][0], e["duration"][1] + 1))
                        if e.get("start"):
                            if (day, e["name"]) in fixed_used:      # фиксированное время — не больше одного в день
                                continue
                            fixed_used.add((day, e["name"]))
                            st = hm(e["start"])
                        elif e.get("evening"):
                            st = max(hm("18:00") + int(rng.integers(0, 4)) * 15, cursor[day])
                            cursor[day] = st + dur + 10
                        else:
                            st = cursor[day]
                            cursor[day] = st + dur + int(rng.integers(5, 30))
                        if st > hm("21:00"):
                            continue
                        en = min(st + dur, DAY_MIN - 1)
                        lo, hi = e["participants"]
                        pm = m["parts"] if e["overload_sensitive"] else 1.0
                        parts = int(round(rng.integers(lo, hi + 1) * pm))
                        cl = None
                        if e.get("class_bound"):
                            cl = t["homeroom"] if (e.get("homeroom") and t["homeroom"]) else int(rng.choice(t["classes"]))
                        add_sched(day, st, en, self.event_id[e["name"]], cl, parts)

            # ---- активность
            if rng.random() < gap_p:
                continue
            for day in week_days:
                di = self.day_idx(day)
                if self.outage[di]:
                    continue
                is_work = day.weekday() < n_wd
                base = 1.0 if is_work else ad["weekend_mult"]
                if day in self.holidays:
                    base *= cfg["period"]["holiday_activity_mult"]
                if day in t["sick"]:
                    base *= cfg["absence"]["activity_during_sick"]
                day_mult = base * self.s_act[di] * shock["act"][w] * m["actions"] * rng.lognormal(0, ad["day_noise_sigma"])
                # действия после уроков
                for end, cl in lesson_ends.get(day, []):
                    for tp, p in (("journal_grades", al["journal_grades_prob"] * self.s_jour[di]),
                                  ("homework_assign", al["homework_assign_prob"])):
                        if rng.random() < min(0.95, p * m["after_lesson"]):
                            if rng.random() < m["evening"]:
                                minute = int(rng.choice(eve_hours, p=eve_w)) * 60 + int(rng.integers(0, 60))
                            else:
                                minute = end + rng.lognormal(al["delay_min_lognormal"]["mu"], al["delay_min_lognormal"]["sigma"])
                            if minute < DAY_MIN:
                                add_act(day, minute, tp, 0, 0, ad["lesson_types"][tp].format(cls=self.class_nm[cl]))
                # фоновые действия сессиями
                n = int(rng.poisson(t["bg_actions"] * day_mult))
                if n == 0:
                    continue
                k = int(min(n, max(1, rng.poisson(ad["sessions_per_workday"] * (1 if is_work else 0.5)))))
                eve = rng.random(k) < m["evening"]
                centers = np.where(eve, rng.choice(eve_hours, size=k, p=eve_w), rng.choice(day_hours, size=k, p=day_w)) * 60 \
                          + rng.integers(0, 60, size=k)
                sess = rng.integers(0, k, size=n)
                minutes = np.clip(centers[sess] + rng.normal(0, ad["session_spread_min"], size=n), 0, DAY_MIN - 1)
                types = rng.choice(len(bg_types), size=n, p=bg_p)
                for j in range(n):
                    tp = bg_types[types[j]]
                    if tp["is_msg"]:
                        if rng.random() > m["msgs"]:
                            continue
                        kk = 1 + int(rng.poisson(max(tp["msg_mean"] - 1, 0)))
                        chars = msg_chars(kk, m)
                    else:
                        kk, chars = 0, 0
                    add_act(day, minutes[j], tp["name"], kk, chars,
                            tp["desc"].format(cls=cls_names[int(rng.integers(len(cls_names)))]))

    # ---------------------------------------------------------------- surveys
    def gen_surveys(self):
        cfg, rng = self.cfg, self.rng
        sv = cfg["survey"]
        lvl2type = {x["level"]: x["type"] for x in sv["burnout_types"]}
        max_lvl = max(lvl2type)
        rows = []

        def measure(t, day):
            w = self.day_idx(day) // 7
            return lvl2type[int(np.clip(np.round(t["latent"][w] + rng.normal(0, sv["noise_sd"])), 0, max_lvl))]

        def p_resp(t, w, k):
            lat = min(max(t["latent"][w], 0), 3) / 3
            return sv["response_rate"] * (1 - sv["burnout_nonresponse"] * lat) * max(0.1, 1 - sv["wave_fatigue"] * k)

        if sv["mode"] == "weekly":
            for t in self.teachers:
                for w in range(self.n_weeks):
                    if not t["employed"][w] or rng.random() >= sv["weekly_prob"] * p_resp(t, w, 0) / sv["response_rate"]:
                        continue
                    cand = [self.start + dt.timedelta(7 * w + k) for k in range(5)]
                    cand = [x for x in cand if x <= self.end]
                    if cand:
                        day = cand[int(rng.integers(len(cand)))]
                        rows.append((t["user_id"], day.isoformat(), measure(t, day)))
            return rows

        waves = list(range(sv["wave_first_week"], self.n_weeks, sv["wave_every_weeks"]))
        for k, w0 in enumerate(waves):
            window = [self.start + dt.timedelta(7 * w0 + j) for j in range(7 * sv["wave_window_weeks"])]
            window = [x for x in window if x <= self.end and x.weekday() < 5 and x not in self.holidays]
            if not window:
                continue
            for t in self.teachers:
                cand = [x for x in window if t["employed"][self.day_idx(x) // 7]]
                if not cand or rng.random() >= p_resp(t, w0, k):
                    continue
                n_ans = 2 if rng.random() < sv["duplicate_prob"] else 1
                for day in sorted(rng.choice(len(cand), size=min(n_ans, len(cand)), replace=False)):
                    day = cand[int(day)]
                    rows.append((t["user_id"], day.isoformat(), measure(t, day)))
        return rows

    # ---------------------------------------------------------------- run
    def run(self, out_path: Path):
        self.build_dictionaries()
        self.build_school_shocks()
        self.build_teachers()
        print(f"Учителей: {len(self.teachers)}, школ: {len(self.schools)}, классов: {len(self.classes)}, недель: {self.n_weeks}")
        sched, act = [], []
        for t in self.teachers:
            self.gen_teacher(t, sched, act)
        sched.sort(key=lambda r: (r[0], r[3]))
        act.sort(key=lambda r: (r[0], r[5]))
        sched = [(i + 1,) + r for i, r in enumerate(sched)]
        act = [(i + 1,) + r for i, r in enumerate(act)]
        surv = sorted(self.gen_surveys(), key=lambda r: (r[0], r[1]))
        surv = [(i + 1,) + r for i, r in enumerate(surv)]
        absn = [(t["user_id"], a.isoformat(), b.isoformat(), "Больничный") for t in self.teachers for a, b in t["absences"]]
        absn = [(i + 1,) + r for i, r in enumerate(absn)]
        print(f"  user_act_schedule: {len(sched):,}\n  user_activity_log: {len(act):,}\n"
              f"  survey_act:        {len(surv):,}\n  user_absence:      {len(absn):,}")

        out_path.parent.mkdir(parents=True, exist_ok=True)
        if out_path.exists():
            out_path.unlink()
        con = sqlite3.connect(out_path)
        con.executescript((ROOT / "sql" / "schema.sql").read_text(encoding="utf-8"))
        ins = lambda tbl, data: data and con.executemany(
            f"INSERT INTO {tbl} VALUES ({','.join('?' * len(data[0]))})", data)
        ins("school_dic", self.schools)
        ins("user_dic", [(t["user_id"], t["name"]) for t in self.teachers])
        ins("class_dic", self.classes)
        ins("event_dic", self.events)
        ins("burnout_type_dic", [(x["type"], x["level"]) for x in self.cfg["survey"]["burnout_types"]])
        ins("user_act_schedule", sched)
        ins("user_activity_log", act)
        ins("survey_act", surv)
        ins("user_absence", absn)
        if self.cfg["output"].get("write_truth_table", True):
            ins("_gen_teacher_truth", [(
                t["user_id"], t["school_id"], "primary" if t["primary"] else "subject", t["stavka"], t["profile"],
                round(t["w_o"], 3), round(t["w_d"], 3), round(t["expression"], 3), t["onset"], t["ramp"],
                round(t["peak"], 3), int(t["recovers"]), t["hire_week"], t["quit_week"]) for t in self.teachers])
            ins("_gen_teacher_week_truth", [(
                t["user_id"], (self.start + dt.timedelta(7 * w)).isoformat(), round(float(t["latent"][w]), 3),
                round(float(t["burn"][w]), 3), round(float(t["over"][w]), 3), int(t["employed"][w]))
                for t in self.teachers for w in range(self.n_weeks)])
        con.commit()
        con.executescript((ROOT / "sql" / "indexes.sql").read_text(encoding="utf-8"))
        con.executescript((ROOT / "sql" / "views.sql").read_text(encoding="utf-8"))
        con.commit()
        if self.cfg["output"].get("export_panel_csv", True):
            import pandas as pd
            panel = pd.read_sql("SELECT * FROM teacher_burnout_panel ORDER BY user_id, week_dt", con)
            csv_path = out_path.with_name(out_path.stem + "_panel.csv")
            panel.to_csv(csv_path, index=False)
            print(f"  teacher_burnout_panel: {len(panel):,} строк ({panel['burnout_level'].notna().sum():,} с таргетом) -> {csv_path.name}")
        con.close()
        out_path.with_name(out_path.stem + "_config.yaml").write_text(
            yaml.safe_dump(self.cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")
        print(f"Готово: {out_path}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", action="append", default=[], help="частичный YAML поверх default.yaml (можно несколько)")
    ap.add_argument("--set", action="append", default=[], help="точечное переопределение: groups.burnout_share=0.3")
    ap.add_argument("--out", default=str(ROOT / "data" / "teacher_burnout.db"))
    a = ap.parse_args()
    Generator(load_config(a.config, a.set)).run(Path(a.out))


if __name__ == "__main__":
    main()
