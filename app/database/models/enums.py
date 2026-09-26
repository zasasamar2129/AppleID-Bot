import enum


class ProductType(str, enum.Enum):
    PERSONAL = "personal"
    READY_MADE = "ready_made"


class OrderType(str, enum.Enum):
    PERSONAL = "PERSONAL"
    READY_MADE = "READY_MADE"


class DeliveryType(str, enum.Enum):
    MANUAL = "manual"
    AUTOMATIC = "automatic"


class InventoryStatus(str, enum.Enum):
    AVAILABLE = "available"
    RESERVED = "reserved"
    SOLD = "sold"
    DISABLED = "disabled"


class OrderStatus(str, enum.Enum):
    PENDING_PAYMENT = "pending_payment"
    PAID = "paid"
    PROCESSING = "processing"
    FULFILLED = "fulfilled"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    REFUND_PENDING = "refund_pending"
    REFUNDED = "refunded"
    DISPUTED = "disputed"


class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    WAITING_USER = "waiting_user"
    PENDING_VERIFICATION = "pending_verification"
    PAID = "paid"
    FAILED = "failed"
    EXPIRED = "expired"
    REFUNDED = "refunded"
    CANCELLED = "cancelled"


class PaymentMethod(str, enum.Enum):
    ONLINE = "online"
    CARD_TO_CARD = "card_to_card"
    WALLET = "wallet"


class WalletTransactionType(str, enum.Enum):
    DEPOSIT = "deposit"
    PURCHASE = "purchase"
    REFUND = "refund"
    BONUS = "bonus"
    REFERRAL = "referral"
    ADMIN_ADJUSTMENT = "admin_adjustment"


class CouponType(str, enum.Enum):
    PERCENTAGE = "percentage"
    FIXED = "fixed"


class SupportStatus(str, enum.Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    WAITING_USER = "waiting_user"
    RESOLVED = "resolved"
    CLOSED = "closed"


class SupportCategory(str, enum.Enum):
    PAYMENT = "payment"
    ORDER = "order"
    APPLE_ID = "apple_id"
    WALLET = "wallet"
    OTHER = "other"


class AdminRole(str, enum.Enum):
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    INVENTORY_MANAGER = "inventory_manager"
    FINANCE = "finance"
    SUPPORT = "support"


class UnlockInquiryStatus(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class UnlockRequestStatus(str, enum.Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    WAITING_FOR_CUSTOMER = "waiting_for_customer"
    PAYMENT_REQUESTED = "payment_requested"
    PAYMENT_PENDING = "payment_pending"
    PAID = "paid"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class UnlockPaymentStatus(str, enum.Enum):
    NOT_REQUESTED = "not_requested"
    REQUESTED = "requested"
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Helper for SQLAlchemy Enum columns
# ---------------------------------------------------------------------------
# By default SQLAlchemy's Enum type stores the Python enum *member name*
# (e.g. "SUBMITTED"). PostgreSQL enum types in this project were created with
# lowercase *values* ("submitted"), so we must force SQLAlchemy to use
# member.value instead. Pass this to every SAEnum(...) call:
#
#   SAEnum(MyEnum, name="myenum", values_callable=enum_values)
#
def enum_values(enum_cls):
    """Return the list of .value strings for a Python enum class."""
    return [member.value for member in enum_cls]