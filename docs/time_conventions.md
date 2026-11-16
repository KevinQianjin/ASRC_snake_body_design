# Time and provenance conventions

Use **US Eastern Time**, with IANA zone **America/New_York**, for displayed
report times, reporting intervals, scheduled handoffs and completion messages.
Always include the corresponding **UTC timestamp**. Resolve daylight saving
time from the event date: EST is UTC−05:00 and EDT is UTC−04:00. Do not use a
fixed five-hour subtraction throughout the year.

Example: `2026-11-15 07:01:11 EST (2026-11-15 12:01:11 UTC)`.
In summer: `2026-07-15 07:00:00 EDT (2026-07-15 11:00:00 UTC)`.

## Morning report edition

The Codex daily engineering task produces the **Morning Report**, scheduled
to start at **07:00 US Eastern Time**: **12:00 UTC in EST** or **11:00 UTC
in EDT**. The current maximum runtime is **two hours**. For an on-time start,
the deadline is **09:00 Eastern**, corresponding to **14:00 UTC in EST** or
**13:00 UTC in EDT**. Record the actual start, deadline and reporting cutoff
for each execution; the scheduled time is not evidence of actual execution.

Use `Morning Engineering Report — YYYY-MM-DD` as the title and
`reports/daily/Morning_Report_YYYY_MM_DD.md` as the report path. Label its
README entry **Morning Report**. Keep morning and evening editions separate
and retain older report links. Historical reports retain their recorded
times and execution limits; do not retroactively apply the current schedule.

## Evening report edition

The evening engineering task produces the **Evening Report**, scheduled for
**20:01 US Eastern Time**. That is **01:01 UTC on the following date in EST**
or **00:01 UTC on the following date in EDT**. Its maximum runtime is two
hours. Title and date it by the **Eastern** calendar date, even when the UTC
date has already advanced: `Evening Engineering Report — YYYY-MM-DD` at
`reports/daily/Evening_Report_YYYY_MM_DD.md`. Evening study folders use an
`evening_YYYYMMDD` suffix, so they remain distinct from same-day morning
output. Each run writes a `HANDOFF.md` in its output folder.

## Recorded timestamps

JSON records expose paired `*_et` and `*_utc` values for known instants.
Offsets are explicit in ISO 8601 values. UTC remains the canonical storage
format for database timestamps, standard document metadata and original source
hashes; readers should format these records in Eastern Time with UTC alongside.
Changing the display zone must not change the represented instant, elapsed
duration, physical simulation time or experimental results.

A calendar date without a recorded clock time is not an exact instant. Preserve
its precision. When the original calendar-day boundary is known, provide the
equivalent Eastern/UTC interval instead of inventing a midnight event. Existing
date-only report titles and dated output folders remain historical identifiers.
Unqualified incidental figure-generation metadata may be omitted when its time
zone cannot be established.

## Historical source provenance

Machine-specific source-directory prefixes are represented as `legacy-source/`
(or its platform path separator) while retaining project-relative suffixes.
These are provenance labels, not executable paths or a claim that the original
source files lived in the current checkout.

Historical source hashes still identify the files used at execution time.
Later presentation-only changes to timestamps or path labels do not constitute
a simulation rerun. The [metadata migration record](time_metadata_migration.json)
links the pre-edit and post-edit hashes at the time of that migration. Current delivery
manifests and the dated evidence checksum list are refreshed for edited files;
archived numerical arrays, measurements and solver results remain unchanged.
