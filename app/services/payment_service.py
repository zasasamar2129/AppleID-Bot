from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.sql import and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.models.enums import OrderStatus, PaymentMethod, PaymentStatus, WalletTransactionType
from app.database.models.order import Order
from app.database.models.payment import Payment
from app.database.repositories.inventory_repo import InventoryRepository
from app.database.repositories.order_repo import OrderRepository
from app.database.repositories.payment_repo import PaymentRepository
from app.database.repositories.wallet_repo import WalletRepository
from app.payments.base import PaymentProvider
from app.payments.online import get_online_payment_provider
from app.payments.sep import SepGatewayError
from app.utils.money import rial_to_toman, to_gateway_amount

logger = logging.getLogger(__name__)

# States an online payment may still be resolved from. Anything else is final.
RECONCILABLE_STATUSES = (
    PaymentStatus.PENDING,
    PaymentStatus.WAITING_USER,
    PaymentStatus.PENDING_VERIFICATION,
)


class PaymentError(Exception):
    """Business-level refusal. Safe to show to the user."""


class AmountMismatchError(PaymentError):
    """Verified amount does not match what we asked for. Financial alert."""


class PaymentAlreadyCompleted(Exception):
    """Another actor finished this payment first. Not an error."""


@dataclass(frozen=True)
class CompletionResult:
    """Outcome of one completion attempt."""

    payment_id: int
    paid: bool
    already_completed: bool = False
    amount_mismatch: bool = False
    reason: str = ""


