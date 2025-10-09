# Congressional Hearing Database - User Guide

A friendly guide to exploring congressional hearings, witnesses, and committee activity using the web interface.

## Getting Started

### Accessing the Database

**Public Instance** (if available):
Visit the deployed site at your Vercel URL

**Local Installation**:
```bash
git clone <repository-url>
cd Hearing-Database
pip install -r requirements.txt
python cli.py web serve
```

Then open http://localhost:5000 in your browser.

## Main Features

### 1. Browse Hearings

The hearings page is your starting point for exploring congressional activity.

**Access**: Click "Hearings" in the navigation or visit `/hearings`

#### Search & Filter

**Text Search**:
- Type keywords in the search box to find hearings by title or committee name
- Examples: "climate change", "defense budget", "agriculture"

**Filter by Chamber**:
- **House** - House of Representatives hearings
- **Senate** - Senate hearings
- **All** - Both chambers

**Filter by Committee**:
- Use the committee dropdown to focus on specific committees
- Examples: "Ways and Means", "Armed Services", "Appropriations"

**Filter by Date**:
- Set "From" and "To" dates to narrow your timeframe
- Useful for tracking recent activity or specific periods

**Sort Results**:
- **By Date** (newest/oldest first)
- **By Title** (alphabetical)
- **By Committee** (alphabetical)
- **By Chamber** (House/Senate)
- **By Status** (scheduled, held, postponed)

#### Understanding Hearing Information

Each hearing shows:
- **Title**: Official hearing title
- **Date**: When the hearing occurred or is scheduled
- **Committee**: Which committee held/will hold it
- **Chamber**: House or Senate
- **Status**: Scheduled, Held, Postponed, or Cancelled

### 2. View Hearing Details

Click any hearing title to see comprehensive information.

**What You'll Find**:

**Basic Information**:
- Full title and description
- Date and time
- Status and hearing type
- Location (if available)
- Associated committees

**Witnesses**:
- List of all testifying witnesses
- Their titles and organizations
- Witness type (Government, Private, Academic, Nonprofit)
- Click witness names to see their full testimony history

**Documents**:
- **Transcripts**: Official hearing transcripts (when available)
- **Witness Statements**: Written testimony submitted by witnesses
- **Supporting Documents**: Additional materials submitted
- Links to official Congress.gov documents

**Related Bills**:
- Legislation discussed in the hearing (when tracked)

### 3. Explore Committees

Track specific committee activities and membership.

**Access**: Click "Committees" in the navigation

#### Committee List

**What You See**:
- Parent committees (main committees)
- Subcommittees (nested under parents)
- Hearing counts for each committee
- Chamber designation (House, Senate, Joint)

**Filter Options**:
- Chamber (House/Senate/Joint)
- Committee type (Standing, Select, Joint)

#### Committee Detail Pages

Click any committee to see:

**Overview**:
- Full committee name
- Parent committee (if a subcommittee)
- Chamber and type
- System code (for reference)

**Recent Hearings**:
- All hearings held by this committee
- Sorted by date (newest first)
- Quick access to hearing details

**Subcommittees**:
- List of all subcommittees (if parent committee)
- Links to subcommittee pages

**Members**:
- Current committee membership
- Member names, party, and state
- Roles (Chair, Ranking Member, Member)

### 4. Track Congressional Members

See what your representatives are working on.

**Access**: Click "Members" in the navigation

#### Member Search

**Filter by**:
- **Party**: Democrat, Republican, Independent
- **State**: All 50 states
- **Chamber**: House or Senate
- **Committee**: See members of specific committees

**What You See**:
- Member name and photo (if available)
- Party affiliation
- State and district (for House members)
- Committee memberships

#### Member Detail Pages

Click any member to see:

**Profile Information**:
- Full name and title
- Party and state
- District (House members)
- Contact information (if available)

**Committee Assignments**:
- All committees they serve on
- Role on each committee
- Active status

**Hearing Participation**:
- Hearings their committees held
- Recent activity timeline

### 5. Explore Witnesses

Discover who's testifying before Congress and organizational representation patterns.

**Access**: Click "Witnesses" in the navigation

#### Witness List

**Search & Filter**:
- **Text Search**: Find witnesses by name or organization
- **Witness Type**:
  - **Government**: Federal, state, local officials
  - **Private**: Corporate representatives, individuals
  - **Academic**: Researchers, university affiliates
  - **Nonprofit**: NGO and advocacy group representatives

**Sort Options**:
- By name (alphabetical)
- By hearing count (most/least appearances)
- By organization

#### Witness Detail Pages

Click any witness to see:

**Profile**:
- Full name
- Title and position
- Organization/affiliation
- Witness type

**Testimony History**:
- All hearings where they testified
- Dates and committees
- Links to hearing details and documents
- Timeline of appearances

**Analysis**:
- Number of appearances
- Committees testified before
- Date range of testimony
- Associated documents

### 6. Search Across Everything

Use global search to find information across all data.

**Access**: Click "Search" or use the search box in navigation

**Search Includes**:
- Hearing titles and descriptions
- Witness names and organizations
- Committee names
- Member names
- Document titles

**Tips for Better Results**:
- Use specific terms ("climate adaptation" vs "climate")
- Try organization names ("EPA", "USDA", "Microsoft")
- Search member names ("Schumer", "Johnson")
- Use date filters to narrow results

## Common Use Cases

### Track a Topic

**Goal**: Monitor hearings on climate change

