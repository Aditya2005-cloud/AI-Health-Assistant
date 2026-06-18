"""
test_backend.py
---------------
Full automated test suite for the AI Health Assistant backend.
Tests: DB connection, signup, login, JWT security, protected routes,
       history, medicine endpoint, and edge cases.

Run with:  python test_backend.py
"""

import sys
import io
import requests
import json
import time

# Fix Windows console encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

BASE = "http://127.0.0.1:5000"
PASS = "[PASS]"
FAIL = "[FAIL]"

results = []   # (label, passed)
token   = None # JWT token shared across tests
user_id = None


def test(label, passed, detail=""):
    icon = PASS if passed else FAIL
    print(f"  {icon}  {label}")
    if detail and not passed:
        print(f"        -> {detail}")
    results.append((label, passed))


def section(title):
    print(f"\n" + "-"*58)
    print(f"  {title}")
    print("-"*58)


# ===========================================================
# 1. SERVER HEALTH
# ===========================================================
section("1. Server Health")

try:
    r = requests.get(f"{BASE}/", timeout=4)
    test("Frontend is served (GET /)", r.status_code == 200)
except Exception as e:
    test("Flask server reachable", False, str(e))
    print("\n[ERROR] Server not reachable. Start it with: python app.py")
    sys.exit(1)


# ===========================================================
# 2. SIGNUP / REGISTRATION
# ===========================================================
section("2. Signup / Registration")

# 2a. Missing required fields
r = requests.post(f"{BASE}/api/auth/register", json={})
test("Signup: rejects empty body -> 400", r.status_code == 400)

# 2b. Weak password (too short)
r = requests.post(f"{BASE}/api/auth/register", json={
    "full_name": "Test User", "email": "test@example.com", "password": "weak"
})
test("Signup: rejects weak password (too short) -> 400", r.status_code == 400)

# 2c. Password with no uppercase
r = requests.post(f"{BASE}/api/auth/register", json={
    "full_name": "Test User", "email": "test@example.com", "password": "alllower1"
})
test("Signup: rejects no-uppercase password -> 400", r.status_code == 400)

# 2d. Invalid email format
r = requests.post(f"{BASE}/api/auth/register", json={
    "full_name": "Test User", "email": "notanemail", "password": "Strong1pass"
})
test("Signup: rejects invalid email -> 400", r.status_code == 400)

# 2e. Invalid blood group
r = requests.post(f"{BASE}/api/auth/register", json={
    "full_name": "Test User", "email": "bg@test.com",
    "password": "Strong1pass", "blood_group": "Z+"
})
test("Signup: rejects invalid blood group -> 400", r.status_code == 400)

# 2f. Valid full signup — stores token and user_id
unique_email = f"testuser_{int(time.time())}@example.com"
r = requests.post(f"{BASE}/api/auth/register", json={
    "full_name":                "Aditya Kumar",
    "email":                    unique_email,
    "password":                 "Secure@123",
    "age":                      22,
    "gender":                   "Male",
    "phone":                    "+91-9876543210",
    "whatsapp":                 "+91-9876543210",
    "known_allergies":          "Penicillin",
    "medical_conditions":       "Diabetes",
    "current_medications":      "Metformin 500mg",
    "blood_group":              "O+",
    "emergency_contact_name":   "Ravi Kumar",
    "emergency_contact_number": "+91-9123456780",
})
data = r.json()
signup_ok = r.status_code == 201 and "token" in data and "user" in data
test("Signup: valid full registration -> 201 + JWT token", signup_ok,
     json.dumps(data) if not signup_ok else "")

if signup_ok:
    token   = data["token"]
    user_id = data["user"]["id"]

# 2g. Password NOT in response
test("Signup: password_hash NOT in response",
     "password" not in data.get("user", {}) and
     "password_hash" not in data.get("user", {}))

# 2h. Duplicate email -> 409
r = requests.post(f"{BASE}/api/auth/register", json={
    "full_name": "Someone", "email": unique_email, "password": "Secure@123"
})
test("Signup: duplicate email -> 409", r.status_code == 409)


# ===========================================================
# 3. LOGIN
# ===========================================================
section("3. Login")

# 3a. Wrong password
r = requests.post(f"{BASE}/api/auth/login",
                  json={"email": unique_email, "password": "wrongpass"})
test("Login: wrong password -> 401", r.status_code == 401)

# 3b. Wrong email (non-existent)
r = requests.post(f"{BASE}/api/auth/login",
                  json={"email": "nobody@nowhere.com", "password": "Secure@123"})
test("Login: unknown email -> 401", r.status_code == 401)

# 3c. Anti-enumeration: same error for wrong email vs wrong password
r1 = requests.post(f"{BASE}/api/auth/login",
                   json={"email": "nobody@x.com", "password": "Abc12345"})