class PaymentService:
    def __init__(self, session: AsyncSession, provider: PaymentProvider | None = None):
        self.session = session
        self.payment_repo = PaymentRepository(session)
        self.order_repo = OrderRepository(session)
        self.wallet_repo = WalletRepository(session)
        self.inventory_repo = InventoryRepository(session)
        self.provider = provider if provider else get_online_payment_provider()

    # ------------------------------------------------------------------
    # Creation
    # ------------------------------------------------------------------
    async def create_payment(
        self,
        order_id: int,
        user_id: int,
        method: PaymentMethod,
        amount: Decimal,
        currency: str = "IRR",
    ) -> Payment:
        data = {
            "order_id": order_id,
            "user_id": user_id,
            "method": method,
            "amount": amount,
            "currency": currency,
            "status": PaymentStatus.PENDING,
        }
        return await self.payment_repo.create(data)

    async def find_open_online_payment(self, user_id: int, order_id: int | None) -> Payment | None:
        """Return a still-open online payment for this user/order, if any.

        Used to refuse creating a second attempt while one is in flight.
        """
        stmt = select(Payment).where(
            and_(
                Payment.user_id == user_id,
                Payment.method == PaymentMethod.ONLINE,
                Payment.status.in_(RECONCILABLE_STATUSES),
                Payment.created_at >= datetime.utcnow() - timedelta(minutes=settings.payment_ttl_minutes),
            )
        )
        if order_id:
            stmt = stmt.where(Payment.order_id == order_id)
        stmt = stmt.order_by(Payment.created_at.desc()).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_online_payment(
        self,
        user_id: int,
        amount_toman: Decimal,
        order_id: int | None = None,
        currency: str = "IRR",
    ) -> tuple[Payment, dict[str, Any]]:
        """Create a durable payment record and obtain a gateway token.

        The record is committed BEFORE the gateway call so a crash between the
        two leaves an auditable row rather than an invisible half-attempt.
        The token is never proof of payment; only ``finalize`` is.
        """
        if not settings.is_online_payment_configured:
            raise PaymentError("gateway_unavailable")

        try:
            gateway_amount = to_gateway_amount(amount_toman)
        except ValueError as exc:
            raise PaymentError("invalid_amount") from exc

        payment = await self.create_payment(order_id, user_id, PaymentMethod.ONLINE, amount_toman, currency)
        payment.provider = "sep" if settings.sep_enabled else "custom_api"
        payment.gateway_amount = gateway_amount
        payment.tracking_code = f"{payment.id}{int(datetime.utcnow().timestamp())}"
        payment.expires_at = datetime.utcnow() + timedelta(minutes=settings.payment_ttl_minutes)
        await self.session.commit()

        logger.info(
            "payment_created payment_id=%s provider=%s amount=%s",
            payment.id,
            payment.provider,
            gateway_amount,
        )

        try:
            gateway_data = await self.provider.create_payment(
                payment.tracking_code, float(amount_toman), currency
            )
        except SepGatewayError as exc:
            # The gateway answered — this attempt is definitively dead.
            await self.payment_repo.update_status(
                payment.id,
                PaymentStatus.FAILED,
                {"failure_reason": str(exc)[:500]},
            )
            logger.warning("payment_create_failed payment_id=%s reason=%s", payment.id, exc)
            raise PaymentError("gateway_unavailable") from exc
        except Exception as exc:  # noqa: BLE001 - transport failure, outcome unknown
            # The request may still have reached Saman. Keep the row open so
            # reconciliation can resolve it instead of declaring defeat.
            await self.payment_repo.update_status(payment.id, PaymentStatus.PENDING_VERIFICATION)
            logger.warning(
                "payment_create_uncertain payment_id=%s error_type=%s",
                payment.id,
                type(exc).__name__,
            )
            raise PaymentError("gateway_unavailable") from exc

        payment.authority = gateway_data.get("token")
        payment.external_payment_id = gateway_data.get("token")
        payment.transaction_id = gateway_data.get("token")
        await self.session.commit()
        await self.session.refresh(payment)

        logger.info("payment_redirected payment_id=%s", payment.id)
        return payment, gateway_data

    # ------------------------------------------------------------------
    # Return from the gateway
    # ------------------------------------------------------------------
    async def record_gateway_return(
        self,
        tracking_code: str,
        state: str,
        reference_number: str | None,
        bank_meta: dict[str, Any] | None = None,
    ) -> Payment | None:
        """Persist what the bank's redirect told us. Never marks anything paid.

        ``State``/``RefNum`` arrive in a URL query string — unauthenticated,
        forgeable, and therefore only usable as a *pointer* to the payment we
        then verify server-side.
        """
        payment = await self.payment_repo.get_by_tracking_code(tracking_code)
        if not payment:
            logger.warning("payment_return_unknown tracking_code=%s", tracking_code)
            return None
        if payment.status == PaymentStatus.PAID:
            logger.info("payment_return_duplicate payment_id=%s", payment.id)
            return payment

        extra: dict[str, Any] = {"reference_number": reference_number}
        if bank_meta:
            extra["metadata"] = json.dumps(
                {k: v for k, v in bank_meta.items() if k.lower() not in {"token"}},
                default=str,
            )[:2000]

        if (state or "").upper() == "OK" and reference_number:
            new_status = PaymentStatus.PENDING_VERIFICATION
        elif payment.status in (PaymentStatus.PENDING, PaymentStatus.WAITING_USER):
            new_status = PaymentStatus.PENDING
            extra["failure_reason"] = f"gateway_state={state or 'unknown'}"
        else:
            return payment

        await self.payment_repo.update_status(payment.id, new_status, extra)
        logger.info(
            "payment_returned payment_id=%s state=%s new_status=%s",
            payment.id,
            state or "unknown",
            new_status.value,
        )
        return payment

    # ------------------------------------------------------------------
    # Verification + completion
    # ------------------------------------------------------------------
    async def finalize_payment(self, payment_id: int) -> CompletionResult:
        """Verify with the gateway and, only on a verified match, complete.

        Exactly-once is enforced by a row lock plus a status re-check inside
        the same transaction, so a duplicated callback, a racing scheduler run
        and an admin retry all collapse to one wallet credit / one fulfilment.

        Order of operations is deliberate: all network I/O happens *before*
        the transaction is opened, so the lock is held for one short write.
        """
        payment = await self.payment_repo.get_by_id(payment_id)
        if not payment:
            return CompletionResult(payment_id, paid=False, reason="not_found")

        # Fast path: already settled. Re-running must be a no-op.
        if payment.status == PaymentStatus.PAID:
            logger.info("payment_already_paid payment_id=%s", payment_id)
            return CompletionResult(payment_id, paid=True, already_completed=True)

        if payment.status not in RECONCILABLE_STATUSES:
            return CompletionResult(
                payment_id, paid=False, reason=f"status={payment.status.value}"
            )

        # --- network I/O, outside any transaction -----------------------
        try:
            verification = await self.provider.verify_payment(payment)
        except SepGatewayError as exc:
            # Indeterminate: leave the row reconcilable.
            logger.warning(
                "payment_verification_uncertain payment_id=%s reason=%s", payment_id, exc
            )
            return CompletionResult(payment_id, paid=False, reason="verify_unavailable")
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "payment_verification_error payment_id=%s error_type=%s",
                payment_id,
                type(exc).__name__,
            )
            return CompletionResult(payment_id, paid=False, reason="verify_error")

        if not verification.get("paid"):
            reason = str(verification.get("reason") or "declined")
            # A definitive decline from the bank is terminal.
            if reason not in {"missing_refnum", "verify_unavailable"}:
                await self.payment_repo.update_status(
                    payment.id,
                    PaymentStatus.FAILED,
                    {"failure_reason": reason[:500]},
                )
                logger.info(
                    "payment_verification_failed payment_id=%s reason=%s", payment_id, reason
                )
                return CompletionResult(payment_id, paid=False, reason=reason)
            return CompletionResult(payment_id, paid=False, reason=reason)

        # --- amount check, still outside the transaction ----------------
        mismatch = self._detect_amount_mismatch(payment, verification)
        if mismatch:
            logger.error(
                "payment_amount_mismatch payment_id=%s expected_gateway=%s verified=%s",
                payment_id,
                payment.gateway_amount,
                verification.get("verified_amount"),
            )
            await self.payment_repo.update_status(
                payment.id,
                PaymentStatus.PENDING_VERIFICATION,
                {"failure_reason": "amount_mismatch"},
            )
            return CompletionResult(
                payment_id, paid=False, amount_mismatch=True, reason="amount_mismatch"
            )

        # --- single atomic write ----------------------------------------
        try:
            result = await self._apply_completion(payment, verification)
        except PaymentAlreadyCompleted:
            return CompletionResult(payment_id, paid=True, already_completed=True)
        except Exception:  # noqa: BLE001 - roll back, keep it reconcilable
            await self.session.rollback()
            logger.exception("payment_completion_failed payment_id=%s", payment_id)
            return CompletionResult(payment_id, paid=False, reason="commit_failed")

        logger.info(
            "payment_verification_success payment_id=%s provider=%s amount=%s",
            payment_id,
            payment.provider,
            payment.gateway_amount,
        )
        return result

    def _detect_amount_mismatch(self, payment: Payment, verification: dict[str, Any]) -> bool:
        """True only when the bank reports an amount we can compare and it differs."""
        if payment.gateway_amount is None:
            return False

        reported = verification.get("verified_amount")
        if reported is None:
            # SEP did not echo an amount; we cannot contradict it. Fall back to
            # trusting the RefNum binding, which the bank will not re-issue.
            return False

        try:
            verified_rial = int(reported)
        except (TypeError, ValueError):
            logger.error(
                "payment_amount_unparseable payment_id=%s value=%r", payment.id, reported
            )
            return True

        if verified_rial == int(payment.gateway_amount):
            return False

        # Some terminals report Toman; accept the ×10 relationship as a match
        # rather than flagging a false positive on a correct payment.
        if verified_rial * 10 == int(payment.gateway_amount):
            logger.info(
                "payment_amount_unit_variant payment_id=%s verified_toman=%s",
                payment.id,
                verified_rial,
            )
            return False
        if verified_rial == int(payment.gateway_amount) * 10:
            return False

        return True

    async def _apply_completion(
        self, payment: Payment, verification: dict[str, Any]
    ) -> CompletionResult:
        """Flip the payment to PAID and perform the business effect, once."""
        # Lock the row; everything below is conditional on what we read back.
        locked = await self.payment_repo.get_for_update(payment.id)
        if locked is None:
            await self.session.rollback()
            return CompletionResult(payment.id, paid=False, reason="row_gone")
        if locked.status == PaymentStatus.PAID:
            await self.session.rollback()
            return CompletionResult(payment.id, paid=True, already_completed=True)

        now = datetime.utcnow()
        external_id = verification.get("external_id")

        locked.status = PaymentStatus.PAID
        locked.verified_at = now
        locked.updated_at = now
        locked.failure_reason = None
        if external_id:
            locked.external_payment_id = str(external_id)

        if locked.order_id:
            order = await self.order_repo.get_by_id(locked.order_id)
            if order and order.status == OrderStatus.PENDING_PAYMENT:
                await self.order_repo.update_status(
                    order.id,
                    OrderStatus.PAID,
                    {"paid_at": now, "payment_method": PaymentMethod.ONLINE},
                    commit=False,
                )
        else:
            # Wallet top-up: credit exactly once, keyed on the payment id so a
            # replayed completion cannot mint a second ledger row.
            reference = f"payment:{locked.id}"
            existing = await self.wallet_repo.get_transaction_by_reference(reference)
            if existing is None:
                await self._credit_wallet_once(locked, reference, now)

        # One commit covers payment + order + wallet + ledger.
        await self.session.commit()

        return CompletionResult(payment.id, paid=True)

    async def _credit_wallet_once(
        self, payment: Payment, reference: str, now: datetime
    ) -> None:
        wallet = await self.wallet_repo.get_or_create(payment.user_id)
        amount_toman = Decimal(payment.amount)
        new_balance = wallet.balance + amount_toman
        await self.wallet_repo.update_balance(wallet.id, new_balance, commit=False)
        await self.wallet_repo.add_transaction(
            wallet.id,
            WalletTransactionType.DEPOSIT,
            amount_toman,
            new_balance,
            reference_id=reference,
            description=f"Online payment #{payment.id}",
            commit=False,
        )

    # ------------------------------------------------------------------
    # Legacy helpers still used by the card-to-card path
    # ------------------------------------------------------------------
    async def verify_online_payment(self, payment: Payment) -> bool:
        result = await self.finalize_payment(payment.id)
        return result.paid

    async def mark_payment_paid(self, payment_id: int, external_id: str | None = None) -> Payment | None:
        payment = await self.payment_repo.get_by_id(payment_id)
        if not payment or payment.status == PaymentStatus.PAID:
            return payment
        extra = {"external_payment_id": external_id} if external_id else None
        return await self.payment_repo.update_status(payment_id, PaymentStatus.PAID, extra)

    async def process_wallet_payment(self, order: Order, user_id: int) -> bool:
        wallet = await self.wallet_repo.get_or_create(user_id)
        if wallet.balance < order.final_price:
            return False
        wallet.balance -= order.final_price
        await self.wallet_repo.update_balance(wallet.id, wallet.balance)
        await self.wallet_repo.add_transaction(
            wallet.id,
            WalletTransactionType.PURCHASE,
            -order.final_price,
            wallet.balance,
            reference_id=str(order.id),
            description=f"Purchase order {order.id}",
        )
        await self.order_repo.update_status(
            order.id,
            OrderStatus.PAID,
            {"paid_at": datetime.utcnow(), "payment_method": PaymentMethod.WALLET},
        )
        return True

    async def create_card_payment(
        self, order: Order, user_id: int, card_number: str, holder: str, bank: str
    ) -> Payment:
        payment = await self.create_payment(
            order.id, user_id, PaymentMethod.CARD_TO_CARD, order.final_price
        )
        payment.status = PaymentStatus.WAITING_USER
        await self.session.commit()
        return payment

    async def submit_card_receipt(
        self, payment_id: int, receipt_file_id: str, reference: str | None = None
    ) -> Payment | None:
        return await self.payment_repo.update_status(
            payment_id,
            PaymentStatus.PENDING_VERIFICATION,
            {"receipt_file_id": receipt_file_id, "transaction_id": reference},
        )

    async def approve_card_payment(self, payment_id: int, admin_id: int) -> Payment | None:
        payment = await self.payment_repo.get_by_id(payment_id)
        if not payment or payment.status == PaymentStatus.PAID:
            return payment
        payment.verified_by = admin_id
        paid = await self.payment_repo.update_status(payment_id, PaymentStatus.PAID)
        if paid and paid.order_id:
            order = await self.order_repo.get_by_id(paid.order_id)
            if order and order.status == OrderStatus.PENDING_PAYMENT:
                await self.order_repo.update_status(
                    order.id, OrderStatus.PAID, {"paid_at": datetime.utcnow()}
                )
        return paid

    async def reject_card_payment(self, payment_id: int, admin_id: int) -> Payment | None:
        payment = await self.payment_repo.update_status(payment_id, PaymentStatus.FAILED)
        if payment and payment.order_id:
            order = await self.order_repo.get_by_id(payment.order_id)
            if order and order.status in (OrderStatus.PENDING_PAYMENT, OrderStatus.PAID):
                await self.order_repo.update_status(
                    order.id, OrderStatus.CANCELLED, {"cancelled_at": datetime.utcnow()}
                )
        return payment


