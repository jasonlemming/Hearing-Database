-- PostgreSQL Schema for Congressional Hearing Database
-- Converted from SQLite schema

-- Committees Table
CREATE TABLE IF NOT EXISTS committees (
    committee_id SERIAL PRIMARY KEY,
    system_code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    chamber TEXT NOT NULL,
    type TEXT NOT NULL,
    parent_committee_id INTEGER,
    is_current BOOLEAN NOT NULL DEFAULT true,
    url TEXT,
    congress INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (parent_committee_id) REFERENCES committees(committee_id),
    CHECK (chamber IN ('House', 'Senate', 'Joint', 'NoChamber')),
    CHECK (type IN ('Standing', 'Select', 'Special', 'Joint', 'Task Force',
                    'Other', 'Subcommittee', 'Commission or Caucus'))
);

CREATE INDEX IF NOT EXISTS idx_committees_chamber ON committees(chamber);
CREATE INDEX IF NOT EXISTS idx_committees_parent ON committees(parent_committee_id);
CREATE INDEX IF NOT EXISTS idx_committees_congress ON committees(congress);
CREATE INDEX IF NOT EXISTS idx_committees_system_code ON committees(system_code);

-- Members Table
CREATE TABLE IF NOT EXISTS members (
    member_id SERIAL PRIMARY KEY,
    bioguide_id TEXT NOT NULL UNIQUE,
    first_name TEXT NOT NULL,
    middle_name TEXT,
    last_name TEXT NOT NULL,
    full_name TEXT NOT NULL,
    party TEXT NOT NULL,
    state TEXT NOT NULL,
    district INTEGER,
    birth_year INTEGER,
    current_member BOOLEAN NOT NULL DEFAULT true,
    honorific_prefix TEXT,
    official_url TEXT,
    office_address TEXT,
    phone TEXT,
    terms_served INTEGER,
    congress INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CHECK (party IN ('D', 'R', 'I', 'ID', 'L', 'Unknown'))
);

CREATE INDEX IF NOT EXISTS idx_members_bioguide ON members(bioguide_id);
CREATE INDEX IF NOT EXISTS idx_members_state ON members(state);
CREATE INDEX IF NOT EXISTS idx_members_party ON members(party);
CREATE INDEX IF NOT EXISTS idx_members_current ON members(current_member);
CREATE INDEX IF NOT EXISTS idx_members_congress ON members(congress);

-- Member Leadership Positions Table
CREATE TABLE IF NOT EXISTS member_leadership_positions (
    position_id SERIAL PRIMARY KEY,
    member_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    congress INTEGER NOT NULL,
    is_current BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (member_id) REFERENCES members(member_id),
    UNIQUE(member_id, title, congress)
);

CREATE INDEX IF NOT EXISTS idx_leadership_member ON member_leadership_positions(member_id);
CREATE INDEX IF NOT EXISTS idx_leadership_congress ON member_leadership_positions(congress);