r2 = requests.post(f"{BASE}/api/auth/login",
                   json={"email": unique_email, "password": "WrongPass1"})
test("Login: same error message for wrong email vs wrong password (anti-enumeration)",
     r1.json().get("error") == r2.json().get("error"))

# 3d. Correct credentials -> 200 + JWT
r = requests.post(f"{BASE}/api/auth/login",
                  json={"email": unique_email, "password": "Secure@123"})
data = r.json()
login_ok = r.status_code == 200 and "token" in data
test("Login: correct credentials -> 200 + JWT token", login_ok)
if login_ok:
    token = data["token"]  # Refresh token

# 3e. Password not exposed on login
test("Login: password_hash NOT in login response",
     "password" not in data.get("user", {}) and
     "password_hash" not in data.get("user", {}))


# ===========================================================
# 4. JWT SECURITY
# ===========================================================
section("4. JWT Security")

# 4a. No token at all -> 401
r = requests.get(f"{BASE}/api/auth/profile")
test("JWT: no token -> 401", r.status_code == 401)

# 4b. Fake/tampered token -> 401
r = requests.get(f"{BASE}/api/auth/profile",
                 headers={"Authorization": "Bearer faketoken.abc.xyz"})
test("JWT: fake/tampered token -> 401", r.status_code == 401)

# 4c. Malformed Authorization header -> 401
r = requests.get(f"{BASE}/api/auth/profile",
                 headers={"Authorization": "NotBearer tokenhere"})
test("JWT: malformed header (not Bearer) -> 401", r.status_code == 401)

# 4d. Valid token -> 200
r = requests.get(f"{BASE}/api/auth/profile",
                 headers={"Authorization": f"Bearer {token}"})
test("JWT: valid token -> 200 (profile accessible)", r.status_code == 200)


# ===========================================================
# 5. DATABASE STORAGE VERIFICATION
# ===========================================================
section("5. Database Storage Verification")

r = requests.get(f"{BASE}/api/auth/profile",
                 headers={"Authorization": f"Bearer {token}"})
user = r.json().get("user", {})

test("DB: full_name stored correctly",           user.get("full_name") == "Aditya Kumar")
test("DB: email stored in lowercase",            user.get("email") == unique_email)
test("DB: age (integer) stored correctly",       user.get("age") == 22)
test("DB: gender stored correctly",              user.get("gender") == "Male")
test("DB: blood_group stored correctly",         user.get("blood_group") == "O+")
test("DB: known_allergies stored",               user.get("known_allergies") == "Penicillin")
test("DB: medical_conditions stored",            user.get("medical_conditions") == "Diabetes")
test("DB: current_medications stored",           user.get("current_medications") == "Metformin 500mg")
test("DB: emergency_contact_name stored",        user.get("emergency_contact_name") == "Ravi Kumar")
test("DB: emergency_contact_number stored",      user.get("emergency_contact_number") == "+91-9123456780")
test("DB: password is NOT exposed in any form",
     "password" not in user and "password_hash" not in user)
test("DB: user has an id assigned",              user.get("id") is not None)
test("DB: created_at timestamp present",         user.get("created_at") is not None)


# ===========================================================
# 6. CONSULTATION ENDPOINT SECURITY
# ===========================================================
section("6. Consultation Endpoint Security")

# 6a. No token -> 401
r = requests.post(f"{BASE}/api/consult", json={"symptoms": "I have a headache"})
test("Consult: no token -> 401 (login required)", r.status_code == 401)

# 6b. Empty symptoms -> 400
r = requests.post(f"{BASE}/api/consult",
                  headers={"Authorization": f"Bearer {token}"},
                  json={"symptoms": ""})
test("Consult: empty symptoms -> 400", r.status_code == 400)

# 6c. Too short -> 400
r = requests.post(f"{BASE}/api/consult",
                  headers={"Authorization": f"Bearer {token}"},
                  json={"symptoms": "ow"})
test("Consult: too short (<10 chars) -> 400", r.status_code == 400)

# 6d. Emergency detection
r = requests.post(f"{BASE}/api/consult",
                  headers={"Authorization": f"Bearer {token}"},
                  json={"symptoms": "I have severe chest pain and difficulty breathing"})
data = r.json()
test("Consult: emergency keywords detected -> is_emergency=True",
     r.status_code == 200 and data.get("is_emergency") == True)
test("Consult: emergency severity returned as 'Emergency'",
     data.get("severity") == "Emergency")
test("Consult: emergency consultation saved (consultation_id in response)",
     "consultation_id" in data)


# ===========================================================
# 7. HISTORY ENDPOINT SECURITY
# ===========================================================
section("7. History Endpoint Security")

# 7a. No token -> 401
r = requests.get(f"{BASE}/api/history")
test("History: no token -> 401", r.status_code == 401)

