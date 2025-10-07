-- Congressional Committee Hearing Database Schema
-- Version: 1.0
-- Date: October 1, 2025

-- 1. committees
-- Stores all congressional committees and subcommittees with hierarchical relationships
CREATE TABLE committees (
    committee_id INTEGER PRIMARY KEY AUTOINCREMENT,
    system_code TEXT NOT NULL UNIQUE,        -- API unique identifier (e.g., "hsif00")
    name TEXT NOT NULL,                       -- Full committee name
    chamber TEXT NOT NULL,                    -- House, Senate, Joint
    type TEXT NOT NULL,                       -- Standing, Select, Special, Joint, etc.
    parent_committee_id INTEGER,              -- NULL for full committees, FK for subcommittees
    is_current BOOLEAN NOT NULL DEFAULT 1,
    url TEXT,                                 -- API reference URL
    congress INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (parent_committee_id) REFERENCES committees(committee_id),
    CHECK (chamber IN ('House', 'Senate', 'Joint', 'NoChamber')),
    CHECK (type IN ('Standing', 'Select', 'Special', 'Joint', 'Task Force',
                    'Other', 'Subcommittee', 'Commission or Caucus'))
);

CREATE INDEX idx_committees_chamber ON committees(chamber);
CREATE INDEX idx_committees_parent ON committees(parent_committee_id);
CREATE INDEX idx_committees_congress ON committees(congress);
CREATE INDEX idx_committees_system_code ON committees(system_code);

-- 2. members
-- Congressional representatives and senators with extended profile data
CREATE TABLE members (
    member_id INTEGER PRIMARY KEY AUTOINCREMENT,
    bioguide_id TEXT NOT NULL UNIQUE,         -- Unique identifier from Biographical Directory
    first_name TEXT NOT NULL,
    middle_name TEXT,
    last_name TEXT NOT NULL,
    full_name TEXT NOT NULL,
    party TEXT NOT NULL,                      -- D, R, I, etc.
    state TEXT NOT NULL,                      -- Two-letter state code
    district INTEGER,                         -- NULL for Senators
    birth_year INTEGER,
    current_member BOOLEAN NOT NULL DEFAULT 1,
    honorific_prefix TEXT,                    -- Mr., Mrs., Ms., Dr., etc.
    official_url TEXT,
    office_address TEXT,
    phone TEXT,
    terms_served INTEGER,
    congress INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CHECK (party IN ('D', 'R', 'I', 'ID', 'L', 'Unknown'))
);

CREATE INDEX idx_members_bioguide ON members(bioguide_id);
CREATE INDEX idx_members_state ON members(state);
CREATE INDEX idx_members_party ON members(party);
CREATE INDEX idx_members_current ON members(current_member);
CREATE INDEX idx_members_congress ON members(congress);

-- 3. member_leadership_positions
-- Tracks leadership positions held by members (Speaker, Majority Leader, etc.)
CREATE TABLE member_leadership_positions (
    position_id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id INTEGER NOT NULL,
    title TEXT NOT NULL,                      -- Speaker, Majority Leader, Whip, etc.
    congress INTEGER NOT NULL,
    is_current BOOLEAN NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (member_id) REFERENCES members(member_id),
    UNIQUE(member_id, title, congress)
);

CREATE INDEX idx_leadership_member ON member_leadership_positions(member_id);
CREATE INDEX idx_leadership_congress ON member_leadership_positions(congress);

