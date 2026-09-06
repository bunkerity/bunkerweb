"""`PUT /instances/bulk` must refuse any method whose rows can hold an enrollment.

The route is a DELETE-by-method followed by a re-INSERT of the payload, so a call that omits a
hostname deletes it -- with the credential the control plane minted for it. L-A closed `"ui"` for
that reason. `"manual"` became exactly as dangerous on 2026-09-02, when environment-declared
instances became enrollable: `save_config.py`'s rebuild carries a minted credential across only
because it sends again the whole roster from the environment, which an API caller cannot reproduce.

Derived from `ENROLLABLE_METHODS`, never hard-coded: the set widened once already, and a frozen
list here would silently stop covering the next method added to it.
"""

import pytest

from db_methods.instances import ENROLLABLE_METHODS  # type: ignore

from schemas import _ALLOWED_INSTANCE_BULK_METHODS, _validate_instance_bulk_method  # type: ignore  (src/api/app on sys.path)


@pytest.mark.parametrize("method", ENROLLABLE_METHODS)
def test_no_enrollable_method_can_be_bulk_reconciled(method):
    """The property, not the list: whatever can be enrolled cannot be bulk-deleted by method."""
    assert method not in _ALLOWED_INSTANCE_BULK_METHODS
    with pytest.raises(ValueError, match="not allowed for bulk instance operations"):
        _validate_instance_bulk_method(method)


@pytest.mark.parametrize("method", ("autoconf", "scheduler", "wizard"))
def test_the_reconciles_that_own_no_enrollment_still_work(method):
    """Closing the door must not close the workflow: autoconf's reconcile is this route's only
    in-tree caller, and it is not enrollable."""
    assert _validate_instance_bulk_method(method) == method


def test_manual_is_the_one_that_moved():
    """Named explicitly so the reason survives in the diff: this is not a tidy-up, it is the
    consequence of `manual` becoming enrollable."""
    assert "manual" in ENROLLABLE_METHODS
    assert "manual" not in _ALLOWED_INSTANCE_BULK_METHODS
