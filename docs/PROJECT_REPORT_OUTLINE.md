# AEROVISTA Aviation Analytics — Academic Project Report Outline

> **Purpose:** A practical writing and evidence plan for the system currently implemented in this repository. This outline separates verified implementation from recommendations and future work. Replace prompts in brackets with team-specific facts and evidence; do not present proposals as completed features.

## Evidence status and project scope

- **Current dataset scope:** BTS-derived data for Southwest Airlines (`WN`), calendar year 2024. The selected-carrier metadata and local aggregate CSVs are under `data/aggregated_WN_2024/`.
- **Verified warehouse:** MySQL 8 database `aviation_dw`; star-schema facts, dimensions, serving views, ETL run/load logs, and DQ checks are defined in `sql/01_create_schema.sql`.
- **Data grains:** operations and capacity are month × carrier × route; turnaround is month × carrier × airport × daypart; DB1B fares are quarter-level at segment, market, or fare-class grains. There are no flight-level fact tables in the current warehouse.
- **Current ETL:** `etl/etl_pipeline.py` loads prepared aggregate CSVs into dimensions/facts and has destructive full-refresh/schema-init options. It is not called by the website. Do not execute it as part of a dashboard demo.
- **Current website:** six Streamlit pages: Overview, Flight Operations, Turnaround Optimization, OLAP Explorer, Reports & Data Quality, and Revenue & Capacity. The app reads MySQL through `services/database.py` and uses parameterized SELECT queries; local DB credentials belong in the ignored `.env` file.
- **Observed validation at the last implementation check:** Python syntax passed; all six page scripts passed Streamlit AppTest without exceptions; the latest observed ETL run was successful with 129 PASS and 0 FAIL DQ checks. Re-run checks before final submission and capture fresh evidence rather than treating these time-sensitive values as permanent results.
- **Known source/documentation gap:** a separate `data_dictionary.xlsx` was not present when this repository was audited. The schema comments, ETL transforms, source CSV headers, and mart definitions are available, but the team should locate/attach the official project data dictionary if required by the course.

---

# Suggested academic report structure

## Front matter

- Cover page: `[institution]`, `[course]`, project title, supervisor, team members, submission date.
- Acknowledgements (optional; do not invent support received).
- Table of contents, list of figures, list of tables, abbreviations.
- Suggested abbreviations: DSS, BI, OLAP, BTS, OTP, NAS, ASM, RPM, PLF, RASK, DB1B, ETL, DQ.

## Executive summary

Write this last. In one page, state:

1. The airline-management problem and target users.
2. The BTS sources and the 2024 WN scope actually implemented.
3. The warehouse/ETL/Streamlit solution actually present.
4. The main observed findings supported by saved SQL/chart evidence (insert measured values only after re-running queries).
5. The strongest limitations: monthly/quarterly aggregates, DB1B sample-based revenue estimate, no individual-flight records, and turnaround inferred by ETL.
6. The management recommendations and which impacts are measured versus hypothetical.

## Chapter 1 — Introduction and objectives

### 1.1 Context and problem statement
- Explain airline operations and revenue decisions that require integrated evidence.
- Identify the intended users: operations managers, revenue/capacity planners, analysts, and data administrators.
- State the business questions in Part A.3 below.

### 1.2 Objectives and scope
- Objective: build a read-only DSS/BI prototype over the existing WN 2024 warehouse.
- In-scope: monthly flight performance, delay-cause aggregates, monthly turnaround aggregates, quarterly T-100/DB1B marts, route/carrier drill-down, DQ/report views.
- Out-of-scope in the current build: individual-flight search/timestamps, weekday-by-daypart delay analysis, raw turnaround-distribution plots, ticket advance-purchase analysis, write-back, ETL execution from the web app, causal impact evaluation.

### 1.3 Method and deliverables
- Describe repository/schema inspection, read-only MySQL verification, ETL/source review, KPI implementation, page tests, and evidence collection.
- List deliverables that exist: Python source, SQL DDL/query files, CSV aggregates and answers, dashboard, requirements, README, and this report outline.

## Chapter 2 — Theoretical background

### 2.1 Decision Support Systems
- Define a DSS and explain its data, model/analytics, and user-interface roles in this prototype.
- Explain decision support versus automated decision-making: recommendations are for management review, not automatic operational control.

### 2.2 Business Intelligence and data warehousing
- Discuss integrated sources, historical analysis, semantic/serving marts, additive measures, and dimensional analysis.
- Explain why the UI uses warehouse aggregation rather than loading large raw fact data into Pandas.

