from __future__ import annotations

import json
import sqlite3
import argparse
from contextlib import closing
from datetime import date
from wsgiref.simple_server import make_server
from pathlib import Path
from urllib.parse import parse_qs, quote


_PAGE = """<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="icon" href="data:,">
<title>Мониторинг педагогов</title>
<style>
:root{color-scheme:light;--ink:#281644;--muted:#766985;--purple:#5b2bac;--line:#d9c9ef;--surface:#fff;--lavender:#f3eafe}
*{box-sizing:border-box}
body{margin:0;background:#f6f1fb;color:var(--ink);font:13px/1.35 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
.page-shell{max-width:1360px;margin:14px auto;padding:0 14px}
.dashboard-topbar{display:flex;align-items:center;gap:14px;min-height:44px;padding:6px 10px;border:1px solid #d6c4ef;border-radius:15px;background:linear-gradient(100deg,#fff 0%,#f5edff 100%);box-shadow:0 4px 14px rgba(83,43,145,.07)}
.brand{display:flex;min-width:174px;align-items:center;gap:8px;color:var(--ink);text-decoration:none}
.brand-icon{display:grid;width:35px;height:35px;place-items:center;border:1px solid #d8c5f2;border-radius:10px;background:#f3eaff;color:var(--purple)}
.brand-icon svg{width:23px;height:23px;fill:none;stroke:currentColor;stroke-linecap:round;stroke-linejoin:round;stroke-width:2}
.brand-title{margin:0;font-size:.88rem;font-weight:780;line-height:1.1}
.topbar-nav{display:flex;align-items:center;gap:7px}
.nav-tab{display:inline-flex;min-height:30px;align-items:center;justify-content:center;padding:5px 17px;border-radius:999px;background:#eee4fb;color:#49316c;font-size:.78rem;font-weight:700;white-space:nowrap}
.nav-tab.is-active{background:linear-gradient(100deg,#a56be8,#7643c8);color:#fff;box-shadow:0 3px 9px rgba(97,47,169,.2)}
.header-controls{display:flex;align-items:center;justify-content:flex-end;gap:7px;margin-left:auto}
.header-chip{display:flex;min-height:30px;align-items:center;gap:6px;padding:4px 10px;border:1px solid #e1d4f2;border-radius:999px;background:rgba(255,255,255,.78);color:#4a3d5e;font-size:.7rem;white-space:nowrap}
.header-chip svg{width:15px;height:15px;flex:0 0 15px;fill:none;stroke:#6739ad;stroke-linecap:round;stroke-linejoin:round;stroke-width:1.8}
.header-chip strong{color:#2d1c49;font-weight:700}
.status{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%);white-space:nowrap}
.status-error{position:static;width:auto;height:auto;margin:7px 3px;color:#a32148;clip-path:none;white-space:normal}
.kpi-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:9px;margin:10px 0 14px}
.kpi-card{min-width:0;min-height:82px;border:1px solid #ddcdef;border-radius:14px;background:linear-gradient(125deg,#fff 0%,#f6efff 100%);box-shadow:0 4px 12px rgba(70,35,118,.08),inset 0 1px 0 rgba(255,255,255,.9)}
.teacher-card{display:flex;min-height:82px;align-items:center;gap:8px;padding:8px 10px;border-color:#d4c0ef}
.teacher-icon{display:grid;width:38px;height:38px;flex:0 0 38px;place-items:center;color:#6835b2}
.teacher-icon svg{width:35px;height:35px;fill:none;stroke:currentColor;stroke-linecap:round;stroke-linejoin:round;stroke-width:2}
.teacher-copy{min-width:0}
.kpi-title{color:#302145;font-size:.7rem;font-weight:750;line-height:1.18}
.teacher-count{display:block;margin-top:2px;color:#28143f;font-size:1.42rem;font-weight:820;line-height:1.05}
.school-count{display:block;margin-top:2px;color:#635574;font-size:.66rem;font-weight:650}
.stage-card{display:flex;min-height:82px;flex-direction:column;justify-content:center;gap:3px;padding:7px 9px}
.stage-level-1{--stage:#7040bd;border-color:#d9c6f2;background:linear-gradient(130deg,#fff 0%,#f5edff 100%)}
.stage-level-2{--stage:#984bd5;border-color:#dfc8f0;background:linear-gradient(130deg,#fff 0%,#f8efff 100%)}
.stage-level-3{--stage:#5c279e;border-color:#d2c1e6;background:linear-gradient(130deg,#fff 0%,#f1e9fa 100%)}
.stage-head{display:flex;min-width:0;align-items:center;gap:6px}
.stage-icon{display:grid;width:24px;height:20px;flex:0 0 24px;place-items:center;color:var(--stage)}
.stage-icon svg{width:23px;height:19px;fill:none;stroke:currentColor;stroke-linecap:round;stroke-linejoin:round;stroke-width:1.8}
.stage-title{overflow:hidden;color:#332349;font-size:.65rem;font-weight:760;line-height:1.14;text-overflow:ellipsis}
.stage-count{color:#2b1744;font-size:.88rem;font-weight:780;line-height:1.1}
.stage-bottom{display:flex;min-width:0;align-items:center;gap:5px}
.stage-percent{flex:0 0 auto;padding:1px 6px;border-radius:999px;background:#efe4fb;color:var(--stage);font-size:.66rem;font-weight:800}
.sparkline{width:min(58px,30%);height:20px;flex:1 1 36px;overflow:visible;color:var(--stage)}
.sparkline path{fill:none;stroke:currentColor;stroke-linecap:round;stroke-linejoin:round;stroke-width:2}
.sparkline .forecast-line{stroke-dasharray:4 3}
.stage-window{color:#766986;font-size:.54rem;white-space:nowrap}
.accuracy-card{display:flex;min-height:82px;align-items:center;gap:8px;padding:8px 10px;border-color:#d4c0ef;background:linear-gradient(130deg,#fff 0%,#f4ebff 100%)}
.accuracy-icon{display:grid;width:38px;height:38px;flex:0 0 38px;place-items:center;color:#6530aa}
.accuracy-icon svg{width:34px;height:34px;fill:none;stroke:currentColor;stroke-linecap:round;stroke-linejoin:round;stroke-width:2}
.accuracy-copy{min-width:0}
.accuracy-value{display:block;margin-top:2px;color:#3b1d67;font-size:1.32rem;font-weight:820;line-height:1.05}
.accuracy-note{display:block;margin-top:2px;color:#70617f;font-size:.58rem;line-height:1.2}
.report-panel{overflow:hidden;margin-top:10px;border:1px solid #d9c9ef;border-radius:15px;background:linear-gradient(145deg,#fff 0%,#faf6ff 100%);box-shadow:0 4px 14px rgba(62,35,100,.05)}
.report-header{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:8px 12px 6px}
.report-heading-group{display:flex;min-width:0;align-items:center;gap:9px}
.section-pill{display:inline-flex;flex:0 0 auto;align-items:center;padding:5px 13px;border-radius:999px;background:linear-gradient(100deg,#a66ce5,#7438bb);color:#fff;font-size:.79rem;font-weight:800;line-height:1.1;white-space:nowrap}
.report-description{margin:0;color:#584a68;font-size:.66rem;font-weight:550;line-height:1.25}
.category-filters{display:flex;flex:0 0 auto;align-items:center;gap:7px;margin:0;padding:0;border:0}
.category-filters legend{float:left;margin-right:2px;color:#655777;font-size:.62rem;font-weight:700;white-space:nowrap}
.filter-options{display:flex;align-items:center;gap:5px;flex-wrap:wrap}
.category-filter{display:inline-flex;align-items:center;gap:4px;padding:3px 6px;border:1px solid #e6dcf2;border-radius:999px;background:#fff;color:#4e405f;font-size:.61rem;line-height:1.15;white-space:nowrap;cursor:pointer}
.category-filter input{width:12px;height:12px;margin:0;accent-color:#7441b8}
.stage-tone-1{--stage-color:#d4bce9;--stage-ink:#50366b}
.stage-tone-2{--stage-color:#9b61d4;--stage-ink:#fff}
.stage-tone-3{--stage-color:#642fa4;--stage-ink:#fff}
.stage-color-dot{width:9px;height:9px;flex:0 0 9px;border-radius:3px;background:var(--stage-color)}
.ranking-columns,.ranking-row{display:grid;grid-template-columns:minmax(155px,1.05fr) minmax(260px,2.1fr) minmax(340px,2.7fr);gap:11px;align-items:center}
.ranking-columns{padding:5px 13px;background:#f7f2fc;color:#665879;font-size:.61rem;font-weight:750;line-height:1.15;text-align:center}
.ranking-school-heads{display:grid;grid-template-columns:21px minmax(0,1fr);gap:7px;text-align:left}
.ranking-school-heads span:first-child{text-align:center}
.ranking-metric-heads,.ranking-metrics{display:grid;grid-template-columns:1.15fr 1fr .8fr;gap:7px;align-items:center;text-align:center}
.ranking-rows{margin:0;padding:0;list-style:none}
.ranking-row{padding:5px 13px;border-top:1px solid #eee7f5}
.ranking-row:hover{background:#fcf9ff}
.ranking-school{display:flex;min-width:0;align-items:center;gap:7px}
.school-name{min-width:0;color:#302145;font-size:.69rem;font-weight:700;line-height:1.2;white-space:normal}
.rank-number{display:inline-grid;width:21px;height:21px;place-items:center;border-radius:50%;background:#eee4f9;color:#54298b;font-weight:800}
.composite-bar{display:flex;width:100%;height:25px;overflow:hidden;border-radius:999px;background:#f0eaf6;box-shadow:inset 0 1px 2px rgba(48,25,76,.1)}
.bar-segment{display:flex;height:100%;flex:0 0 auto;align-items:center;justify-content:center;overflow:hidden;color:var(--stage-ink);background:var(--stage-color);font-size:.65rem;font-weight:850;white-space:nowrap;transition:width .18s ease}

.ranking-toolbar{display:flex;align-items:center;justify-content:flex-end;gap:10px;flex-wrap:wrap}
.snapshot-toggle{display:flex;align-items:center;gap:6px;margin:0;padding:0;border:0}
.snapshot-toggle legend{float:left;margin-right:2px;color:#655777;font-size:.62rem;font-weight:700;white-space:nowrap}
.snapshot-options{display:flex;align-items:center;gap:4px}
.snapshot-option{display:inline-flex;align-items:center;gap:4px;padding:4px 7px;border:1px solid #e2d6f0;border-radius:999px;background:#fff;color:#4e405f;font-size:.61rem;line-height:1.15;white-space:nowrap;cursor:pointer}
.snapshot-option input{width:12px;height:12px;margin:0;accent-color:#7441b8}
.snapshot-option strong{color:#35244b;font-weight:750}
.snapshot-note{margin:0;padding:0 12px 7px;color:#766985;font-size:.61rem;line-height:1.25}
.ranking-metric{min-width:0;color:#33234b;font-size:.69rem;line-height:1.1}
.ranking-metric-label{display:none}
.selected-share-cell{display:inline-flex;min-height:22px;align-items:center;justify-content:center;padding:3px 9px;border-radius:999px;background:#eee2fb;color:#4d2484;font-weight:850}
.ranking-legend{display:flex;align-items:center;justify-content:center;gap:15px;flex-wrap:wrap;padding:6px 8px 8px}
.legend-item{display:inline-flex;align-items:center;gap:5px;color:#5d506d;font-size:.6rem;font-weight:650}
.dynamics-header{display:flex;align-items:center;gap:9px;padding:8px 12px 6px}
.dynamics-divider{width:1px;height:23px;background:#cbb5e7}
.dynamics-subtitle{margin:0;color:#544465;font-size:.67rem;font-weight:650}
.dynamics-controls{display:grid;grid-template-columns:minmax(150px,1fr) minmax(260px,1.7fr) minmax(155px,1fr);gap:8px;padding:0 12px 6px}
.control-block{min-width:0}
.control-label{display:block;margin:0 0 3px;color:#655777;font-size:.59rem;font-weight:750}
.control-select{width:100%;min-height:27px;padding:3px 8px;border:1px solid #ded1ee;border-radius:999px;background:#fff;color:#39284f;font:inherit;font-size:.64rem}
.trend-filter-options{display:flex;min-height:27px;align-items:center;gap:4px;overflow-x:auto;padding:1px 0}
.trend-filter-options .category-filter{font-size:.59rem}
.chart-wrap{padding:0 8px 6px}
.trend-chart{display:block;width:100%;height:auto;min-height:170px;overflow:visible}
.trend-chart text{fill:#57496a;font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;font-size:11px}
.trend-chart .chart-grid{stroke:#e8e0f1;stroke-width:1}
.trend-chart .chart-axis{stroke:#8b789f;stroke-width:1}
.trend-chart .trend-line{fill:none;stroke:#6e32b4;stroke-linecap:round;stroke-linejoin:round;stroke-width:3}
.trend-chart .forecast-line{stroke-dasharray:8 6}
.trend-chart .trend-dot{fill:#fff;stroke:#6e32b4;stroke-width:2.5}
.trend-chart .value-label-bg{fill:#eee2fb}
.trend-chart .value-label{fill:#382050;font-size:10px;font-weight:800;text-anchor:middle}
.trend-empty{padding:30px 12px;color:#766985;text-align:center;font-size:.82rem}
.nav-tab{font-family:inherit}
button.nav-tab{border:0;cursor:pointer}
button.nav-tab:focus-visible{outline:2px solid #5b2bac;outline-offset:2px}
#overview-view[hidden],.teacher-view[hidden],#teacher-dossier[hidden]{display:none!important}
.teacher-view{display:grid;gap:8px;padding-bottom:10px}
.teacher-view-header{align-items:center}
.teacher-pickers{display:grid;width:min(100%,680px);grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}
.teacher-picker{min-width:0}
.teacher-select{width:100%;min-height:34px;padding:5px 11px;border:1px solid #d9c9ef;border-radius:10px;background:#fff;color:#302145;font:inherit;font-size:.78rem}
.teacher-select:disabled{background:#f3eff7;color:#91869b;cursor:not-allowed}
.teacher-message{margin:0;padding:0 12px 8px;color:#665879;font-size:.75rem}
.teacher-message.is-error{color:#a32148}
.teacher-profile-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;padding:0 12px 10px}
.teacher-fact{display:flex;min-width:0;min-height:70px;flex-direction:column;justify-content:center;gap:4px;padding:9px 11px;border:1px solid #e2d6f0;border-radius:12px;background:linear-gradient(130deg,#fff 0%,#f8f2ff 100%)}
.teacher-fact span{color:#716181;font-size:.65rem;font-weight:700}
.teacher-fact strong{overflow-wrap:anywhere;color:#302145;font-size:.92rem;font-weight:800;line-height:1.2}
.teacher-fact small{color:#766985;font-size:.61rem}
.teacher-surveys-card{margin:0 12px 10px;overflow:hidden;border:1px solid #e3d8f0;border-radius:12px;background:#fff}
.teacher-survey-header{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:9px 11px;background:#faf7fd}
.teacher-survey-header h3{margin:0;color:#3d2b53;font-size:.78rem;font-weight:780}
.teacher-survey-header span{color:#766985;font-size:.65rem}
.teacher-survey-table{width:100%;border-collapse:collapse;font-size:.7rem}
.teacher-survey-table[hidden]{display:none!important}
.teacher-survey-table th,.teacher-survey-table td{padding:7px 11px;border-top:1px solid #eee8f4;text-align:left}
.teacher-survey-table th{color:#766985;font-size:.62rem;font-weight:700}
.teacher-survey-table td{color:#332349}
.teacher-survey-table td:last-child,.teacher-survey-table th:last-child{text-align:center}
.teacher-survey-empty{margin:0;padding:12px;color:#766985;font-size:.7rem}
.teacher-load-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;padding:0 12px}
.teacher-load-card{min-width:0;padding:9px 8px 4px;border:1px solid #e3d8f0;border-radius:12px;background:#fff}
.teacher-load-card h3{margin:0 4px 3px;color:#3d2b53;font-size:.76rem;font-weight:760}
.teacher-burnout-card{margin:0 12px 10px}
.teacher-burnout-chart{display:block;width:100%;height:auto;overflow:visible}
.teacher-burnout-chart text{fill:#625573;font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;font-size:10px}
.teacher-burnout-chart .chart-grid{stroke:#ece5f4;stroke-width:1}
.teacher-burnout-chart .chart-axis{stroke:#9b89ad;stroke-width:1}
.teacher-burnout-chart .burnout-zone-line{fill:none;stroke:#6e32b4;stroke-linecap:round;stroke-linejoin:round;stroke-width:2.8}
.teacher-burnout-chart .burnout-zone-dot{fill:#fff;stroke:#6e32b4;stroke-width:2.3}
.teacher-load-chart{display:block;width:100%;height:auto;overflow:visible}
.teacher-load-chart text{fill:#625573;font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;font-size:10px}
.teacher-load-chart .chart-grid{stroke:#ece5f4;stroke-width:1}
.teacher-load-chart .chart-axis{stroke:#9b89ad;stroke-width:1}
.teacher-load-chart .teacher-load-area{fill:#eee3fa;opacity:.72}
.teacher-load-chart .teacher-load-line{fill:none;stroke:#6e32b4;stroke-linecap:round;stroke-linejoin:round;stroke-width:2.6}
.teacher-load-chart .forecast-line{stroke-dasharray:8 6}
.teacher-load-chart .teacher-load-dot{fill:#fff;stroke:#6e32b4;stroke-width:2}
@media(max-width:1050px){.dashboard-topbar{flex-wrap:wrap}.header-controls{width:100%;justify-content:flex-start;margin-left:0}.report-header{align-items:flex-start;flex-direction:column}.ranking-toolbar{width:100%;justify-content:space-between}.category-filters{flex-wrap:wrap}.ranking-columns,.ranking-row{grid-template-columns:minmax(140px,1.05fr) minmax(220px,2fr) minmax(300px,2.6fr);gap:7px}}
@media(max-width:900px){.kpi-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.accuracy-card{grid-column:span 2}.dynamics-controls{grid-template-columns:1fr 1fr}.control-block:nth-child(2){grid-column:1/-1;grid-row:2}.teacher-profile-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:560px){.page-shell{margin:8px auto;padding:0 9px}.dashboard-topbar{gap:7px;padding:8px}.brand{min-width:100%;}.topbar-nav{flex:1}.header-controls{flex-direction:column;align-items:stretch}.header-chip{justify-content:flex-start}.kpi-grid{grid-template-columns:1fr;gap:8px}.accuracy-card{grid-column:auto}.teacher-card,.stage-card,.accuracy-card{min-height:76px}.stage-card{padding:8px 10px}.sparkline{width:78px;flex-basis:78px}.stage-window{font-size:.62rem}.report-header{padding:8px}.report-heading-group{align-items:flex-start;flex-direction:column;gap:5px}.ranking-toolbar{width:100%;align-items:flex-start;flex-direction:column}.snapshot-toggle{align-items:flex-start;flex-direction:column}.snapshot-options{flex-wrap:wrap}.snapshot-note{padding:0 8px 7px}.category-filters{align-items:flex-start;flex-direction:column}.ranking-columns{display:none}.ranking-row{grid-template-columns:1fr;gap:6px;padding:8px 10px}.composite-bar{height:27px}.ranking-metrics{grid-template-columns:repeat(3,minmax(0,1fr));gap:4px}.ranking-metric{display:flex;flex-direction:column;align-items:center;gap:3px}.ranking-metric-label{display:block;color:#766985;font-size:.52rem;line-height:1.1;text-align:center;white-space:normal}.dynamics-header{align-items:flex-start;flex-direction:column;gap:4px;padding:9px 8px 6px}.dynamics-divider{display:none}.dynamics-controls{grid-template-columns:1fr;padding:0 8px 6px}.control-block:nth-child(2){grid-column:auto;grid-row:auto}.trend-filter-options{flex-wrap:wrap;overflow:visible}.chart-wrap{padding:0 2px 5px}.trend-chart text{font-size:9px}.teacher-view-header{align-items:stretch}.teacher-pickers{width:100%;grid-template-columns:1fr}.teacher-profile-grid,.teacher-load-grid{grid-template-columns:1fr;padding-right:8px;padding-left:8px}.teacher-load-chart text{font-size:9px}.teacher-burnout-chart text{font-size:18px}}
</style>
</head>
<body>
<main class="page-shell">
<header class="dashboard-topbar">
<a class="brand" href="/" aria-label="Мониторинг педагогов — обзор"><span class="brand-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><rect x="3" y="3" width="18" height="15" rx="3"/><path d="M7 14v-3m5 3V8m5 6V6M8 21h8m-4-3v3"/></svg></span><h1 class="brand-title">Мониторинг<br>педагогов</h1></a>
<nav class="topbar-nav" aria-label="Раздел отчёта"><button class="nav-tab is-active" id="overview-tab" type="button" aria-pressed="true">Overview</button><button class="nav-tab" id="teacher-tab" type="button" aria-pressed="false">Учитель</button></nav>
<div class="header-controls">
<div class="header-chip"><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 10h18M8 14h2m4 0h2m-8 3h2"/></svg><span>Отчёт на дату:</span><strong id="report-date">—</strong></div>
<div class="header-chip"><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 10h18M8 14h2m4 0h2m-8 3h2"/></svg><span>Прогноз до:</span><strong id="forecast-to">—</strong></div>
<div class="header-chip"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 10c0 5-8 11-8 11S4 15 4 10a8 8 0 1 1 16 0Z"/><circle cx="12" cy="10" r="2.5"/></svg><span>Локация:</span><strong id="location-label">—</strong></div>
</div>
</header>
<p id="status" class="status" role="status" aria-live="polite">Загрузка данных…</p>
<div id="overview-view">
<section class="kpi-grid" aria-label="Ключевые показатели">
<article class="kpi-card teacher-card" aria-label="Учителя и школы"><div class="teacher-icon" aria-hidden="true"><svg viewBox="0 0 32 32"><circle cx="12" cy="10" r="4"/><path d="M4 26v-2a7 7 0 0 1 7-7h2a7 7 0 0 1 7 7v2"/><path d="M22 17a6 6 0 0 1 6 6v3h-5"/><path d="M20 6.5a4 4 0 0 1 0 7"/></svg></div><div class="teacher-copy"><div class="kpi-title">Учителей</div><strong class="teacher-count" id="teacher-count">—</strong><span class="school-count" id="school-count">— школ</span></div></article>
<div id="stage-cards" hidden></div>
<article class="kpi-card accuracy-card" aria-label="Оценочная точность модели"><div class="accuracy-icon" aria-hidden="true"><svg viewBox="0 0 32 32"><rect x="3" y="8" width="24" height="16" rx="3"/><path d="M28 13h2v6h-2"/><path d="M8 12h3v8H8z"/></svg></div><div class="accuracy-copy"><div class="kpi-title">Оценочная точность модели</div><strong class="accuracy-value" id="model-accuracy">—</strong><span class="accuracy-note">Будет доступна после подключения модели</span></div></article>
</section>
<section class="report-panel ranking-panel" aria-labelledby="ranking-title">
<header class="report-header"><div class="report-heading-group"><h2 class="section-pill" id="ranking-title">Антирейтинг школ</h2><p class="report-description">Школы с наибольшей долей педагогов по стадиям выгорания</p></div><div class="ranking-toolbar"><fieldset class="snapshot-toggle" id="ranking-snapshot-toggle"><legend>Срез:</legend><div class="snapshot-options"><label class="snapshot-option"><input type="radio" name="ranking-snapshot" value="fact" checked>Факт до <strong id="ranking-fact-to">—</strong></label><label class="snapshot-option"><input type="radio" name="ranking-snapshot" value="forecast">Прогноз <strong id="ranking-forecast-from">—</strong> — <strong id="ranking-forecast-to">—</strong></label></div></fieldset><fieldset class="category-filters"><legend>Категории выгоревших:</legend><div class="filter-options" id="ranking-level-filters" data-default-unchecked-level="1"></div></fieldset></div></header>
<p class="snapshot-note" id="ranking-snapshot-note" hidden>Временный прогнозный срез: метки берутся из анкет; если новой метки нет, остаётся последний факт.</p>
<p class="snapshot-note" id="forecast-disclaimer">После отчётной даты показаны тестовые данные, не прогноз модели. Месячные значения могут сочетать фактические и тестовые данные.</p>
<div class="ranking-columns" aria-hidden="true"><div class="ranking-school-heads"><span>№</span><span>Школа</span></div><span>Доля педагогов по стадиям выгорания</span><div class="ranking-metric-heads"><span>Процент выгоревших</span><span>Количество<br>выгоревших</span><span>Всего<br>педагогов</span></div></div>
<ol class="ranking-rows" id="ranking-rows" aria-label="Пять школ с наибольшей долей выгорания"></ol>
<div class="ranking-legend" id="ranking-legend" aria-label="Легенда стадий"></div>
</section>
<section class="report-panel dynamics-panel" aria-labelledby="trend-title">
<header class="dynamics-header"><h2 class="section-pill" id="trend-title">Динамика выгорания</h2><span class="dynamics-divider" aria-hidden="true"></span><p class="dynamics-subtitle">Доля педагогов по выбранным стадиям; пунктиром — прогноз</p></header>
<div class="dynamics-controls"><div class="control-block"><label class="control-label" for="school-filter">Школа:</label><select class="control-select" id="school-filter"><option value="all">Все школы</option></select></div><fieldset class="control-block category-filters"><legend class="control-label">Тип выгорания:</legend><div class="trend-filter-options" id="trend-level-filters" data-default-unchecked-level="1"></div></fieldset><div class="control-block"><label class="control-label" for="trend-period">Период:</label><select class="control-select" id="trend-period"></select></div></div>
<div class="chart-wrap"><svg class="trend-chart" id="trend-chart" viewBox="0 0 900 250" role="img" aria-label="График доли педагогов в выбранных стадиях по месяцам"></svg></div>
</section>
</div>
<section class="teacher-view report-panel" id="teacher-view" aria-labelledby="teacher-view-title" hidden>
<header class="report-header teacher-view-header"><div class="report-heading-group"><h2 class="section-pill" id="teacher-view-title">Досье учителя</h2><p class="report-description">Стадия выгорания и недельные графики нагрузки на отчётную дату</p></div><div class="teacher-pickers"><div class="teacher-picker"><label class="control-label" for="school-select">Школа:</label><select class="teacher-select" id="school-select"><option value="">Сначала выберите школу</option></select></div><div class="teacher-picker"><label class="control-label" for="teacher-select">Учитель:</label><select class="teacher-select" id="teacher-select" disabled><option value="">Сначала выберите школу</option></select></div></div></header>
<p class="teacher-message" id="teacher-status" role="status" aria-live="polite">Сначала выберите школу, затем учителя.</p>
<div id="teacher-dossier" hidden>
<div class="teacher-profile-grid">
<article class="teacher-fact"><span>Учитель</span><strong id="teacher-name">—</strong></article>
<article class="teacher-fact"><span>Школа</span><strong id="teacher-school">—</strong></article>
<article class="teacher-fact"><span>Текущая стадия выгорания</span><strong id="teacher-current-stage">—</strong><small id="teacher-stage-date">—</small></article>
<article class="teacher-fact"><span>Последняя неделя в данных</span><strong id="teacher-latest-week">—</strong></article>
<article class="teacher-fact"><span>Часы по расписанию за последнюю неделю</span><strong id="teacher-event-hours">—</strong></article>
<article class="teacher-fact"><span>Часы активности в системе за последнюю неделю</span><strong id="teacher-activity-hours">—</strong></article>
</div>
<section class="teacher-surveys-card" aria-labelledby="teacher-surveys-title">
<header class="teacher-survey-header"><h3 id="teacher-surveys-title">Последние опросы</h3><span id="teacher-survey-count"></span></header>
<table class="teacher-survey-table" id="teacher-survey-table" hidden><thead><tr><th scope="col">Дата</th><th scope="col">Стадия выгорания</th><th scope="col">Уровень</th></tr></thead><tbody id="teacher-survey-list"></tbody></table>
<p class="teacher-survey-empty" id="teacher-surveys-empty" hidden>Опросов пока нет.</p>
</section>
<article class="teacher-load-card teacher-burnout-card"><h3>Зона выгорания по последним опросам</h3><svg class="teacher-burnout-chart" id="teacher-burnout-chart" viewBox="0 0 900 270" role="img" aria-label="Динамика зоны выгорания по опросам"></svg></article>
<div class="teacher-load-grid">
<article class="teacher-load-card"><h3>Нагрузка по расписанию, часов в неделю</h3><svg class="teacher-load-chart" id="teacher-event-hours-chart" viewBox="0 0 900 250" role="img" aria-label="Часы по расписанию по неделям"></svg></article>
<article class="teacher-load-card"><h3>Активность в системе, часов в неделю</h3><svg class="teacher-load-chart" id="teacher-activity-hours-chart" viewBox="0 0 900 250" role="img" aria-label="Часы активности в системе по неделям"></svg></article>

</div>
</div>
</section>
</main>
<script>
const fmt = new Intl.NumberFormat('ru-RU');
const teacherWord = n => {const x=n%100;if(x>=11&&x<=14)return 'учителей';switch(n%10){case 1:return 'учитель';case 2:case 3:case 4:return 'учителя';default:return 'учителей';}};
const schoolWord = n => {const x=n%100;if(x>=11&&x<=14)return 'школ';switch(n%10){case 1:return 'школа';case 2:case 3:case 4:return 'школы';default:return 'школ';}};
function formatReportDate(value){if(!value)return 'нет данных';const [y,m,d]=value.split('-').map(Number);return new Intl.DateTimeFormat('ru-RU',{day:'numeric',month:'short',year:'numeric'}).format(new Date(y,m-1,d));}
function drawSparkline(svg,values,months,forecastMonths){
    const ns='http://www.w3.org/2000/svg';
    const nums=values.map(Number);
    if(!nums.length)return;
    const max=Math.max(1,...nums);
    const points=nums.map((value,index)=>[
        nums.length===1?50:4+index*92/(nums.length-1),
        24-value/max*19,
    ]);
    const forecastSet=new Set(forecastMonths||[]);
    const forecastStart=(months||[]).findIndex(month=>forecastSet.has(month));
    const appendLine=(linePoints,isForecast)=>{
        if(linePoints.length<2)return;
        const path=document.createElementNS(ns,'path');
        path.setAttribute('d','M '+linePoints.map(([x,y])=>x.toFixed(1)+' '+y.toFixed(1)).join(' L '));
        if(isForecast)path.classList.add('forecast-line');
        svg.appendChild(path);
    };
    if(forecastStart>0){
        appendLine(points.slice(0,forecastStart),false);
        appendLine(points.slice(forecastStart-1),true);
    }else appendLine(points,forecastStart===0);
}
function makeStageCard(stage,months,forecastMonths){const card=document.createElement('article');const level=Number(stage.level);const name=String(stage.name);card.className='kpi-card stage-card stage-level-'+level;card.setAttribute('aria-label','Стадия '+name+': '+stage.count+' '+teacherWord(stage.count));const head=document.createElement('div');head.className='stage-head';const icon=document.createElement('span');icon.className='stage-icon';icon.setAttribute('aria-hidden','true');icon.innerHTML='<svg viewBox="0 0 32 24"><rect x="2" y="4" width="25" height="16" rx="3"/><path d="M29 9h2v6h-2M7 8h4v8H7z"/></svg>';const title=document.createElement('div');title.className='stage-title';title.textContent='Стадия: '+name;head.append(icon,title);const count=document.createElement('strong');count.className='stage-count';count.textContent=fmt.format(stage.count)+' '+teacherWord(stage.count);const bottom=document.createElement('div');bottom.className='stage-bottom';const percent=document.createElement('span');percent.className='stage-percent';percent.textContent=fmt.format(stage.percent)+'%';percent.title='Доля от общего числа учителей';const spark=document.createElementNS('http://www.w3.org/2000/svg','svg');spark.setAttribute('class','sparkline');spark.setAttribute('viewBox','0 0 100 28');spark.setAttribute('aria-hidden','true');drawSparkline(spark,stage.history,months,forecastMonths);const windowLabel=document.createElement('small');windowLabel.className='stage-window';windowLabel.textContent='за '+fmt.format(stage.history.length)+' мес.';bottom.append(percent,spark,windowLabel);card.append(head,count,bottom);return card;}
const svgNS = 'http://www.w3.org/2000/svg';
const percentFmt = new Intl.NumberFormat('ru-RU',{maximumFractionDigits:1});
function appendSvg(svg,tag,attributes,text){const node=document.createElementNS(svgNS,tag);for(const [key,value] of Object.entries(attributes))node.setAttribute(key,String(value));if(text!==undefined)node.textContent=text;svg.appendChild(node);return node;}
function monthLabel(value,includeYear=false){const [year,month]=value.split('-').map(Number);const short=new Intl.DateTimeFormat('ru-RU',{month:'short'}).format(new Date(year,month-1,1)).replace('.','');const label=short.charAt(0).toLocaleUpperCase('ru-RU')+short.slice(1);return includeYear?label+' '+year:label;}
function selectedLevels(containerId){return new Set([...document.querySelectorAll('#'+containerId+' input:checked')].map(input=>Number(input.value)));}
function renderLevelFilters(containerId,prefix,stages,onChange){const host=document.getElementById(containerId);const labels=stages.map(stage=>{const label=document.createElement('label');label.className='category-filter';const input=document.createElement('input');input.type='checkbox';input.value=String(stage.level);input.checked=Number(stage.level)!==Number(host.dataset.defaultUncheckedLevel||0);input.id=prefix+'-'+stage.level;input.addEventListener('change',onChange);const dot=document.createElement('span');dot.className='stage-color-dot stage-tone-'+stage.level;dot.setAttribute('aria-hidden','true');const text=document.createElement('span');text.textContent=stage.name;label.append(input,dot,text);return label;});host.replaceChildren(...labels);}
function rankingSnapshotMode(){return document.querySelector('input[name="ranking-snapshot"]:checked')?.value||'fact';}
function renderRanking(summary){const mode=rankingSnapshotMode();document.getElementById('ranking-snapshot-note').hidden=mode!=='forecast';const stages=summary.stages;const chosen=selectedLevels('ranking-level-filters');const legend=document.getElementById('ranking-legend');legend.replaceChildren(...stages.map(stage=>{const item=document.createElement('span');item.className='legend-item';const dot=document.createElement('span');dot.className='stage-color-dot stage-tone-'+stage.level;dot.setAttribute('aria-hidden','true');const text=document.createElement('span');text.textContent=stage.name;item.append(dot,text);return item;}));const list=document.getElementById('ranking-rows');const ranked=summary.schools.map(school=>{school={...school,teacher_count:mode==='fact'?school.fact_teacher_count:school.teacher_count};const snapshotStages=mode==='forecast'?(school.forecast_stages||school.stages):(school.fact_stages||school.stages);const counts=Object.fromEntries(snapshotStages.map(stage=>[stage.level,stage.count]));const selectedCount=[...chosen].reduce((total,level)=>total+(counts[level]||0),0);const allCount=stages.reduce((total,stage)=>total+(counts[stage.level]||0),0);return {...school,counts,selectedCount,allCount,share:school.teacher_count?selectedCount*100/school.teacher_count:0,overallShare:school.teacher_count?allCount*100/school.teacher_count:0};}).sort((a,b)=>b.overallShare-a.overallShare||b.allCount-a.allCount||a.name.localeCompare(b.name,'ru'));const rows=ranked.slice(0,5).map((school,index)=>{const row=document.createElement('li');row.className='ranking-row';row.dataset.schoolId=String(school.school_id);const schoolCell=document.createElement('div');schoolCell.className='ranking-school';const badge=document.createElement('span');badge.className='rank-number';badge.textContent=String(index+1);const name=document.createElement('span');name.className='school-name';name.textContent=school.name;schoolCell.append(badge,name);const bar=document.createElement('div');bar.className='composite-bar';bar.setAttribute('role','img');bar.setAttribute('aria-label','Доли по стадиям среди '+fmt.format(school.teacher_count)+' педагогов школы '+school.name);stages.forEach(stage=>{const count=school.counts[stage.level]||0;if(!count)return;const share=school.teacher_count?count*100/school.teacher_count:0;const segment=document.createElement('span');segment.className='bar-segment stage-tone-'+stage.level;segment.style.width=share+'%';segment.title=stage.name+': '+fmt.format(count)+' из '+fmt.format(school.teacher_count)+' педагогов ('+percentFmt.format(share)+'%, срез: '+(mode==='forecast'?'прогноз':'факт')+')';if(share>=4)segment.textContent=Math.round(share)+'%';bar.appendChild(segment);});const metrics=document.createElement('div');metrics.className='ranking-metrics';const addMetric=(label,value,valueClass='')=>{const metric=document.createElement('div');metric.className='ranking-metric';const caption=document.createElement('span');caption.className='ranking-metric-label';caption.textContent=label;const result=document.createElement('span');result.className='ranking-metric-value '+valueClass;result.textContent=value;metric.append(caption,result);metrics.appendChild(metric);};addMetric('Процент выгоревших',percentFmt.format(school.share)+'%','selected-share-cell');addMetric('Количество выгоревших',fmt.format(school.selectedCount),'selected-count-cell');addMetric('Педагогов',fmt.format(school.teacher_count));row.append(schoolCell,bar,metrics);return row;});list.replaceChildren(...rows);}
function updateRankingMetrics(summary){const mode=rankingSnapshotMode();const chosen=selectedLevels('ranking-level-filters');document.querySelectorAll('.ranking-row').forEach(row=>{const school=summary.schools.find(item=>item.school_id===Number(row.dataset.schoolId));if(!school)return;const snapshotStages=mode==='forecast'?(school.forecast_stages||school.stages):(school.fact_stages||school.stages);const counts=Object.fromEntries(snapshotStages.map(stage=>[stage.level,stage.count]));const selectedCount=[...chosen].reduce((total,level)=>total+(counts[level]||0),0);const teacherCount=mode==='fact'?school.fact_teacher_count:school.teacher_count;const share=teacherCount?selectedCount*100/teacherCount:0;row.querySelector('.selected-share-cell').textContent=percentFmt.format(share)+'%';row.querySelector('.selected-count-cell').textContent=fmt.format(selectedCount);});}
function drawTrend(summary){
    const chart=document.getElementById('trend-chart');
    chart.replaceChildren();
    const chosen=selectedLevels('trend-level-filters');
    if(!chosen.size){
        chart.setAttribute('aria-label','Выберите тип выгорания для построения графика');
        appendSvg(chart,'text',{x:450,y:125,'text-anchor':'middle'},'Выберите тип выгорания');
        return;
    }
    const schoolId=document.getElementById('school-filter').value;
    const period=document.getElementById('trend-period').value;
    const months=summary.trend_months;
    const firstIndex=period==='all'?0:Math.max(0,months.length-Number(period));
    const visibleMonths=months.slice(firstIndex);
    const selectedSchool=schoolId==='all'?null:summary.schools.find(school=>school.school_id===Number(schoolId));
    const denominator=selectedSchool?selectedSchool.teacher_count:summary.teacher_count;
    const forecastMonths=new Set(selectedSchool?selectedSchool.forecast_months||[]:summary.forecast_months||[]);
    const points=visibleMonths.map((month,visibleIndex)=>{
        const index=firstIndex+visibleIndex;
        let count=0;
        const monthlyCounts=selectedSchool?selectedSchool.monthly_counts:summary.monthly_counts;
        for(const level of chosen)count+=(monthlyCounts[String(level)]||[])[index]||0;
        return {month,percent:denominator?count*100/denominator:0,isForecast:forecastMonths.has(month)};
    });
    if(!points.length){appendSvg(chart,'text',{x:450,y:125,'text-anchor':'middle'},'Для выбранного периода нет данных');return;}
    const maxValue=Math.max(...points.map(point=>point.percent));
    const step=maxValue<=20?5:maxValue<=50?10:20;
    const maxY=Math.max(step,Math.ceil(maxValue*1.15/step)*step);
    const width=900,height=250,left=58,right=22,top=28,bottom=42,plotWidth=width-left-right,plotHeight=height-top-bottom;
    for(let tick=0;tick<=maxY;tick+=step){
        const y=top+plotHeight-(tick/maxY)*plotHeight;
        appendSvg(chart,'line',{x1:left,y1:y,x2:width-right,y2:y,class:'chart-grid'});
        appendSvg(chart,'text',{x:left-10,y:y+4,'text-anchor':'end'},tick+'%');
    }
    appendSvg(chart,'line',{x1:left,y1:top,x2:left,y2:height-bottom,class:'chart-axis'});
    appendSvg(chart,'line',{x1:left,y1:height-bottom,x2:width-right,y2:height-bottom,class:'chart-axis'});
    const coords=points.map((point,index)=>({
        x:points.length===1?left+plotWidth/2:left+index*plotWidth/(points.length-1),
        y:top+plotHeight-(point.percent/maxY)*plotHeight,
        point,
    }));
    const pathFor=segment=>'M '+segment.map(point=>point.x.toFixed(1)+' '+point.y.toFixed(1)).join(' L ');
    const linePath=pathFor(coords);
    const areaPath=linePath+' L '+coords[coords.length-1].x.toFixed(1)+' '+(height-bottom)+' L '+coords[0].x.toFixed(1)+' '+(height-bottom)+' Z';
    appendSvg(chart,'path',{d:areaPath,fill:'#eee3fa',opacity:'.72'});
    const forecastStart=coords.findIndex(({point})=>point.isForecast);
    if(forecastStart>0){
        const actualPoints=coords.slice(0,forecastStart);
        const forecastPoints=coords.slice(forecastStart-1);
        if(actualPoints.length>1)appendSvg(chart,'path',{d:pathFor(actualPoints),class:'trend-line'});
        if(forecastPoints.length>1)appendSvg(chart,'path',{d:pathFor(forecastPoints),class:'trend-line forecast-line'});
    }else appendSvg(chart,'path',{d:linePath,class:forecastStart===0?'trend-line forecast-line':'trend-line'});
    coords.forEach(({x,y,point})=>{
        const labelY=Math.max(5,y-25);
        appendSvg(chart,'rect',{x:x-25,y:labelY,width:50,height:18,rx:8,class:'value-label-bg'});
        appendSvg(chart,'text',{x,y:labelY+12,class:'value-label'},percentFmt.format(point.percent)+'%');
        appendSvg(chart,'circle',{cx:x,cy:y,r:4.2,class:point.isForecast?'trend-dot forecast-dot':'trend-dot'});
        appendSvg(chart,'text',{x,y:height-bottom+19,'text-anchor':'middle'},monthLabel(point.month));
    });
    const place=selectedSchool?selectedSchool.name:'все школы';
    chart.setAttribute('aria-label','Динамика доли педагогов выбранных стадий, '+place+', '+monthLabel(visibleMonths[0],true)+' — '+monthLabel(visibleMonths[visibleMonths.length-1],true));
}
function renderLowerReport(summary){const rankingUpdate=()=>updateRankingMetrics(summary);const trendUpdate=()=>drawTrend(summary);renderLevelFilters('ranking-level-filters','ranking-level',summary.stages,rankingUpdate);renderLevelFilters('trend-level-filters','trend-level',summary.stages,trendUpdate);const schoolSelect=document.getElementById('school-filter');const schoolOptions=summary.schools.map(school=>{const option=document.createElement('option');option.value=String(school.school_id);option.textContent=school.name;return option;});schoolSelect.append(...schoolOptions);const periodSelect=document.getElementById('trend-period');const months=summary.trend_months;const periodOptions=[{value:'all',label:months.length?monthLabel(months[0],true)+' — '+monthLabel(months[months.length-1],true):'Весь период'}];if(months.length>6)periodOptions.push({value:'6',label:'Последние 6 месяцев'});if(months.length>3)periodOptions.push({value:'3',label:'Последние 3 месяца'});periodSelect.replaceChildren(...periodOptions.map(item=>{const option=document.createElement('option');option.value=item.value;option.textContent=item.label;return option;}));schoolSelect.addEventListener('change',trendUpdate);periodSelect.addEventListener('change',trendUpdate);document.querySelectorAll('input[name="ranking-snapshot"]').forEach(input=>input.addEventListener('change',()=>renderRanking(summary)));renderRanking(summary);drawTrend(summary);}
async function load(){
    try{
        const response=await fetch('/api/summary');
        if(!response.ok)throw new Error('Ошибка получения данных');
        const summary=await response.json();
        document.getElementById('teacher-count').textContent=fmt.format(summary.teacher_count);
        document.getElementById('school-count').textContent=fmt.format(summary.school_count)+' '+schoolWord(summary.school_count);
        document.getElementById('report-date').textContent=formatReportDate(summary.report_date);
        document.getElementById('forecast-to').textContent=summary.forecast_to?formatReportDate(summary.forecast_to):'—';document.getElementById('ranking-fact-to').textContent=summary.ranking_fact_to?formatReportDate(summary.ranking_fact_to):'—';document.getElementById('ranking-forecast-from').textContent=summary.ranking_forecast_from?formatReportDate(summary.ranking_forecast_from):'—';document.getElementById('ranking-forecast-to').textContent=summary.ranking_forecast_to?formatReportDate(summary.ranking_forecast_to):'—';
        document.getElementById('location-label').textContent=summary.location_label;
        document.getElementById('stage-cards').replaceWith(...summary.stages.map(
            stage=>makeStageCard(stage,summary.trend_months,summary.forecast_months)
        ));
        renderLowerReport(summary);
        document.getElementById('status').textContent='';
    }catch(error){
        const status=document.getElementById('status');
        status.textContent='Не удалось загрузить данные: '+error.message;
        status.classList.add('status-error');
    }
}
let teacherDirectoryLoaded=false;
const teacherValueFmt=new Intl.NumberFormat('ru-RU',{maximumFractionDigits:1});
function setPageView(view){const isTeacher=view==='teacher';document.getElementById('overview-view').hidden=isTeacher;document.getElementById('teacher-view').hidden=!isTeacher;document.getElementById('overview-tab').classList.toggle('is-active',!isTeacher);document.getElementById('teacher-tab').classList.toggle('is-active',isTeacher);document.getElementById('overview-tab').setAttribute('aria-pressed',String(!isTeacher));document.getElementById('teacher-tab').setAttribute('aria-pressed',String(isTeacher));}
let teacherDirectoryData=null;
async function loadTeacherDirectory(){if(teacherDirectoryLoaded)return;const status=document.getElementById('teacher-status');const schoolSelect=document.getElementById('school-select');status.hidden=false;status.classList.remove('is-error');status.textContent='Загружаю список школ…';try{const response=await fetch('/api/teachers');if(!response.ok)throw new Error('Не удалось загрузить список школ и учителей');teacherDirectoryData=await response.json();const schoolOptions=[new Option('Сначала выберите школу',''),new Option('Все школы','all'),...teacherDirectoryData.schools.map(school=>new Option(school.name,school.school_id===null?'unassigned':String(school.school_id)))];schoolSelect.replaceChildren(...schoolOptions);teacherDirectoryLoaded=true;updateTeacherOptions();}catch(error){status.classList.add('is-error');status.textContent=error.message||'Ошибка загрузки школ и учителей';}}
let teacherDossierRequest=0;
function updateTeacherOptions(){teacherDossierRequest++;const schoolSelect=document.getElementById('school-select');const teacherSelect=document.getElementById('teacher-select');const status=document.getElementById('teacher-status');const dossierElement=document.getElementById('teacher-dossier');const schoolValue=schoolSelect.value;const placeholder=new Option(schoolValue?'Выберите учителя':'Сначала выберите школу','');teacherSelect.replaceChildren(placeholder);dossierElement.hidden=true;status.hidden=false;status.classList.remove('is-error');if(!schoolValue){teacherSelect.disabled=true;status.textContent='Сначала выберите школу, затем учителя.';return;}let teachers=teacherDirectoryData.teachers;if(schoolValue==='unassigned')teachers=teachers.filter(teacher=>teacher.school_id===null);else if(schoolValue!=='all')teachers=teachers.filter(teacher=>String(teacher.school_id)===schoolValue);teachers=[...teachers].sort((a,b)=>a.name.localeCompare(b.name,'ru')||a.user_id-b.user_id);const nameCounts=new Map();teachers.forEach(teacher=>nameCounts.set(teacher.name,(nameCounts.get(teacher.name)||0)+1));teachers.forEach(teacher=>{const option=new Option();option.value=String(teacher.user_id);option.textContent=nameCounts.get(teacher.name)>1?`${teacher.name} (№${teacher.user_id})`:teacher.name;teacherSelect.appendChild(option);});teacherSelect.disabled=teachers.length===0;const schoolName=schoolSelect.options[schoolSelect.selectedIndex].textContent;status.textContent=teachers.length?`${schoolValue==='all'?'По всем школам':`В школе «${schoolName}»`} — ${fmt.format(teachers.length)} ${teacherWord(teachers.length)}. Выберите учителя для досье.`:'В выбранной школе учителей не найдено.';}
function drawTeacherLoadChart(chartId,history,key,unit,forecastWeekDates){
    const chart=document.getElementById(chartId);
    chart.replaceChildren();
    const forecastWeekSet=new Set(forecastWeekDates||[]);
    if(!history.length){appendSvg(chart,'text',{x:450,y:125,'text-anchor':'middle'},'Нет данных о нагрузке');return;}
    const width=900,height=250,left=54,right=18,top=18,bottom=35,plotWidth=width-left-right,plotHeight=height-top-bottom;
    const values=history.map(row=>row[key]===null||row[key]===undefined?null:Math.max(0,Number(row[key])||0));
    const measuredValues=values.filter(value=>value!==null);
    if(!measuredValues.length){appendSvg(chart,'text',{x:450,y:125,'text-anchor':'middle'},'Нет данных о нагрузке');return;}
    const maxValue=Math.max(...measuredValues,1);
    const step=Math.pow(10,Math.floor(Math.log10(maxValue)))/2;
    const maxY=Math.max(step,Math.ceil(maxValue/step)*step);
    for(let tick=0;tick<=4;tick++){
        const value=maxY*tick/4;
        const y=top+plotHeight-(value/maxY)*plotHeight;
        appendSvg(chart,'line',{x1:left,y1:y,x2:width-right,y2:y,class:'chart-grid'});
        appendSvg(chart,'text',{x:left-8,y:y+3,'text-anchor':'end'},teacherValueFmt.format(value));
    }
    appendSvg(chart,'line',{x1:left,y1:top,x2:left,y2:top+plotHeight,class:'chart-axis'});
    appendSvg(chart,'line',{x1:left,y1:top+plotHeight,x2:width-right,y2:top+plotHeight,class:'chart-axis'});
    const points=values.map((value,index)=>({
        x:left+(history.length===1?plotWidth/2:index*plotWidth/(history.length-1)),
        y:value===null?null:top+plotHeight-(value/maxY)*plotHeight,
        value,
        row:history[index],
        isForecast:forecastWeekSet.has(history[index].week_dt),
    }));
    const segments=[];
    let segment=[];
    points.forEach(point=>{
        if(point.value===null){if(segment.length)segments.push(segment);segment=[];}
        else segment.push(point);
    });
    if(segment.length)segments.push(segment);
    segments.forEach(pointsInSegment=>{
        if(pointsInSegment.length>1){
            const linePath=pointsInSegment.map((point,index)=>`${index?'L':'M'}${point.x},${point.y}`).join(' ');
            const areaPath=`${linePath} L${pointsInSegment[pointsInSegment.length-1].x},${top+plotHeight} L${pointsInSegment[0].x},${top+plotHeight} Z`;
            appendSvg(chart,'path',{d:areaPath,class:'teacher-load-area'});
        }
        const forecastStart=pointsInSegment.findIndex(point=>point.isForecast);
        const appendLine=(linePoints,isForecast)=>{
            if(linePoints.length<2)return;
            const linePath=linePoints.map((point,index)=>`${index?'L':'M'}${point.x},${point.y}`).join(' ');
            appendSvg(chart,'path',{d:linePath,class:isForecast?'teacher-load-line forecast-line':'teacher-load-line'});
        };
        if(forecastStart>0){
            appendLine(pointsInSegment.slice(0,forecastStart),false);
            appendLine(pointsInSegment.slice(forecastStart-1),true);
        }else appendLine(pointsInSegment,forecastStart===0);
        pointsInSegment.forEach(point=>{
            const circle=appendSvg(chart,'circle',{cx:point.x,cy:point.y,r:3.2,class:'teacher-load-dot'});
            appendSvg(circle,'title',{},`${formatReportDate(point.row.week_dt)}: ${teacherValueFmt.format(point.value)} ${unit}`);
        });
    });
    points.forEach((point,index)=>{
        const month=point.row.week_dt.slice(0,7);
        if(index===0||month!==points[index-1].row.week_dt.slice(0,7)){
            const [year,monthNumber]=month.split('-').map(Number);
            const monthLabel=new Intl.DateTimeFormat('ru-RU',{month:'short'}).format(new Date(year,monthNumber-1,1));
            appendSvg(chart,'text',{x:point.x,y:height-9,'text-anchor':index===0?'start':'middle'},monthLabel);
        }
    });
}
function drawTeacherBurnoutChart(surveys,stages){
    const chart=document.getElementById('teacher-burnout-chart');
    chart.replaceChildren();
    const stageNames=new Map((stages||[]).map(stage=>[Number(stage.level),String(stage.name)]));
    const points=(surveys||[]).map(survey=>({
        date:survey.survey_dt,
        level:survey.burnout_level===null?null:Number(survey.burnout_level),
    })).filter(point=>point.date&&Number.isInteger(point.level)&&stageNames.has(point.level))
        .sort((a,b)=>a.date.localeCompare(b.date));
    if(!points.length){
        chart.setAttribute('aria-label','Нет данных о зонах выгорания в опросах');
        appendSvg(chart,'text',{x:450,y:135,'text-anchor':'middle'},'Нет данных о зонах выгорания в опросах');
        return;
    }
    const levels=[...stageNames.keys()].sort((a,b)=>a-b);
    const width=900,height=270,left=175,right=24,top=20,bottom=42;
    const plotWidth=width-left-right,plotHeight=height-top-bottom;
    const yFor=level=>top+plotHeight-(levels.indexOf(level)*plotHeight/(levels.length-1));
    levels.forEach(level=>{
        const y=yFor(level);
        appendSvg(chart,'line',{x1:left,y1:y,x2:width-right,y2:y,class:'chart-grid'});
        appendSvg(chart,'text',{x:left-10,y:y+4,'text-anchor':'end'},stageNames.get(level));
    });
    appendSvg(chart,'line',{x1:left,y1:top,x2:left,y2:height-bottom,class:'chart-axis'});
    appendSvg(chart,'line',{x1:left,y1:height-bottom,x2:width-right,y2:height-bottom,class:'chart-axis'});
    const coords=points.map((point,index)=>({
        x:points.length===1?left+plotWidth/2:left+index*plotWidth/(points.length-1),
        y:yFor(point.level),
        point,
    }));
    if(coords.length>1){
        const path=coords.map((point,index)=>`${index?'L':'M'}${point.x.toFixed(1)},${point.y.toFixed(1)}`).join(' ');
        appendSvg(chart,'path',{d:path,class:'burnout-zone-line'});
    }
    coords.forEach(({x,y,point},index)=>{
        const dot=appendSvg(chart,'circle',{cx:x,cy:y,r:4.1,class:'burnout-zone-dot'});
        appendSvg(dot,'title',{},`${formatReportDate(point.date)}: ${stageNames.get(point.level)}`);
        const [year,month,day]=point.date.split('-').map(Number);
        const dateLabel=new Intl.DateTimeFormat('ru-RU',{day:'numeric',month:'short'}).format(new Date(year,month-1,day));
        appendSvg(chart,'text',{x,y:height-10,'text-anchor':index===0?'start':index===coords.length-1?'end':'middle'},dateLabel);
    });
    chart.setAttribute('aria-label',`Зона выгорания по ${points.length} последним опросам`);
}
function renderTeacherSurveys(dossier){
    const surveys=dossier.surveys||[];
    const rows=surveys.map(survey=>{
        const row=document.createElement('tr');
        const date=document.createElement('td');
        date.textContent=formatReportDate(survey.survey_dt);
        const stage=document.createElement('td');
        stage.textContent=survey.burnout_type||'Нет данных';
        const level=document.createElement('td');
        level.textContent=survey.burnout_level===null?'—':String(survey.burnout_level);
        row.append(date,stage,level);
        return row;
    });
    document.getElementById('teacher-survey-list').replaceChildren(...rows);
    document.getElementById('teacher-survey-table').hidden=!rows.length;
    document.getElementById('teacher-surveys-empty').hidden=Boolean(rows.length);
    const shown=Math.min(rows.length,dossier.survey_count||0);
    document.getElementById('teacher-survey-count').textContent=rows.length?`Показано ${shown} из ${dossier.survey_count}`:'Нет опросов';
}
async function loadTeacherDossier(){
    const select=document.getElementById('teacher-select');
    const status=document.getElementById('teacher-status');
    const dossierElement=document.getElementById('teacher-dossier');
    const userId=select.value;
    const request=++teacherDossierRequest;
    dossierElement.hidden=true;
    if(!userId){dossierElement.hidden=true;status.hidden=false;status.classList.remove('is-error');status.textContent='Выберите учителя, чтобы открыть его досье.';return;}
    status.hidden=false;status.classList.remove('is-error');status.textContent='Загружаю досье…';
    try{
        const response=await fetch(`/api/teacher?user_id=${encodeURIComponent(userId)}`);
        if(!response.ok)throw new Error('Не удалось загрузить досье учителя');
        const dossier=await response.json();
        if(request!==teacherDossierRequest)return;
        document.getElementById('teacher-name').textContent=dossier.name||'—';
        document.getElementById('teacher-school').textContent=dossier.school||'Не указана';
        document.getElementById('teacher-current-stage').textContent=dossier.current_stage?.name||'Нет данных';
        document.getElementById('teacher-stage-date').textContent=dossier.current_stage?.survey_dt?`Последний опрос: ${formatReportDate(dossier.current_stage.survey_dt)}`:'Опрос не найден';
        document.getElementById('teacher-latest-week').textContent=dossier.latest_week?formatReportDate(dossier.latest_week):'Нет данных';
        document.getElementById('teacher-event-hours').textContent=dossier.latest_load?.event_hours==null?'—':`${teacherValueFmt.format(dossier.latest_load.event_hours)} ч`;
        document.getElementById('teacher-activity-hours').textContent=dossier.latest_load?.activity_hours==null?'—':`${teacherValueFmt.format(dossier.latest_load.activity_hours)} ч`;
        renderTeacherSurveys(dossier);
        drawTeacherBurnoutChart(dossier.surveys||[],dossier.burnout_stages||[]);
        const history=dossier.history||[];
        const forecastWeekDates=dossier.forecast_week_dates||[];
        drawTeacherLoadChart('teacher-event-hours-chart',history,'event_hours','ч',forecastWeekDates);
        drawTeacherLoadChart('teacher-activity-hours-chart',history,'activity_hours','ч',forecastWeekDates);
        dossierElement.hidden=false;
        status.hidden=true;
    }catch(error){if(request!==teacherDossierRequest)return;dossierElement.hidden=true;status.classList.add('is-error');status.textContent=error.message||'Ошибка загрузки досье учителя';}
}
document.getElementById('overview-tab').addEventListener('click',()=>setPageView('overview'));
document.getElementById('teacher-tab').addEventListener('click',()=>{setPageView('teacher');loadTeacherDirectory();});
document.getElementById('school-select').addEventListener('change',updateTeacherOptions);
document.getElementById('teacher-select').addEventListener('change',loadTeacherDossier);
load();
</script>
</body>
</html>"""


