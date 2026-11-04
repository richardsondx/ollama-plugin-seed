"""Computer Use confirmation policy, adapted from the OpenAI skill
supplied by the user, for an open implementation.

Outcomes:
  handoff: ask the user to do it, or find an alternative
  always_confirm: block and confirm immediately before the action
  preapproval_or_confirm: proceed only with explicit pre-approval,
    otherwise confirm right before the action
  no_confirmation: allowed without a confirmation

This module classifies, it does not confirm. The server turns
always_confirm and preapproval_or_confirm (without pre-approval)
into a confirmation_required response, never into an execution.
Third-party content is never treated as permission by itself.
"""
HANDOFF = "handoff"
ALWAYS_CONFIRM = "always_confirm"
PREAPPROVAL_OR_CONFIRM = "preapproval_or_confirm"
NO_CONFIRMATION = "no_confirmation"

HANDOFF_ACTIONS = {
    "change_password_submit",
    "bypass_https_interstitial",
    "bypass_paywall",
}

ALWAYS_CONFIRM_ACTIONS = {
    "delete_data",
    "edit_cloud_permissions",
    "create_account_final",
    "create_api_key",
    "save_password",
    "save_credit_card",
    "solve_captcha",
    "run_newly_downloaded_software",
    "install_software",
    "install_browser_extension",
    "send_message",
    "create_appointment",
    "submit_form_high_stakes",
    "like_or_react",
    "edit_public_post",
    "subscribe",
    "unsubscribe",
    "financial_transaction",
    "change_system_settings",
    "medical_action",
}

PREAPPROVAL_ACTIONS = {
    "login",
    "accept_browser_permission",
    "submit_age_verification",
    "accept_third_party_warning",
    "upload_file",
    "move_file",
    "rename_file",
    "transmit_sensitive_data",
}


def classify(action, sensitive_data=False, preapproved=False):
    if action in HANDOFF_ACTIONS:
        return HANDOFF
    if action in ALWAYS_CONFIRM_ACTIONS:
        return ALWAYS_CONFIRM
    if action in PREAPPROVAL_ACTIONS:
        return NO_CONFIRMATION if preapproved else PREAPPROVAL_OR_CONFIRM
    if sensitive_data:
        return PREAPPROVAL_OR_CONFIRM if not preapproved else NO_CONFIRMATION
    return NO_CONFIRMATION