### 2.3 OLAP and analytics
- Explain slice/dice, aggregation, and the available drill-down path: carrier summary → route aggregate.
- Clearly state that flight-level drill-down is **not implemented** because no flight-grain warehouse fact is present.

### 2.4 Airline performance concepts
- Define OTP, cancellation rate, PLF, ASM, RPM, RASK, yield, and turnaround with the project’s units and denominators (Chapter 5).
- Explain BTS’s five delay categories and that reported cause minutes are not a complete causal model of all operational disruption.

## Chapter 3 — Data collection and preprocessing

### 3.1 Data sources
Document source name, provider, time range, selection, files, extraction date, and license/terms based on evidence actually collected:

| Source | Current use in repository | Evidence to add |
|---|---|---|
| BTS Reporting Carrier On-Time Performance | Monthly operational aggregates: scheduled/completed/cancelled/diverted flights, delay counts/minutes, five BTS cause-minute fields; turnaround inputs are derived upstream | BTS query/download parameters, original filenames, extraction date, sample source headers |
| BTS T-100 Domestic Segment | Monthly carrier-route seats, passengers, departures, ASM, RPM and related capacity measures | Query/download parameters, service class/filter decisions, units |
| BTS DB1B | Quarterly sampled ticket/segment/market/fare-class values used for estimated revenue, RASK/yield and fare analyses | DB1B files/quarters, sample expansion/allocation rules, quality filters |

Do not claim raw BTS feeds are live-connected to the web app. The dashboard reads the existing MySQL warehouse; the ETL consumes local prepared CSVs.

### 3.2 Collection and preprocessing workflow
- Draw the observed flow: BTS sources → source download/cleaning and aggregate CSVs → ETL into MySQL → serving marts → read-only Streamlit dashboard.
- Describe only transformations verified in `etl/etl_pipeline.py`, source manifests, source CSVs, and SQL. Attach exact records/commands as evidence.
- Explain carrier scope WN and calendar-year scope 2024. Explain filtering, duplicate handling, NULL policy, units, and any DB1B sample-expansion/allocation rules from the ETL implementation.
- Describe `manifest_clean_files.csv` and note whether referenced original files are included or absent from the submitted package.

### 3.3 Data dictionary and limitations
- Build a team-verified dictionary table: field, definition, source, type/unit, grain, NULL/zero semantics, transformation, and dashboard use.
- Use DDL comments, ETL mappings, and source headers as evidence. Attach the course data dictionary if obtained.
- State explicitly: DB1B is a 10% ticket sample; estimated passenger revenue is not actual total airline revenue; DB1B has no purchase lead-time field; BTS reports five cause groups only; turnaround is inferred from tail number and adjacent flight times by the upstream ETL; and the warehouse currently lacks individual flight timestamps.

## Chapter 4 — Technical design and implementation

### 4.1 Requirements and architecture
- Describe users, read-only dashboard behavior, filter/chart requirements, empty/error handling, and reporting/export requirements.
- Include an architecture diagram showing data-source/ETL, MySQL warehouse, SQLAlchemy/PyMySQL data access, analytics services, shared components, and Streamlit pages.
- Distinguish the existing ETL operator workflow from the dashboard request path. The website must not run ETL or mutate warehouse tables.

### 4.2 Data Warehouse design
- Present the actual schema from `sql/01_create_schema.sql`, not a proposed schema.
- Explain dimensions including date/month/quarter, carrier, airport, route, aircraft, daypart, delay cause, and cancel reason.
- Explain facts and measured grains:
  - `fact_ontime_route_month`: month × carrier × route.
  - `fact_capacity_route_month`: month × carrier × route.
  - `fact_turnaround_airport_daypart_month`: month × carrier × airport × daypart.
  - `fact_fare_segment_quarter`: quarter × ticketing carrier × operating carrier × segment.
  - `fact_fare_market_quarter`: quarter × ticketing carrier × O&D × ticket flags.
  - `fact_fare_class_quarter`: quarter × operating carrier × fare class.
- Include the actual PK, unique-grain, and FK diagram. Explain why facts with different grains must not be joined and re-aggregated in ways that multiply measures.

### 4.3 ETL and serving marts
- Describe the extract/transform/load and validation stages from `etl/etl_pipeline.py` and `etl/verify_consistency.py`.
- Call out that ETL full refresh and schema initialization are destructive operator options; they are not dashboard features and were not invoked during dashboard testing.
- Describe actual views: `mart_carrier_month`, `mart_route_month`, `mart_carrier_quarter_rask`, `mart_route_quarter_rask`, `mart_delay_cause_month`, `mart_turnaround_daypart_month`, `mart_turnaround_airport_month`, and `mart_fare_market_quarter`.
- Include view SQL snippets and grain/coverage rationale. Identify answer CSVs as existing ETL outputs/reference results, not dashboard-generated live predictions.

