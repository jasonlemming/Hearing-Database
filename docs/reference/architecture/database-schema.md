# Database Schema Reference

Complete reference for the Congressional Hearing Database schema (20 tables).

## Table of Contents

1. [Overview](#overview)
2. [Entity-Relationship Diagram](#entity-relationship-diagram)
3. [Core Entity Tables](#core-entity-tables)
4. [Relationship Tables](#relationship-tables)
5. [Document Tables](#document-tables)
6. [System & Management Tables](#system--management-tables)
7. [Indexes & Performance](#indexes--performance)
8. [Common Queries](#common-queries)
9. [Data Integrity Rules](#data-integrity-rules)

---

## Overview

The database consists of **20 tables** organized into logical domains:

| Domain | Tables | Purpose |
|--------|--------|---------|
| **Core Entities** | 5 tables | committees, members, hearings, bills, witnesses |
| **Relationships** | 7 tables | committee_memberships, hearing_committees, hearing_bills, witness_appearances, committee_jurisdictions, member_leadership_positions, policy_areas |
| **Documents** | 3 tables | hearing_transcripts, witness_documents, supporting_documents |
| **System** | 5 tables | sync_tracking, import_errors, scheduled_tasks, update_logs, schedule_execution_logs |

**Total Records** (119th Congress):
- 1,168+ hearings
- 213 committees
- Witnesses, members, bills, documents (thousands)

**Database Engine**: SQLite 3.8+
**Foreign Keys**: Enabled (`PRAGMA foreign_keys = ON`)

---

## Entity-Relationship Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         CORE ENTITIES                                   │
└─────────────────────────────────────────────────────────────────────────┘

       ┌──────────────┐              ┌──────────────┐
       │  committees  │              │   members    │
       │              │              │              │
       │ committee_id │◀──┐          │  member_id   │◀──┐
       │ system_code  │   │          │ bioguide_id  │   │
       │ name         │   │          │ full_name    │   │
       │ chamber      │   │          │ party        │   │
       │ type         │   │          │ state        │   │
       └──────┬───────┘   │          └──────┬───────┘   │
              │           │                 │           │
              │ parent    │                 │           │
              │           │                 │           │
              ▼           │                 ▼           │
        (subcommittees)   │         ┌──────────────┐   │
                          │         │   member_    │   │
                          │         │  leadership_ │   │
                          │         │  positions   │   │
                          │         └──────────────┘   │
                          │                            │
                          │                            │
       ┌──────────────────┴──────────┐                 │
       │  committee_memberships      │                 │
       │                             │                 │
       │  committee_id (FK) ─────────┘                 │
       │  member_id (FK) ──────────────────────────────┘
       │  role                       │
       │  congress                   │
       └─────────────────────────────┘


       ┌──────────────┐              ┌──────────────┐
       │   hearings   │              │    bills     │
       │              │              │              │
       │  hearing_id  │              │   bill_id    │
       │  event_id    │              │  congress    │
       │  title       │              │  bill_type   │
       │  chamber     │              │  bill_number │
       │  hearing_date│              └──────────────┘
       │  video_url   │                      ▲
       │  youtube_id  │                      │
       └──────┬───────┘                      │
              │                              │
              │                              │
       ┌──────┴───────────────────┐          │
       │ hearing_committees       │          │
       │                          │          │
       │ hearing_id (FK) ─────────┘          │
       │ committee_id (FK) ───────┐          │
       │ is_primary               │          │
       └──────────────────────────┘          │
              │                              │
              └──────────────┐               │
                             │               │
       ┌─────────────────────┴────┐          │
       │  hearing_bills           │          │
       │                          │          │
       │  hearing_id (FK)         │          │
       │  bill_id (FK) ───────────┴──────────┘
       │  relationship_type       │
       └──────────────────────────┘


       ┌──────────────┐              ┌──────────────────┐
       │  witnesses   │              │ witness_         │
       │              │              │ appearances      │
       │  witness_id  │◀─────────────│                  │
       │  full_name   │              │ appearance_id    │
       │  organization│              │ witness_id (FK)  │
       └──────────────┘              │ hearing_id (FK) ─┘
                                     │ position         │
                                     │ witness_type     │
                                     └──────────────────┘
                                              │
                                              │
                                     ┌────────┴──────────┐
                                     │ witness_documents │
                                     │                   │
                                     │ appearance_id (FK)│
                                     │ document_type     │
                                     │ title             │
                                     │ document_url      │
                                     └───────────────────┘


┌─────────────────────────────────────────────────────────────────────────┐
│                         DOCUMENT TABLES                                 │
└─────────────────────────────────────────────────────────────────────────┘

       ┌──────────────────┐          ┌──────────────────┐
       │ hearing_         │          │ supporting_      │
       │ transcripts      │          │ documents        │
       │                  │          │                  │
       │ hearing_id (FK) ─┘          │ hearing_id (FK) ─┘
       │ jacket_number    │          │ document_type    │
       │ title            │          │ title            │
       │ pdf_url          │          │ description      │
       │ html_url         │          │ document_url     │
       └──────────────────┘          └──────────────────┘


┌─────────────────────────────────────────────────────────────────────────┐
│                    SYSTEM & MANAGEMENT TABLES                           │
└─────────────────────────────────────────────────────────────────────────┘

       ┌──────────────────┐          ┌──────────────────┐
       │ sync_tracking    │          │ import_errors    │
       │                  │          │                  │
       │ entity_type      │          │ entity_type      │
       │ last_sync_time   │          │ error_type       │
       │ records_processed│          │ error_message    │
       │ status           │          │ severity         │
       └──────────────────┘          └──────────────────┘

       ┌──────────────────┐          ┌──────────────────┐
       │ scheduled_tasks  │          │ update_logs      │
       │                  │          │                  │
       │ task_id          │◀─────────│ schedule_id (FK) │
       │ schedule_cron    │          │ update_date      │
       │ lookback_days    │          │ hearings_updated │
       │ components       │          │ duration_seconds │
       │ is_active        │          │ success          │
       └──────────────────┘          └──────────────────┘
              │                              │
              │                              │
              └──────────────┬───────────────┘
                             │
                    ┌────────┴──────────────┐
                    │ schedule_execution_   │
                    │ logs                  │
                    │                       │
                    │ schedule_id (FK)      │
                    │ log_id (FK)           │
                    │ execution_time        │
                    │ success               │
                    └───────────────────────┘
```

---

## Core Entity Tables

### 1. committees

**Purpose**: Stores all congressional committees and subcommittees with hierarchical relationships.

**Columns**:

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `committee_id` | INTEGER | PRIMARY KEY | Auto-incrementing identifier |
| `system_code` | TEXT | NOT NULL, UNIQUE | API unique identifier (e.g., "hsif00") |
| `name` | TEXT | NOT NULL | Full committee name |
| `chamber` | TEXT | NOT NULL | House, Senate, Joint, NoChamber |
| `type` | TEXT | NOT NULL | Standing, Select, Special, Joint, Subcommittee, etc. |
| `parent_committee_id` | INTEGER | FOREIGN KEY | NULL for full committees, FK for subcommittees |
| `is_current` | BOOLEAN | NOT NULL, DEFAULT 1 | Active status |
| `url` | TEXT | | API reference URL |
| `congress` | INTEGER | NOT NULL | Congress number (e.g., 119) |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Record creation time |
| `updated_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Last update time |

**Constraints**:
- `chamber IN ('House', 'Senate', 'Joint', 'NoChamber')`
- `type IN ('Standing', 'Select', 'Special', 'Joint', 'Task Force', 'Other', 'Subcommittee', 'Commission or Caucus')`
- Self-referencing FK: `parent_committee_id` → `committee_id`

**Indexes**:
- `idx_committees_chamber` ON `chamber`
- `idx_committees_parent` ON `parent_committee_id`
- `idx_committees_congress` ON `congress`
- `idx_committees_system_code` ON `system_code`

**Example Query**:
```sql
-- Get all House committees with their subcommittees
SELECT
    c.name as committee,
    sc.name as subcommittee,
    c.type
FROM committees c
LEFT JOIN committees sc ON sc.parent_committee_id = c.committee_id
WHERE c.chamber = 'House'
  AND c.parent_committee_id IS NULL
ORDER BY c.name, sc.name;
```

---

### 2. members

**Purpose**: Congressional representatives and senators with extended profile data.

**Columns**:

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `member_id` | INTEGER | PRIMARY KEY | Auto-incrementing identifier |
| `bioguide_id` | TEXT | NOT NULL, UNIQUE | Unique ID from Biographical Directory |
| `first_name` | TEXT | NOT NULL | First name |
| `middle_name` | TEXT | | Middle name or initial |
| `last_name` | TEXT | NOT NULL | Last name |
| `full_name` | TEXT | NOT NULL | Full display name |
| `party` | TEXT | NOT NULL | D, R, I, ID, L, Unknown |
| `state` | TEXT | NOT NULL | Two-letter state code (e.g., CA, TX) |
| `district` | INTEGER | | District number (NULL for Senators) |
| `birth_year` | INTEGER | | Year of birth |
| `current_member` | BOOLEAN | NOT NULL, DEFAULT 1 | Currently serving |
| `honorific_prefix` | TEXT | | Mr., Mrs., Ms., Dr., etc. |
| `official_url` | TEXT | | Official website |
| `office_address` | TEXT | | Congressional office address |
| `phone` | TEXT | | Office phone number |
| `terms_served` | INTEGER | | Number of terms served |
| `congress` | INTEGER | NOT NULL | Congress number |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Record creation time |
| `updated_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Last update time |

**Constraints**:
- `party IN ('D', 'R', 'I', 'ID', 'L', 'Unknown')`

**Indexes**:
- `idx_members_bioguide` ON `bioguide_id`
- `idx_members_state` ON `state`
- `idx_members_party` ON `party`
- `idx_members_current` ON `current_member`
- `idx_members_congress` ON `congress`

**Example Query**:
```sql
-- Get all current members by party and state
SELECT
    full_name,
    party,
    state,
    district,
    CASE
        WHEN district IS NULL THEN 'Senator'
        ELSE 'Representative'
    END as position
FROM members
WHERE current_member = 1
  AND congress = 119
ORDER BY state, district NULLS FIRST;
```

---

### 3. hearings

**Purpose**: Committee hearings, meetings, and markups.

**Columns**:

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `hearing_id` | INTEGER | PRIMARY KEY | Auto-incrementing identifier |
| `event_id` | TEXT | NOT NULL, UNIQUE | API event identifier (e.g., LC12345) |
| `congress` | INTEGER | NOT NULL | Congress number |
| `chamber` | TEXT | NOT NULL | House, Senate, NoChamber |
| `title` | TEXT | NOT NULL | Hearing title |
| `hearing_type` | TEXT | NOT NULL | Hearing, Meeting, Markup |
| `status` | TEXT | NOT NULL | Scheduled, Canceled, Postponed, Rescheduled |
| `hearing_date` | DATE | | Date of hearing |
| `hearing_date_only` | DATE | | Date component only (for sorting) |
| `hearing_time` | TIME | | Time component only |
| `location` | TEXT | | Room/building location |
| `jacket_number` | TEXT | | 5-digit transcript identifier |
| `url` | TEXT | | API reference URL |
| `congress_gov_url` | TEXT | | Public Congress.gov URL |
| `video_url` | TEXT | | Full Congress.gov video URL |
| `youtube_video_id` | TEXT | | Extracted YouTube video ID |
| `update_date` | TIMESTAMP | | From API - for sync tracking |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Record creation time |
| `updated_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Last update time |

**Constraints**:
- `chamber IN ('House', 'Senate', 'NoChamber')`
- `hearing_type IN ('Hearing', 'Meeting', 'Markup')`
- `status IN ('Scheduled', 'Canceled', 'Postponed', 'Rescheduled')`

**Indexes**:
- `idx_hearings_congress` ON `congress`
- `idx_hearings_chamber` ON `chamber`
- `idx_hearings_date` ON `hearing_date`
- `idx_hearings_status` ON `status`
- `idx_hearings_update_date` ON `update_date`
- `idx_hearings_jacket` ON `jacket_number`
- `idx_youtube_video_id` ON `youtube_video_id` (for video queries)

**Example Query**:
```sql
-- Get all hearings with videos from last 30 days
SELECT
    h.title,
    h.hearing_date,
    h.chamber,
    h.youtube_video_id,
    c.name as committee_name
FROM hearings h
JOIN hearing_committees hc ON h.hearing_id = hc.hearing_id
JOIN committees c ON hc.committee_id = c.committee_id
WHERE h.hearing_date >= date('now', '-30 days')
  AND h.youtube_video_id IS NOT NULL
ORDER BY h.hearing_date DESC;
```

---

### 4. bills

**Purpose**: Lightweight bill information for hearing linkage.

**Columns**:

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `bill_id` | INTEGER | PRIMARY KEY | Auto-incrementing identifier |
| `congress` | INTEGER | NOT NULL | Congress number |
| `bill_type` | TEXT | NOT NULL | HR, S, HJRES, SJRES, HCONRES, SCONRES, HRES, SRES |
| `bill_number` | INTEGER | NOT NULL | Bill number |
| `title` | TEXT | | Bill title |
| `url` | TEXT | | API reference URL |
| `introduced_date` | DATE | | Date introduced |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Record creation time |
| `updated_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Last update time |

**Constraints**:
- `bill_type IN ('HR', 'S', 'HJRES', 'SJRES', 'HCONRES', 'SCONRES', 'HRES', 'SRES')`
- UNIQUE(`congress`, `bill_type`, `bill_number`)

**Indexes**:
- `idx_bills_congress` ON `congress`
- `idx_bills_type` ON `bill_type`
- `idx_bills_number` ON `bill_number`

**Example Query**:
```sql
-- Find all hearings discussing a specific bill
SELECT
    h.title as hearing_title,
    h.hearing_date,
    b.bill_type || ' ' || b.bill_number as bill,
    b.title as bill_title,
    hb.relationship_type
FROM bills b
JOIN hearing_bills hb ON b.bill_id = hb.bill_id
JOIN hearings h ON hb.hearing_id = h.hearing_id
WHERE b.congress = 119
  AND b.bill_type = 'HR'
  AND b.bill_number = 1
ORDER BY h.hearing_date DESC;
```

---

### 5. witnesses

**Purpose**: Individual witnesses who testify at hearings.

**Columns**:

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `witness_id` | INTEGER | PRIMARY KEY | Auto-incrementing identifier |
| `first_name` | TEXT | | First name |
| `last_name` | TEXT | | Last name |
| `full_name` | TEXT | NOT NULL | Full display name |
| `title` | TEXT | | Professional title |
| `organization` | TEXT | | Affiliated organization |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Record creation time |
| `updated_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Last update time |

**Indexes**:
- `idx_witnesses_name` ON (`last_name`, `first_name`)
- `idx_witnesses_org` ON `organization`

**Example Query**:
```sql
-- Find all appearances for a specific witness
SELECT
    w.full_name,
    w.organization,
    h.title as hearing_title,
    h.hearing_date,
    wa.position,
    c.name as committee_name
FROM witnesses w
JOIN witness_appearances wa ON w.witness_id = wa.witness_id
JOIN hearings h ON wa.hearing_id = h.hearing_id
JOIN hearing_committees hc ON h.hearing_id = hc.hearing_id
JOIN committees c ON hc.committee_id = c.committee_id
WHERE w.full_name LIKE '%Smith%'
ORDER BY h.hearing_date DESC;
```

---

## Relationship Tables

### 6. committee_memberships

**Purpose**: Member assignments to committees with roles (many-to-many with role tracking).

**Columns**:

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `membership_id` | INTEGER | PRIMARY KEY | Auto-incrementing identifier |
| `committee_id` | INTEGER | NOT NULL, FOREIGN KEY | Committee reference |
| `member_id` | INTEGER | NOT NULL, FOREIGN KEY | Member reference |
| `role` | TEXT | NOT NULL | Chair, Ranking Member, Vice Chair, Member |
| `congress` | INTEGER | NOT NULL | Congress number |
| `is_active` | BOOLEAN | NOT NULL, DEFAULT 1 | Current membership status |
| `start_date` | DATE | | Membership start date |
| `end_date` | DATE | | Membership end date (NULL if active) |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Record creation time |
| `updated_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Last update time |

**Constraints**:
- `role IN ('Chair', 'Ranking Member', 'Vice Chair', 'Member')`
- UNIQUE(`committee_id`, `member_id`, `congress`)
- FOREIGN KEY: `committee_id` → `committees(committee_id)`
- FOREIGN KEY: `member_id` → `members(member_id)`

**Indexes**:
- `idx_memberships_committee` ON `committee_id`
- `idx_memberships_member` ON `member_id`
- `idx_memberships_role` ON `role`
- `idx_memberships_active` ON `is_active`

**Example Query**:
```sql
-- Get all committee chairs for 119th Congress
SELECT
    m.full_name,
    m.party,
    m.state,
    c.name as committee_name,
    c.chamber
FROM committee_memberships cm
JOIN members m ON cm.member_id = m.member_id
JOIN committees c ON cm.committee_id = c.committee_id
WHERE cm.role = 'Chair'
  AND cm.congress = 119
  AND cm.is_active = 1
ORDER BY c.chamber, c.name;
```

---

### 7. hearing_committees

**Purpose**: Links hearings to committees (many-to-many for joint hearings).

**Columns**:

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `hearing_id` | INTEGER | NOT NULL, FOREIGN KEY | Hearing reference |
| `committee_id` | INTEGER | NOT NULL, FOREIGN KEY | Committee reference |
| `is_primary` | BOOLEAN | NOT NULL, DEFAULT 1 | Primary committee vs participating |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Record creation time |

**Constraints**:
- PRIMARY KEY(`hearing_id`, `committee_id`)
- FOREIGN KEY: `hearing_id` → `hearings(hearing_id)`
- FOREIGN KEY: `committee_id` → `committees(committee_id)`

**Indexes**:
- `idx_hearing_committees_hearing` ON `hearing_id`
- `idx_hearing_committees_committee` ON `committee_id`

**Example Query**:
```sql
-- Find all joint hearings (multiple committees)
SELECT
    h.title,
    h.hearing_date,
    GROUP_CONCAT(c.name, ' + ') as committees
FROM hearings h
JOIN hearing_committees hc ON h.hearing_id = hc.hearing_id
JOIN committees c ON hc.committee_id = c.committee_id
GROUP BY h.hearing_id, h.title, h.hearing_date
HAVING COUNT(DISTINCT hc.committee_id) > 1
ORDER BY h.hearing_date DESC;
```

---

### 8. hearing_bills

**Purpose**: Links hearings to bills with relationship context (many-to-many).

**Columns**:

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `hearing_bill_id` | INTEGER | PRIMARY KEY | Auto-incrementing identifier |
| `hearing_id` | INTEGER | NOT NULL, FOREIGN KEY | Hearing reference |
| `bill_id` | INTEGER | NOT NULL, FOREIGN KEY | Bill reference |
| `relationship_type` | TEXT | NOT NULL | primary_subject, mentioned, markup, related, theoretical |
| `notes` | TEXT | | Additional context |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Record creation time |

**Constraints**:
- `relationship_type IN ('primary_subject', 'mentioned', 'markup', 'related', 'theoretical')`
- UNIQUE(`hearing_id`, `bill_id`)
- FOREIGN KEY: `hearing_id` → `hearings(hearing_id)`
- FOREIGN KEY: `bill_id` → `bills(bill_id)`

**Indexes**:
- `idx_hearing_bills_hearing` ON `hearing_id`
- `idx_hearing_bills_bill` ON `bill_id`
- `idx_hearing_bills_type` ON `relationship_type`

**Example Query**:
```sql
-- Find bill markups in last 60 days
SELECT
    b.bill_type || ' ' || b.bill_number as bill,
    b.title as bill_title,
    h.title as hearing_title,
    h.hearing_date,
    c.name as committee_name
FROM hearing_bills hb
JOIN bills b ON hb.bill_id = b.bill_id
JOIN hearings h ON hb.hearing_id = h.hearing_id
JOIN hearing_committees hc ON h.hearing_id = hc.hearing_id
JOIN committees c ON hc.committee_id = c.committee_id
WHERE hb.relationship_type = 'markup'
  AND h.hearing_date >= date('now', '-60 days')
ORDER BY h.hearing_date DESC;
```

---

### 9. witness_appearances

**Purpose**: Junction entity representing a witness appearing at a specific hearing.

**Columns**:

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `appearance_id` | INTEGER | PRIMARY KEY | Auto-incrementing identifier |
| `witness_id` | INTEGER | NOT NULL, FOREIGN KEY | Witness reference |
| `hearing_id` | INTEGER | NOT NULL, FOREIGN KEY | Hearing reference |
| `position` | TEXT | | Position at time of testimony |
| `witness_type` | TEXT | | Government, Private, Academic, etc. |
| `appearance_order` | INTEGER | | Sequence/panel order in hearing |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Record creation time |

**Constraints**:
- UNIQUE(`witness_id`, `hearing_id`)
- FOREIGN KEY: `witness_id` → `witnesses(witness_id)`
- FOREIGN KEY: `hearing_id` → `hearings(hearing_id)`

**Indexes**:
- `idx_appearances_witness` ON `witness_id`
- `idx_appearances_hearing` ON `hearing_id`

**Example Query**:
```sql
-- Get all witnesses for a specific hearing with documents
SELECT
    w.full_name,
    w.organization,
    wa.position,
    wa.appearance_order,
    COUNT(wd.document_id) as document_count
FROM witness_appearances wa
JOIN witnesses w ON wa.witness_id = w.witness_id
LEFT JOIN witness_documents wd ON wa.appearance_id = wd.appearance_id
WHERE wa.hearing_id = 123
GROUP BY wa.appearance_id, w.full_name, w.organization, wa.position, wa.appearance_order
ORDER BY wa.appearance_order;
```

---

### 10. member_leadership_positions

**Purpose**: Tracks leadership positions held by members.

**Columns**:

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `position_id` | INTEGER | PRIMARY KEY | Auto-incrementing identifier |
| `member_id` | INTEGER | NOT NULL, FOREIGN KEY | Member reference |
| `title` | TEXT | NOT NULL | Speaker, Majority Leader, Whip, etc. |
| `congress` | INTEGER | NOT NULL | Congress number |
| `is_current` | BOOLEAN | NOT NULL, DEFAULT 1 | Currently holding position |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Record creation time |

**Constraints**:
- UNIQUE(`member_id`, `title`, `congress`)
- FOREIGN KEY: `member_id` → `members(member_id)`

**Indexes**:
- `idx_leadership_member` ON `member_id`
- `idx_leadership_congress` ON `congress`

---

### 11. policy_areas

**Purpose**: Manual reference table for policy areas/jurisdictions.

**Columns**:

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `policy_area_id` | INTEGER | PRIMARY KEY | Auto-incrementing identifier |
| `name` | TEXT | NOT NULL, UNIQUE | Healthcare, Immigration, Tax Policy, etc. |
| `description` | TEXT | | Policy area description |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Record creation time |

---

### 12. committee_jurisdictions

**Purpose**: Links committees to their policy area jurisdictions (many-to-many).

**Columns**:

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `committee_id` | INTEGER | NOT NULL, FOREIGN KEY | Committee reference |
| `policy_area_id` | INTEGER | NOT NULL, FOREIGN KEY | Policy area reference |
| `is_primary` | BOOLEAN | NOT NULL, DEFAULT 1 | Primary vs secondary jurisdiction |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Record creation time |

**Constraints**:
- PRIMARY KEY(`committee_id`, `policy_area_id`)
- FOREIGN KEY: `committee_id` → `committees(committee_id)`
- FOREIGN KEY: `policy_area_id` → `policy_areas(policy_area_id)`

**Indexes**:
- `idx_jurisdictions_committee` ON `committee_id`
- `idx_jurisdictions_policy` ON `policy_area_id`

---

## Document Tables

### 13. hearing_transcripts

**Purpose**: Hearing transcript documents (metadata and URLs only, not full text).

**Columns**:

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `transcript_id` | INTEGER | PRIMARY KEY | Auto-incrementing identifier |
| `hearing_id` | INTEGER | NOT NULL, FOREIGN KEY | Hearing reference |
| `jacket_number` | TEXT | | 5-digit transcript identifier |
| `title` | TEXT | | Document title |
| `document_url` | TEXT | | Congress.gov document page |
| `pdf_url` | TEXT | | Direct PDF link |
| `html_url` | TEXT | | HTML version if available |
| `format_type` | TEXT | | PDF, HTML, Text |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Record creation time |
| `updated_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Last update time |

**Constraints**:
- FOREIGN KEY: `hearing_id` → `hearings(hearing_id)`
- UNIQUE(`hearing_id`, `document_url`)

**Indexes**:
- `idx_transcripts_hearing` ON `hearing_id`
- `idx_transcripts_jacket` ON `jacket_number`

**Example Query**:
```sql
-- Find all hearings with transcripts for a committee
SELECT
    h.title,
    h.hearing_date,
    ht.jacket_number,
    ht.pdf_url
FROM hearings h
JOIN hearing_committees hc ON h.hearing_id = hc.hearing_id
JOIN committees c ON hc.committee_id = c.committee_id
JOIN hearing_transcripts ht ON h.hearing_id = ht.hearing_id
WHERE c.system_code = 'hsif00'
  AND h.hearing_date >= '2025-01-01'
ORDER BY h.hearing_date DESC;
```

---

### 14. witness_documents

**Purpose**: Documents submitted by witnesses (linked to specific appearances).

**Columns**:

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `document_id` | INTEGER | PRIMARY KEY | Auto-incrementing identifier |
| `appearance_id` | INTEGER | NOT NULL, FOREIGN KEY | Witness appearance reference |
| `document_type` | TEXT | NOT NULL | Statement, Biography, Truth Statement, Questions for Record, Supplemental |
| `title` | TEXT | | Document title |
| `document_url` | TEXT | | Document URL |
| `format_type` | TEXT | | PDF, HTML, Text |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Record creation time |
| `updated_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Last update time |

**Constraints**:
- `document_type IN ('Statement', 'Biography', 'Truth Statement', 'Questions for Record', 'Supplemental')`
- FOREIGN KEY: `appearance_id` → `witness_appearances(appearance_id)`
- UNIQUE(`appearance_id`, `document_url`)

**Indexes**:
- `idx_witness_docs_appearance` ON `appearance_id`
- `idx_witness_docs_type` ON `document_type`

**Example Query**:
```sql
-- Get all witness statements for a hearing
SELECT
    w.full_name,
    w.organization,
    wd.document_type,
    wd.title,
    wd.document_url
FROM witness_documents wd
JOIN witness_appearances wa ON wd.appearance_id = wa.appearance_id
JOIN witnesses w ON wa.witness_id = w.witness_id
WHERE wa.hearing_id = 123
  AND wd.document_type = 'Statement'
ORDER BY wa.appearance_order;
```

---

### 15. supporting_documents

**Purpose**: Additional hearing-related documents (not transcripts or witness docs).

**Columns**:

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `document_id` | INTEGER | PRIMARY KEY | Auto-incrementing identifier |
| `hearing_id` | INTEGER | NOT NULL, FOREIGN KEY | Hearing reference |
| `document_type` | TEXT | NOT NULL | Activity Report, Committee Rules, Member Statements, etc. |
| `title` | TEXT | | Document title |
| `description` | TEXT | | Document description |
| `document_url` | TEXT | | Document URL |
| `format_type` | TEXT | | PDF, HTML, Text |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Record creation time |
| `updated_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Last update time |

**Constraints**:
- FOREIGN KEY: `hearing_id` → `hearings(hearing_id)`
- UNIQUE(`hearing_id`, `document_url`)

**Indexes**:
- `idx_supporting_docs_hearing` ON `hearing_id`
- `idx_supporting_docs_type` ON `document_type`

---

## System & Management Tables

### 16. sync_tracking

**Purpose**: Tracks synchronization status for incremental updates.

**Columns**:

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `sync_id` | INTEGER | PRIMARY KEY | Auto-incrementing identifier |
| `entity_type` | TEXT | NOT NULL | committees, members, hearings, bills, documents |
| `last_sync_timestamp` | TIMESTAMP | NOT NULL | Time of last sync |
| `records_processed` | INTEGER | | Number of records processed |
| `errors_count` | INTEGER | | Number of errors encountered |
| `status` | TEXT | NOT NULL | success, partial, failed |
| `notes` | TEXT | | Additional notes |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Record creation time |

**Constraints**:
- `entity_type IN ('committees', 'members', 'hearings', 'bills', 'documents')`
- `status IN ('success', 'partial', 'failed')`

**Indexes**:
- `idx_sync_entity` ON `entity_type`
- `idx_sync_timestamp` ON `last_sync_timestamp`

**Example Query**:
```sql
-- Get last successful sync for each entity type
SELECT
    entity_type,
    last_sync_timestamp,
    records_processed,
    errors_count
FROM sync_tracking
WHERE status = 'success'
  AND sync_id IN (
    SELECT MAX(sync_id)
    FROM sync_tracking
    WHERE status = 'success'
    GROUP BY entity_type
  )
ORDER BY last_sync_timestamp DESC;
```

---

### 17. import_errors

**Purpose**: Logs errors during import/sync for troubleshooting.

**Columns**:

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `error_id` | INTEGER | PRIMARY KEY | Auto-incrementing identifier |
| `entity_type` | TEXT | NOT NULL | Entity type (hearing, committee, etc.) |
| `entity_identifier` | TEXT | | API reference or ID |
| `error_type` | TEXT | NOT NULL | validation, api_error, parse_error, network_error |
| `error_message` | TEXT | NOT NULL | Error message |
| `severity` | TEXT | NOT NULL | critical, warning |
| `is_resolved` | BOOLEAN | NOT NULL, DEFAULT 0 | Resolution status |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Record creation time |

**Constraints**:
- `error_type IN ('validation', 'api_error', 'parse_error', 'network_error')`
- `severity IN ('critical', 'warning')`

**Indexes**:
- `idx_errors_entity` ON `entity_type`
- `idx_errors_severity` ON `severity`
- `idx_errors_resolved` ON `is_resolved`

**Example Query**:
```sql
-- Get all unresolved critical errors
SELECT
    entity_type,
    entity_identifier,
    error_type,
    error_message,
    created_at
FROM import_errors
WHERE severity = 'critical'
  AND is_resolved = 0
ORDER BY created_at DESC;
```

---

### 18. scheduled_tasks

**Purpose**: Defines recurring update schedules for automated data ingestion.

**Columns**:

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `task_id` | INTEGER | PRIMARY KEY | Auto-incrementing identifier |
| `name` | TEXT | NOT NULL | User-friendly name (e.g., "Daily Hearings Update") |
| `description` | TEXT | | Optional description |
| `schedule_cron` | TEXT | NOT NULL | Cron expression (e.g., "0 6 * * *") |
| `lookback_days` | INTEGER | NOT NULL, DEFAULT 7 | Days to look back for updates |
| `components` | TEXT | NOT NULL | JSON array: ["hearings", "committees", "witnesses"] |
| `chamber` | TEXT | DEFAULT 'both' | Filter: both, house, senate |
| `mode` | TEXT | NOT NULL, DEFAULT 'incremental' | incremental or full |
| `is_active` | BOOLEAN | NOT NULL, DEFAULT 1 | Enable/disable task |
| `is_deployed` | BOOLEAN | NOT NULL, DEFAULT 0 | Deployed to Vercel |
| `last_run_at` | TIMESTAMP | | Last successful execution |
| `next_run_at` | TIMESTAMP | | Calculated next run time |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Record creation time |
| `updated_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Last update time |
| `created_by` | TEXT | DEFAULT 'admin' | Creator identifier |

**Constraints**:
- `lookback_days BETWEEN 1 AND 90`
- `chamber IN ('both', 'house', 'senate')`
- `mode IN ('incremental', 'full')`

**Indexes**:
- `idx_scheduled_tasks_active` ON `is_active`
- `idx_scheduled_tasks_deployed` ON `is_deployed`
- `idx_scheduled_tasks_next_run` ON `next_run_at`

**Example Query**:
```sql
-- Get all active scheduled tasks
SELECT
    name,
    schedule_cron,
    lookback_days,
    components,
    last_run_at,
    next_run_at
FROM scheduled_tasks
WHERE is_active = 1
ORDER BY next_run_at;
```

---

### 19. update_logs

**Purpose**: Tracks all update operations (manual and scheduled) with detailed metrics.

**Columns**:

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `log_id` | INTEGER | PRIMARY KEY | Auto-incrementing identifier |
| `update_date` | DATE | NOT NULL | Date of update |
| `start_time` | DATETIME | NOT NULL | Update start time |
| `end_time` | DATETIME | | Update end time |
| `duration_seconds` | REAL | | Duration in seconds |
| `hearings_checked` | INTEGER | DEFAULT 0 | Number of hearings checked |
| `hearings_updated` | INTEGER | DEFAULT 0 | Number of hearings updated |
| `hearings_added` | INTEGER | DEFAULT 0 | Number of hearings added |
| `committees_updated` | INTEGER | DEFAULT 0 | Number of committees updated |
| `witnesses_updated` | INTEGER | DEFAULT 0 | Number of witnesses updated |
| `api_requests` | INTEGER | DEFAULT 0 | Number of API requests made |
| `error_count` | INTEGER | DEFAULT 0 | Number of errors |
| `errors` | TEXT | | JSON array of error messages |
| `success` | BOOLEAN | DEFAULT 1 | Success status |
| `trigger_source` | TEXT | DEFAULT 'manual' | manual, vercel_cron, test |
| `schedule_id` | INTEGER | FOREIGN KEY | Scheduled task reference (NULL for manual) |
| `created_at` | DATETIME | DEFAULT CURRENT_TIMESTAMP | Record creation time |

**Constraints**:
- `trigger_source IN ('manual', 'vercel_cron', 'test')`
- FOREIGN KEY: `schedule_id` → `scheduled_tasks(task_id)`

**Indexes**:
- `idx_update_logs_date` ON `update_date`
- `idx_update_logs_schedule` ON `schedule_id`
- `idx_update_logs_success` ON `success`
- `idx_update_logs_source` ON `trigger_source`

**Example Query**:
```sql
-- Get update performance metrics for last 30 days
SELECT
    DATE(update_date) as date,
    COUNT(*) as update_count,
    AVG(duration_seconds) as avg_duration,
    SUM(hearings_updated) as total_hearings_updated,
    SUM(hearings_added) as total_hearings_added,
    SUM(error_count) as total_errors
FROM update_logs
WHERE update_date >= date('now', '-30 days')
  AND success = 1
GROUP BY DATE(update_date)
ORDER BY date DESC;
```

---

### 20. schedule_execution_logs

**Purpose**: Links scheduled tasks to their execution results for detailed tracking.

**Columns**:

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `execution_id` | INTEGER | PRIMARY KEY | Auto-incrementing identifier |
| `schedule_id` | INTEGER | NOT NULL, FOREIGN KEY | Scheduled task reference |
| `log_id` | INTEGER | NOT NULL, FOREIGN KEY | Update log reference |
| `execution_time` | DATETIME | NOT NULL | Execution timestamp |
| `success` | BOOLEAN | NOT NULL | Success status |
| `error_message` | TEXT | | Error message if failed |
| `config_snapshot` | TEXT | | JSON snapshot of schedule config |
| `created_at` | DATETIME | DEFAULT CURRENT_TIMESTAMP | Record creation time |

**Constraints**:
- UNIQUE(`schedule_id`, `log_id`)
- FOREIGN KEY: `schedule_id` → `scheduled_tasks(task_id)`
- FOREIGN KEY: `log_id` → `update_logs(log_id)`

**Indexes**:
- `idx_schedule_exec_schedule` ON `schedule_id`
- `idx_schedule_exec_time` ON `execution_time`
- `idx_schedule_exec_success` ON `success`

**Example Query**:
```sql
-- Get success rate for each scheduled task
SELECT
    st.name,
    COUNT(*) as total_executions,
    SUM(CASE WHEN sel.success = 1 THEN 1 ELSE 0 END) as successful,
    ROUND(100.0 * SUM(CASE WHEN sel.success = 1 THEN 1 ELSE 0 END) / COUNT(*), 2) as success_rate
FROM schedule_execution_logs sel
JOIN scheduled_tasks st ON sel.schedule_id = st.task_id
WHERE sel.execution_time >= datetime('now', '-30 days')
GROUP BY st.task_id, st.name
ORDER BY success_rate DESC;
```

---

## Indexes & Performance

### Index Strategy

The database uses **37 indexes** across 20 tables for optimal query performance:

**Primary Indexes** (Foreign Key Support):
- All junction tables indexed on both FK columns
- All parent tables indexed on primary keys

**Query Optimization Indexes**:
- **Date-based queries**: `hearing_date`, `update_date`
- **Chamber filters**: `chamber` on hearings, committees, members
- **Status filters**: `status`, `is_active`, `is_current`
- **Text searches**: Composite indexes on `(last_name, first_name)`

**Performance Considerations**:

```sql
-- GOOD: Uses index on hearing_date
SELECT * FROM hearings WHERE hearing_date >= '2025-01-01';

-- GOOD: Uses index on chamber and date (compound)
SELECT * FROM hearings WHERE chamber = 'House' AND hearing_date >= '2025-01-01';

-- AVOID: Function on indexed column (no index used)
SELECT * FROM hearings WHERE strftime('%Y', hearing_date) = '2025';

-- BETTER: Use range comparison instead
SELECT * FROM hearings WHERE hearing_date >= '2025-01-01' AND hearing_date < '2026-01-01';
```

### Maintenance Commands

```sql
-- Rebuild indexes and update statistics
VACUUM;
ANALYZE;

-- Check database integrity
PRAGMA integrity_check;

-- Check foreign key constraints
PRAGMA foreign_key_check;

-- View table sizes
SELECT
    name,
    (page_count * page_size) / 1024 / 1024 as size_mb
FROM pragma_page_count('main'), pragma_page_size(), sqlite_master
WHERE type = 'table'
ORDER BY page_count DESC;
```

---

## Common Queries

### Query 1: Hearings by Committee with Witness Count

```sql
SELECT
    h.hearing_id,
    h.title,
    h.hearing_date,
    c.name as committee_name,
    COUNT(DISTINCT wa.witness_id) as witness_count,
    COUNT(DISTINCT ht.transcript_id) as transcript_count
FROM hearings h
JOIN hearing_committees hc ON h.hearing_id = hc.hearing_id
JOIN committees c ON hc.committee_id = c.committee_id
LEFT JOIN witness_appearances wa ON h.hearing_id = wa.hearing_id
LEFT JOIN hearing_transcripts ht ON h.hearing_id = ht.hearing_id
WHERE c.system_code = 'hsif00'
  AND h.hearing_date >= '2025-01-01'
GROUP BY h.hearing_id, h.title, h.hearing_date, c.name
ORDER BY h.hearing_date DESC;
```

### Query 2: Member Activity Report

```sql
SELECT
    m.full_name,
    m.party,
    m.state,
    COUNT(DISTINCT cm.committee_id) as committee_count,
    GROUP_CONCAT(DISTINCT c.name, ', ') as committees,
    MAX(CASE WHEN cm.role = 'Chair' THEN 1 ELSE 0 END) as is_chair
FROM members m
JOIN committee_memberships cm ON m.member_id = cm.member_id
JOIN committees c ON cm.committee_id = c.committee_id
WHERE m.current_member = 1
  AND cm.is_active = 1
  AND cm.congress = 119
GROUP BY m.member_id, m.full_name, m.party, m.state
ORDER BY committee_count DESC, m.last_name;
```

### Query 3: Witness Testimony Frequency

```sql
SELECT
    w.full_name,
    w.organization,
    COUNT(*) as appearance_count,
    MIN(h.hearing_date) as first_appearance,
    MAX(h.hearing_date) as last_appearance,
    GROUP_CONCAT(DISTINCT c.name, ', ') as committees
FROM witnesses w
JOIN witness_appearances wa ON w.witness_id = wa.witness_id
JOIN hearings h ON wa.hearing_id = h.hearing_id
JOIN hearing_committees hc ON h.hearing_id = hc.hearing_id
JOIN committees c ON hc.committee_id = c.committee_id
WHERE h.congress = 119
GROUP BY w.witness_id, w.full_name, w.organization
HAVING COUNT(*) >= 2
ORDER BY appearance_count DESC, last_appearance DESC;
```

### Query 4: Video Availability Report

```sql
SELECT
    c.name as committee_name,
    COUNT(DISTINCT h.hearing_id) as total_hearings,
    SUM(CASE WHEN h.youtube_video_id IS NOT NULL THEN 1 ELSE 0 END) as with_video,
    ROUND(100.0 * SUM(CASE WHEN h.youtube_video_id IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 2) as video_percentage
FROM committees c
JOIN hearing_committees hc ON c.committee_id = hc.committee_id
JOIN hearings h ON hc.hearing_id = h.hearing_id
WHERE h.congress = 119
  AND c.parent_committee_id IS NULL
GROUP BY c.committee_id, c.name
ORDER BY video_percentage DESC;
```

### Query 5: Document Completeness Analysis

```sql
SELECT
    h.hearing_id,
    h.title,
    h.hearing_date,
    CASE WHEN ht.transcript_id IS NOT NULL THEN 1 ELSE 0 END as has_transcript,
    COUNT(DISTINCT wd.document_id) as witness_docs,
    COUNT(DISTINCT sd.document_id) as supporting_docs
FROM hearings h
LEFT JOIN hearing_transcripts ht ON h.hearing_id = ht.hearing_id
LEFT JOIN witness_appearances wa ON h.hearing_id = wa.hearing_id
LEFT JOIN witness_documents wd ON wa.appearance_id = wd.appearance_id
LEFT JOIN supporting_documents sd ON h.hearing_id = sd.hearing_id
WHERE h.hearing_date >= '2025-01-01'
GROUP BY h.hearing_id, h.title, h.hearing_date, ht.transcript_id
ORDER BY h.hearing_date DESC;
```

---

## Data Integrity Rules

### Foreign Key Constraints

All foreign keys are enforced with `PRAGMA foreign_keys = ON`. Key rules:

1. **Cannot delete referenced records**:
   - Deleting a committee with associated hearings will fail
   - Deleting a hearing with witnesses/documents will fail

2. **Orphaned records prevented**:
   - Cannot create hearing_committees without valid hearing and committee
   - Cannot create witness_documents without valid appearance

3. **Cascade deletes** (where appropriate):
   - Some relationships may use `ON DELETE CASCADE` for automatic cleanup

### Check Constraints

All enum fields validated with CHECK constraints:

```sql
-- Hearings chamber validation
CHECK (chamber IN ('House', 'Senate', 'NoChamber'))

-- Member party validation
CHECK (party IN ('D', 'R', 'I', 'ID', 'L', 'Unknown'))

-- Bill type validation
CHECK (bill_type IN ('HR', 'S', 'HJRES', 'SJRES', 'HCONRES', 'SCONRES', 'HRES', 'SRES'))
```

### Unique Constraints

Prevents duplicate records:

```sql
-- One committee per system_code
UNIQUE(system_code)

-- One bill per congress/type/number combination
UNIQUE(congress, bill_type, bill_number)

-- One witness appearance per hearing
UNIQUE(witness_id, hearing_id)

-- One document URL per hearing (for transcripts and supporting docs)
UNIQUE(hearing_id, document_url)
```

### Data Validation Best Practices

When inserting data:

```python
# GOOD: Use upsert methods from DatabaseManager
hearing_id = db.upsert_hearing(hearing_data)

# AVOID: Raw INSERT OR REPLACE (breaks foreign keys)
conn.execute("INSERT OR REPLACE INTO hearings ...")
```

**Why?** `INSERT OR REPLACE` deletes and re-inserts, breaking foreign key references. The DatabaseManager upsert methods use proper UPDATE/INSERT logic.

---

## Additional Resources

### Related Documentation

- **[System Architecture](SYSTEM_ARCHITECTURE.md)** - Overall system design
- **[Development Guide](../../guides/developer/DEVELOPMENT.md)** - Development patterns
- **[CLI Guide](../../guides/developer/CLI_GUIDE.md)** - Database commands

### External Resources

- **[SQLite Documentation](https://www.sqlite.org/docs.html)** - SQL syntax reference
- **[SQLite Foreign Key Support](https://www.sqlite.org/foreignkeys.html)** - FK constraints
- **[DB Browser for SQLite](https://sqlitebrowser.org/)** - Database inspection tool

---

**Last Updated**: October 9, 2025
**Schema Version**: 1.0
**Total Tables**: 20
**Database Size**: ~50 MB (with 1,168+ hearings)

[← Back: System Architecture](SYSTEM_ARCHITECTURE.md) | [Up: Documentation Hub](../../README.md) | [Next: Web Architecture →](WEB_ARCHITECTURE.md)