# 7b. Valid token -> 200 with consultations list
r = requests.get(f"{BASE}/api/history",
                 headers={"Authorization": f"Bearer {token}"})
data = r.json()
test("History: valid token -> 200 with consultations list",
     r.status_code == 200 and "consultations" in data)
test("History: emergency consultation is in history",
     any(c.get("is_emergency") for c in data.get("consultations", [])))

# 7c. User isolation — register a second user, they should NOT see user1's data
r2 = requests.post(f"{BASE}/api/auth/register", json={
    "full_name": "Other User",
    "email":     f"other_{int(time.time())}@example.com",
    "password":  "Other@9999",
})
if r2.status_code == 201:
    token2 = r2.json()["token"]
    r2_hist = requests.get(f"{BASE}/api/history",
                           headers={"Authorization": f"Bearer {token2}"})
    other_records = r2_hist.json().get("consultations", [])
    # Second user should see 0 records (they haven't consulted yet)
    test("History: user isolation (second user sees 0 records)",
         len(other_records) == 0)
else:
    test("History: user isolation test setup", False, "Could not register second user")

# 7d. GET single consultation by ID
all_consultations = requests.get(f"{BASE}/api/history",
                                 headers={"Authorization": f"Bearer {token}"}).json()
if all_consultations.get("consultations"):
    first_id = all_consultations["consultations"][0]["id"]
    r = requests.get(f"{BASE}/api/history/{first_id}",
                     headers={"Authorization": f"Bearer {token}"})
    test("History: GET single consultation by ID -> 200",
         r.status_code == 200 and "consultation" in r.json())
    # Second user trying to access first user's consultation
    r_steal = requests.get(f"{BASE}/api/history/{first_id}",
                           headers={"Authorization": f"Bearer {token2}"})
    test("History: cross-user access denied -> 404",
         r_steal.status_code == 404)
else:
    test("History: single consultation fetch (no data to test)", False)


# ===========================================================
# 8. MEDICINE ENDPOINT
# ===========================================================
section("8. Medicine Endpoint")

# 8a. Public access (no token)
r = requests.get(f"{BASE}/api/medicines")
data = r.json()
test("Medicines: accessible without login -> 200",   r.status_code == 200)
test("Medicines: returns a list",                    isinstance(data.get("medicines"), list))
test("Medicines: at least 20 OTC medicines seeded",  len(data.get("medicines", [])) >= 20)
test("Medicines: each has name, category, purpose",
     all("name" in m and "category" in m and "purpose" in m
         for m in data.get("medicines", [])))

# 8b. With JWT — conflict_warning field should be present
r = requests.get(f"{BASE}/api/medicines",
                 headers={"Authorization": f"Bearer {token}"})
meds = r.json().get("medicines", [])
test("Medicines: conflict_warning field returned for logged-in user",
     all("conflict_warning" in m for m in meds))


# ===========================================================
# 9. PROFILE UPDATE
# ===========================================================
section("9. Profile Update")

r = requests.put(f"{BASE}/api/auth/profile",
                 headers={"Authorization": f"Bearer {token}"},
                 json={"known_allergies": "Penicillin, Aspirin", "blood_group": "A+"})
test("Profile update: valid token -> 200",       r.status_code == 200)

# Verify update was persisted
r = requests.get(f"{BASE}/api/auth/profile",
                 headers={"Authorization": f"Bearer {token}"})
updated = r.json().get("user", {})
test("Profile update: changes saved in DB",
     updated.get("known_allergies") == "Penicillin, Aspirin" and
     updated.get("blood_group") == "A+")

# No token -> 401
r = requests.put(f"{BASE}/api/auth/profile", json={"full_name": "Hacker"})
test("Profile update: no token -> 401",          r.status_code == 401)


# ===========================================================
# 10. LOGOUT
# ===========================================================
section("10. Logout")

r = requests.post(f"{BASE}/api/auth/logout",
                  headers={"Authorization": f"Bearer {token}"})
test("Logout: valid token -> 200", r.status_code == 200)

r = requests.post(f"{BASE}/api/auth/logout")
test("Logout: no token -> 401",    r.status_code == 401)


# ===========================================================
# FINAL SUMMARY
# ===========================================================
section("FINAL TEST RESULTS")

passed_count = sum(1 for _, p in results if p)
total        = len(results)
failed_tests = [(l, p) for l, p in results if not p]

print(f"\n  Total  : {total}")
print(f"  Passed : {passed_count}")
print(f"  Failed : {total - passed_count}")

if failed_tests:
    print("\n  Failed tests:")
    for label, _ in failed_tests:
        print(f"    [FAIL]  {label}")

print()
if passed_count == total:
    print("  All tests passed! Backend is secure and working correctly.")
else:
    print(f"  {total - passed_count} test(s) need attention (see above).")
print()
