"""
UiTM ECR Course Slot Monitor
=============================
Monitors a course group page and alerts you when a slot opens.

SETUP:
    pip install playwright plyer
    playwright install chromium

USAGE:
    python init.py
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

# Course code to register (shown in "Register New Courses" page)
TARGET_COURSE = "CSP650"

# Group name to monitor. Set to None to alert on ANY available group.
TARGET_GROUP = "NBCS24010A"

# How often to check in seconds
CHECK_INTERVAL = 30

# Set to False to see the browser window (recommended while testing)
HEADLESS = False

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

    # Try multiple possible button selectors
    for selector in ["input[name='btnLogin']", "input[type='submit']", "button[type='submit']", "button:has-text('Login')"]:
        try:
            page.click(selector, timeout=3000)
            break
        except Exception:
            continue

    # Wait for redirect after login
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

def get_course_url(page):
    """
    Go to the Register New Courses page, find the link for TARGET_COURSE,
    and return the URL of its group selection page.
    Returns: url string, None (not found), or "relogin" (session expired)
    """
    print("Finding course page...", end=" ", flush=True)

    try:
        page.goto(REGISTER_URL, wait_until="networkidle", timeout=30000)
    except PlaywrightTimeout:
        print("Timeout loading register page.")
        return None

    # Session expired — redirected back to login
    if "login" in page.url.lower():
        return "relogin"

    # Scan all rows for course code in text, then extract URL from button onclick
    rows = page.locator("table tbody tr").all()
    for row in rows:
        text = row.inner_text()
        if TARGET_COURSE.upper() in text.upper():
            # Button uses onclick="location.href = 'url';" instead of <a href>
            button = row.locator("button[onclick]").first
            try:
                onclick = button.get_attribute("onclick", timeout=3000)
                if onclick:
                    match = re.search(r"location\.href\s*=\s*['\"]([^'\"]+)['\"]", onclick)
                    if match:
                        href = match.group(1)
                        if not href.startswith("http"):
                            href = f"{BASE_URL}/{href.lstrip('/')}"
                        return href
            except Exception:
                continue

    print(f"\n[WARN] Could not find course {TARGET_COURSE} on the register page.")
    print("  Make sure the course is listed under '1.0 Register New Courses'.")
    print("  Page text snippet:", page.inner_text("body")[:400])
    return None


# ─────────────────────────────────────────
#  SLOT CHECKER
# ─────────────────────────────────────────

def check_slots(page, course_url):
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

    # Wait for table to appear
    try:
        page.wait_for_selector("table#dataTableExample1 tbody tr", timeout=10000)
    except PlaywrightTimeout:
        print("  [WARN] No table found - page structure may have changed.")
        print("  Page snippet:", page.inner_text("body")[:300])
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
            if TARGET_GROUP is None or TARGET_GROUP.upper() in group_name.upper():
                available.append({
                    "group":      group_name,
                    "max":        max_slots,
                    "cur":        cur_slots,
                    "slots_left": max_slots - cur_slots,
                })

    return available


# ─────────────────────────────────────────
#  ALERT
# ─────────────────────────────────────────

def alert(available_groups, course_url):
    print("\n" + "=" * 60)
    print("  *** SLOT AVAILABLE! GO REGISTER NOW! ***")
    print("=" * 60)
    for g in available_groups:
        print(f"  Group: {g['group']}  |  {g['cur']}/{g['max']} filled  |  {g['slots_left']} slot(s) left")
    print(f"\n  Open this in your browser NOW:")
    print(f"  {course_url}")
    print("=" * 60 + "\n")

    try:
        from plyer import notification
        notification.notify(
            title="UiTM ECR - SLOT OPEN!",
            message=f"{TARGET_COURSE} slot open! Register NOW. Group: {available_groups[0]['group']}",
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
    print("=" * 60)
    print("  UiTM ECR Course Monitor")
    print(f"  Student    : {STUDENT_ID}")
    print(f"  Course     : {TARGET_COURSE}")
    print(f"  Group      : {TARGET_GROUP or 'ANY'}")
    print(f"  Interval   : {CHECK_INTERVAL}s")
    print(f"  Headless   : {HEADLESS}")
    print("=" * 60)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        context = browser.new_context()
        page    = context.new_page()

        # Initial login
        if not login(page):
            browser.close()
            sys.exit(1)

        course_url  = None
        check_count = 0

        while True:
            # Resolve course URL if we don't have it yet
            if course_url is None:
                course_url = get_course_url(page)

                if course_url == "relogin":
                    print("Session expired, re-logging in...")
                    if not login(page):
                        browser.close()
                        sys.exit(1)
                    course_url = None
                    continue

                if course_url is None:
                    print(f"Course {TARGET_COURSE} not found. Retrying in 30s...")
                    time.sleep(30)
                    continue

                print(f"Found: {course_url}")

            # Check slots
            check_count += 1
            now = datetime.now().strftime("%H:%M:%S")
            print(f"[{now}] Check #{check_count} ...", end=" ", flush=True)

            result = check_slots(page, course_url)

            if result == "relogin":
                print("Session expired, re-logging in...")
                if not login(page):
                    browser.close()
                    sys.exit(1)
                course_url = None
                continue

            if result is None:
                print("Network error - retrying...")

            elif len(result) == 0:
                print("All full. Waiting...")

            else:
                print(f"FOUND {len(result)} available group(s)!")
                alert(result, course_url)
                time.sleep(30)
                continue

            time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
