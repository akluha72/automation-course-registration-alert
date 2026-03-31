
UiTM ECR Course Slot Monitor
=============================
Monitors a specific course group page and alerts you when a slot opens up.

SETUP
  pip install requests beautifulsoup4 plyer

USAGE
  python uitm_monitor.py

Fill in your credentials and target course URL below.


import requests
from bs4 import BeautifulSoup
import time
import winsound  # Windows only for beep — see cross-platform note below
import os
import sys
from datetime import datetime

# ─────────────────────────────────────────
#  CONFIGURATION — fill these in
# ─────────────────────────────────────────

STUDENT_ID       = 2023630358        # Your UiTM Student ID
STUDENT_PASSWORD = YOUR_PASSWORD     # Your student portal password

# The URL of the group selection page for your target course
# (the page shown in your screenshot)
TARGET_URL = httpsecr.uitm.edu.myestudentecr01_cr_register_select.cfmkey1=37B31FC9DFCAE9CF4C&key2=0C1CCA78009ACB07C0

# How often to check (in seconds). 10s is a safe interval — not too aggressive.
CHECK_INTERVAL = 10

# The group you want to monitor. Set to None to alert on ANY available group.
# Example NBCS2406A  or  None
TARGET_GROUP = None

# ─────────────────────────────────────────
#  LOGIN
# ─────────────────────────────────────────

LOGIN_URL = httpsecr.uitm.edu.myestudentecrlogin.cfm

def create_session()
    Log in and return an authenticated session.
    session = requests.Session()
    session.headers.update({
        User-Agent Mozilla5.0 (Windows NT 10.0; Win64; x64) AppleWebKit537.36 Chrome120 Safari537.36,
        Referer LOGIN_URL,
    })

    # First GET the login page to grab any hidden fields  cookies
    resp = session.get(LOGIN_URL, timeout=15)
    soup = BeautifulSoup(resp.text, html.parser)

    # Build login payload — adjust field names if login fails
    payload = {
        stuID   STUDENT_ID,
        stuPass STUDENT_PASSWORD,
    }

    # Include any hidden form fields (e.g. CSRF tokens)
    for hidden in soup.find_all(input, type=hidden)
        if hidden.get(name)
            payload[hidden[name]] = hidden.get(value, )

    login_resp = session.post(LOGIN_URL, data=payload, timeout=15)

    if logout in login_resp.text.lower() or selection menu in login_resp.text.lower()
        print(✅ Login successful!)
        return session
    else
        print(❌ Login failed. Check your credentials or the login field names.)
        print(   Hint Open browser DevTools  Network  login request  check form field names)
        sys.exit(1)

# ─────────────────────────────────────────
#  SLOT CHECKER
# ─────────────────────────────────────────

def check_slots(session)
    
    Fetch the course group page and return a list of available (not full) groups.
    Returns list of dicts — [{group NBCS2406A, max 40, cur 35}]
    
    try
        resp = session.get(TARGET_URL, timeout=15)
    except requests.RequestException as e
        print(f  ⚠️  Network error {e})
        return None

    # Check if session expired
    if login in resp.url.lower() or please enter your credentials in resp.text.lower()
        print(  🔄 Session expired, re-logging in...)
        return relogin

    soup = BeautifulSoup(resp.text, html.parser)
    rows = soup.select(table#dataTableExample1 tbody tr)

    available = []

    for row in rows
        cells = row.find_all(td)
        if len(cells)  3
            continue

        group_info = cells[1].get_text( , strip=True)
        action_cell = cells[2]

        # Parse MAX and CUR from group info text
        # Format CampusB  Group  NBCS2406A ( MAX 40 - CUR  40 )
        import re
        match = re.search(rMAXs(d+).CURss(d+), group_info)
        group_match = re.search(rGroupss(S+), group_info)

        if not match
            continue

        max_slots = int(match.group(1))
        cur_slots = int(match.group(2))
        group_name = group_match.group(1) if group_match else Unknown

        # Determine if slot is available (no Full button)
        is_full = bool(action_cell.find(button, string=lambda s s and Full in s))

        if not is_full and cur_slots  max_slots
            # Filter by target group if specified
            if TARGET_GROUP is None or TARGET_GROUP.upper() in group_name.upper()
                available.append({
                    group group_name,
                    max max_slots,
                    cur cur_slots,
                    slots_left max_slots - cur_slots
                })

    return available

# ─────────────────────────────────────────
#  ALERT
# ─────────────────────────────────────────

def alert(available_groups)
    Make noise and print a big visible alert.
    print(n + =  60)
    print(🚨🚨🚨  SLOT AVAILABLE! GO REGISTER NOW!  🚨🚨🚨)
    print(=  60)
    for g in available_groups
        print(f  ✅  Group {g['group']}    {g['cur']}{g['max']} filled    {g['slots_left']} slot(s) left)
    print(fn  👉  Open this URL in your browser NOW)
    print(f  {TARGET_URL})
    print(=  60 + n)

    # ── Desktop notification (cross-platform) ──
    try
        from plyer import notification
        notification.notify(
            title=🚨 UiTM ECR — SLOT OPEN!,
            message=fCourse slot available! Open browser NOW.n{available_groups[0]['group']} — {available_groups[0]['slots_left']} slot(s),
            timeout=30
        )
    except Exception
        pass  # plyer not installed — that's fine, the beep + print still works

    # ── Audio alert ──
    try
        # Windows
        for _ in range(5)
            winsound.Beep(1000, 500)
            time.sleep(0.2)
    except Exception
        # macOS  Linux fallback
        try
            os.system(afplay SystemLibrarySoundsGlass.aiff 2devnull  
                      paplay usrsharesoundsfreedesktopstereocomplete.oga 2devnull  
                      echo 'aaaaa')
        except Exception
            print(aaaaa)  # terminal bell

# ─────────────────────────────────────────
#  MAIN LOOP
# ─────────────────────────────────────────

def main()
    print(=  60)
    print(  UiTM ECR Course Monitor)
    print(f  Student ID  {STUDENT_ID})
    print(f  Target URL  {TARGET_URL})
    print(f  Interval    every {CHECK_INTERVAL}s)
    print(f  Target grp  {TARGET_GROUP or 'ANY available group'})
    print(=  60)

    session = create_session()
    check_count = 0

    while True
        check_count += 1
        now = datetime.now().strftime(%H%M%S)
        print(f[{now}] Check #{check_count} ..., end= , flush=True)

        result = check_slots(session)

        if result == relogin
            session = create_session()
            continue

        if result is None
            print(error — retrying...)
        elif len(result) == 0
            print(All full. Waiting...)
        else
            print(fFOUND {len(result)} available group(s)!)
            alert(result)
            # Keep alerting every 30s until you register
            time.sleep(30)
            continue

        time.sleep(CHECK_INTERVAL)

if __name__ == __main__
    main()