# ---------------------------------------------------------------------------
# Reconciliation query helpers (used by the scheduler job)
# ---------------------------------------------------------------------------
def reconcilable_online_payments_query(limit: int):
    """Online payments that may still be resolvable with the gateway.

    Statuses: every non-final online state. Expiry is applied by the caller so
    an expired row can be finalised instead of silently dropped.
    """
    return (
        select(Payment)
        .where(
            and_(
                Payment.method == PaymentMethod.ONLINE,
                Payment.status.in_(RECONCILABLE_STATUSES),
                or_(
                    Payment.reference_number.is_not(None),
                    Payment.authority.is_not(None),
                    Payment.status == PaymentStatus.PENDING_VERIFICATION,
                ),
            )
        )
        .order_by(Payment.created_at)
        .limit(limit)
    )


async def claim_payment_for_processing(session: AsyncSession, payment_id: int) -> bool:
    """Conditional heartbeat claim. Returns False if someone else owns it.

    The WHERE clause on status is what makes this a real claim rather than a
    timestamp bump: a payment already moved to PAID no longer matches.
    """
    stmt = (
        update(Payment)
        .where(
            and_(
                Payment.id == payment_id,
                Payment.status.in_(RECONCILABLE_STATUSES),
            )
        )
        .values(updated_at=datetime.utcnow())
    )
    result = await session.execute(stmt)
    return result.rowcount > 0
