"""Database models for statements, ledger entries, matches, runs and breaks."""

import uuid

from django.db import models
from django.db.models import Q
from django.utils import timezone


class Direction(models.TextChoices):
    CREDIT = "C", "Credit"
    DEBIT = "D", "Debit"


def money_field() -> models.DecimalField:
    """Return the decimal field used for every monetary amount."""
    return models.DecimalField(max_digits=18, decimal_places=2)


class Account(models.Model):
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=128)
    currency = models.CharField(max_length=3)

    def __str__(self) -> str:
        return self.code


class Statement(models.Model):
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="statements")
    statement_ref = models.CharField(max_length=35)
    sequence = models.CharField(max_length=16)
    opening_cd = models.CharField(max_length=1, choices=Direction.choices)
    opening_amount = money_field()
    opening_date = models.DateField()
    closing_cd = models.CharField(max_length=1, choices=Direction.choices)
    closing_amount = money_field()
    closing_date = models.DateField()
    file_hash = models.CharField(max_length=64, unique=True)
    loaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.statement_ref} ({self.closing_date})"


class StatementLine(models.Model):
    statement = models.ForeignKey(Statement, on_delete=models.CASCADE, related_name="lines")
    row_index = models.PositiveIntegerField()
    value_date = models.DateField()
    book_date = models.DateField(null=True, blank=True)
    cd = models.CharField(max_length=1, choices=Direction.choices)
    amount = money_field()
    ref_ours = models.CharField(max_length=35, blank=True)
    ref_theirs = models.CharField(max_length=35, blank=True)
    narrative = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["statement", "row_index"], name="statement_line_unique_row"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.statement_id}#{self.row_index} {self.cd} {self.amount}"


class Match(models.Model):
    class State(models.TextChoices):
        AUTO = "auto", "Auto"
        PENDING_REVIEW = "pending_review", "Pending review"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    score = models.DecimalField(max_digits=4, decimal_places=3)
    rule = models.CharField(max_length=32)
    state = models.CharField(max_length=16, choices=State.choices)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.CharField(max_length=128, blank=True)
    reason = models.TextField(blank=True)
    statement_lines = models.ManyToManyField(StatementLine, related_name="matches")

    def __str__(self) -> str:
        return f"{self.id} {self.state} {self.score}"


class LedgerEntry(models.Model):
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="ledger_entries")
    entry_ref = models.CharField(max_length=64)
    value_date = models.DateField()
    cd = models.CharField(max_length=1, choices=Direction.choices)
    amount = money_field()
    ref = models.CharField(max_length=64, blank=True)
    narrative = models.TextField(blank=True)
    is_matched = models.BooleanField(default=False, db_index=True)
    matched_at = models.DateTimeField(null=True, blank=True)
    match = models.ForeignKey(
        Match,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="ledger_entries",
    )

    class Meta:
        verbose_name_plural = "ledger entries"
        constraints = [
            models.UniqueConstraint(
                fields=["account", "entry_ref"], name="ledger_entry_unique_ref"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.entry_ref} {self.cd} {self.amount}"


class ReconRun(models.Model):
    class State(models.TextChoices):
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"

    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="recon_runs")
    as_of_date = models.DateField()
    state = models.CharField(max_length=16, choices=State.choices, default=State.RUNNING)
    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True)
    lines_in = models.PositiveIntegerField(default=0)
    entries_in = models.PositiveIntegerField(default=0)
    auto_count = models.PositiveIntegerField(default=0)
    review_count = models.PositiveIntegerField(default=0)
    break_count = models.PositiveIntegerField(default=0)

    def __str__(self) -> str:
        return f"run {self.pk} {self.as_of_date} {self.state}"


class Break(models.Model):
    class Side(models.TextChoices):
        STATEMENT = "statement", "Statement"
        LEDGER = "ledger", "Ledger"

    class State(models.TextChoices):
        OPEN = "open", "Open"
        RESOLVED = "resolved", "Resolved"

    run = models.ForeignKey(ReconRun, on_delete=models.CASCADE, related_name="breaks")
    side = models.CharField(max_length=16, choices=Side.choices)
    statement_line = models.ForeignKey(
        StatementLine, null=True, blank=True, on_delete=models.CASCADE, related_name="breaks"
    )
    ledger_entry = models.ForeignKey(
        LedgerEntry, null=True, blank=True, on_delete=models.CASCADE, related_name="breaks"
    )
    state = models.CharField(max_length=16, choices=State.choices, default=State.OPEN)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(side="statement", statement_line__isnull=False, ledger_entry__isnull=True)
                    | Q(side="ledger", ledger_entry__isnull=False, statement_line__isnull=True)
                ),
                name="break_side_matches_item",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.side} break {self.pk} ({self.state})"
