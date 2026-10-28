"""Lightweight tests for the approval state transition rules."""

def can_submit(status):
    return status in ("draft", "rejected")

def can_decide(status):
    return status == "pending_approval"

def test_draft_can_be_submitted():
    assert can_submit("draft")

def test_rejected_can_be_resubmitted():
    assert can_submit("rejected")

def test_approved_cannot_be_resubmitted_directly():
    assert not can_submit("approved")

def test_only_pending_can_be_decided():
    assert can_decide("pending_approval")
    assert not can_decide("draft")