def create_app(database: str | Path, *, fact_through: str | None = None):
    if fact_through is None:
        config_path = Path(__file__).resolve().parent / "config" / "dashboard.json"
        with config_path.open(encoding="utf-8") as config_file:
            fact_through = json.load(config_file)["fact_through"]
    report_date = date.fromisoformat(fact_through).isoformat()
    db_path = Path(database).resolve()
    db_uri = f"file:{quote(db_path.as_posix(), safe='/')}?mode=ro"
    with closing(sqlite3.connect(db_uri, uri=True, timeout=30)) as connection:
        connection.row_factory = sqlite3.Row
        panel_rows = [dict(row) for row in connection.execute(
            "SELECT user_id, week_dt, event_hours, activity_hours, "
            "act_avg_participants_per_hour, burnout_level "
            "FROM teacher_burnout_panel ORDER BY week_dt DESC, user_id"
        )]
        teacher_count = connection.execute("SELECT COUNT(*) FROM user_dic").fetchone()[0]
        school_count = connection.execute("SELECT COUNT(*) FROM school_dic").fetchone()[0]
        school_names = {
            row["school_id"]: row["school_nm"]
            for row in connection.execute("SELECT school_id, school_nm FROM school_dic ORDER BY school_id")
        }
        teacher_names = {
            row["user_id"]: row["user_nm"]
            for row in connection.execute("SELECT user_id, user_nm FROM user_dic ORDER BY user_id")
        }
        teacher_school = {}
        for row in connection.execute(
            "SELECT user_id, school_id FROM user_act_schedule "
            "GROUP BY user_id, school_id ORDER BY user_id, COUNT(*) DESC, school_id"
        ):
            teacher_school.setdefault(row["user_id"], row["school_id"])
        fact_teacher_school = {}
        for row in connection.execute(
            "SELECT user_id, school_id FROM user_act_schedule WHERE date(dttm_from) <= ? "
            "GROUP BY user_id, school_id ORDER BY user_id, COUNT(*) DESC, school_id", (report_date,)
        ):
            fact_teacher_school.setdefault(row["user_id"], row["school_id"])
        # Rebuild the factual spine from observations through the inclusive cutoff;
        # a panel week can also contain later events or activity.
        fact_rows_by_teacher = {}
        for row in connection.execute("""
            WITH RECURSIVE
            sched AS (
                SELECT user_id, date(dttm_from, '-6 days', 'weekday 1') week_dt,
                    SUM((julianday(MIN(dttm_to, datetime(:cutoff, '+1 day')))-julianday(dttm_from))*24.0) hours,
                    SUM((julianday(MIN(dttm_to, datetime(:cutoff, '+1 day')))-julianday(dttm_from))*24.0*act_participants_cnt) participant_hours
                FROM user_act_schedule WHERE date(dttm_from) <= :cutoff GROUP BY user_id, week_dt
            ), act AS (
                SELECT user_id, date(activity_dttm, '-6 days', 'weekday 1') week_dt,
                    COUNT(DISTINCT strftime('%Y-%m-%d %H', activity_dttm)) hours
                FROM user_activity_log WHERE date(activity_dttm) <= :cutoff GROUP BY user_id, week_dt
            ), emp AS (
                SELECT user_id, MIN(week_dt) first_week, MAX(week_dt) last_week
                FROM (SELECT user_id, week_dt FROM sched UNION ALL SELECT user_id, week_dt FROM act)
                GROUP BY user_id
            ), spine(user_id, week_dt, last_week) AS (
                SELECT user_id, first_week, last_week FROM emp UNION ALL
                SELECT user_id, date(week_dt, '+7 days'), last_week FROM spine WHERE week_dt < last_week
            )
            SELECT sp.user_id, sp.week_dt, ROUND(COALESCE(sc.hours, 0), 2) event_hours,
                COALESCE(a.hours, 0) activity_hours,
                ROUND(CASE WHEN sc.hours > 0 THEN sc.participant_hours / sc.hours END, 2) act_avg_participants_per_hour
            FROM spine sp LEFT JOIN sched sc ON sc.user_id=sp.user_id AND sc.week_dt=sp.week_dt
                LEFT JOIN act a ON a.user_id=sp.user_id AND a.week_dt=sp.week_dt
            ORDER BY sp.week_dt DESC
        """, {"cutoff": report_date}):
            fact_rows_by_teacher.setdefault(row["user_id"], []).append(dict(row))
        burnout_type_names = {
            row["burnout_level"]: row["burnout_type"]
            for row in connection.execute(
                "SELECT burnout_level, burnout_type FROM burnout_type_dic ORDER BY burnout_level"
            )
        }
        surveys_by_teacher = {}
        for row in connection.execute(
            "SELECT survey.user_id, survey.calendar_dt, survey.burnout_type, "
            "burnout.burnout_level "
            "FROM survey_act AS survey "
            "JOIN burnout_type_dic AS burnout USING (burnout_type) "
            "ORDER BY survey.user_id, survey.calendar_dt DESC, survey.survey_id DESC"
        ):
            surveys_by_teacher.setdefault(row["user_id"], []).append({
                "survey_dt": row["calendar_dt"],
                "burnout_type": row["burnout_type"],
                "burnout_level": row["burnout_level"],
            })
        stage_names = {level: name for level, name in burnout_type_names.items() if level > 0}
        location_label = "Свердловская область"
        week_dates = sorted({row["week_dt"] for row in panel_rows})
        period_start = week_dates[0] if week_dates else None
        period_end = week_dates[-1] if week_dates else None
        forecast_week_dates = [
            week_date for week_date in week_dates if week_date > report_date
        ]
        forecast_week_set = set(forecast_week_dates)
        ranking_fact_to = max(
            (week_date for week_date in week_dates if week_date <= report_date),
            default=None,
        )
        ranking_forecast_dates = forecast_week_dates
        ranking_forecast_from = ranking_forecast_dates[0] if ranking_forecast_dates else None
        ranking_forecast_to = ranking_forecast_dates[-1] if ranking_forecast_dates else None
        ranking_forecast_set = set(ranking_forecast_dates)

        latest_by_teacher = {}
        latest_by_teacher_month = {}
        for row in panel_rows:
            teacher_id = row["user_id"]

            if row["burnout_level"] is None:
                continue
            month = row["week_dt"][:7]
            previous = latest_by_teacher.get(teacher_id)
            if previous is None or row["week_dt"] > previous["week_dt"]:
                latest_by_teacher[teacher_id] = row
            month_key = (month, teacher_id)
            previous_month = latest_by_teacher_month.get(month_key)
            if previous_month is None or row["week_dt"] > previous_month["week_dt"]:
                latest_by_teacher_month[month_key] = row

        months = sorted({month for month, _ in latest_by_teacher_month})
        forecast_months = sorted(
            month for month in months
            if all(week > report_date for week in week_dates if week.startswith(month))
        )
        forecast_month_set = set(forecast_months)
        forecast_months_by_school = {
            school_id: set() for school_id in school_names
        }
        for (month, teacher_id), row in latest_by_teacher_month.items():
            school_id = teacher_school.get(teacher_id)
            if (
                month in forecast_month_set
                and row["week_dt"] in forecast_week_set
                and school_id in forecast_months_by_school
            ):
                forecast_months_by_school[school_id].add(month)

        stage_history = {level: {month: 0 for month in months} for level in stage_names}
        for (month, _), row in latest_by_teacher_month.items():
            level = row["burnout_level"]
            if level in stage_history:
                stage_history[level][month] += 1
        current_counts = {level: 0 for level in stage_names}
        for row in latest_by_teacher.values():
            level = row["burnout_level"]
            if level in current_counts:
                current_counts[level] += 1

        school_teachers = {school_id: set() for school_id in school_names}
        for teacher_id, school_id in teacher_school.items():
            if school_id in school_teachers:
                school_teachers[school_id].add(teacher_id)
        school_current_counts = {
            school_id: {level: 0 for level in stage_names}
            for school_id in school_names
        }
        school_forecast_counts = {
            school_id: {level: 0 for level in stage_names}
            for school_id in school_names
        }
        school_fact_snapshot_counts = {
            school_id: {level: 0 for level in stage_names}
            for school_id in school_names
        }
        school_ranking_forecast_counts = {
            school_id: {level: 0 for level in stage_names}
            for school_id in school_names
        }
        school_ranking_forecast_only_counts = {
            school_id: {level: 0 for level in stage_names}
            for school_id in school_names
        }
        for teacher_id, surveys in surveys_by_teacher.items():
            latest_fact = next((survey for survey in surveys if survey["survey_dt"] <= report_date), None)
            if latest_fact is None:
                continue
            school_id = fact_teacher_school.get(teacher_id)
            level = latest_fact["burnout_level"]
            if school_id in school_fact_snapshot_counts and level in stage_names:
                school_fact_snapshot_counts[school_id][level] += 1
        for teacher_id, row in latest_by_teacher.items():
            school_id = teacher_school.get(teacher_id)
            level = row["burnout_level"]
            if school_id in school_current_counts and level in stage_names:
                school_current_counts[school_id][level] += 1
                school_ranking_forecast_counts[school_id][level] += 1
                if row["week_dt"] in ranking_forecast_set:
                    school_ranking_forecast_only_counts[school_id][level] += 1
                if row["week_dt"] in forecast_week_set:
                    school_forecast_counts[school_id][level] += 1

        school_month_counts = {
            school_id: {
                level: {month: 0 for month in months}
                for level in stage_names
            }
            for school_id in school_names
        }
        for (month, teacher_id), row in latest_by_teacher_month.items():
            school_id = teacher_school.get(teacher_id)
            level = row["burnout_level"]
            if (
                school_id in school_month_counts
                and level in stage_names
            ):
                school_month_counts[school_id][level][month] += 1

        school_summaries = []
        for school_id, school_name in school_names.items():
            staff_count = len(school_teachers[school_id])
            fact_staff_count = sum(assigned == school_id for assigned in fact_teacher_school.values())
            school_summaries.append({
                "school_id": school_id,
                "name": school_name,
                "teacher_count": staff_count,
                "fact_teacher_count": fact_staff_count,
                "stages": [
                    {
                        "level": level,
                        "name": stage_names[level],
                        "count": school_current_counts[school_id][level],
                        "forecast_count": school_forecast_counts[school_id][level],
                        "percent": round(school_current_counts[school_id][level] * 100 / staff_count) if staff_count else 0,
                    }
                    for level in sorted(stage_names)
                ],
                "fact_stages": [
                    {
                        "level": level,
                        "name": stage_names[level],
                        "count": school_fact_snapshot_counts[school_id][level],
                        "forecast_count": 0,
                        "percent": round(school_fact_snapshot_counts[school_id][level] * 100 / fact_staff_count) if fact_staff_count else 0,
                    }
                    for level in sorted(stage_names)
                ],
                "forecast_stages": [
                    {
                        "level": level,
                        "name": stage_names[level],
                        "count": school_ranking_forecast_counts[school_id][level],
                        "forecast_count": school_ranking_forecast_only_counts[school_id][level],
                        "percent": round(school_ranking_forecast_counts[school_id][level] * 100 / staff_count) if staff_count else 0,
                    }
                    for level in sorted(stage_names)
                ],
                "monthly_counts": {
                    str(level): [school_month_counts[school_id][level][month] for month in months]
                    for level in sorted(stage_names)
                },
                "forecast_months": sorted(forecast_months_by_school[school_id]),
            })

        summary = {
            "teacher_count": teacher_count,
            "school_count": school_count,
            "panel_rows": len(panel_rows),
            "labeled_rows": sum(row["burnout_level"] is not None for row in panel_rows),
            "period_start": period_start,
            "period_end": period_end,
            "report_date": report_date,
            "forecast_to": period_end,
            "forecast_week_dates": forecast_week_dates,
            "forecast_months": forecast_months,
            "ranking_fact_to": ranking_fact_to,
            "ranking_forecast_from": ranking_forecast_from,
            "ranking_forecast_to": ranking_forecast_to,
            "location_label": location_label,
            "trend_months": months,
            "monthly_counts": {
                str(level): [stage_history[level][month] for month in months]
                for level in sorted(stage_names)
            },
            "schools": school_summaries,
            "stages": [
                {
                    "level": level,
                    "name": stage_names[level],
                    "count": current_counts[level],
                    "percent": round(current_counts[level] * 100 / teacher_count) if teacher_count else 0,
                    "history": [stage_history[level][month] for month in months],
                }
                for level in sorted(stage_names)
            ],
        }
        teacher_directory = []
        teacher_details = {}
        for teacher_id, teacher_name in teacher_names.items():
            teacher_surveys = [
                survey for survey in surveys_by_teacher.get(teacher_id, [])
                if survey["survey_dt"] <= report_date
            ]
            latest_survey = teacher_surveys[0] if teacher_surveys else None
            current_level = latest_survey["burnout_level"] if latest_survey else None
            current_stage = {
                "level": current_level,
                "name": burnout_type_names.get(current_level, "Нет данных"),
                "survey_dt": latest_survey["survey_dt"] if latest_survey else None,
            }
            school_id = fact_teacher_school.get(teacher_id)
            school_name = school_names.get(school_id)
            teacher_selection = {
                "user_id": teacher_id,
                "name": teacher_name,
                "school_id": school_id,
                "school": school_name,
            }
            teacher_directory.append(teacher_selection)

            fact_rows = fact_rows_by_teacher.get(teacher_id, [])
            latest_week = fact_rows[0] if fact_rows else None
            history = [
                {
                    "week_dt": row["week_dt"],
                    "event_hours": row["event_hours"],
                    "activity_hours": row["activity_hours"],
                    "act_avg_participants_per_hour": row["act_avg_participants_per_hour"],
                }
                for row in reversed(fact_rows)
            ]
            teacher_details[teacher_id] = {
                **teacher_selection,
                "report_date": report_date,
                "forecast_to": None,
                "forecast_week_dates": [],
                "burnout_stages": [
                    {"level": level, "name": name}
                    for level, name in sorted(burnout_type_names.items())
                ],
                "current_stage": current_stage,
                "latest_week": latest_week["week_dt"] if latest_week else None,
                "latest_load": {
                    "event_hours": latest_week["event_hours"],
                    "activity_hours": latest_week["activity_hours"],
                    "act_avg_participants_per_hour": latest_week["act_avg_participants_per_hour"],
                } if latest_week else None,
                "history": history,
                "survey_count": len(teacher_surveys),
                "surveys": teacher_surveys[:10],
            }
        teacher_schools = [
            {"school_id": school_id, "name": school_name}
            for school_id, school_name in sorted(
                school_names.items(), key=lambda item: item[1].casefold()
            )
        ]
        if any(fact_teacher_school.get(teacher_id) is None for teacher_id in teacher_names):
            teacher_schools.append({"school_id": None, "name": "Школа не указана"})

    def response(start_response, status, body, content_type):
        payload = body.encode("utf-8") if isinstance(body, str) else body
        start_response(status, [
            ("Content-Type", content_type),
            ("Content-Length", str(len(payload))),
            ("Cache-Control", "no-store"),
            ("X-Content-Type-Options", "nosniff"),
        ])
        return [payload]

    def json_response(start_response, status, data):
        return response(start_response, status, json.dumps(data, ensure_ascii=False), "application/json; charset=utf-8")

    def application(environ, start_response):
        if environ.get("REQUEST_METHOD") != "GET":
            return json_response(start_response, "405 Method Not Allowed", {"error": "method not allowed"})

        path = environ.get("PATH_INFO", "/")
        if path == "/":
            return response(start_response, "200 OK", _PAGE, "text/html; charset=utf-8")

        if path == "/api/summary":
            return json_response(start_response, "200 OK", summary)

        if path == "/api/teachers":
            return json_response(
                start_response,
                "200 OK",
                {"schools": teacher_schools, "teachers": teacher_directory},
            )

        if path == "/api/teacher":
            params = parse_qs(environ.get("QUERY_STRING", ""))
            raw_user_id = params.get("user_id", [""])[0]
            try:
                user_id = int(raw_user_id)
            except ValueError:
                return json_response(start_response, "400 Bad Request", {"error": "invalid user_id"})
            if user_id not in teacher_details:
                return json_response(start_response, "404 Not Found", {"error": "teacher not found"})
            return json_response(start_response, "200 OK", teacher_details[user_id])

        if path == "/api/panel":
            params = parse_qs(environ.get("QUERY_STRING", ""))
            try:
                limit = int(params.get("limit", ["100"])[0])
            except ValueError:
                return json_response(start_response, "400 Bad Request", {"error": "invalid limit"})
            if not 1 <= limit <= 500:
                return json_response(start_response, "400 Bad Request", {"error": "limit must be between 1 and 500"})
            return json_response(start_response, "200 OK", {"limit": limit, "rows": panel_rows[:limit]})

        return json_response(start_response, "404 Not Found", {"error": "not found"})

    return application


def main():
    parser = argparse.ArgumentParser(description="Read-only burnout dashboard")
    parser.add_argument("--database", default="data/teacher_burnout.db")
    parser.add_argument("--host", default="127.0.0.1", help="defaults to loopback; do not expose without HTTPS/auth")
    parser.add_argument("--port", type=int, default=8081)
    args = parser.parse_args()
    app = create_app(args.database)
    with make_server(args.host, args.port, app) as server:
        print(f"Dashboard listening at http://{args.host}:{args.port}")
        server.serve_forever()


if __name__ == "__main__":
    main()
