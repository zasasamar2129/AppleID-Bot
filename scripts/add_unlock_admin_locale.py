"""One-off script: add admin unlock-flow localization keys."""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

EN = {
    "unlock_admin.title": "🔓 Apple ID Unlock Requests",
    "unlock_admin.none": "No unlock requests found.",
    "unlock_admin.not_found": "Request not found",
    "unlock_admin.series": "Series",
    "unlock_admin.email_access": "Email Access",
    "unlock_admin.other_locked": "Other Locked iPhone",
    "unlock_admin.payment": "Payment",
    "unlock_admin.status": "Status",
    "unlock_admin.created": "Created",
    "unlock_admin.additional": "Details",
    "unlock_admin.notes": "Admin note",
    "unlock_admin.view_creds": "View Credentials",
    "unlock_admin.request_payment": "Request Payment",
    "unlock_admin.change_status": "Change Status",
    "unlock_admin.add_note": "Add Note",
    "unlock_admin.complete": "Complete",
    "unlock_admin.reject": "Reject",
    "unlock_admin.creds_title": "Credentials",
    "unlock_admin.creds_warning": "Handle these credentials carefully. Do not share with unauthorized people.",
    "unlock_admin.pay_amount_prompt": "Enter the payment amount (number):",
    "unlock_admin.invalid_amount": "Invalid amount. Please enter a positive number.",
    "unlock_admin.pay_requested": "Payment requested for request #{request_id}.",
    "unlock_admin.pay_notify_customer": "💳 Your unlock request #{request_id} has been reviewed.\n\n💵 Payment of {amount} is now required.\n\nPlease contact the admin to complete your payment.",
    "unlock_admin.choose_status": "Choose new status:",
    "unlock_admin.invalid_status": "Invalid status",
    "unlock_admin.status_changed": "Status updated.",
    "unlock_admin.note_prompt": "Enter the note:",
    "unlock_admin.note_added": "✅ Note added.",
    "unlock_admin.completed": "✅ Request completed.",
    "unlock_admin.rejected": "❌ Request rejected.",
    "unlock_admin.status.draft": "Draft",
    "unlock_admin.status.submitted": "Submitted",
    "unlock_admin.status.under_review": "Under Review",
    "unlock_admin.status.waiting_for_customer": "Waiting for Customer",
    "unlock_admin.status.payment_requested": "Payment Requested",
    "unlock_admin.status.payment_pending": "Payment Pending",
    "unlock_admin.status.paid": "Paid",
    "unlock_admin.status.in_progress": "In Progress",
    "unlock_admin.status.completed": "Completed",
    "unlock_admin.status.rejected": "Rejected",
    "unlock_admin.status.cancelled": "Cancelled",
    "unlock_admin.payment.not_requested": "Not Requested",
    "unlock_admin.payment.requested": "Requested",
    "unlock_admin.payment.pending": "Pending",
    "unlock_admin.payment.paid": "Paid",
    "unlock_admin.payment.failed": "Failed",
}

FA = {
    "unlock_admin.title": "🔓 درخواست‌های آنلاک Apple ID",
    "unlock_admin.none": "درخواست آنلاکی پیدا نشد.",
    "unlock_admin.not_found": "درخواست پیدا نشد",
    "unlock_admin.series": "سری",
    "unlock_admin.email_access": "دسترسی به ایمیل",
    "unlock_admin.other_locked": "آیفون دیگر قفل‌شده",
    "unlock_admin.payment": "پرداخت",
    "unlock_admin.status": "وضعیت",
    "unlock_admin.created": "ایجاد شده",
    "unlock_admin.additional": "توضیحات",
    "unlock_admin.notes": "یادداشت مدیر",
    "unlock_admin.view_creds": "مشاهده اطلاعات حساس",
    "unlock_admin.request_payment": "درخواست پرداخت",
    "unlock_admin.change_status": "تغییر وضعیت",
    "unlock_admin.add_note": "افزودن یادداشت",
    "unlock_admin.complete": "تکمیل",
    "unlock_admin.reject": "رد",
    "unlock_admin.creds_title": "اطلاعات حساس",
    "unlock_admin.creds_warning": "با این اطلاعات با احتیاط رفتار کنید. به اشخاص غیرمجاز نشان ندهید.",
    "unlock_admin.pay_amount_prompt": "مبلغ پرداخت را وارد کنید (عدد):",
    "unlock_admin.invalid_amount": "مبلغ نامعتبر است. لطفاً یک عدد مثبت وارد کنید.",
    "unlock_admin.pay_requested": "برای درخواست #{request_id} پرداخت درخواست شد.",
    "unlock_admin.pay_notify_customer": "💳 درخواست آنلاک #{request_id} شما بررسی شد.\n\n💵 مبلغ {amount} پرداخت لازم است.\n\nبرای تکمیل پرداخت، با ادمین در ارتباط باشید.",
    "unlock_admin.choose_status": "وضعیت جدید را انتخاب کنید:",
    "unlock_admin.invalid_status": "وضعیت نامعتبر",
    "unlock_admin.status_changed": "وضعیت به‌روزرسانی شد.",
    "unlock_admin.note_prompt": "یادداشت را وارد کنید:",
    "unlock_admin.note_added": "✅ یادداشت اضافه شد.",
    "unlock_admin.completed": "✅ درخواست تکمیل شد.",
    "unlock_admin.rejected": "❌ درخواست رد شد.",
    "unlock_admin.status.draft": "پیش‌نویس",
    "unlock_admin.status.submitted": "ارسال شده",
    "unlock_admin.status.under_review": "در حال بررسی",
    "unlock_admin.status.waiting_for_customer": "در انتظار مشتری",
    "unlock_admin.status.payment_requested": "پرداخت درخواست شده",
    "unlock_admin.status.payment_pending": "در انتظار پرداخت",
    "unlock_admin.status.paid": "پرداخت شده",
    "unlock_admin.status.in_progress": "در حال انجام",
    "unlock_admin.status.completed": "تکمیل شده",
    "unlock_admin.status.rejected": "رد شده",
    "unlock_admin.status.cancelled": "لغو شده",
    "unlock_admin.payment.not_requested": "درخواست نشده",
    "unlock_admin.payment.requested": "درخواست شده",
    "unlock_admin.payment.pending": "در انتظار",
    "unlock_admin.payment.paid": "پرداخت شده",
    "unlock_admin.payment.failed": "ناموفق",
}


def main():
    for name, extra in (("en", EN), ("fa", FA)):
        path = os.path.join(ROOT, "app", "localization", f"{name}.json")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        data.update(extra)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"{name}.json updated: {len(extra)} keys, total {len(data)}")


if __name__ == "__main__":
    main()