"""One-off script: add unlock-flow localization keys to fa.json and en.json."""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

EN_NEW = {
    "unlock.new_request": "📝 New request",
    "unlock.select_series": "📱 Select iPhone Series\n\nChoose your iPhone series:",
    "unlock.email_access_question": (
        "📧 Do you have access to the Apple ID email?\n\n"
        "By “I don’t have access”, we mean you completely don’t have access to the email account.\n\n"
        "This does NOT mean that you simply don’t remember the password or that the email is temporarily unavailable.\n\n"
        "Email access is NOT required for checking/inquiry.\n"
        "Email access is only required if the unlock process needs to be carried out."
    ),
    "unlock.email_access_question_short": "📧 Do you have access to the Apple ID email?",
    "unlock.enter_email": "📧 Enter the Apple ID email:\n\nSend the email address connected to this Apple ID.",
    "unlock.enter_password": (
        "🔐 Enter the Apple ID password:\n\n"
        "Sending the password is optional.\n\n"
        "If you don’t want to provide it, tap “Skip”."
    ),
    "unlock.enter_imei": "📱 Enter the iPhone IMEI:\n\nThe IMEI should be 15 digits.",
    "unlock.other_locked_question": "📱 Is any other iPhone also locked with this Apple ID?",
    "unlock.additional_info": (
        "📝 Additional information\n\n"
        "If you have any extra details about the device or Apple ID, send them here.\n\n"
        "If you don’t have anything else to add, tap “Skip”."
    ),
    "unlock.invalid_email": "⚠️ Invalid email.\n\nPlease send the email address connected to this Apple ID again.",
    "unlock.invalid_imei": "⚠️ Invalid IMEI.\n\nPlease send the 15-digit iPhone IMEI again.",
    "unlock.invalid_input": "⚠️ Invalid input. Please try again.",
    "unlock.invalid_selection": "⚠️ Invalid selection.",
    "unlock.invalid_incomplete": "⚠️ Your request is incomplete. Please review and try again.",
    "unlock.additional_too_long": "⚠️ Too long. Please keep it under 4000 characters.",
    "unlock.skip": "Skip",
    "unlock.request_title": "Apple ID Unlock Request",
    "unlock.summary_series": "Device series",
    "unlock.summary_email_access": "Email access",
    "unlock.summary_email": "Email",
    "unlock.summary_password": "Apple ID password",
    "unlock.summary_password_set": "✅ provided",
    "unlock.summary_password_skipped": "⏭ not sent",
    "unlock.summary_imei": "IMEI",
    "unlock.summary_other_locked": "Another iPhone locked",
    "unlock.summary_additional": "Details",
    "unlock.summary_none": "None",
    "unlock.payment_rule_title": "Payment",
    "unlock.payment_after_admin": (
        "No payment is required to submit this request.\n\n"
        "Payment is only made when an admin asks you to pay.\n\n"
        "Your request will be reviewed by the admin after submission."
    ),
    "unlock.confirm_submit": "Confirm & Submit",
    "unlock.edit": "Edit",
    "unlock.edit_help": "✏️ Edit\n\nWhich field would you like to change?",
    "unlock.edit_series": "iPhone series",
    "unlock.edit_email_access": "Email access",
    "unlock.edit_email": "Email",
    "unlock.edit_password": "Password",
    "unlock.edit_imei": "IMEI",
    "unlock.edit_other_locked": "Another locked iPhone",
    "unlock.edit_additional": "Additional info",
    "unlock.submitted_success": (
        "✅ Your request has been submitted.\n\n"
        "🧾 Request: #{request_id}\n\n"
        "Your request has been sent for review.\n\n"
        "💳 No payment is required yet.\n"
        "Payment will only be requested by an admin when needed.\n\n"
        "📩 If anything else is needed, we will contact you through the bot."
    ),
    "unlock.admin_notify": (
        "🔓 New Apple ID Unlock Request\n\n"
        "🧾 Request: #{request_id}\n"
        "📱 Series: {series}\n"
        "📧 Email Access: {email_access}\n"
        "📱 Other Locked iPhone: {other_locked}\n\n"
        "🟡 Status: New"
    ),
    "unlock.admin_view": "View Request",
    "unlock.series.iphone_17": "17 Series",
    "unlock.series.iphone_16": "16 Series",
    "unlock.series.iphone_15": "15 Series",
    "unlock.series.iphone_14": "14 Series",
    "unlock.series.iphone_13": "13 Series",
    "unlock.series.iphone_12": "12 Series",
    "unlock.series.iphone_11": "11 Series",
    "unlock.series.iphone_x_or_older": "X and Older",
}

