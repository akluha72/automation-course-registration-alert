"""
UiTM ECR Course Slot Monitor
=============================
Monitors course group pages and alerts you when a slot opens.
Checks every 10 minutes and sends a status notification each cycle.

SETUP:
    pip install playwright plyer
    playwright install chromium

USAGE:
    python init.py
    
    Unregister-ScheduledTask -TaskName 'UiTM-ECR-Monitor' -Confirm:$false
    powershell -ExecutionPolicy Bypass -File "C:\laragon\www\automation-uitm-course-registration\schedule_task.ps1"
    Start-ScheduledTask -TaskName 'UiTM-ECR-Monitor'
"""

import re
import time
import os
import sys
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

# ─────────────────────────────────────────
#  CONFIGURATION
# ─────────────────────────────────────────

STUDENT_ID       = "2023630358"
STUDENT_PASSWORD = "luTfi@kmal72"

# Courses to monitor. Each entry: {"course": <code>, "group": <group or None for ANY>}
COURSES = [
    {"course": "ICT600", "group": "NBCS2406A"},
    {"course": "MAT415", "group": "NBCS2406A"},
    {"course": "CSP600", "group": "NBCS2409A"},   
]

# How often to check (10 minutes)
CHECK_INTERVAL = 600

# Set to True when running via Task Scheduler (no visible desktop needed)
HEADLESS = True

# ─────────────────────────────────────────
#  URLS
# ─────────────────────────────────────────

BASE_URL     = "https://ecr.uitm.edu.my/estudent/ecr"
LOGIN_URL    = f"{BASE_URL}/login.cfm"
REGISTER_URL = f"{BASE_URL}/01_cr_register.cfm"


# ─────────────────────────────────────────
#  LOGIN
# ─────────────────────────────────────────

def login(page):
    """Navigate to login page and submit credentials. Returns True on success."""
    print("Navigating to login page...")
    page.goto(LOGIN_URL, wait_until="networkidle", timeout=30000)

    page.fill("input[name='txtUser']", STUDENT_ID)
    page.fill("input[name='txtPass']", STUDENT_PASSWORD)

    for selector in ["input[name='btnLogin']", "input[type='submit']", "button[type='submit']", "button:has-text('Login')"]:
        try:
            page.click(selector, timeout=3000)
            break
        except Exception:
            continue

    try:
        page.wait_for_url("**/main.cfm**", timeout=15000)
        print("[OK] Login successful!")
        return True
    except PlaywrightTimeout:
        final_url = page.url
        print(f"[ERROR] Login failed. Final URL: {final_url}")
        if "key=0" in final_url or "login" in final_url.lower():
            print("  Hint: Wrong credentials or account temporarily locked.")
        return False


# ─────────────────────────────────────────
#  FIND COURSE LINK
# ─────────────────────────────────────────

def get_course_url(page, course_code):
    """
    Go to the Register New Courses page, find the link for course_code,
    and return the URL of its group selection page.
    Returns: url string, None (not found), or "relogin" (session expired)
    """
    print(f"  Finding page for {course_code}...", end=" ", flush=True)

    try:
        page.goto(REGISTER_URL, wait_until="networkidle", timeout=30000)
    except PlaywrightTimeout:
        print("Timeout loading register page.")
        return None

    if "login" in page.url.lower():
        return "relogin"

    rows = page.locator("table tbody tr").all()
    for row in rows:
        text = row.inner_text()
        if course_code.upper() in text.upper():
            button = row.locator("button[onclick]").first
            try:
                onclick = button.get_attribute("onclick", timeout=3000)
                if onclick:
                    match = re.search(r"location\.href\s*=\s*['\"]([^'\"]+)['\"]", onclick)
                    if match:
                        href = match.group(1)
                        if not href.startswith("http"):
                            href = f"{BASE_URL}/{href.lstrip('/')}"
                        print(f"found.")
                        return href
            except Exception:
                continue

    print(f"\n[WARN] Could not find course {course_code} on the register page.")
    return None


# ─────────────────────────────────────────
#  SLOT CHECKER
# ─────────────────────────────────────────