1. Go to Hearings
2. Search for "climate"
3. Apply date filter (last 6 months)
4. Sort by date (newest first)
5. Bookmark the filtered URL

### Follow a Committee

**Goal**: Track House Ways and Means Committee

1. Go to Committees
2. Filter by "House"
3. Find "Ways and Means"
4. Click to view details
5. Bookmark committee page for regular visits

### Monitor Your Representative

**Goal**: See what your senator is working on

1. Go to Members
2. Filter by your state
3. Select "Senate" chamber
4. Click your senator's name
5. Review committee assignments and recent hearings

### Analyze Witness Patterns

**Goal**: See who represents the tech industry

1. Go to Witnesses
2. Filter by "Private" witness type
3. Search for tech companies (search "Google", "Microsoft", "Meta")
4. Click witness names to see testimony history
5. Note frequency and committees

### Find Specific Documents

**Goal**: Locate transcript from a hearing

1. Go to Hearings
2. Find the specific hearing (use search/filters)
3. Click hearing title
4. Scroll to "Documents" section
5. Click transcript link (opens Congress.gov)

## Understanding the Data

### Data Coverage

**Current Scope**:
- **Congress**: 119th (2025-2027) - currently active
- **Hearings**: 1,168 total
  - 613 House hearings
  - 555 Senate hearings
- **Witnesses**: 1,545 individuals (1,620 total appearances)
- **Committees**: 53 parent committees + 161 subcommittees
- **Members**: 538 congressional members

**Updates**:
- Database updates daily at 6:00 AM UTC
- New hearings appear within 24 hours of being scheduled
- Document links update as Congress.gov publishes them

### Data Freshness

**Check Last Update**:
Visit `/api/update-status` to see:
- Last successful update time
- Number of hearings updated
- Update success/failure status

**Missing Data?**
Some hearings may not have:
- Transcripts (published weeks after hearing)
- Witness lists (for very recent hearings)
- Complete metadata (work in progress)

### Document Access

**Important Notes**:
- This database stores **links** to documents, not the full text
- Clicking document links takes you to official Congress.gov sources
- Some older hearings may not have digitized transcripts
- Witness statements published separately from transcripts

## Tips & Tricks

### Efficient Browsing

1. **Use Filters**: Narrow results before searching
2. **Bookmark Filters**: Save your filtered URLs for quick access
3. **Sort Strategically**: Use date sorting for recent activity, title sorting for browsing
4. **Check Related Info**: Click through witness names and committee links for more context

### Finding Specific Information

**To find recent activity on a topic**:
1. Search keywords in Hearings
2. Set date filter to last 30-90 days
3. Sort by date (newest first)

**To track organizational influence**:
1. Go to Witnesses
2. Search organization name
3. Review testimony frequency and committees
4. Click individual witnesses for full history

**To understand committee focus**:
1. Go to specific committee page
2. Review recent hearings
3. Note patterns in topics
4. Check subcommittee activities

### Mobile Access

The interface works on mobile devices:
- Responsive design adapts to screen size
- Filters collapse into dropdowns on small screens
- All features available on mobile

## Frequently Asked Questions

### How often is data updated?

The database updates automatically every day at 6:00 AM UTC, fetching new and modified hearings from the last 30 days.

### Why can't I find a specific hearing?

Possible reasons:
- Hearing was scheduled/held before the 119th Congress
- Very recent hearing (may take 24 hours to appear)
- Private or closed hearing (not publicly listed)
- Hearing was cancelled and removed from Congress.gov

### Where do the documents come from?

All document links point to official Congress.gov sources. This database doesn't host documents directly, ensuring you always get the official version.

### Can I download the data?

Yes! The database is open source and can be:
- Run locally (see Installation section)
- Queried via SQLite
- Accessed via JSON API (see API Reference)

### How do I report missing or incorrect data?

1. Check if the information is correct on Congress.gov
2. If Congress.gov has it but the database doesn't, wait 24 hours for next update
3. If still missing, open a GitHub issue with details

### Can I search full text of transcripts?

Currently no - the system stores links only. Full-text search may be added in the future if an alternative data source is identified.

## Keyboard Shortcuts

While no formal keyboard shortcuts exist, standard browser shortcuts work:

- **Ctrl/Cmd + F**: Find on page
- **Ctrl/Cmd + Click**: Open link in new tab
- **Tab**: Navigate through form fields
- **Enter**: Submit search/filter

## Getting Help

**Documentation**:
- [CLI Commands Reference](../../reference/cli-commands.md) - For technical users
- [API Reference](../../reference/API_REFERENCE.md) - For developers
- [Deployment Guide](../../deployment/DEPLOYMENT.md) - For hosting

**Support**:
- GitHub Issues - Report bugs or request features
- Check `/api/stats` for database statistics
- Review logs if running locally

## Privacy & Data Usage

**Public Data Only**:
- All data sourced from public Congress.gov API
- No user tracking or analytics
- No personal information collected
- No cookies required for browsing

**Disclaimer**:
This is an independent project not affiliated with Congress.gov or any government entity. Data accuracy depends on the official source.

---

**Happy exploring!** The Congressional Hearing Database makes government oversight more accessible. Use it to stay informed about what's happening in Congress.

---

**Last Updated**: October 9, 2025
**Target Audience**: End Users and Casual Browsers

[← Back: Quick Start](../../getting-started/quick-start.md) | [Up: Documentation Hub](../../README.md) | [Next: CLI Commands →](../../reference/cli-commands.md)