FA_NEW = {
    "unlock.new_request": "📝 درخواست جدید",
    "unlock.select_series": "📱 سری آیفون را انتخاب کنید\n\nسری آیفون خود را انتخاب کنید:",
    "unlock.email_access_question": (
        "📧 دسترسی به ایمیل Apple ID دارید؟\n\n"
        "كلاً دسترسی ندارم یعنی اصلاً به ایمیل دسترسی ندارید، نه اینکه الان رمز را ندارید یا موقتاً در دسترس نیست.\n\n"
        "برای استعلام به دسترسی ایمیل نیاز نیست.\n"
        "دسترسی ایمیل فقط برای انجام کار ریجکتی لازم است."
    ),
    "unlock.email_access_question_short": "📧 دسترسی به ایمیل Apple ID دارید؟",
    "unlock.enter_email": "📧 ایمیل Apple ID را وارد کنید:\n\nایمیل متصل به این Apple ID را ارسال کنید.",
    "unlock.enter_password": (
        "🔐 رمز Apple ID را وارد کنید:\n\n"
        "ارسال رمز اختیاری است.\n\n"
        "اگر نمی‌خواهید رمز را ارسال کنید، روی «رد کردن» بزنید."
    ),
    "unlock.enter_imei": "📱 IMEI آیفون را وارد کنید:\n\nIMEI دستگاه ۱۵ رقمی است.",
    "unlock.other_locked_question": "📱 آیا آیفون دیگری هم با این Apple ID قفل شده است؟",
    "unlock.additional_info": (
        "📝 اطلاعات تکمیلی\n\n"
        "اگر توضیح، نکته یا اطلاعات دیگری درباره دستگاه یا Apple ID دارید، اینجا ارسال کنید.\n\n"
        "اگر موردی ندارید، «رد کردن» را بزنید."
    ),
    "unlock.invalid_email": "⚠️ ایمیل معتبر نیست.\n\nلطفاً ایمیل متصل به این Apple ID را دوباره ارسال کنید.",
    "unlock.invalid_imei": "⚠️ IMEI معتبر نیست.\n\nلطفاً IMEI ۱۵ رقمی آیفون را دوباره ارسال کنید.",
    "unlock.invalid_input": "⚠️ ورودی نامعتبر است. دوباره تلاش کنید.",
    "unlock.invalid_selection": "⚠️ انتخاب نامعتبر است.",
    "unlock.invalid_incomplete": "⚠️ اطلاعات درخواست ناقص است. لطفاً بررسی و دوباره تلاش کنید.",
    "unlock.additional_too_long": "⚠️ بیش از حد طولانی است. لطفاً زیر ۴۰۰۰ نویسه ارسال کنید.",
    "unlock.skip": "رد کردن",
    "unlock.request_title": "درخواست آنلاک Apple ID",
    "unlock.summary_series": "سری دستگاه",
    "unlock.summary_email_access": "دسترسی به ایمیل",
    "unlock.summary_email": "ایمیل",
    "unlock.summary_password": "رمز Apple ID",
    "unlock.summary_password_set": "✅ وارد شده",
    "unlock.summary_password_skipped": "⏭ ارسال نشده",
    "unlock.summary_imei": "IMEI",
    "unlock.summary_other_locked": "آیفون دیگر با همین Apple ID",
    "unlock.summary_additional": "توضیحات",
    "unlock.summary_none": "مورد خاصی ندارم",
    "unlock.payment_rule_title": "پرداخت",
    "unlock.payment_after_admin": (
        "برای ثبت درخواست نیازی به پرداخت نیست.\n\n"
        "هزینه فقط زمانی پرداخت می‌شود که ادمین از شما درخواست پرداخت کند.\n\n"
        "درخواست شما بعد از ثبت توسط ادمین بررسی می‌شود."
    ),
    "unlock.confirm_submit": "تأیید و ارسال",
    "unlock.edit": "ویرایش",
    "unlock.edit_help": "✏️ ویرایش\n\nکدام بخش را می‌خواهید تغییر دهید؟",
    "unlock.edit_series": "سری آیفون",
    "unlock.edit_email_access": "دسترسی به ایمیل",
    "unlock.edit_email": "ایمیل",
    "unlock.edit_password": "رمز عبور",
    "unlock.edit_imei": "IMEI",
    "unlock.edit_other_locked": "آیفون دیگر قفل‌شده",
    "unlock.edit_additional": "اطلاعات تکمیلی",
    "unlock.submitted_success": (
        "✅ درخواست شما ثبت شد.\n\n"
        "🧾 شماره درخواست: #{request_id}\n\n"
        "درخواست شما برای بررسی ارسال شد.\n\n"
        "💳 فعلاً نیازی به پرداخت نیست.\n"
        "هزینه فقط زمانی پرداخت می‌شود که ادمین از شما درخواست پرداخت کند.\n\n"
        "📩 در صورت نیاز، از طریق همین ربات با شما در ارتباط خواهیم بود."
    ),
    "unlock.admin_notify": (
        "🔓 درخواست جدید آنلاک Apple ID\n\n"
        "🧾 درخواست: #{request_id}\n"
        "📱 سری: {series}\n"
        "📧 دسترسی به ایمیل: {email_access}\n"
        "📱 آیفون دیگر قفل‌شده: {other_locked}\n\n"
        "🟡 وضعیت: جدید"
    ),
    "unlock.admin_view": "مشاهده درخواست",
    "unlock.series.iphone_17": "سری 17",
    "unlock.series.iphone_16": "سری 16",
    "unlock.series.iphone_15": "سری 15",
    "unlock.series.iphone_14": "سری 14",
    "unlock.series.iphone_13": "سری 13",
    "unlock.series.iphone_12": "سری 12",
    "unlock.series.iphone_11": "سری 11",
    "unlock.series.iphone_x_or_older": "X و قدیمی‌تر",
}


def main():
    for name, extra in (("en", EN_NEW), ("fa", FA_NEW)):
        path = os.path.join(ROOT, "app", "localization", f"{name}.json")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        data.update(extra)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"{name}.json updated: {len(extra)} keys added, total {len(data)}")


if __name__ == "__main__":
    main()