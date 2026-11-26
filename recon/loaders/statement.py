"""Load an MT940 statement file into Statement and StatementLine rows."""

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path

from django.db import transaction

from recon.exceptions import ParseError
from recon.models import Account, Statement, StatementLine
from recon.parsers.mt940 import parse_mt940

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StatementLoadResult:
    statement: Statement
    created: bool
    line_count: int


def load_statement(path: Path, account: Account) -> StatementLoadResult:
    """Load an MT940 file for an account, skipping files whose hash was already loaded."""
    content = path.read_bytes()
    file_hash = hashlib.sha256(content).hexdigest()

    existing_statement = Statement.objects.filter(file_hash=file_hash).first()
    if existing_statement is not None:
        return StatementLoadResult(
            statement=existing_statement,
            created=False,
            line_count=existing_statement.lines.count(),
        )

    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ParseError(f"{path.name} is not valid UTF-8") from exc
    parsed = parse_mt940(text)

    with transaction.atomic():
        statement = Statement.objects.create(
            account=account,
            statement_ref=parsed.statement_ref,
            sequence=parsed.sequence,
            opening_cd=parsed.opening_cd,
            opening_amount=parsed.opening_amount,
            opening_date=parsed.opening_date,
            closing_cd=parsed.closing_cd,
            closing_amount=parsed.closing_amount,
            closing_date=parsed.closing_date,
            file_hash=file_hash,
        )
        StatementLine.objects.bulk_create(
            StatementLine(
                statement=statement,
                row_index=row_index,
                value_date=parsed_line.value_date,
                book_date=parsed_line.book_date,
                cd=parsed_line.cd,
                amount=parsed_line.amount,
                ref_ours=parsed_line.ref_ours,
                ref_theirs=parsed_line.ref_theirs,
                narrative=parsed_line.narrative,
            )
            for row_index, parsed_line in enumerate(parsed.lines, start=1)
        )

    logger.info(
        "loaded statement %s with %d lines for %s",
        statement.statement_ref,
        len(parsed.lines),
        account.code,
    )
    return StatementLoadResult(statement=statement, created=True, line_count=len(parsed.lines))