### 4.4 Streamlit implementation
- Summarize actual modules: `app.py`; shared header/sidebar/styles; `services/database.py`; `services/analytics.py`; and the six page scripts.
- Describe image-based navigation and identify the actual turnaround image filename (`assets/turn-down.png`; the requested `turnover.png` was not present).
- Describe parameterized read-only SELECT access, cache TTLs, MySQL connection pooling, missing-configuration/database error states, and use of `.env` ignored by Git.
- Include screenshots of the connected UI and representative page layouts.

### 4.5 KPI definitions

| KPI | Implemented calculation | Unit / caveat |
|---|---|---|
| OTP | `1 − arr_del15_count / flights_completed` | Percent; completed-flight denominator, not scheduled flights |
| Cancellation rate | `flights_cancelled / flights_scheduled` | Percent |
| PLF | `passengers / seats` | Percent; sum numerator and denominator before division |
| ASM | T-100 aggregate | Available seat-miles; seat-miles |
| RPM | T-100 aggregate | Revenue passenger-miles; passenger-miles |
| RASK | Estimated DB1B passenger revenue / ASM | Displayed in cents per ASM; only for qualifying source coverage |
| Yield | DB1B segment sample revenue / DB1B passenger-miles | Displayed in cents per RPM; use only the correct DB1B sample measures |
| Average turnaround | `turn_actual_sum_min / turn_n` | Minutes per valid inferred turnaround event |
| Over-schedule turnaround rate | `turn_over_sched_n / turn_n` | Percent of valid events |
| Delay-cause contribution | Cause minutes / total minutes in the five BTS cause groups | Percent of reported BTS cause minutes; not all possible delay mechanisms |

Explain NULL/zero-denominator handling and N/A states. For all annual/route rates, show that additive counts/minutes are aggregated first and ratios are calculated afterward.

### 4.6 Implemented dashboard interactions
- Overview: year selection and data-backed KPI/trend/route/cause summaries.
- Flight Operations: year/month/carrier/origin/destination/daypart filters; cause-category selection and metric toggle; date range, analysis dimension, carrier/airport filters, and OTP/average-delay selection for the performance explorer; filter reset.
- Turnaround Optimization: month/year scope; reduction slider; measured current versus hypothetical target chart; scenario time saving = assumed per-event reduction × observed valid event count; separate existing ETL reference scenario when its CSV is present.
- OLAP Explorer: route search, route selection, route-level details, and return-to-carrier breadcrumb. No individual flight rows.
- Reports & Data Quality: coverage, row counts, ETL/DQ review, metadata, and CSV downloads. No write operation or ETL trigger.
- Revenue & Capacity: quarterly/route quarter selection, coverage gating, route ranking, fare-class mix.

## Chapter 5 — Data quality, testing, and results

### 5.1 Data-quality rules
- Explain row-count, measure parity, FK/orphan, grain-duplicate, cross-source coverage, mart parity, and answer validation rules from `etl/verify_consistency.py` and the DQ tables.
- Re-run the project’s verification script only as an explicitly approved ETL/data-operations workflow; do not run it as part of the Streamlit app. Capture its output and resulting report from the team’s authorized process.
- Record latest ETL run ID/status and check counts with a timestamp. Do not reuse stale success figures without rechecking.

### 5.2 Software testing
- Record Python/Streamlit versions, dependency versions, syntax validation, page-level AppTest result, interactive widget tests, and DB read-only query checks.
- Add test cases for: missing credentials, MySQL unavailable, empty year, zero denominators, no coverage, month/airport/carrier filters, empty cause selection, OLAP navigation, and CSV download.
- State test environment and distinguish a successful page render from formal functional, security, or load testing.

### 5.3 Results and visual evidence
- Insert actual result values only after an authorized fresh query. Provide query text and report timestamp alongside values.
- Capture figures/screenshots at readable resolution with filters and data scope visible.
- Discuss findings, not just screenshots: largest delay-cause contributor, best/worst OTP route/month if supported, coverage gaps, turnaround performance, and route-level revenue/capacity patterns.

## Chapter 6 — Management questions and decision support

### 6.1 Which delay causes contribute most to total delay minutes?
- Use the interactive Flight Delay Analysis with carrier/month and selected BTS categories.
- Report cause minutes and contribution share from the same selected scope.
- Explain that Carrier, Weather, NAS, Security, and Late aircraft are the only reported BTS groups. Do not split Carrier into maintenance/fuel/crew/loading measurements unless an independent source supports it.
- Recommendation template: finding → operational owner → action to test → metric to monitor → evidence/uncertainty.

