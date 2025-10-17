# Legacy Database Files Archive

**Date Archived:** October 15, 2025
**Reason:** PostgreSQL migration completed - all data migrated to unified Neon Postgres database

## Files Archived

| File | Size | Status | Notes |
|------|------|--------|-------|
| `database.db` | 8.7MB | Stale | Main hearing database - superseded by Postgres |
| `brookings_products.db.gz` | 1.7MB | Stale | Policy library database - superseded by Postgres |
| `database_audit.db` | 2.0MB | Stale | Old audit database |
| `congressional_data.db` | 0B | Empty | Unused file |
| `congressional_hearings.db` | 0B | Empty | Unused file |
| `hearings.db` | 0B | Empty | Unused file |
| `hearings_database.db` | 0B | Empty | Unused file |

## Migration Details

All data from these SQLite databases has been successfully migrated to a unified PostgreSQL database hosted on Neon. The migration was completed and validated on October 15, 2025.

**Validation Report:** See `VALIDATION_REPORT.md` in the project root for complete validation results showing all 7/7 tests passed.

**Migration Documentation:** See `POSTGRES_MIGRATION.md` for complete migration details.

## Database Architecture (Current)

The application now uses:
- **Primary:** Neon PostgreSQL 17 (unified database for all projects)
- **Projects included:**
  - Congressional Hearing Database (1,340 hearings)
  - CRS Products Database (133 products)
  - Policy Library (133 documents)

**Total Records:** 12,255 records across 10 tables

## Can These Files Be Deleted?

Yes, these files can be safely deleted. They are retained in this archive for:
1. Historical reference
2. Emergency rollback capability (if needed within 30 days)
3. Data audit trail

**Recommended retention:** 30 days, then permanent deletion

## Rollback Instructions (If Needed)

If you need to temporarily rollback to SQLite:

1. Move desired `.db` file back to project root
2. Unset `POSTGRES_URL` in `.env`
3. Set `DATABASE_PATH=database.db` in `.env`
4. Restart application

The `UnifiedDatabaseManager` will automatically detect and use SQLite.

**Note:** Any data added to Postgres after the migration will NOT be in these SQLite files.

## References

- Migration completed: October 15, 2025
- Validation report: `/VALIDATION_REPORT.md`
- Migration documentation: `/POSTGRES_MIGRATION.md`
- Database manager: `/database/unified_manager.py`