-- Policy Areas Table
CREATE TABLE IF NOT EXISTS policy_areas (
    policy_area_id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Committee Jurisdictions Table
CREATE TABLE IF NOT EXISTS committee_jurisdictions (
    committee_id INTEGER NOT NULL,
    policy_area_id INTEGER NOT NULL,
    is_primary BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (committee_id, policy_area_id),
    FOREIGN KEY (committee_id) REFERENCES committees(committee_id),
    FOREIGN KEY (policy_area_id) REFERENCES policy_areas(policy_area_id)
);

CREATE INDEX IF NOT EXISTS idx_jurisdictions_committee ON committee_jurisdictions(committee_id);
CREATE INDEX IF NOT EXISTS idx_jurisdictions_policy ON committee_jurisdictions(policy_area_id);

-- Committee Memberships Table
CREATE TABLE IF NOT EXISTS committee_memberships (
    membership_id SERIAL PRIMARY KEY,
    committee_id INTEGER NOT NULL,
    member_id INTEGER NOT NULL,
    role TEXT NOT NULL,
    congress INTEGER NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    start_date DATE,
    end_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (committee_id) REFERENCES committees(committee_id),
    FOREIGN KEY (member_id) REFERENCES members(member_id),
    CHECK (role IN ('Chair', 'Ranking Member', 'Vice Chair', 'Member')),
    UNIQUE(committee_id, member_id, congress)
);

CREATE INDEX IF NOT EXISTS idx_memberships_committee ON committee_memberships(committee_id);
CREATE INDEX IF NOT EXISTS idx_memberships_member ON committee_memberships(member_id);
CREATE INDEX IF NOT EXISTS idx_memberships_role ON committee_memberships(role);
CREATE INDEX IF NOT EXISTS idx_memberships_active ON committee_memberships(is_active);

-- Hearings Table
CREATE TABLE IF NOT EXISTS hearings (
    hearing_id SERIAL PRIMARY KEY,
    event_id TEXT NOT NULL UNIQUE,
    congress INTEGER NOT NULL,
    chamber TEXT NOT NULL,
    title TEXT NOT NULL,
    hearing_type TEXT NOT NULL,
    status TEXT NOT NULL,
    hearing_date DATE,
    location TEXT,
    jacket_number TEXT,
    url TEXT,
    congress_gov_url TEXT,
    update_date TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    hearing_date_only DATE,
    hearing_time TIME,
    video_url TEXT,
    youtube_video_id TEXT,
    video_type TEXT,

    CHECK (chamber IN ('House', 'Senate', 'NoChamber')),
    CHECK (hearing_type IN ('Hearing', 'Meeting', 'Markup')),
    CHECK (status IN ('Scheduled', 'Canceled', 'Postponed', 'Rescheduled'))
);

CREATE INDEX IF NOT EXISTS idx_hearings_congress ON hearings(congress);
CREATE INDEX IF NOT EXISTS idx_hearings_chamber ON hearings(chamber);
CREATE INDEX IF NOT EXISTS idx_hearings_date ON hearings(hearing_date);
CREATE INDEX IF NOT EXISTS idx_hearings_status ON hearings(status);
CREATE INDEX IF NOT EXISTS idx_hearings_update_date ON hearings(update_date);
CREATE INDEX IF NOT EXISTS idx_hearings_jacket ON hearings(jacket_number);
CREATE INDEX IF NOT EXISTS idx_hearings_video ON hearings(youtube_video_id) WHERE youtube_video_id IS NOT NULL;

-- Hearing Committees Table
CREATE TABLE IF NOT EXISTS hearing_committees (
    hearing_id INTEGER NOT NULL,
    committee_id INTEGER NOT NULL,
    is_primary BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (hearing_id, committee_id),
    FOREIGN KEY (hearing_id) REFERENCES hearings(hearing_id),
    FOREIGN KEY (committee_id) REFERENCES committees(committee_id)
);

CREATE INDEX IF NOT EXISTS idx_hearing_committees_hearing ON hearing_committees(hearing_id);
CREATE INDEX IF NOT EXISTS idx_hearing_committees_committee ON hearing_committees(committee_id);

-- Bills Table
CREATE TABLE IF NOT EXISTS bills (
    bill_id SERIAL PRIMARY KEY,
    congress INTEGER NOT NULL,
    bill_type TEXT NOT NULL,
    bill_number INTEGER NOT NULL,
    title TEXT,
    url TEXT,
    introduced_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CHECK (bill_type IN ('HR', 'S', 'HJRES', 'SJRES', 'HCONRES', 'SCONRES', 'HRES', 'SRES')),
    UNIQUE(congress, bill_type, bill_number)
);

CREATE INDEX IF NOT EXISTS idx_bills_congress ON bills(congress);
CREATE INDEX IF NOT EXISTS idx_bills_type ON bills(bill_type);
CREATE INDEX IF NOT EXISTS idx_bills_number ON bills(bill_number);

-- Hearing Bills Table
CREATE TABLE IF NOT EXISTS hearing_bills (
    hearing_bill_id SERIAL PRIMARY KEY,
    hearing_id INTEGER NOT NULL,
    bill_id INTEGER NOT NULL,
    relationship_type TEXT NOT NULL,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (hearing_id) REFERENCES hearings(hearing_id),
    FOREIGN KEY (bill_id) REFERENCES bills(bill_id),
    CHECK (relationship_type IN ('primary_subject', 'mentioned', 'markup',
                                   'related', 'theoretical')),
    UNIQUE(hearing_id, bill_id)
);

CREATE INDEX IF NOT EXISTS idx_hearing_bills_hearing ON hearing_bills(hearing_id);
CREATE INDEX IF NOT EXISTS idx_hearing_bills_bill ON hearing_bills(bill_id);
CREATE INDEX IF NOT EXISTS idx_hearing_bills_type ON hearing_bills(relationship_type);

-- Witnesses Table
CREATE TABLE IF NOT EXISTS witnesses (
    witness_id SERIAL PRIMARY KEY,
    first_name TEXT,
    last_name TEXT,
    full_name TEXT NOT NULL,
    title TEXT,
    organization TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_witnesses_name ON witnesses(last_name, first_name);
CREATE INDEX IF NOT EXISTS idx_witnesses_org ON witnesses(organization);

-- Witness Appearances Table
CREATE TABLE IF NOT EXISTS witness_appearances (
    appearance_id SERIAL PRIMARY KEY,
    witness_id INTEGER NOT NULL,
    hearing_id INTEGER NOT NULL,
    position TEXT,
    witness_type TEXT,
    appearance_order INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (witness_id) REFERENCES witnesses(witness_id),
    FOREIGN KEY (hearing_id) REFERENCES hearings(hearing_id),
    UNIQUE(witness_id, hearing_id)
);

CREATE INDEX IF NOT EXISTS idx_appearances_witness ON witness_appearances(witness_id);
CREATE INDEX IF NOT EXISTS idx_appearances_hearing ON witness_appearances(hearing_id);

-- Hearing Transcripts Table
CREATE TABLE IF NOT EXISTS hearing_transcripts (
    transcript_id SERIAL PRIMARY KEY,
    hearing_id INTEGER NOT NULL,
    jacket_number TEXT,
    title TEXT,
    document_url TEXT,
    pdf_url TEXT,
    html_url TEXT,
    format_type TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (hearing_id) REFERENCES hearings(hearing_id)
);

CREATE INDEX IF NOT EXISTS idx_transcripts_hearing ON hearing_transcripts(hearing_id);
CREATE INDEX IF NOT EXISTS idx_transcripts_jacket ON hearing_transcripts(jacket_number);
CREATE UNIQUE INDEX IF NOT EXISTS idx_transcripts_unique ON hearing_transcripts(hearing_id, document_url);

-- Witness Documents Table
CREATE TABLE IF NOT EXISTS witness_documents (
    document_id SERIAL PRIMARY KEY,
    appearance_id INTEGER NOT NULL,
    document_type TEXT NOT NULL,
    title TEXT,
    document_url TEXT,
    format_type TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (appearance_id) REFERENCES witness_appearances(appearance_id),
    CHECK (document_type IN ('Statement', 'Biography', 'Truth Statement',
                              'Questions for Record', 'Supplemental'))
);

CREATE INDEX IF NOT EXISTS idx_witness_docs_appearance ON witness_documents(appearance_id);
CREATE INDEX IF NOT EXISTS idx_witness_docs_type ON witness_documents(document_type);
CREATE UNIQUE INDEX IF NOT EXISTS idx_witness_docs_unique ON witness_documents(appearance_id, document_url);

-- Supporting Documents Table
CREATE TABLE IF NOT EXISTS supporting_documents (
    document_id SERIAL PRIMARY KEY,
    hearing_id INTEGER NOT NULL,
    document_type TEXT NOT NULL,
    title TEXT,
    description TEXT,
    document_url TEXT,
    format_type TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (hearing_id) REFERENCES hearings(hearing_id)
);

CREATE INDEX IF NOT EXISTS idx_supporting_docs_hearing ON supporting_documents(hearing_id);
CREATE INDEX IF NOT EXISTS idx_supporting_docs_type ON supporting_documents(document_type);
CREATE UNIQUE INDEX IF NOT EXISTS idx_supporting_docs_unique ON supporting_documents(hearing_id, document_url);

-- Sync Tracking Table
CREATE TABLE IF NOT EXISTS sync_tracking (
    sync_id SERIAL PRIMARY KEY,
    entity_type TEXT NOT NULL,
    last_sync_timestamp TIMESTAMP NOT NULL,
    records_processed INTEGER,
    errors_count INTEGER,
    status TEXT NOT NULL,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CHECK (entity_type IN ('committees', 'members', 'hearings', 'bills', 'documents')),
    CHECK (status IN ('success', 'partial', 'failed'))
);

CREATE INDEX IF NOT EXISTS idx_sync_entity ON sync_tracking(entity_type);
CREATE INDEX IF NOT EXISTS idx_sync_timestamp ON sync_tracking(last_sync_timestamp);

-- Import Errors Table
CREATE TABLE IF NOT EXISTS import_errors (
    error_id SERIAL PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_identifier TEXT,
    error_type TEXT NOT NULL,
    error_message TEXT NOT NULL,
    severity TEXT NOT NULL,
    is_resolved BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CHECK (error_type IN ('validation', 'api_error', 'parse_error', 'network_error')),
    CHECK (severity IN ('critical', 'warning'))
);

CREATE INDEX IF NOT EXISTS idx_errors_entity ON import_errors(entity_type);
CREATE INDEX IF NOT EXISTS idx_errors_severity ON import_errors(severity);
CREATE INDEX IF NOT EXISTS idx_errors_resolved ON import_errors(is_resolved);

-- Update Logs Table
CREATE TABLE IF NOT EXISTS update_logs (
    log_id SERIAL PRIMARY KEY,
    update_date DATE NOT NULL,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    duration_seconds REAL,
    hearings_checked INTEGER DEFAULT 0,
    hearings_updated INTEGER DEFAULT 0,
    hearings_added INTEGER DEFAULT 0,
    committees_updated INTEGER DEFAULT 0,
    witnesses_updated INTEGER DEFAULT 0,
    api_requests INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    errors TEXT,
    success BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    trigger_source TEXT DEFAULT 'manual',
    schedule_id INTEGER
);

CREATE INDEX IF NOT EXISTS idx_update_logs_schedule ON update_logs(schedule_id);
CREATE INDEX IF NOT EXISTS idx_update_logs_source ON update_logs(trigger_source);

-- Scheduled Tasks Table
CREATE TABLE IF NOT EXISTS scheduled_tasks (
    task_id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    schedule_cron TEXT NOT NULL,
    lookback_days INTEGER NOT NULL DEFAULT 7,
    components TEXT NOT NULL,
    chamber TEXT DEFAULT 'both',
    mode TEXT NOT NULL DEFAULT 'incremental',
    is_active BOOLEAN NOT NULL DEFAULT true,
    is_deployed BOOLEAN NOT NULL DEFAULT false,
    last_run_at TIMESTAMP,
    next_run_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT DEFAULT 'admin',

    CHECK (lookback_days BETWEEN 1 AND 90),
    CHECK (chamber IN ('both', 'house', 'senate')),
    CHECK (mode IN ('incremental', 'full'))
);

CREATE INDEX IF NOT EXISTS idx_scheduled_tasks_active ON scheduled_tasks(is_active);
CREATE INDEX IF NOT EXISTS idx_scheduled_tasks_deployed ON scheduled_tasks(is_deployed);
CREATE INDEX IF NOT EXISTS idx_scheduled_tasks_next_run ON scheduled_tasks(next_run_at);

-- Add foreign key for update_logs.schedule_id (after scheduled_tasks is created)
ALTER TABLE update_logs
ADD CONSTRAINT fk_update_logs_schedule
FOREIGN KEY (schedule_id) REFERENCES scheduled_tasks(task_id);

-- Schedule Execution Logs Table
CREATE TABLE IF NOT EXISTS schedule_execution_logs (
    execution_id SERIAL PRIMARY KEY,
    schedule_id INTEGER NOT NULL,
    log_id INTEGER NOT NULL,
    execution_time TIMESTAMP NOT NULL,
    success BOOLEAN NOT NULL,
    error_message TEXT,
    config_snapshot TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (schedule_id) REFERENCES scheduled_tasks(task_id),
    FOREIGN KEY (log_id) REFERENCES update_logs(log_id),
    UNIQUE(schedule_id, log_id)
);

CREATE INDEX IF NOT EXISTS idx_schedule_exec_schedule ON schedule_execution_logs(schedule_id);
CREATE INDEX IF NOT EXISTS idx_schedule_exec_time ON schedule_execution_logs(execution_time);
CREATE INDEX IF NOT EXISTS idx_schedule_exec_success ON schedule_execution_logs(success);