-- 4. policy_areas
-- Manual reference table for policy areas/jurisdictions (manually maintained)
CREATE TABLE policy_areas (
    policy_area_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,                -- Healthcare, Immigration, Tax Policy, etc.
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 5. committee_jurisdictions
-- Links committees to their policy area jurisdictions (many-to-many)
CREATE TABLE committee_jurisdictions (
    committee_id INTEGER NOT NULL,
    policy_area_id INTEGER NOT NULL,
    is_primary BOOLEAN NOT NULL DEFAULT 1,    -- Primary vs secondary jurisdiction
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (committee_id, policy_area_id),
    FOREIGN KEY (committee_id) REFERENCES committees(committee_id),
    FOREIGN KEY (policy_area_id) REFERENCES policy_areas(policy_area_id)
);

CREATE INDEX idx_jurisdictions_committee ON committee_jurisdictions(committee_id);
CREATE INDEX idx_jurisdictions_policy ON committee_jurisdictions(policy_area_id);

-- 6. committee_memberships
-- Member assignments to committees with roles (many-to-many with role tracking)
CREATE TABLE committee_memberships (
    membership_id INTEGER PRIMARY KEY AUTOINCREMENT,
    committee_id INTEGER NOT NULL,
    member_id INTEGER NOT NULL,
    role TEXT NOT NULL,                       -- Chair, Ranking Member, Vice Chair, Member
    congress INTEGER NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT 1,     -- Track departures/membership changes
    start_date DATE,
    end_date DATE,                            -- NULL if still active
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (committee_id) REFERENCES committees(committee_id),
    FOREIGN KEY (member_id) REFERENCES members(member_id),
    CHECK (role IN ('Chair', 'Ranking Member', 'Vice Chair', 'Member')),
    UNIQUE(committee_id, member_id, congress)
);

CREATE INDEX idx_memberships_committee ON committee_memberships(committee_id);
CREATE INDEX idx_memberships_member ON committee_memberships(member_id);
CREATE INDEX idx_memberships_role ON committee_memberships(role);
CREATE INDEX idx_memberships_active ON committee_memberships(is_active);

-- 7. hearings
-- Committee hearings, meetings, and markups
CREATE TABLE hearings (
    hearing_id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL UNIQUE,            -- API event identifier
    congress INTEGER NOT NULL,
    chamber TEXT NOT NULL,                    -- House, Senate, NoChamber
    title TEXT NOT NULL,
    hearing_type TEXT NOT NULL,               -- Hearing, Meeting, Markup
    status TEXT NOT NULL,                     -- Scheduled, Canceled, Postponed, Rescheduled
    hearing_date DATE,
    location TEXT,
    jacket_number TEXT,                       -- Links to transcript (5-digit number)
    url TEXT,                                 -- API reference URL
    congress_gov_url TEXT,                    -- Public Congress.gov URL
    video_url TEXT,                           -- Full Congress.gov video URL
    youtube_video_id TEXT,                    -- Extracted YouTube video ID
    update_date TIMESTAMP,                    -- From API - for sync tracking
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CHECK (chamber IN ('House', 'Senate', 'NoChamber')),
    CHECK (hearing_type IN ('Hearing', 'Meeting', 'Markup')),
    CHECK (status IN ('Scheduled', 'Canceled', 'Postponed', 'Rescheduled'))
);

CREATE INDEX idx_hearings_congress ON hearings(congress);
CREATE INDEX idx_hearings_chamber ON hearings(chamber);
CREATE INDEX idx_hearings_date ON hearings(hearing_date);
CREATE INDEX idx_hearings_status ON hearings(status);
CREATE INDEX idx_hearings_update_date ON hearings(update_date);
CREATE INDEX idx_hearings_jacket ON hearings(jacket_number);

-- 8. hearing_committees
-- Links hearings to committees (many-to-many for joint hearings)
CREATE TABLE hearing_committees (
    hearing_id INTEGER NOT NULL,
    committee_id INTEGER NOT NULL,
    is_primary BOOLEAN NOT NULL DEFAULT 1,    -- Primary committee vs participating
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (hearing_id, committee_id),
    FOREIGN KEY (hearing_id) REFERENCES hearings(hearing_id),
    FOREIGN KEY (committee_id) REFERENCES committees(committee_id)
);

CREATE INDEX idx_hearing_committees_hearing ON hearing_committees(hearing_id);
CREATE INDEX idx_hearing_committees_committee ON hearing_committees(committee_id);

-- 9. bills
-- Lightweight bill information for hearing linkage
CREATE TABLE bills (
    bill_id INTEGER PRIMARY KEY AUTOINCREMENT,
    congress INTEGER NOT NULL,
    bill_type TEXT NOT NULL,                  -- HR, S, HJRES, SJRES, HCONRES, SCONRES, HRES, SRES
    bill_number INTEGER NOT NULL,
    title TEXT,
    url TEXT,                                 -- API reference URL
    introduced_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CHECK (bill_type IN ('HR', 'S', 'HJRES', 'SJRES', 'HCONRES', 'SCONRES', 'HRES', 'SRES')),
    UNIQUE(congress, bill_type, bill_number)
);

CREATE INDEX idx_bills_congress ON bills(congress);
CREATE INDEX idx_bills_type ON bills(bill_type);
CREATE INDEX idx_bills_number ON bills(bill_number);

-- 10. hearing_bills
-- Links hearings to bills with relationship context (many-to-many)
CREATE TABLE hearing_bills (
    hearing_bill_id INTEGER PRIMARY KEY AUTOINCREMENT,
    hearing_id INTEGER NOT NULL,
    bill_id INTEGER NOT NULL,
    relationship_type TEXT NOT NULL,          -- primary_subject, mentioned, markup, related, theoretical
    notes TEXT,                               -- For future context/classification
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (hearing_id) REFERENCES hearings(hearing_id),
    FOREIGN KEY (bill_id) REFERENCES bills(bill_id),
    CHECK (relationship_type IN ('primary_subject', 'mentioned', 'markup',
                                   'related', 'theoretical')),
    UNIQUE(hearing_id, bill_id)
);

CREATE INDEX idx_hearing_bills_hearing ON hearing_bills(hearing_id);
CREATE INDEX idx_hearing_bills_bill ON hearing_bills(bill_id);
CREATE INDEX idx_hearing_bills_type ON hearing_bills(relationship_type);

-- 11. witnesses
-- Individual witnesses who testify at hearings
CREATE TABLE witnesses (
    witness_id INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name TEXT,
    last_name TEXT,
    full_name TEXT NOT NULL,
    title TEXT,                               -- Professional title
    organization TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_witnesses_name ON witnesses(last_name, first_name);
CREATE INDEX idx_witnesses_org ON witnesses(organization);

-- 12. witness_appearances
-- Junction entity representing a witness appearing at a specific hearing
CREATE TABLE witness_appearances (
    appearance_id INTEGER PRIMARY KEY AUTOINCREMENT,
    witness_id INTEGER NOT NULL,
    hearing_id INTEGER NOT NULL,
    position TEXT,                            -- Position at time of testimony (Director, CEO, etc.)
    witness_type TEXT,                        -- Government, Private, Academic, etc.
    appearance_order INTEGER,                 -- Sequence/panel order in hearing
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (witness_id) REFERENCES witnesses(witness_id),
    FOREIGN KEY (hearing_id) REFERENCES hearings(hearing_id),
    UNIQUE(witness_id, hearing_id)
);

CREATE INDEX idx_appearances_witness ON witness_appearances(witness_id);
CREATE INDEX idx_appearances_hearing ON witness_appearances(hearing_id);

-- 13. hearing_transcripts
-- Hearing transcript documents (metadata and URLs only)
CREATE TABLE hearing_transcripts (
    transcript_id INTEGER PRIMARY KEY AUTOINCREMENT,
    hearing_id INTEGER NOT NULL,
    jacket_number TEXT,                       -- 5-digit identifier
    title TEXT,
    document_url TEXT,                        -- Congress.gov document page
    pdf_url TEXT,                             -- Direct PDF link
    html_url TEXT,                            -- HTML version if available
    format_type TEXT,                         -- PDF, HTML, Text
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (hearing_id) REFERENCES hearings(hearing_id)
);

CREATE INDEX idx_transcripts_hearing ON hearing_transcripts(hearing_id);
CREATE INDEX idx_transcripts_jacket ON hearing_transcripts(jacket_number);

-- 14. witness_documents
-- Documents submitted by witnesses (linked to specific appearances)
CREATE TABLE witness_documents (
    document_id INTEGER PRIMARY KEY AUTOINCREMENT,
    appearance_id INTEGER NOT NULL,           -- Links to specific witness appearance
    document_type TEXT NOT NULL,              -- Statement, Biography, Truth Statement, Questions for Record, Supplemental
    title TEXT,
    document_url TEXT,
    format_type TEXT,                         -- PDF, HTML, Text
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (appearance_id) REFERENCES witness_appearances(appearance_id),
    CHECK (document_type IN ('Statement', 'Biography', 'Truth Statement',
                              'Questions for Record', 'Supplemental'))
);

CREATE INDEX idx_witness_docs_appearance ON witness_documents(appearance_id);
CREATE INDEX idx_witness_docs_type ON witness_documents(document_type);

-- 15. supporting_documents
-- Additional hearing-related documents
CREATE TABLE supporting_documents (
    document_id INTEGER PRIMARY KEY AUTOINCREMENT,
    hearing_id INTEGER NOT NULL,
    document_type TEXT NOT NULL,              -- Activity Report, Committee Rules, Member Statements, etc.
    title TEXT,
    description TEXT,
    document_url TEXT,
    format_type TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (hearing_id) REFERENCES hearings(hearing_id)
);

CREATE INDEX idx_supporting_docs_hearing ON supporting_documents(hearing_id);
CREATE INDEX idx_supporting_docs_type ON supporting_documents(document_type);

-- 16. sync_tracking
-- Tracks synchronization status for incremental updates
CREATE TABLE sync_tracking (
    sync_id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL,                -- hearings, committees, members, bills
    last_sync_timestamp TIMESTAMP NOT NULL,
    records_processed INTEGER,
    errors_count INTEGER,
    status TEXT NOT NULL,                     -- success, partial, failed
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CHECK (entity_type IN ('committees', 'members', 'hearings', 'bills', 'documents')),
    CHECK (status IN ('success', 'partial', 'failed'))
);

CREATE INDEX idx_sync_entity ON sync_tracking(entity_type);
CREATE INDEX idx_sync_timestamp ON sync_tracking(last_sync_timestamp);

-- 17. import_errors
-- Logs errors during import/sync for troubleshooting
CREATE TABLE import_errors (
    error_id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL,
    entity_identifier TEXT,                   -- API reference or ID
    error_type TEXT NOT NULL,                 -- validation, api_error, parse_error
    error_message TEXT NOT NULL,
    severity TEXT NOT NULL,                   -- critical, warning
    is_resolved BOOLEAN NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CHECK (error_type IN ('validation', 'api_error', 'parse_error', 'network_error')),
    CHECK (severity IN ('critical', 'warning'))
);

CREATE INDEX idx_errors_entity ON import_errors(entity_type);
CREATE INDEX idx_errors_severity ON import_errors(severity);
CREATE INDEX idx_errors_resolved ON import_errors(is_resolved);