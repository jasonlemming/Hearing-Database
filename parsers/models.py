"""
Pydantic models for data validation
"""
from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, Field, validator


class CommitteeModel(BaseModel):
    """Committee data model"""
    system_code: str
    name: str
    chamber: str
    type: str
    parent_committee_id: Optional[int] = None
    is_current: bool = True
    url: Optional[str] = None
    congress: int

    @validator('chamber')
    def validate_chamber(cls, v):
        valid_chambers = ['House', 'Senate', 'Joint', 'NoChamber']
        if v not in valid_chambers:
            raise ValueError(f'Chamber must be one of {valid_chambers}')
        return v

    @validator('type')
    def validate_type(cls, v):
        valid_types = ['Standing', 'Select', 'Special', 'Joint', 'Task Force',
                      'Other', 'Subcommittee', 'Commission or Caucus']
        if v not in valid_types:
            raise ValueError(f'Type must be one of {valid_types}')
        return v

    class Config:
        str_strip_whitespace = True


class MemberModel(BaseModel):
    """Member data model"""
    bioguide_id: str
    first_name: str
    middle_name: Optional[str] = None
    last_name: str
    full_name: str
    party: str
    state: str
    district: Optional[int] = None
    birth_year: Optional[int] = None
    current_member: bool = True
    honorific_prefix: Optional[str] = None
    official_url: Optional[str] = None
    office_address: Optional[str] = None
    phone: Optional[str] = None
    terms_served: Optional[int] = None
    congress: int

    @validator('party')
    def validate_party(cls, v):
        valid_parties = ['D', 'R', 'I', 'ID', 'L', 'Unknown']
        if v not in valid_parties:
            raise ValueError(f'Party must be one of {valid_parties}')
        return v

    @validator('state')
    def validate_state(cls, v):
        if len(v) != 2:
            raise ValueError('State must be 2-letter code')
        return v.upper()

    @validator('birth_year')
    def validate_birth_year(cls, v):
        if v is not None and (v < 1900 or v > 2010):
            raise ValueError('Birth year must be between 1900 and 2010')
        return v

    class Config:
        str_strip_whitespace = True


class HearingModel(BaseModel):
    """Hearing data model"""
    event_id: str
    congress: int
    chamber: str
    title: str
    hearing_type: str
    status: str
    hearing_date: Optional[date] = None
    location: Optional[str] = None
    jacket_number: Optional[str] = None
    url: Optional[str] = None
    congress_gov_url: Optional[str] = None
    update_date: Optional[datetime] = None

    @validator('chamber')
    def validate_chamber(cls, v):
        valid_chambers = ['House', 'Senate', 'NoChamber']
        if v not in valid_chambers:
            raise ValueError(f'Chamber must be one of {valid_chambers}')
        return v

    @validator('hearing_type')
    def validate_hearing_type(cls, v):
        valid_types = ['Hearing', 'Meeting', 'Markup']
        if v not in valid_types:
            raise ValueError(f'Hearing type must be one of {valid_types}')
        return v

    @validator('status')
    def validate_status(cls, v):
        valid_statuses = ['Scheduled', 'Canceled', 'Postponed', 'Rescheduled']
        if v not in valid_statuses:
            raise ValueError(f'Status must be one of {valid_statuses}')
        return v

    class Config:
        str_strip_whitespace = True


class BillModel(BaseModel):
    """Bill data model"""
    congress: int
    bill_type: str
    bill_number: int
    title: Optional[str] = None
    url: Optional[str] = None
    introduced_date: Optional[date] = None

    @validator('bill_type')
    def validate_bill_type(cls, v):
        valid_types = ['HR', 'S', 'HJRES', 'SJRES', 'HCONRES', 'SCONRES', 'HRES', 'SRES']
        if v not in valid_types:
            raise ValueError(f'Bill type must be one of {valid_types}')
        return v

    @validator('bill_number')
    def validate_bill_number(cls, v):
        if v <= 0:
            raise ValueError('Bill number must be positive')
        return v

    class Config:
        str_strip_whitespace = True


class WitnessModel(BaseModel):
    """Witness data model"""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    full_name: str
    title: Optional[str] = None
    organization: Optional[str] = None

    @validator('full_name')
    def validate_full_name(cls, v):
        if not v or not v.strip():
            raise ValueError('Full name is required')
        return v

    class Config:
        str_strip_whitespace = True


class WitnessAppearanceModel(BaseModel):
    """Witness appearance data model"""
    witness_id: int
    hearing_id: int
    position: Optional[str] = None
    witness_type: Optional[str] = None
    appearance_order: Optional[int] = None

    class Config:
        str_strip_whitespace = True


class CommitteeMembershipModel(BaseModel):
    """Committee membership data model"""
    committee_id: int
    member_id: int
    role: str
    congress: int
    is_active: bool = True
    start_date: Optional[date] = None
    end_date: Optional[date] = None

    @validator('role')
    def validate_role(cls, v):
        valid_roles = ['Chair', 'Ranking Member', 'Vice Chair', 'Member']
        if v not in valid_roles:
            raise ValueError(f'Role must be one of {valid_roles}')
        return v

    class Config:
        str_strip_whitespace = True


class HearingBillModel(BaseModel):
    """Hearing-bill relationship data model"""
    hearing_id: int
    bill_id: int
    relationship_type: str
    notes: Optional[str] = None

    @validator('relationship_type')
    def validate_relationship_type(cls, v):
        valid_types = ['primary_subject', 'mentioned', 'markup', 'related', 'theoretical']
        if v not in valid_types:
            raise ValueError(f'Relationship type must be one of {valid_types}')
        return v

    class Config:
        str_strip_whitespace = True


class DocumentModel(BaseModel):
    """Document data model"""
    title: Optional[str] = None
    document_url: Optional[str] = None
    format_type: Optional[str] = None

    class Config:
        str_strip_whitespace = True


class HearingTranscriptModel(DocumentModel):
    """Hearing transcript data model"""
    hearing_id: int
    jacket_number: Optional[str] = None
    pdf_url: Optional[str] = None
    html_url: Optional[str] = None


class WitnessDocumentModel(DocumentModel):
    """Witness document data model"""
    appearance_id: int
    document_type: str

    @validator('document_type')
    def validate_document_type(cls, v):
        valid_types = ['Statement', 'Biography', 'Truth Statement',
                      'Questions for Record', 'Supplemental']
        if v not in valid_types:
            raise ValueError(f'Document type must be one of {valid_types}')
        return v


class SupportingDocumentModel(DocumentModel):
    """Supporting document data model"""
    hearing_id: int
    document_type: str
    description: Optional[str] = None