### 6.2 What operational improvements could reduce turnaround time by 15%?
- Use the measured average, valid-event count, airport/daypart aggregates, late-inbound association, ETL reference scenario, and user-adjustable simulator.
- Present the slider result as a **hypothetical arithmetic scenario**. Total assumed turnaround minutes saved are not recovered flight-delay minutes and are not causal evidence.
- Propose operational pilots only as recommendations, such as reviewing high-excess airports/dayparts, coordinating inbound disruption response, and monitoring over-schedule share.
- Expected impact must be labelled a target/hypothesis until an intervention study or before/after design validates it.

### 6.3 How can PLF and revenue performance be improved?
- Use route-quarter records with matching T-100/DB1B coverage, PLF, RASK, yield, estimated revenue and fare-class mix.
- Explain limitations: DB1B 10% sample, estimated revenue, quarterly grain, coverage restrictions, and no booking-purchase lead-time field.
- Recommend investigating route capacity/seasonality, load factor, and revenue mix. Do not claim a pricing or capacity intervention will improve profit without cost and demand evidence.

### 6.4 Evidence-based recommendations
For every recommendation, provide: observed metric and query scope; business interpretation; proposed action; expected direction (not invented magnitude); accountable role; success metric; monitoring period; confounders/limitations; and a plan to evaluate results.

## Chapter 7 — Conclusion, limitations, and future work

### 7.1 Conclusion
Summarize only delivered features and verified evidence. Map each objective to a dashboard page, query, and test.

### 7.2 Current limitations
- WN/2024 is a narrow carrier/time scope.
- Warehouse is monthly/quarterly aggregate; no flight-level fact/timestamps, daily/weekday breakdown, or raw turnaround events.
- DB1B is sampled and revenue is estimated.
- No ticket purchase date; no advance-purchase analysis.
- Turnaround is inferred upstream and aggregate associations are not causal.
- `data_dictionary.xlsx` was not found in the repository audit; confirm official definitions and units with course materials.
- The current web UI has no authenticated user roles or write-back; production security/load testing evidence is not yet documented.

### 7.3 Future work (proposals, not implemented)
- Add an approved flight-grain source/fact for individual-flight drill-down and weekday/daypart analysis.
- Add raw turnaround-event distributions if privacy and source availability permit.
- Add more carriers/years and scheduled service/date dimensions, then validate comparability.
- Add role-based access, secret-management deployment, automated regression tests, monitoring, and controlled performance tests.
- Assess turnaround interventions using an approved experimental or quasi-experimental design.
- Acquire the authoritative data dictionary and document source licenses/refresh cadence.

## References

Create a bibliography from sources the team actually consulted. At minimum, verify and cite:

1. Official BTS On-Time Performance documentation and field definitions.
2. Official BTS T-100 documentation and field/unit definitions.
3. Official BTS DB1B documentation, sample design, and limitations.
4. Course materials for DSS, BI, dimensional modeling, and OLAP.
5. Streamlit, SQLAlchemy, MySQL, and Python documentation for technologies actually used.
6. This project’s SQL DDL, ETL source, consistency-check source, and data dictionary (if obtained) as primary project artifacts.

Record access dates and exact titles/URLs. Do not cite this outline as evidence of external facts and do not invent publication details.

---

# Team task allocation table

Fill names and actual contribution evidence after confirming with the team. The assignments below are **suggested roles only**, not a record of work already completed.

| Work package | Suggested accountable role | Team member(s) | Evidence of actual contribution |
|---|---|---|---|
| BTS collection and source log | Data acquisition lead | `[name(s)]` | `[download/query logs, source manifests]` |
| Cleaning, aggregation, and dictionary | Data preparation lead | `[name(s)]` | `[scripts, rules, reviewed dictionary]` |
| Warehouse schema and ETL | Data warehouse lead | `[name(s)]` | `[DDL/ETL commits, test evidence]` |
| KPI definitions and analytics | BI/analytics lead | `[name(s)]` | `[SQL, formula review, parity results]` |
| Streamlit UI and interaction | Dashboard lead | `[name(s)]` | `[page implementation, screenshots, tests]` |
| DQ, documentation, and presentation | QA/report lead | `[name(s)]` | `[test logs, report sections, rehearsal notes]` |

## Suggested presentation storyline (Part B/C)

