"""initial migration

Revision ID: 0001
Revises: 
Create Date: 2024-01-01 00:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('telegram_id', sa.BigInteger(), unique=True, index=True),
        sa.Column('username', sa.String(255), nullable=True),
        sa.Column('first_name', sa.String(255)),
        sa.Column('last_name', sa.String(255), nullable=True),
        sa.Column('language', sa.String(10), default='fa'),
        sa.Column('is_blocked', sa.Boolean(), default=False),
        sa.Column('is_vip', sa.Boolean(), default=False),
        sa.Column('referrer_id', sa.BigInteger(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('last_active_at', sa.DateTime(timezone=True), nullable=True),
    )

    # Create products table
    op.create_table(
        'products',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('name', sa.String(255)),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('type', sa.Enum('PERSONAL', 'READY_MADE', name='producttype')),
        sa.Column('region', sa.String(100), nullable=True),
        sa.Column('price', sa.Numeric(12,2)),
        sa.Column('currency', sa.String(10), default='IRR'),
        sa.Column('discount', sa.Numeric(12,2), default=0),
        sa.Column('processing_time', sa.String(100), nullable=True),
        sa.Column('delivery_type', sa.Enum('MANUAL', 'AUTOMATIC', name='deliverytype'), default='MANUAL'),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('is_featured', sa.Boolean(), default=False),
        sa.Column('is_popular', sa.Boolean(), default=False),
        sa.Column('is_new', sa.Boolean(), default=False),
        sa.Column('is_premium', sa.Boolean(), default=False),
        sa.Column('sort_order', sa.Integer(), default=0),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Create inventory table
    op.create_table(
        'inventory',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('product_id', sa.BigInteger(), sa.ForeignKey('products.id'), index=True),
        sa.Column('region', sa.String(100), nullable=True),
        sa.Column('status', sa.Enum('AVAILABLE', 'RESERVED', 'SOLD', 'DISABLED', name='inventorystatus'), default='AVAILABLE', index=True),
        sa.Column('encrypted_account_identifier', sa.Text()),
        sa.Column('encrypted_fulfillment_data', sa.Text(), nullable=True),
        sa.Column('internal_notes', sa.Text(), nullable=True),
        sa.Column('reservation_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reserved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('sold_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Create orders table
    op.create_table(
        'orders',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('users.id'), index=True),
        sa.Column('product_id', sa.BigInteger(), sa.ForeignKey('products.id')),
        sa.Column('inventory_id', sa.BigInteger(), sa.ForeignKey('inventory.id'), nullable=True),
        sa.Column('order_type', sa.Enum('PERSONAL', 'READY_MADE', name='ordertype')),
        sa.Column('price', sa.Numeric(12,2)),
        sa.Column('discount', sa.Numeric(12,2), default=0),
        sa.Column('final_price', sa.Numeric(12,2)),
        sa.Column('currency', sa.String(10), default='IRR'),
        sa.Column('payment_method', sa.Enum('ONLINE', 'CARD_TO_CARD', 'WALLET', name='paymentmethod'), nullable=True),
        sa.Column('status', sa.Enum('PENDING_PAYMENT', 'PAID', 'PROCESSING', 'FULFILLED', 'DELIVERED', 'CANCELLED', 'REFUND_PENDING', 'REFUNDED', 'DISPUTED', name='orderstatus'), default='PENDING_PAYMENT', index=True),
        sa.Column('customer_information', sa.Text(), nullable=True),
        sa.Column('admin_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
    )

    # Create payments table
    op.create_table(
        'payments',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('order_id', sa.BigInteger(), sa.ForeignKey('orders.id'), index=True),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('users.id'), index=True),
        sa.Column('provider', sa.String(50), default='custom_api'),
        sa.Column('method', sa.Enum('ONLINE', 'CARD_TO_CARD', 'WALLET', name='paymentmethod_pay')),
        sa.Column('amount', sa.Numeric(12,2)),
        sa.Column('currency', sa.String(10), default='IRR'),
        sa.Column('transaction_id', sa.String(255), nullable=True),
        sa.Column('external_payment_id', sa.String(255), nullable=True),
        sa.Column('status', sa.Enum('PENDING', 'WAITING_USER', 'PENDING_VERIFICATION', 'PAID', 'FAILED', 'EXPIRED', 'REFUNDED', 'CANCELLED', name='paymentstatus'), default='PENDING', index=True),
        sa.Column('receipt_file_id', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True),
    )

    # Create wallets table
    op.create_table(
        'wallets',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('users.id'), unique=True),
        sa.Column('balance', sa.Numeric(12,2), default=0),
        sa.Column('currency', sa.String(10), default='IRR'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Create wallet_transactions table
    op.create_table(
        'wallet_transactions',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('wallet_id', sa.BigInteger(), sa.ForeignKey('wallets.id'), index=True),
        sa.Column('type', sa.Enum('DEPOSIT', 'PURCHASE', 'REFUND', 'BONUS', 'REFERRAL', 'ADMIN_ADJUSTMENT', name='wallettransactiontype')),
        sa.Column('amount', sa.Numeric(12,2)),
        sa.Column('balance_after', sa.Numeric(12,2)),
        sa.Column('reference_id', sa.String(255), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Create coupons table
    op.create_table(
        'coupons',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('code', sa.String(50), unique=True, index=True),
        sa.Column('type', sa.Enum('PERCENTAGE', 'FIXED', name='coupontype')),
        sa.Column('value', sa.Numeric(12,2)),
        sa.Column('max_discount', sa.Numeric(12,2), nullable=True),
        sa.Column('min_order_amount', sa.Numeric(12,2), nullable=True),
        sa.Column('global_usage_limit', sa.Integer(), nullable=True),
        sa.Column('per_user_limit', sa.Integer(), default=1),
        sa.Column('usage_count', sa.Integer(), default=0),
        sa.Column('start_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('end_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('product_restrictions', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Create coupon_usages table
    op.create_table(
        'coupon_usages',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('coupon_id', sa.BigInteger(), sa.ForeignKey('coupons.id'), index=True),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('users.id'), index=True),
        sa.Column('order_id', sa.BigInteger(), sa.ForeignKey('orders.id'), nullable=True),
        sa.Column('used_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Create referrals table
    op.create_table(
        'referrals',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('referrer_id', sa.BigInteger(), sa.ForeignKey('users.id'), index=True),
        sa.Column('referred_user_id', sa.BigInteger(), sa.ForeignKey('users.id'), unique=True, index=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('reward_given', sa.Boolean(), default=False),
        sa.Column('reward_given_at', sa.DateTime(timezone=True), nullable=True),
    )

    # Create admin_users table BEFORE support_tickets
    op.create_table(
        'admin_users',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('telegram_id', sa.BigInteger(), unique=True, index=True),
        sa.Column('username', sa.String(255), nullable=True),
        sa.Column('first_name', sa.String(255)),
        sa.Column('last_name', sa.String(255), nullable=True),
        sa.Column('role', sa.Enum('SUPER_ADMIN', 'ADMIN', 'INVENTORY_MANAGER', 'FINANCE', 'SUPPORT', name='adminrole')),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('permissions', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Create support_tickets table
    op.create_table(
        'support_tickets',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('users.id'), index=True),
        sa.Column('admin_id', sa.BigInteger(), sa.ForeignKey('admin_users.id'), nullable=True),
        sa.Column('category', sa.Enum('PAYMENT', 'ORDER', 'APPLE_ID', 'WALLET', 'OTHER', name='supportcategory')),
        sa.Column('status', sa.Enum('OPEN', 'IN_PROGRESS', 'WAITING_USER', 'RESOLVED', 'CLOSED', name='supportstatus'), default='OPEN', index=True),
        sa.Column('subject', sa.String(255)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Create support_messages table
    op.create_table(
        'support_messages',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('ticket_id', sa.BigInteger(), sa.ForeignKey('support_tickets.id'), index=True),
        sa.Column('sender_user_id', sa.BigInteger(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('sender_admin_id', sa.BigInteger(), sa.ForeignKey('admin_users.id'), nullable=True),
        sa.Column('message', sa.Text()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Create audit_logs table
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('admin_id', sa.BigInteger(), sa.ForeignKey('admin_users.id'), nullable=True),
        sa.Column('action', sa.String(100), index=True),
        sa.Column('target_type', sa.String(100)),
        sa.Column('target_id', sa.String(255), nullable=True),
        sa.Column('metadata_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Create settings table
    op.create_table(
        'settings',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('key', sa.String(100), unique=True, index=True),
        sa.Column('value', sa.Text()),
        sa.Column('value_type', sa.String(20), default='str'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Create broadcasts table
    op.create_table(
        'broadcasts',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('admin_id', sa.BigInteger(), sa.ForeignKey('admin_users.id')),
        sa.Column('content_type', sa.String(20)),
        sa.Column('content', sa.Text()),
        sa.Column('caption', sa.Text(), nullable=True),
        sa.Column('inline_buttons_json', sa.Text(), nullable=True),
        sa.Column('audience_filter', sa.Text()),
        sa.Column('target_count', sa.Integer(), default=0),
        sa.Column('sent_count', sa.Integer(), default=0),
        sa.Column('failed_count', sa.Integer(), default=0),
        sa.Column('blocked_count', sa.Integer(), default=0),
        sa.Column('status', sa.String(20), default='queued'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    )

    # Create broadcast_receipts table
    op.create_table(
        'broadcast_receipts',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('broadcast_id', sa.BigInteger(), sa.ForeignKey('broadcasts.id'), index=True),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('users.id'), index=True),
        sa.Column('status', sa.String(20)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('broadcast_receipts')
    op.drop_table('broadcasts')
    op.drop_table('settings')
    op.drop_table('audit_logs')
    op.drop_table('support_messages')
    op.drop_table('support_tickets')
    op.drop_table('admin_users')
    op.drop_table('referrals')
    op.drop_table('coupon_usages')
    op.drop_table('coupons')
    op.drop_table('wallet_transactions')
    op.drop_table('wallets')
    op.drop_table('payments')
    op.drop_table('orders')
    op.drop_table('inventory')
    op.drop_table('products')
    op.drop_table('users')