from app.core.database import SessionLocal
from app.services.audit_chain_service import record_chain_event, verify_chain_integrity


def test_chain_integrity_and_tamper(client):
    # client fixture ensures DB/tables exist
    _ = client
    db = SessionLocal()
    try:
        for i in range(5):
            record_chain_event(
                db,
                action=f"test.event.{i}",
                actor_id="u1",
                actor_role="regional_officer",
                mode="SIMULATED",
                result_summary={"i": i},
            )
        db.commit()
        ok = verify_chain_integrity(db)
        assert ok.ok is True
        assert ok.checked == 5

        # Tamper middle row
        from app.models.audit_chain import AuditChainEvent

        row = db.query(AuditChainEvent).filter(AuditChainEvent.sequence == 3).one()
        row.result_summary = "TAMPERED"
        db.commit()
        bad = verify_chain_integrity(db)
        assert bad.ok is False
        assert bad.first_bad_sequence == 3
    finally:
        db.close()
