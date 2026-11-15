# Time and provenance conventions

Use **US Eastern Time**, with IANA zone **America/New_York**, for displayed
report times, reporting intervals, scheduled handoffs and completion messages.
Always include the corresponding **UTC timestamp**. Resolve daylight saving
time from the event date: EST is UTC−05:00 and EDT is UTC−04:00. Do not use a
fixed five-hour subtraction throughout the year.

Example: `2026-11-15 07:01:11 EST (2026-11-15 12:01:11 UTC)`.
In summer: `2026-07-15 07:00:00 EDT (2026-07-15 11:00:00 UTC)`.

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
links the pre-edit and current hashes of the affected files. Current delivery
manifests and the dated evidence checksum list are refreshed for edited files;
archived numerical arrays, measurements and solver results remain unchanged.