1. **Problem:** managers need consistent operational and commercial evidence across BTS sources.
2. **Data reality:** sources, WN/2024 scope, aggregate grains, and limitations.
3. **Architecture:** prepared source data → ETL → star schema/marts → read-only dashboard.
4. **Trust:** KPI definitions, coverage gating, DQ evidence, and no-write safety boundary.
5. **Decision 1:** identify largest reported delay-cause contribution and explain scope.
6. **Decision 2:** inspect turnaround by airport/daypart and demonstrate the explicitly hypothetical reduction simulator.
7. **Decision 3:** examine PLF, estimated revenue, RASK/yield and route coverage.
8. **Conclusion:** recommendations, limitations, and future evidence needed.

## Recommended live demonstration sequence

1. Show the connected database status, selected carrier/year, and Overview KPI cards.
2. Open **Flight Operations**. Set a carrier and month; show the native delay-cause chart, contribution percentage, and category filter.
3. In **Flight performance explorer**, select a date range, analysis dimension, airport filter, and metric. Explain month-level resolution.
4. Open **Turnaround Optimization**. Show measured average/event count, change the reduction slider, compare current and scenario target, and state the time-savings assumption aloud.
5. Open **Revenue & Capacity**. Show quarter coverage before interpreting estimated revenue, RASK, yield, or route comparisons.
6. Open **OLAP Explorer**. Search/select a route, inspect the aggregate row, and show the back navigation. Explicitly note why flight-level details are unavailable.
7. Open **Reports & Data Quality**. Show the latest ETL status, check counts, coverage, and a real CSV export.
8. End by showing the read-only dashboard boundary and the documented limitations.

## Suggested presenter allocation

| Presenter | Suggested segment | Assign actual teammate |
|---|---|---|
| Presenter 1 | Problem, objectives, BTS sources and preprocessing | `[name]` |
| Presenter 2 | Warehouse, grains, ETL and DQ | `[name]` |
| Presenter 3 | Operations, delay analysis and turnaround simulator | `[name]` |
| Presenter 4 | Revenue/capacity, OLAP, recommendations and limitations | `[name]` |

Adjust for the actual team size and preparation; do not imply a member implemented work they did not perform.

## Likely lecturer questions to prepare for

1. Why is OTP based on completed flights, while cancellation rate uses scheduled flights?
2. Why can’t the OLAP page show flight numbers, scheduled/actual times, or tail numbers?
3. How does joining facts at different grains risk double-counting, and how does the design avoid it?
4. What do ASM, RPM, PLF, RASK, and yield mean, and what units are displayed?
5. Why is DB1B revenue estimated rather than actual airline revenue? What does the 10% sample mean in this ETL?
6. What coverage conditions are required before showing RASK? What is displayed when coverage is missing?
7. How are delay-cause contribution shares calculated, and why are there only five groups?
8. What exactly does the turnaround slider calculate? Why does it not prove a 15% reduction in total delay?
9. How is turnaround derived, and what risks arise from using adjacent-flight/tail-number data?
10. Which ETL and DQ checks were run, on what date/run, and where is the reproducible output?
11. Does the dashboard make any database changes? How are credentials configured and protected?
12. Which recommendations are measured findings versus hypotheses, and what study would validate the hypotheses?
13. Where is the authoritative data dictionary, source documentation, extraction log, and evidence of each member’s contribution?
14. Which tests were actually completed, and which deployment/security/load tests remain future work?

## Evidence checklist for the final report and defense

- [ ] Screenshot of each of the six pages with readable filters, data scope, and English labels.
- [ ] Screenshot of image navigation showing the active-page treatment and all six supplied icons.
- [ ] Screenshots of the delay cause chart with selected carrier/month/categories and its contribution table.
- [ ] Screenshots of performance explorer for at least two dimensions and filter states.
- [ ] Screenshot of simulator showing measured current values, selected reduction, scenario target, and explicit assumption text.
- [ ] Screenshot of revenue page showing quarter coverage and the labels “estimated”/DB1B sample caveat.
- [ ] Screenshot of OLAP route drill-down and its limitation message.
- [ ] Screenshot of DQ page with run ID/status, check counts, source coverage, and export action.
- [ ] Copy of schema/ERD and SQL excerpts defining grains, keys, and KPI views.
- [ ] Saved read-only SQL query text and timestamp for each result reported in Chapter 6.
- [ ] Fresh output from the authorized consistency-check process, including run identifier and generated DQ report; no stale figures.
- [ ] AppTest/syntax-check command output, Python and Streamlit version, and test case outcomes.
- [ ] BTS source/download query details, original file list, extraction date, transformation scripts/logs, and official data dictionary.
- [ ] Git history or other verified contribution records and team-approved allocation table.
- [ ] References with verified URLs/titles/access dates.