def check_slots(page, course_url, target_group):
    """
    Fetch the group selection page and return available (not full) groups.
    Returns:
        list      - available groups (empty list = all full)
        None      - network/timeout error
        "relogin" - session expired
    """
    try:
        page.goto(course_url, wait_until="networkidle", timeout=30000)
    except PlaywrightTimeout:
        print("Timeout loading course page.")
        return None

    if "login" in page.url.lower():
        return "relogin"

    try:
        page.wait_for_selector("table#dataTableExample1 tbody tr", timeout=10000)
    except PlaywrightTimeout:
        print("  [WARN] No table found - page structure may have changed.")
        return []

    rows = page.locator("table#dataTableExample1 tbody tr").all()
    available = []

    for row in rows:
        cells = row.locator("td").all()
        if len(cells) < 3:
            continue

        group_info  = cells[1].inner_text()
        action_html = cells[2].inner_html()

        match       = re.search(r"MAX\s*:?\s*(\d+).*?CUR\s*:?\s*(\d+)", group_info)
        group_match = re.search(r"Group\s*:?\s*(\S+)", group_info)

        if not match:
            continue

        max_slots  = int(match.group(1))
        cur_slots  = int(match.group(2))
        group_name = group_match.group(1) if group_match else "Unknown"

        is_full = "btn-danger" in action_html

        if not is_full and "btn-success" in action_html and cur_slots < max_slots:
            if target_group is None or target_group.upper() in group_name.upper():
                available.append({
                    "group":      group_name,
                    "max":        max_slots,
                    "cur":        cur_slots,
                    "slots_left": max_slots - cur_slots,
                })

    return available


# ─────────────────────────────────────────
#  NOTIFICATIONS
# ─────────────────────────────────────────

def notify_status(statuses):
    """Send a desktop notification summarising the status of all monitored courses."""
    lines = []
    for s in statuses:
        course = s["course"]
        result = s["result"]
        if result is None:
            lines.append(f"{course}: error")
        elif result == "relogin":
            lines.append(f"{course}: session expired")
        elif len(result) == 0:
            lines.append(f"{course}: all full")
        else:
            total = sum(g["slots_left"] for g in result)
            lines.append(f"{course}: {total} slot(s) open!")

    message = " | ".join(lines)
    print(f"  Status: {message}")

    try:
        from plyer import notification
        notification.notify(
            title="UiTM ECR Status Update",
            message=message,
            timeout=15,
        )
    except Exception:
        pass


def alert_slot_open(course_code, available_groups, course_url):
    """Alert loudly when a slot opens for a course."""
    print("\n" + "=" * 60)
    print(f"  *** SLOT AVAILABLE FOR {course_code}! GO REGISTER NOW! ***")
    print("=" * 60)
    for g in available_groups:
        print(f"  Group: {g['group']}  |  {g['cur']}/{g['max']} filled  |  {g['slots_left']} slot(s) left")
    print(f"\n  Open this in your browser NOW:")
    print(f"  {course_url}")
    print("=" * 60 + "\n")

    try:
        from plyer import notification
        notification.notify(
            title=f"UiTM ECR - {course_code} SLOT OPEN!",
            message=f"{course_code} slot open! Register NOW. Group: {available_groups[0]['group']}",
            timeout=30,
        )
    except Exception:
        pass

    try:
        import winsound
        for _ in range(6):
            winsound.Beep(1000, 400)
            time.sleep(0.15)
    except Exception:
        os.system("printf '\a\a\a\a\a'")


# ─────────────────────────────────────────
#  MAIN LOOP
# ─────────────────────────────────────────

def main():
    """
    Run one full check cycle across all COURSES, send a status notification,
    then exit. Schedule this script via Windows Task Scheduler to repeat every
    10 minutes — no terminal needs to stay open.
    """
    course_labels = ", ".join(
        f"{c['course']} ({c['group'] or 'ANY'})" for c in COURSES
    )
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print("=" * 60)
    print("  UiTM ECR Course Monitor")
    print(f"  Run at     : {now}")
    print(f"  Student    : {STUDENT_ID}")
    print(f"  Courses    : {course_labels}")
    print(f"  Headless   : {HEADLESS}")
    print("=" * 60)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        context = browser.new_context()
        page    = context.new_page()

        if not login(page):
            browser.close()
            sys.exit(1)

        statuses = []

        for entry in COURSES:
            course_code  = entry["course"]
            target_group = entry["group"]

            # Resolve course group-selection URL
            url = get_course_url(page, course_code)

            if url == "relogin":
                print("  Session expired, re-logging in...")
                if not login(page):
                    browser.close()
                    sys.exit(1)
                url = get_course_url(page, course_code)

            if url is None or url == "relogin":
                print(f"  [{course_code}] Could not resolve URL, skipping.")
                statuses.append({"course": course_code, "result": None})
                continue

            print(f"  [{course_code}] Checking slots...", end=" ", flush=True)
            result = check_slots(page, url, target_group)

            if result == "relogin":
                print("Session expired, re-logging in...")
                if not login(page):
                    browser.close()
                    sys.exit(1)
                result = check_slots(page, url, target_group)

            if result is None:
                print("network error.")
            elif len(result) == 0:
                print("all full.")
            else:
                print(f"{len(result)} group(s) available!")
                alert_slot_open(course_code, result, url)

            statuses.append({"course": course_code, "result": result})

        browser.close()

    # One status notification summarising all courses, then script exits
    notify_status(statuses)
    print("\nDone. Script will be re-run by Task Scheduler in 10 min.")


if __name__ == "__main__":
    main()
