/* ==========================================
   Medivio — Frontend Logic
   Works with the Python Flask backend.
   
   Changes from v1:
   - Stores JWT token from login/register
   - Sends "Authorization: Bearer <token>" on protected API calls
   - Redirects to login if token is missing or expired
   - /api/consult now requires login (JWT protected)
   - /api/history now uses JWT (no user_id in URL)
   ========================================== */

const API = "";  // Same origin — Flask serves both frontend and API

// ── App State ──────────────────────────────
let currentUser = null;  // Logged-in user object
let authToken   = null;  // JWT token
let allMedicines = [];   // Cached medicine list
let currentMedicineView = [];
let medicineRecommendationActive = false;
let lastConsultationData = null;
let lastConsultInputs = null;
let googleClientId = null;
let googleScriptReady = false;
let googleButtonInitialized = false;
let pendingSsoUser = null;

// ── On Page Load ───────────────────────────
document.addEventListener("DOMContentLoaded", () => {
    // Restore session from localStorage (survives browser refresh)
    const savedToken = localStorage.getItem("healthai_token");
    const savedUser  = localStorage.getItem("healthai_user");

    if (savedToken && savedUser) {
        authToken   = savedToken;
        currentUser = JSON.parse(savedUser);
        updateAuthUI();
        // Silently verify the token is still valid
        verifyToken();
    }

    setupNavigation();
    loadSsoConfig();
    loadMedicines();
    startNotificationPolling();
});

// ── JWT Helper ─────────────────────────────
/** Build headers with JWT token for protected API calls. */
function authHeaders() {
    const headers = { "Content-Type": "application/json" };
    if (authToken) headers["Authorization"] = `Bearer ${authToken}`;
    return headers;
}

/** Call /api/auth/profile to check if the saved token is still valid. */
async function verifyToken() {
    try {
        const res = await fetch(API + "/api/auth/profile", { headers: authHeaders() });
        if (!res.ok) {
            // Token expired or invalid — clear session silently
            clearSession();
        } else {
            const data = await res.json();
            currentUser = data.user;
            localStorage.setItem("healthai_user", JSON.stringify(currentUser));
            updateAuthUI();
        }
    } catch {
        // Network error — keep session as-is
    }
}

/** Clear all auth state from memory and localStorage. */
function clearSession() {
    currentUser = null;
    authToken   = null;
    localStorage.removeItem("healthai_token");
    localStorage.removeItem("healthai_user");
    updateAuthUI();
}

// ── Navigation ─────────────────────────────
function setupNavigation() {
    document.querySelectorAll(".nav-link").forEach(link => {
        link.addEventListener("click", e => {
            e.preventDefault();
            navigateTo(link.dataset.page);
        });
    });
}

function navigateTo(page) {
    // Consult, History, and Reminders require login
    const protectedPages = ["consult", "history", "reminders"];
    if (protectedPages.includes(page) && !currentUser) {
        showToast("Please login to access this feature.", "error");
        showModal("login");
        return;
    }

    // Switch visible page
    document.querySelectorAll(".page").forEach(p => p.classList.remove("active"));
    document.querySelectorAll(".nav-link").forEach(l => l.classList.remove("active"));

    const target  = document.getElementById("page-" + page);
    const navLink = document.querySelector(`.nav-link[data-page="${page}"]`);
    if (target)  target.classList.add("active");
    if (navLink) navLink.classList.add("active");

    if (page === "history") loadHistory();
    if (page === "reminders") {
        loadReminders();
        loadNotifications();
        loadEmailLogs();
    }
    window.scrollTo({ top: 0, behavior: "smooth" });
}

// ── Auth Modals ────────────────────────────
function showModal(type) {
    document.getElementById("modal-overlay").classList.remove("hidden");
    document.getElementById("login-form").classList.toggle("hidden", type !== "login");
    document.getElementById("register-form").classList.toggle("hidden", type !== "register");
    document.getElementById("sso-profile-form").classList.add("hidden");
    document.querySelectorAll(".form-error").forEach(e => e.classList.add("hidden"));
    renderGoogleSigninButtons();
}
function closeModal() {
    document.getElementById("modal-overlay").classList.add("hidden");
}

// ── Login ──────────────────────────────────
async function handleLogin() {
    const email    = document.getElementById("login-email").value.trim();
    const password = document.getElementById("login-password").value;

    if (!email || !password) return showFormError("login-error", "All fields are required");

    try {
        const res  = await fetch(API + "/api/auth/login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, password }),
        });
        const data = await res.json();

        if (!res.ok) return showFormError("login-error", data.error || "Login failed");

        // Save token + user
        authToken   = data.token;
        currentUser = data.user;
        localStorage.setItem("healthai_token", authToken);
        localStorage.setItem("healthai_user",  JSON.stringify(currentUser));

        updateAuthUI();
        prefillConsultFields(currentUser);
        closeModal();
        showToast("Welcome back, " + currentUser.full_name + "! 👋", "success");

    } catch {
        showFormError("login-error", "Connection error. Is the server running?");
    }
}

// ── Register ───────────────────────────────
async function handleRegister() {
    const name     = document.getElementById("reg-name").value.trim();
    const email    = document.getElementById("reg-email").value.trim();
    const password = document.getElementById("reg-password").value;

    if (!name || !email || !password)
        return showFormError("register-error", "Name, email and password are required");
    if (password.length < 8)
        return showFormError("register-error", "Password must be at least 8 characters");

    const payload = {
        full_name:          name,
        email,
        password,
        age:                document.getElementById("reg-age").value || null,
        gender:             document.getElementById("reg-gender").value || null,
        medical_conditions: document.getElementById("reg-conditions").value || null,
        known_allergies:    document.getElementById("reg-allergies").value || null,
    };

    try {
        const res  = await fetch(API + "/api/auth/register", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        const data = await res.json();

        if (!res.ok) return showFormError("register-error", data.error || "Registration failed");

        // Save token + user
        authToken   = data.token;
        currentUser = data.user;
        localStorage.setItem("healthai_token", authToken);
        localStorage.setItem("healthai_user",  JSON.stringify(currentUser));

        updateAuthUI();
        prefillConsultFields(currentUser);
        closeModal();
        showToast("Account created! 🎉", "success");

    } catch {
        showFormError("register-error", "Connection error. Is the server running?");
    }
}

// ── Logout ─────────────────────────────────
async function logout() {
    if (authToken) {
        // Tell the server (best practice, even though JWT is stateless)
        try {
            await fetch(API + "/api/auth/logout", {
                method: "POST",
                headers: authHeaders(),
            });
        } catch { /* ignore */ }
    }
    clearSession();
    navigateTo("home");
    showToast("Logged out successfully.", "success");
}

// ── Update navbar UI ───────────────────────
function updateAuthUI() {
    const authDiv = document.getElementById("nav-auth");
    const userDiv = document.getElementById("nav-user");

    if (currentUser) {
        authDiv.classList.add("hidden");
        userDiv.classList.remove("hidden");
        document.getElementById("user-greeting").textContent =
            "Hi, " + currentUser.full_name.split(" ")[0];
        prefillConsultFields(currentUser);
    } else {
        authDiv.classList.remove("hidden");
        userDiv.classList.add("hidden");
    }
}

function showFormError(id, msg) {
    const el = document.getElementById(id);
    el.textContent = msg;
    el.classList.remove("hidden");
}

function prefillConsultFields(user = currentUser) {
    if (!user) return;

    const usernameField = document.getElementById("patient-username");
    const bloodGroupField = document.getElementById("patient-blood-group");
    const allergiesField = document.getElementById("patient-allergies");
    const ageField = document.getElementById("patient-age");
    const genderField = document.getElementById("patient-gender");

    if (usernameField && !usernameField.value) {
        usernameField.value = user.full_name || "";
    }
    if (bloodGroupField && !bloodGroupField.value) {
        bloodGroupField.value = user.blood_group || "";
    }
    if (allergiesField && !allergiesField.value) {
        allergiesField.value = user.known_allergies || "";
    }
    if (ageField && !ageField.value && user.age) {
        ageField.value = user.age;
    }
    if (genderField && !genderField.value && user.gender) {
        genderField.value = user.gender;
    }
}

function getConsultInputs() {
    return {
        username: document.getElementById("patient-username")?.value.trim() || "",
        blood_group: document.getElementById("patient-blood-group")?.value || "",
        allergies: document.getElementById("patient-allergies")?.value.trim() || "",
        age: document.getElementById("patient-age")?.value || "",
        gender: document.getElementById("patient-gender")?.value || "",
        symptoms: document.getElementById("symptoms-input")?.value.trim() || "",
    };
}

function showSsoProfileForm(user) {
    pendingSsoUser = user || currentUser;
    document.getElementById("login-form").classList.add("hidden");
    document.getElementById("register-form").classList.add("hidden");
    document.getElementById("sso-profile-form").classList.remove("hidden");
    document.querySelectorAll(".form-error").forEach(e => e.classList.add("hidden"));

    document.getElementById("sso-gender").value = pendingSsoUser?.gender || "";
    document.getElementById("sso-conditions").value = pendingSsoUser?.medical_conditions || "";
    document.getElementById("sso-allergies").value = pendingSsoUser?.known_allergies || "";
}

async function loadSsoConfig() {
    try {
        const res = await fetch(API + "/api/auth/sso-config");
        const data = await res.json();
        googleClientId = data.google_client_id || null;
        if (data.enabled && googleClientId) {
            loadGoogleIdentityScript();
        }
    } catch {
        // Keep normal auth working even if SSO config cannot load.
    }
}

function loadGoogleIdentityScript() {
    if (googleScriptReady || document.getElementById("google-identity-script")) return;
    const script = document.createElement("script");
    script.id = "google-identity-script";
    script.src = "https://accounts.google.com/gsi/client";
    script.async = true;
    script.defer = true;
    script.onload = () => {
        googleScriptReady = true;
        renderGoogleSigninButton();
    };
    document.head.appendChild(script);
}

function renderGoogleSigninButtons() {
    if (!googleClientId || !window.google?.accounts?.id) return;
    if (!googleButtonInitialized) {
        window.google.accounts.id.initialize({
            client_id: googleClientId,
            callback: handleGoogleCredentialResponse,
            cancel_on_tap_outside: false,
        });
        googleButtonInitialized = true;
    }
    renderGoogleSigninButton("google-signin-button-login");
    renderGoogleSigninButton("google-signin-button-register");
}

function renderGoogleSigninButton(containerId) {
    const container = document.getElementById(containerId);
    if (!container || container.children.length) return;

    window.google.accounts.id.renderButton(container, {
        theme: "filled_blue",
        size: "large",
        shape: "pill",
        text: "continue_with",
        width: 320,
    });
}

async function handleGoogleCredentialResponse(response) {
    if (!response?.credential) {
        showToast("Google sign-in did not return a credential.", "error");
        return;
    }

    try {
        const res = await fetch(API + "/api/auth/google", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ credential: response.credential }),
        });
        const data = await res.json();

        if (!res.ok) {
            showToast(data.error || "Google sign-in failed.", "error");
            return;
        }

        authToken = data.token;
        currentUser = data.user;
        localStorage.setItem("healthai_token", authToken);
        localStorage.setItem("healthai_user", JSON.stringify(currentUser));

        updateAuthUI();
        if (data.auth_method === "google" && data.needs_profile_completion) {
            showToast("Please complete your profile details.", "success");
            showSsoProfileForm(currentUser);
            return;
        }

        closeModal();
        showToast("Signed in with Google successfully.", "success");
    } catch (error) {
        showToast("Google sign-in failed: " + error.message, "error");
    }
}

async function saveSsoProfile() {
    if (!currentUser) {
        showToast("Please sign in first.", "error");
        return;
    }

    const payload = {
        gender: document.getElementById("sso-gender").value || null,
        medical_conditions: document.getElementById("sso-conditions").value.trim() || null,
        known_allergies: document.getElementById("sso-allergies").value.trim() || null,
    };

    if (!payload.gender || !payload.medical_conditions || !payload.known_allergies) {
        showFormError("sso-profile-error", "Please complete gender, allergies, and conditions.");
        return;
    }

    try {
        const res = await fetch(API + "/api/auth/profile", {
            method: "PUT",
            headers: authHeaders(),
            body: JSON.stringify(payload),
        });
        const data = await res.json();

        if (!res.ok) {
            showFormError("sso-profile-error", data.error || "Could not save profile details.");
            return;
        }

        currentUser = data.user;
        localStorage.setItem("healthai_user", JSON.stringify(currentUser));
        pendingSsoUser = null;
        closeModal();
        updateAuthUI();
        showToast("Profile completed successfully.", "success");
    } catch (error) {
        showFormError("sso-profile-error", error.message || "Failed to save profile.");
    }
}

// ── Consultation ───────────────────────────
function addTag(tag) {
    const ta = document.getElementById("symptoms-input");
    ta.value = ta.value ? ta.value + ", " + tag : tag;
    ta.focus();
}

async function analyzeSymptoms() {
    // Must be logged in to consult
    if (!currentUser) {
        showToast("Please login to start a consultation.", "error");
        showModal("login");
        return;
    }

    const consultInputs = getConsultInputs();
    lastConsultInputs = consultInputs;
    const symptoms = consultInputs.symptoms;
    if (!symptoms)        return showToast("Please describe your symptoms", "error");
    if (symptoms.length < 10) return showToast("Please provide more detail (min 10 characters).", "error");

    const btn = document.getElementById("btn-analyze");
    btn.disabled = true;
    btn.innerHTML = "Analyzing...";

    const panel   = document.getElementById("results-panel");
    const loading = document.getElementById("loading-state");
    const report  = document.getElementById("report");
    panel.classList.remove("hidden");
    loading.classList.remove("hidden");
    report.classList.add("hidden");

    resetSteps();
    activateStep(1);

    try {
        setTimeout(() => { completeStep(1); activateStep(2); }, 2000);
        setTimeout(() => { completeStep(2); activateStep(3); }, 5000);

        // POST /api/consult — requires JWT
        const res = await fetch(API + "/api/consult", {
            method: "POST",
            headers: authHeaders(),
            body: JSON.stringify({
                symptoms,
                patient_profile: {
                    username: consultInputs.username,
                    blood_group: consultInputs.blood_group,
                    allergies: consultInputs.allergies,
                    age: consultInputs.age,
                    gender: consultInputs.gender,
                },
            }),
        });

        if (res.status === 401) {
            clearSession();
            showToast("Session expired. Please login again.", "error");
            showModal("login");
            return;
        }

        const data = await res.json();
        if (!res.ok) {
            showToast(data.error || "Consultation failed. Please try again.", "error");
            loading.classList.add("hidden");
            return;
        }

        completeStep(3);
        setTimeout(() => {
            loading.classList.add("hidden");
            renderReport(data);
            report.classList.remove("hidden");
        }, 600);

    } catch (err) {
        showToast("Failed to analyze symptoms: " + err.message, "error");
        loading.classList.add("hidden");
    } finally {
        btn.disabled = false;
        btn.innerHTML = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg> Analyze My Symptoms`;
    }
}

function resetSteps() {
    [1,2,3].forEach(i => {
        const el = document.getElementById("step-" + i);
        if (el) el.classList.remove("active", "done");
    });
}
function activateStep(n) {
    const el = document.getElementById("step-" + n);
    if (el) el.classList.add("active");
}
function completeStep(n) {
    const el = document.getElementById("step-" + n);
    if (el) { el.classList.remove("active"); el.classList.add("done"); }
}

// ── Render AI Report ───────────────────────
function renderReport(data) {
    lastConsultationData = data;
    const eBanner = document.getElementById("emergency-banner");
    if (data.is_emergency) eBanner.classList.remove("hidden");
    else eBanner.classList.add("hidden");

    const sev     = (data.severity || "Unknown").toLowerCase();
    const sevMap  = { low: "severity-low", medium: "severity-medium", high: "severity-high", emergency: "severity-emergency" };
    const sevIcons = { low: "🟢", medium: "🟡", high: "🟠", emergency: "🔴" };
    document.getElementById("severity-section").innerHTML =
        `<span class="severity-badge ${sevMap[sev] || ''}">${sevIcons[sev] || "⚪"} Severity: ${data.severity || "Unknown"}</span>`;

    document.getElementById("unified-report-body").innerHTML = buildUnifiedReportHTML(data);
    document.getElementById("results-panel").scrollIntoView({ behavior: "smooth", block: "start" });
}

function buildUnifiedReportHTML(data) {
    let html = "";
    const g = data.gemini_response || {};
    const q = data.groq_response   || {};

    // Patient summary
    const summary = g.patient_summary || g.junior_clinician_assessment?.presentation_summary;
    if (summary) html += sec("Patient Intake & Case Presentation", `<p>${summary}</p>`);

    // Clinical notes
    const notes = q.clinical_discussion_notes || q.doctor_review;
    if (notes) html += sec("Clinical Board Assessment Notes",
        `<div style="background:rgba(99,102,241,.08);border-left:4px solid var(--primary);padding:14px 18px;border-radius:6px;font-style:italic;line-height:1.6;"><p>${notes}</p></div>`);

    // Diagnoses
    const diagnoses = q.validated_diagnoses || g.junior_clinician_assessment?.differential_diagnoses || g.possible_causes || [];
    if (diagnoses.length) html += sec("Provisional Diagnoses",
        diagnoses.map(c => `<div style="margin-bottom:12px;padding:14px;border-radius:8px;background:rgba(255,255,255,.03);border:1px solid var(--border);">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
                <span style="font-weight:600;font-size:1.05rem;">${c.condition}</span>
                <span style="font-size:.85rem;padding:2px 8px;border-radius:12px;background:rgba(99,102,241,.2);color:var(--primary-light);font-weight:500;">
                    ${c.confidence || c.probability || "Medium"}
                </span>
            </div>
            <div style="font-size:.9rem;color:var(--text-muted);line-height:1.5;">${c.clinical_notes || c.reason || ""}</div>
        </div>`).join(""));

    // Treatment plan
    const plan = q.attending_treatment_plan || q.approved_treatment_plan || g.junior_clinician_assessment?.proposed_treatment || g.recommended_actions;
    if (plan) {
        let planHtml = "";

        const rest = plan.bed_rest_routine || plan.rest;
        if (rest) planHtml += block("🛏️ Rest & Activity", rest);

        const diet = plan.diet_and_hydration || plan.diet_hydration;
        if (diet) planHtml += block("🍵 Diet & Hydration", diet);

        const avoid = plan.things_to_avoid;
        if (avoid) planHtml += `<div style="margin-bottom:18px;padding:14px;border-radius:8px;background:rgba(239,68,68,.06);border:1px solid rgba(239,68,68,.2);">
            <h5 style="margin-bottom:8px;color:#fca5a5;font-weight:600;">🚫 Contraindications & Avoidances</h5>
            <p style="color:#fcd34d;font-size:.95rem;line-height:1.6;">${avoid}</p>
        </div>`;

        const meds = plan.approved_otc_medicines || plan.otc_medicines || plan.proposed_otc_meds || [];
        if (meds.length) planHtml += `<div style="margin-bottom:18px;">
            <h5 style="margin-bottom:10px;font-weight:600;">💊 Approved OTC Medicines</h5>
            <div style="display:flex;flex-direction:column;gap:10px;">` +
            meds.map(m => {
                if (typeof m === "string") return `<div style="padding:10px 14px;border-radius:6px;background:rgba(16,185,129,.08);border-left:3px solid #10b981;">✅ <strong style="color:#34d399;">${m}</strong></div>`;
                return `<div style="padding:12px 16px;border-radius:6px;background:rgba(16,185,129,.06);border-left:4px solid #10b981;">
                    <div style="font-weight:600;color:#34d399;margin-bottom:4px;">✅ ${m.medicine_name || m.name}</div>
                    ${m.purpose  ? `<div style="font-size:.9rem;color:var(--text-muted);">Purpose: ${m.purpose}</div>` : ""}
                    ${m.dosage   ? `<div style="font-size:.85rem;color:var(--text-muted);">📋 ${m.dosage}</div>` : ""}
                    ${m.warning  ? `<div style="font-size:.82rem;color:#fcd34d;margin-top:4px;">⚠ ${m.warning}</div>` : ""}
                </div>`;
            }).join("") + `</div></div>`;

        const care = plan.additional_care_guidelines || plan.home_remedies || [];
        if (care.length) planHtml += `<div>
            <h5 style="margin-bottom:8px;font-weight:600;">📋 Practical Care Guidelines</h5>
            <ul style="padding-left:20px;line-height:1.6;color:var(--text-muted);font-size:.95rem;">
                ${care.map(s => `<li>${s}</li>`).join("")}
            </ul>
        </div>`;

        const tests = plan.approved_medical_tests || plan.recommended_medical_tests || [];
        if (tests.length) planHtml += `<div style="margin-top:18px;">
            <h5 style="margin-bottom:10px;font-weight:600;">🔬 Recommended Medical Tests</h5>
            <div style="display:flex;flex-direction:column;gap:10px;">` +
            tests.map(t => `<div style="padding:12px 16px;border-radius:6px;background:rgba(59,130,246,.08);border-left:4px solid var(--primary);">
                <div style="font-weight:600;color:var(--primary-light);margin-bottom:4px;">${t.test_name}</div>
                <div style="font-size:.9rem;color:var(--text-muted);"><strong>When to do:</strong> ${t.when_to_do}</div>
            </div>`).join("") + `</div></div>`;

        const herbals = plan.approved_herbal_remedies || plan.recommended_herbal_remedies || [];
        if (herbals.length) planHtml += `<div style="margin-top:18px;">
            <h5 style="margin-bottom:10px;font-weight:600;">🌿 Herbal & Natural Remedies</h5>
            <div style="display:flex;flex-direction:column;gap:10px;">` +
            herbals.map(h => `<div style="padding:12px 16px;border-radius:6px;background:rgba(16,185,129,.06);border-left:4px solid #10b981;">
                <div style="font-weight:600;color:#059669;margin-bottom:4px;">${h.remedy_name}</div>
                <div style="font-size:.9rem;color:var(--text-muted);"><strong>Usage:</strong> ${h.usage}</div>
            </div>`).join("") + `</div></div>`;

        const exercises = plan.approved_exercises || plan.recommended_exercises || [];
        if (exercises.length) planHtml += `<div style="margin-top:18px;">
            <h5 style="margin-bottom:10px;font-weight:600;">🤸 Recommended Exercises</h5>
            <div style="display:flex;flex-direction:column;gap:10px;">` +
            exercises.map(e => `<div style="padding:12px 16px;border-radius:6px;background:rgba(139,92,246,.06);border-left:4px solid #8b5cf6;">
                <div style="font-weight:600;color:#7c3aed;margin-bottom:4px;">${e.exercise_name}</div>
                <div style="font-size:.9rem;color:var(--text-muted);"><strong>Instructions:</strong> ${e.instructions}</div>
            </div>`).join("") + `</div></div>`;

        html += sec("Consolidated Treatment Protocol", planHtml);
    }

    // Red flags
    const flags = q.red_flags || g.red_flags;
    if (flags) {
        const list = Array.isArray(flags) ? flags : [flags];
        html += sec("⚠️ Critical Warning Signs",
            list.map(r => `<div style="margin-bottom:8px;padding:12px;border-radius:6px;background:rgba(239,68,68,.08);border-left:4px solid var(--red);color:#fca5a5;font-size:.95rem;">⚠ ${r}</div>`).join(""));
    }

    // Doctor recommendation
    const rec = q.doctor_recommendation || g.when_to_see_doctor;
    if (rec) html += sec("Urgency & Follow-up", `<p style="line-height:1.6;font-size:.95rem;">${rec}</p>`);

    // Disclaimer
    const disclaimer = q.final_disclaimer || g.disclaimer ||
        "This consultation provides educational guidance and is not a substitute for professional medical advice.";
    html += `<p style="font-size:.8rem;color:var(--text-muted);margin-top:18px;font-style:italic;border-top:1px solid var(--border);padding-top:12px;">⚕️ ${disclaimer}</p>`;

    return html;
}

function sec(title, content) {
    return `<div class="report-section"><h4>${title}</h4>${content}</div>`;
}
function block(title, text) {
    return `<div style="margin-bottom:18px;"><h5 style="margin-bottom:8px;font-weight:600;">${title}</h5><p style="line-height:1.6;color:var(--text-muted);font-size:.95rem;">${text}</p></div>`;
}

function resetConsultation() {
    document.getElementById("symptoms-input").value = "";
    const usernameField = document.getElementById("patient-username");
    const bloodGroupField = document.getElementById("patient-blood-group");
    const allergiesField = document.getElementById("patient-allergies");
    const ageField = document.getElementById("patient-age");
    const genderField = document.getElementById("patient-gender");
    if (usernameField) usernameField.value = "";
    if (bloodGroupField) bloodGroupField.value = "";
    if (allergiesField) allergiesField.value = "";
    if (ageField) ageField.value = "";
    if (genderField) genderField.value = "";
    document.getElementById("results-panel").classList.add("hidden");
    document.getElementById("report").classList.add("hidden");
    document.getElementById("loading-state").classList.remove("hidden");
    document.getElementById("prescription-panel").classList.add("hidden");
    document.getElementById("prescription-panel").innerHTML = "";
    lastConsultationData = null;
    lastConsultInputs = null;
    resetSteps();
}

function generatePrescription(preventScroll = false) {
    if (!lastConsultationData) {
        showToast("Please run a consultation first.", "error");
        return;
    }

    const panel = document.getElementById("prescription-panel");
    panel.innerHTML = buildPrescriptionHTML(lastConsultationData);
    panel.classList.remove("hidden");
    if (!preventScroll) {
        panel.scrollIntoView({ behavior: "smooth", block: "start" });
    }
}

function printPrescription() {
    const panel = document.getElementById('prescription-panel');
    if (panel.classList.contains('hidden')) {
        generatePrescription(true);
        if (panel.classList.contains('hidden')) return; // Prevent export if generation failed
    }

    const patientName = lastConsultInputs?.username || currentUser?.full_name || "Patient";
    const filename = `Medivio_Consultation_${patientName.replace(/\s+/g, '_')}.pdf`;
    
    // Capture the entire report (which includes the detailed report and prescription)
    // The action buttons will be automatically ignored via data-html2canvas-ignore
    const targetElement = document.getElementById('report');

    const opt = {
        margin:       10,
        filename:     filename,
        image:        { type: 'jpeg', quality: 0.98 },
        html2canvas:  { scale: 2, useCORS: true, scrollY: 0 },
        jsPDF:        { unit: 'mm', format: 'a4', orientation: 'portrait' }
    };

    // Wait for DOM to settle completely
    setTimeout(() => {
        html2pdf().set(opt).from(targetElement).save().then(() => {
            showToast("PDF Exported Successfully!", "success");
        }).catch(err => {
            console.error("PDF Export Error:", err);
            showToast("Failed to export PDF.", "error");
        });
    }, 500);
}

function buildPrescriptionHTML(data) {
    const g = data.gemini_response || {};
    const q = data.groq_response || {};
    const plan = q.attending_treatment_plan || q.approved_treatment_plan || g.junior_clinician_assessment?.proposed_treatment || g.recommended_actions || {};
    const consult = lastConsultInputs || getConsultInputs();
    const symptoms = consult.symptoms || document.getElementById("symptoms-input")?.value || "";
    const meds = plan.approved_otc_medicines || plan.otc_medicines || plan.proposed_otc_meds || [];
    const medRows = meds.length ? meds.map((m, index) => {
        const name = typeof m === "string" ? m : (m.medicine_name || m.name || "Medication");
        const purpose = typeof m === "string" ? "Symptom relief support" : (m.purpose || "");
        const dosage = typeof m === "string" ? "Use only as directed on the label" : (m.dosage || m.common_dosage || "Follow label instructions");
        const note = typeof m === "string" ? "" : (m.warning || m.clinical_justification || "");
        const detailedDosage = buildDetailedDosage(name, dosage, purpose, index);
        return `<tr>
            <td><strong>${name}</strong></td>
            <td>${purpose}</td>
            <td>${detailedDosage}</td>
            <td>${note}</td>
        </tr>`;
    }).join("") : `<tr><td colspan="4">No OTC medicines were approved for this consultation.</td></tr>`;

    const followUp = q.doctor_recommendation || g.when_to_see_doctor || "Follow up with a licensed clinician if symptoms worsen or do not improve.";
    const disclaimer = q.final_disclaimer || g.disclaimer || "AI-generated informational summary only.";
    const avoidText = plan.things_to_avoid || "Avoid alcohol, duplicate painkillers, and any medicine not approved in this prescription.";
    const brandedAvoid = buildBrandedAvoidList(meds, symptoms, consult.allergies);
    const symptomCare = buildSymptomCareSection(symptoms, meds);
    const patientName = consult.username || currentUser?.full_name || "Patient";
    const bloodGroup = consult.blood_group || currentUser?.blood_group || "Not provided";
    const allergies = consult.allergies || currentUser?.known_allergies || "Not provided";
    const ageValue = consult.age || currentUser?.age || "—";
    const genderValue = consult.gender || currentUser?.gender || "—";
    const brandedExamples = meds.slice(0, 2).filter(Boolean);

    const tests = plan.approved_medical_tests || plan.recommended_medical_tests || [];
    const testsRows = tests.length ? tests.map(t => `<tr>
        <td><strong>${t.test_name}</strong></td>
        <td>${t.when_to_do}</td>
    </tr>`).join("") : "";

    const testsSection = tests.length ? `<div class="prescription-section">
        <h4>Recommended Medical Tests</h4>
        <table class="prescription-med-table">
            <thead>
                <tr>
                    <th>Test Name</th>
                    <th>When to Perform</th>
                </tr>
            </thead>
            <tbody>${testsRows}</tbody>
        </table>
    </div>` : "";

    const herbals = plan.approved_herbal_remedies || plan.recommended_herbal_remedies || [];
    const herbalsRows = herbals.length ? herbals.map(h => `<tr>
        <td><strong>${h.remedy_name}</strong></td>
        <td>${h.usage}</td>
    </tr>`).join("") : "";
    const herbalsSection = herbals.length ? `<div class="prescription-section">
        <h4>Herbal & Natural Remedies</h4>
        <table class="prescription-med-table">
            <thead>
                <tr>
                    <th>Remedy</th>
                    <th>Usage Instructions</th>
                </tr>
            </thead>
            <tbody>${herbalsRows}</tbody>
        </table>
    </div>` : "";

    const exercises = plan.approved_exercises || plan.recommended_exercises || [];
    const exercisesRows = exercises.length ? exercises.map(e => `<tr>
        <td><strong>${e.exercise_name}</strong></td>
        <td>${e.instructions}</td>
    </tr>`).join("") : "";
    const exercisesSection = exercises.length ? `<div class="prescription-section">
        <h4>Recommended Exercises</h4>
        <table class="prescription-med-table">
            <thead>
                <tr>
                    <th>Exercise</th>
                    <th>Instructions</th>
                </tr>
            </thead>
            <tbody>${exercisesRows}</tbody>
        </table>
    </div>` : "";

    return `
        <div class="prescription-card">
            <div class="prescription-header">
                <div class="prescription-brand">
                    <div class="brand-mark"><img src="/assets/logo.png" alt="Medivio logo"></div>
                    <div>
                        <h3>Medivio</h3>
                        <p>AI Prescription Summary</p>
                    </div>
                </div>
            </div>
            <div class="prescription-body">
                <div class="prescription-grid">
                    <div class="prescription-field">
                        <span class="label">Patient</span>
                        <div class="value">${patientName}</div>
                    </div>
                    <div class="prescription-field">
                        <span class="label">Blood Group</span>
                        <div class="value">${bloodGroup}</div>
                    </div>
                    <div class="prescription-field">
                        <span class="label">Age / Gender</span>
                        <div class="value">${ageValue} / ${genderValue}</div>
                    </div>
                    <div class="prescription-field">
                        <span class="label">Allergies</span>
                        <div class="value">${allergies}</div>
                    </div>
                    <div class="prescription-field">
                        <span class="label">Consultation</span>
                        <div class="value">${new Date().toLocaleString()}</div>
                    </div>
                </div>

                <div class="prescription-section">
                    <h4>Chief Complaint</h4>
                    <div class="prescription-note">${symptoms || "No symptoms recorded."}</div>
                </div>

                <div class="prescription-section">
                    <h4>Assessment / Guidance</h4>
                    <div class="prescription-note">${q.clinical_discussion_notes || g.patient_summary || "AI-assisted guidance generated from the consultation."}</div>
                </div>

                ${symptomCare ? `<div class="prescription-section">
                    <h4>Symptom-Specific Care</h4>
                    <div class="prescription-note">${symptomCare}</div>
                </div>` : ""}

                <div class="prescription-section">
                    <h4>Prescription Table</h4>
                    <table class="prescription-med-table">
                        <thead>
                            <tr>
                                <th>Medicine</th>
                                <th>Use</th>
                                <th>Dosage</th>
                                <th>Notes</th>
                            </tr>
                        </thead>
                        <tbody>${medRows}</tbody>
                    </table>
                </div>

                ${testsSection}
                ${herbalsSection}
                ${exercisesSection}

                <div class="prescription-section">
                    <h4>Follow-up</h4>
                    <div class="prescription-note">${followUp}</div>
                </div>

                <div class="prescription-section">
                    <h4>What To Avoid</h4>
                    <div class="prescription-note">${avoidText}</div>
                    ${brandedAvoid ? `<div class="prescription-note" style="margin-top:10px;background:rgba(239,68,68,0.06);border-left-color:var(--red);">${brandedAvoid}</div>` : ""}
                </div>

                ${brandedExamples.length ? `<div class="prescription-section">
                    <h4>Branded Medicines Reviewed</h4>
                    <table class="prescription-med-table">
                        <thead>
                            <tr>
                                <th>Brand</th>
                                <th>Why It Was Chosen</th>
                                <th>Dosage</th>
                                <th>Watch-outs</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${brandedExamples.map((m, index) => {
                                const brandName = typeof m === "string" ? m : (m.medicine_name || m.name || "Medicine");
                                const reason = typeof m === "string" ? "Included as a general OTC option." : (m.purpose || "OTC support");
                                const dosage = typeof m === "string" ? "Follow package directions" : (m.dosage || m.common_dosage || "Follow label instructions");
                                const watchouts = typeof m === "string" ? "" : (m.warning || m.clinical_justification || "");
                                return `<tr>
                                    <td><strong>${brandName}</strong></td>
                                    <td>${reason}</td>
                                    <td>${buildDetailedDosage(brandName, dosage, reason, index)}</td>
                                    <td>${watchouts}</td>
                                </tr>`;
                            }).join("")}
                        </tbody>
                    </table>
                </div>` : ""}

                <div class="signature-row">
                    <div class="signature-box">
                        <div class="signature-line"></div>
                        <div class="signature-name">Medivio AI Clinical Signature</div>
                        <div class="signature-title">Digitally signed consultation summary</div>
                    </div>
                    <div class="signature-seal">Verified AI-generated medical guidance</div>
                </div>

                <div class="prescription-note" style="margin-top:18px;">${disclaimer} This document is for informational use only and is not a substitute for an in-person prescription from a licensed clinician.</div>
            </div>
        </div>
    `;
}

function buildDetailedDosage(name, dosage, purpose, index = 0) {
    const base = (dosage || "Follow the package directions").trim();
    const lower = `${name} ${purpose} ${base}`.toLowerCase();
    const notes = [];

    if (/(paracetamol|acetaminophen|dolo|crocin)/i.test(lower)) {
        notes.push("Do not combine with other paracetamol-containing products.");
        notes.push("Take at the lowest effective dose and avoid alcohol.");
    }
    if (/(ibuprofen|diclofenac|combiflam|volini|moov)/i.test(lower)) {
        notes.push("Take after food and avoid if you have stomach ulcer, kidney disease, or NSAID allergy.");
    }
    if (/(antihistamine|cetirizine|fexofenadine|benadryl|allegra)/i.test(lower)) {
        notes.push("May cause drowsiness; avoid driving if you feel sleepy.");
    }
    if (/(ors|oral rehydration|electral)/i.test(lower)) {
        notes.push("Mix exactly as directed and use within 24 hours.");
    }
    if (/(lozenge|strepsils)/i.test(lower)) {
        notes.push("Let dissolve slowly and do not exceed the daily limit.");
    }

    if (!notes.length) {
        notes.push("Use only as directed by the clinician or on the package label.");
    }

    if (index === 0) {
        notes.unshift("Primary option for symptom relief.");
    }

    return `${base}<br><span style="color:#475569;">${notes.join(" ")}</span>`;
}

function buildBrandedAvoidList(meds, symptoms, allergies = "") {
    const text = `${symptoms} ${allergies} ${(meds || []).map(m => typeof m === "string" ? m : `${m.name || ""} ${m.purpose || ""} ${m.warning || ""}`).join(" ")}`.toLowerCase();
    const items = [];

    if (/(fever|pain|headache)/.test(text)) {
        items.push("Avoid taking Crocin, Dolo, or Combiflam together unless a licensed clinician explicitly instructs it.");
    }
    if (/(cold|cough|throat|allergy)/.test(text)) {
        items.push("Avoid Benadryl or similar sedating cough syrups before driving or operating machinery.");
    }
    if (/(acidity|stomach|gas|digestive)/.test(text)) {
        items.push("Avoid Eno or similar acid-relief sachets if you need to limit sodium or have been advised against antacids.");
    }
    if (allergies) {
        items.push(`Avoid medicines that conflict with the stated allergy history: ${allergies}.`);
    }

    return items.slice(0, 2).join("<br>");
}

function buildSymptomCareSection(symptoms, meds) {
    const text = (symptoms || "").toLowerCase();
    const lines = [];
    const findings = [];

    if (/(vomit|vomiting|nausea|nauseous)/.test(text)) {
        findings.push("Vomiting / nausea");
        lines.push("Rest your stomach for a short period, then take small frequent sips of water or ORS. Avoid exercise, heavy meals, oily food, and alcohol until the vomiting settles.");
        lines.push("If you cannot keep fluids down, add ORS (Electral) in small sips and seek medical care if vomiting is persistent or severe.");
        lines.push("Potential OTC support: ORS, as directed on the packet; do not self-start anti-vomiting medicines unless specifically advised by a clinician.");
    }
    if (/(fever|temperature|body pain|headache|pain)/.test(text)) {
        findings.push("Fever / pain");
        lines.push("Take complete rest, drink plenty of fluids, and use paracetamol-based relief only if it was approved in the prescription and you do not already take another paracetamol product.");
    }
    if (/(cough|cold|throat|congestion)/.test(text)) {
        findings.push("Cold / cough");
        lines.push("Use warm fluids, steam if tolerated, and avoid cold drinks if they worsen your symptoms.");
    }
    if (/(acidity|gas|indigestion|stomach ache|diarrhea)/.test(text)) {
        findings.push("Digestive symptoms");
        lines.push("Keep meals light and frequent, avoid fried/spicy food, and replace fluids carefully if there is loose motion.");
    }
    if (/(allergy|itch|hives|sneezing|runny nose)/.test(text)) {
        findings.push("Allergy symptoms");
        lines.push("Avoid the suspected trigger, wash hands and face after exposure, and use antihistamines only when they are included in the approved medicine list.");
    }

    const medSupport = (meds || []).map(m => typeof m === "string" ? m : (m.name || m.medicine_name || "")).filter(Boolean).slice(0, 3);
    if (medSupport.length) {
        lines.push(`Approved medicine support noted: ${medSupport.join(", ")}.`);
    }

    if (!lines.length) return "";

    return `${findings.length ? `<strong>${findings.join(" • ")}</strong><br>` : ""}${lines.map(item => `• ${item}`).join("<br>")}`;
}

// ── History ────────────────────────────────
async function loadHistory() {
    const prompt = document.getElementById("history-login-prompt");
    const list   = document.getElementById("history-list");
    const clearBtn = document.getElementById("btn-clear-history");

    if (!currentUser) {
        prompt.classList.remove("hidden");
        list.innerHTML = "";
        if (clearBtn) clearBtn.style.display = "none";
        return;
    }
    prompt.classList.add("hidden");
    list.innerHTML = `<div style="text-align:center;padding:2rem;color:var(--text-muted);">Loading…</div>`;
    if (clearBtn) clearBtn.style.display = "none";

    try {
        // GET /api/history — JWT required
        const res = await fetch(API + "/api/history", { headers: authHeaders() });

        if (res.status === 401) {
            clearSession();
            showToast("Session expired. Please login again.", "error");
            showModal("login");
            return;
        }

        const data = await res.json();

        if (!data.consultations?.length) {
            list.innerHTML = `<div class="glass-card text-center"><p style="color:var(--text-muted);">No consultations yet. Start your first consultation!</p></div>`;
            return;
        }
        
        if (clearBtn) clearBtn.style.display = "block";

        list.innerHTML = data.consultations.map(c => {
            const date    = new Date(c.created_at).toLocaleString();
            const sevClass = (c.severity || "").toLowerCase();
            const preview  = (c.symptoms_input || "").substring(0, 150);
            return `<div class="history-card" onclick="viewConsultation(${c.id})">
                <div class="hc-top">
                    <span class="severity-badge severity-${sevClass}">${c.severity || "Low"}</span>
                    <span class="hc-date">${date}</span>
                </div>
                <p class="hc-symptoms">${preview}${preview.length >= 150 ? "…" : ""}</p>
            </div>`;
        }).join("");

    } catch {
        list.innerHTML = `<p style="color:var(--red)">Failed to load history.</p>`;
    }
}

async function viewConsultation(id) {
    try {
        const res  = await fetch(API + "/api/history/" + id, { headers: authHeaders() });
        const data = await res.json();
        if (data.consultation) {
            navigateTo("consult");
            const c = data.consultation;
            document.getElementById("symptoms-input").value = c.symptoms_input;
            
            lastConsultInputs = {
                symptoms: c.symptoms_input,
                username: currentUser?.full_name,
                age: currentUser?.age,
                gender: currentUser?.gender,
                blood_group: currentUser?.blood_group,
                allergies: currentUser?.known_allergies
            };
            
            lastConsultationData = {
                severity:        c.severity,
                is_emergency:    c.is_emergency,
                gemini_response: c.gemini_analysis,
                groq_response:   c.groq_validation,
            };

            document.getElementById("results-panel").classList.remove("hidden");
            document.getElementById("loading-state").classList.add("hidden");
            document.getElementById("report").classList.remove("hidden");
            document.getElementById("prescription-panel").classList.add("hidden");
            
            renderReport(lastConsultationData);
        }
    } catch {
        showToast("Failed to load consultation", "error");
    }
}

async function clearHistory() {
    if (!currentUser) return;
    if (!confirm("Are you sure you want to clear your entire consultation history? This cannot be undone.")) return;

    try {
        const res = await fetch(API + "/api/history", { 
            method: "DELETE",
            headers: authHeaders() 
        });

        if (res.status === 401) {
            clearSession();
            showToast("Session expired. Please login again.", "error");
            showModal("login");
            return;
        }

        if (res.ok) {
            showToast("History cleared successfully.", "success");
            loadHistory();
        } else {
            const data = await res.json();
            showToast(data.error || "Failed to clear history.", "error");
        }
    } catch {
        showToast("Error clearing history.", "error");
    }
}

// ── Medicines ──────────────────────────────
async function loadMedicines() {
    try {
        const res  = await fetch(API + "/api/medicines", { headers: authHeaders() });
        const data = await res.json();
        allMedicines = data.medicines || [];
        currentMedicineView = allMedicines;
        medicineRecommendationActive = false;
        renderMedicines(currentMedicineView);
    } catch { /* silent */ }
}

function renderMedicines(meds) {
    const grid = document.getElementById("medicines-grid");
    if (!meds.length) {
        grid.innerHTML = `<p style="color:var(--text-muted);grid-column:1/-1;text-align:center;">No medicines found.</p>`;
        return;
    }
    currentMedicineView = meds;
    grid.innerHTML = meds.map(m => `
        <div class="med-card">
            <span class="category-tag">${m.category || "General"}</span>
            <div class="meta-row">
                <span class="meta-chip">${m.type || m.medicine_type || "Medicine"}</span>
                ${m.prescription_required ? `<span class="meta-chip">Prescription required</span>` : `<span class="meta-chip">OTC</span>`}
            </div>
            ${m.conflict_warning
                ? `<div style="background:rgba(239,68,68,.15);border:1px solid rgba(239,68,68,.4);padding:6px 10px;border-radius:6px;font-size:.8rem;color:#fca5a5;margin-bottom:8px;">⚠ ${m.conflict_warning}</div>`
                : ""}
            <h4>${m.name}</h4>
            <div class="generic">${m.generic_name || ""}</div>
            <div class="purpose"><strong>What it does:</strong> ${m.what_it_does || m.purpose || "See product details"}</div>
            <div class="dosage"><strong>Dosage:</strong> ${m.dosage || m.common_dosage || "Follow pack instructions"}</div>
            ${m.composition ? `<div class="dosage"><strong>Composition:</strong> ${m.composition}</div>` : ""}
            ${m.product_name && m.product_name !== m.name ? `<div class="dosage"><strong>Product:</strong> ${m.product_name}</div>` : ""}
            ${m.warnings   ? `<div class="warning">⚠ ${m.warnings}</div>` : ""}
            ${m.price_range ? `<span class="price">${m.price_range}</span>` : ""}
        </div>
    `).join("");
}

function filterMedicines(cat) {
    document.querySelectorAll(".filter-tab").forEach(t => t.classList.remove("active"));
    event.target.classList.add("active");
    medicineRecommendationActive = false;
    renderMedicines(cat ? allMedicines.filter(m => m.category === cat) : allMedicines);
}

function searchMedicines() {
    const q        = document.getElementById("medicine-search").value.toLowerCase();
    const source   = medicineRecommendationActive ? currentMedicineView : allMedicines;
    const filtered = source.filter(m =>
        (m.name || "").toLowerCase().includes(q) ||
        (m.generic_name || "").toLowerCase().includes(q) ||
        (m.what_it_does || m.purpose || "").toLowerCase().includes(q) ||
        (m.composition || "").toLowerCase().includes(q) ||
        (m.category || "").toLowerCase().includes(q)
    );
    renderMedicines(filtered);
}

async function recommendMedicinesForSymptoms() {
    const symptoms = document.getElementById("medicine-symptoms").value.trim();
    if (!symptoms) {
        showToast("Please enter your symptoms first.", "error");
        return;
    }

    try {
        const res = await fetch(API + "/api/marketplace/recommend", {
            method: "POST",
            headers: authHeaders(),
            body: JSON.stringify({ symptoms }),
        });

        const data = await res.json();
        if (!res.ok) {
            showToast(data.error || "Could not find matching medicines.", "error");
            return;
        }

        medicineRecommendationActive = true;
        currentMedicineView = data.medicines || [];
        renderMedicines(currentMedicineView);
        document.getElementById("medicines-grid").scrollIntoView({ behavior: "smooth", block: "start" });
        showToast("Showing medicines that match your symptoms.", "success");
    } catch (error) {
        showToast("Medicine matching failed: " + error.message, "error");
    }
}

function showAllMedicines() {
    medicineRecommendationActive = false;
    document.getElementById("medicine-symptoms").value = "";
    document.getElementById("medicine-search").value = "";
    renderMedicines(allMedicines);
    showToast("Showing the full marketplace.", "success");
}

// ── Toast Notifications ────────────────────
function showToast(msg, type = "success") {
    const container = document.getElementById("toast-container");
    const toast     = document.createElement("div");
    toast.className = "toast " + type;
    toast.textContent = msg;
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = "0";
        setTimeout(() => toast.remove(), 300);
    }, 3500);
}

// ── Medicine Reminders & Notifications ────────────────────
let notifiedIds = new Set();
let pollingIntervalId = null;

function startNotificationPolling() {
    if (pollingIntervalId) clearInterval(pollingIntervalId);
    pollNotifications();
    pollingIntervalId = setInterval(pollNotifications, 10000);
}

async function pollNotifications() {
    if (!authToken || !currentUser) return;
    try {
        const res = await fetch(API + "/api/notifications/unread", { headers: authHeaders() });
        if (!res.ok) return;
        const data = await res.json();
        
        // Native browser notification permission status
        const hasPermission = Notification.permission === "granted";
        
        let newNotifsCount = 0;
        data.notifications.forEach(notif => {
            if (!notifiedIds.has(notif.id)) {
                notifiedIds.add(notif.id);
                newNotifsCount++;
                
                if (hasPermission) {
                    new Notification(notif.title, {
                        body: notif.message,
                        icon: "/favicon.ico"
                    });
                } else {
                    // Fallback to in-app Toast
                    showToast(`⏰ ${notif.title}: ${notif.message}`, "success");
                }
            }
        });
        
        // Refresh UI lists if user is currently looking at the reminders page
        const remindersPage = document.getElementById("page-reminders");
        if (remindersPage && remindersPage.classList.contains("active") && newNotifsCount > 0) {
            loadNotifications();
        }
    } catch (e) {
        console.error("Polling error:", e);
    }
}

async function requestBrowserNotificationPermission() {
    if (!("Notification" in window)) {
        showToast("Native browser notifications are not supported on this browser.", "error");
        return;
    }
    
    const permission = await Notification.requestPermission();
    updateBrowserNotifButton(permission);
    
    if (permission === "granted") {
        showToast("Native notifications enabled! 🔔", "success");
        new Notification("Medivio Alerts Enabled", {
            body: "You will receive desktop alerts for your medicine reminders."
        });
    } else {
        showToast("Desktop notifications permission denied.", "error");
    }
}

function updateBrowserNotifButton(permission) {
    const btn = document.getElementById("btn-browser-notif-permission");
    if (!btn) return;
    
    if (permission === "granted") {
        btn.textContent = "Enabled ✅";
        btn.disabled = true;
        btn.classList.add("btn-ghost");
        btn.classList.remove("btn-outline");
    } else if (permission === "denied") {
        btn.textContent = "Denied ❌";
        btn.disabled = false;
        btn.classList.remove("btn-ghost");
        btn.classList.add("btn-outline");
    } else {
        btn.textContent = "Enable";
        btn.disabled = false;
        btn.classList.remove("btn-ghost");
        btn.classList.add("btn-outline");
    }
}

function toggleReminderDays() {
    const freq = document.getElementById("rem-frequency").value;
    const daysGroup = document.getElementById("reminder-days-group");
    if (freq === "weekly" || freq === "specific_days") {
        daysGroup.classList.remove("hidden");
    } else {
        daysGroup.classList.add("hidden");
    }
}

async function loadReminders() {
    if (!authToken) return;
    try {
        const listDiv = document.getElementById("reminders-list");
        listDiv.innerHTML = `<div class="text-center" style="padding:20px; color:var(--text-muted);">Loading reminders...</div>`;
        
        const res = await fetch(API + "/api/reminders", { headers: authHeaders() });
        if (!res.ok) throw new Error("Could not load reminders");
        const data = await res.json();
        
        if (!data.reminders || data.reminders.length === 0) {
            listDiv.innerHTML = `<div class="empty-state">No scheduled reminders. Add one above!</div>`;
            return;
        }
        
        listDiv.innerHTML = "";
        data.reminders.forEach(r => {
            const card = document.createElement("div");
            card.className = "reminder-card";
            
            // Format time HH:MM
            let timeStr = r.reminder_time;
            if (timeStr && timeStr.length > 5) timeStr = timeStr.substring(0, 5);
            
            let meta = `Time: ${timeStr} | Frequency: ${r.frequency}`;
            if (r.reminder_days) meta += ` (${r.reminder_days})`;
            if (r.dosage) meta += ` | Dosage: ${r.dosage}`;
            if (r.instructions) meta += ` | Instructions: ${r.instructions}`;
            
            card.innerHTML = `
                <div class="reminder-info">
                    <span class="reminder-name">${r.medicine_name}</span>
                    <span class="reminder-meta">${meta}</span>
                </div>
                <div class="reminder-actions">
                    <button class="btn ${r.is_active ? 'btn-primary' : 'btn-outline'}" onclick="toggleReminder(${r.id})" style="font-size:0.75rem; padding:6px 12px;">
                        ${r.is_active ? 'Active' : 'Inactive'}
                    </button>
                    <button class="btn btn-outline" onclick="deleteReminder(${r.id})" style="font-size:0.75rem; padding:6px 12px; border-color:var(--red); color:var(--red);">
                        Delete
                    </button>
                </div>
            `;
            listDiv.appendChild(card);
        });
    } catch (e) {
        showToast(e.message, "error");
    }
}

async function addReminder() {
    const medicine_name = document.getElementById("rem-medicine-name").value.trim();
    const reminder_time = document.getElementById("rem-time").value;
    const dosage = document.getElementById("rem-dosage").value.trim();
    const frequency = document.getElementById("rem-frequency").value;
    const instructions = document.getElementById("rem-instructions").value.trim();
    
    let reminder_days = null;
    if (frequency === "weekly" || frequency === "specific_days") {
        const checked = Array.from(document.querySelectorAll("input[name='rem-day']:checked")).map(c => c.value);
        if (checked.length === 0) {
            showToast("Please select at least one reminder day.", "error");
            return;
        }
        reminder_days = checked.join(",");
    }
    
    const payload = {
        medicine_name,
        reminder_time,
        dosage,
        frequency,
        reminder_days,
        instructions
    };
    
    try {
        const res = await fetch(API + "/api/reminders", {
            method: "POST",
            headers: authHeaders(),
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        
        if (!res.ok) throw new Error(data.error || "Failed to create reminder");
        
        showToast("Medicine reminder created! ⏰", "success");
        document.getElementById("reminder-form").reset();
        toggleReminderDays();
        loadReminders();
    } catch (e) {
        showToast(e.message, "error");
    }
}

async function toggleReminder(id) {
    try {
        const res = await fetch(API + `/api/reminders/${id}/toggle`, {
            method: "POST",
            headers: authHeaders()
        });
        if (!res.ok) throw new Error("Failed to toggle reminder");
        loadReminders();
    } catch (e) {
        showToast(e.message, "error");
    }
}

async function deleteReminder(id) {
    if (!confirm("Are you sure you want to delete this reminder?")) return;
    try {
        const res = await fetch(API + `/api/reminders/${id}`, {
            method: "DELETE",
            headers: authHeaders()
        });
        if (!res.ok) throw new Error("Failed to delete reminder");
        showToast("Reminder deleted.", "success");
        loadReminders();
    } catch (e) {
        showToast(e.message, "error");
    }
}

async function loadNotifications() {
    if (!authToken) return;
    try {
        const listDiv = document.getElementById("notifications-list");
        listDiv.innerHTML = `<div class="text-center" style="padding:20px; color:var(--text-muted);">Loading notifications...</div>`;
        
        // Update browser notification button state on page load/render
        if ("Notification" in window) {
            updateBrowserNotifButton(Notification.permission);
        }
        
        const res = await fetch(API + "/api/notifications", { headers: authHeaders() });
        if (!res.ok) throw new Error("Could not load notifications");
        const data = await res.json();
        
        if (!data.notifications || data.notifications.length === 0) {
            listDiv.innerHTML = `<div class="empty-state">No notifications.</div>`;
            return;
        }
        
        listDiv.innerHTML = "";
        data.notifications.forEach(n => {
            const card = document.createElement("div");
            card.className = `notification-item-card ${n.is_read ? '' : 'unread'}`;
            
            // Format timestamp
            let timeStr = "";
            if (n.created_at) {
                const d = new Date(n.created_at);
                timeStr = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) + " " + d.toLocaleDateString();
            }
            
            card.innerHTML = `
                <div class="notification-header">
                    <span class="notification-title">${n.title}</span>
                    <span class="notification-time">${timeStr}</span>
                </div>
                <div class="notification-msg">${n.message}</div>
                ${!n.is_read ? `<button class="notification-btn-read" onclick="markNotificationRead(${n.id})">Mark as read</button>` : ''}
            `;
            listDiv.appendChild(card);
        });
    } catch (e) {
        showToast(e.message, "error");
    }
}

async function markNotificationRead(id) {
    try {
        const res = await fetch(API + `/api/notifications/${id}/read`, {
            method: "POST",
            headers: authHeaders()
        });
        if (!res.ok) throw new Error("Failed to update notification");
        loadNotifications();
    } catch (e) {
        showToast(e.message, "error");
    }
}

async function markAllNotificationsRead() {
    try {
        const res = await fetch(API + "/api/notifications/mark-read", {
            method: "POST",
            headers: authHeaders()
        });
        if (!res.ok) throw new Error("Failed to clear notifications");
        showToast("All notifications marked as read.", "success");
        loadNotifications();
    } catch (e) {
        showToast(e.message, "error");
    }
}

// ── Email Diagnostics & Tracking ──────────────────────────────────────────
async function loadEmailLogs() {
    if (!authToken) return;
    try {
        const listBody = document.getElementById("email-logs-list");
        if (!listBody) return;
        
        listBody.innerHTML = `<tr><td colspan="6" style="padding:24px; text-align:center; color:var(--text-muted);">Loading email logs...</td></tr>`;
        
        const res = await fetch(API + "/api/email-status", { headers: authHeaders() });
        if (!res.ok) throw new Error("Could not load email delivery logs");
        const data = await res.json();
        
        if (!data.logs || data.logs.length === 0) {
            listBody.innerHTML = `<tr><td colspan="6" style="padding:24px; text-align:center; color:var(--text-muted);">No email records found. Send a consultation to trigger an email log.</td></tr>`;
            return;
        }
        
        listBody.innerHTML = "";
        data.logs.forEach(log => {
            const tr = document.createElement("tr");
            tr.style.borderBottom = "1px solid var(--border-glass)";
            
            // Recipient
            const recipient = log.recipient_email || "—";
            
            // Subject
            const subject = log.subject || "—";
            
            // Status badge styling
            let statusBadge = "";
            if (log.status === "delivered") {
                statusBadge = `<span style="display:inline-block; padding:2px 8px; border-radius:50px; background:rgba(34,197,94,0.1); color:var(--green); font-size:0.78rem; font-weight:600;">Delivered</span>`;
            } else if (log.status === "failed") {
                statusBadge = `<span style="display:inline-block; padding:2px 8px; border-radius:50px; background:rgba(239,68,68,0.1); color:var(--red); font-size:0.78rem; font-weight:600;" title="${log.error_message || ''}">Failed</span>`;
            } else if (log.status === "queued") {
                statusBadge = `<span style="display:inline-block; padding:2px 8px; border-radius:50px; background:rgba(234,179,8,0.1); color:var(--yellow); font-size:0.78rem; font-weight:600;">Queued</span>`;
            } else {
                statusBadge = `<span style="display:inline-block; padding:2px 8px; border-radius:50px; background:rgba(255,255,255,0.05); color:var(--text-muted); font-size:0.78rem;">${log.status || 'Unknown'}</span>`;
            }
            
            // Sent At
            let sentAtStr = "—";
            if (log.sent_at || log.created_at) {
                const date = new Date(log.sent_at || log.created_at);
                sentAtStr = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) + " " + date.toLocaleDateString();
            }
            
            // Opened At
            let openedAtStr = "—";
            if (log.opened_at) {
                const date = new Date(log.opened_at);
                openedAtStr = `👁️ ` + date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) + " " + date.toLocaleDateString();
            }
            
            // Actions
            let actionBtn = "";
            if (log.status === "failed" || log.status === "skipped" || (log.status === "delivered" && !log.opened_at)) {
                actionBtn = `<button class="btn btn-outline" onclick="resendEmail(${log.id})" style="font-size:0.72rem; padding:4px 10px; border-color:var(--accent-1); color:var(--accent-1);">Resend</button>`;
            }
            
            tr.innerHTML = `
                <td style="padding:12px; color:var(--text-primary); font-weight:500;">${recipient}</td>
                <td style="padding:12px; color:var(--text-secondary); max-width:200px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${subject}</td>
                <td style="padding:12px;">${statusBadge}</td>
                <td style="padding:12px; color:var(--text-muted); font-size:0.8rem;">${sentAtStr}</td>
                <td style="padding:12px; color:var(--accent-2); font-size:0.8rem;">${openedAtStr}</td>
                <td style="padding:12px; text-align:right;">${actionBtn}</td>
            `;
            listBody.appendChild(tr);
        });
    } catch (e) {
        console.error(e);
        const listBody = document.getElementById("email-logs-list");
        if (listBody) {
            listBody.innerHTML = `<tr><td colspan="6" style="padding:24px; text-align:center; color:var(--red);">Failed to load email logs: ${e.message}</td></tr>`;
        }
    }
}

async function sendTestEmail() {
    const email = prompt("Enter the recipient email address for the deliverability test:", currentUser?.email || "");
    if (!email) return;
    
    showToast("Sending test email...", "success");
    try {
        const res = await fetch(API + "/api/email-status/send-test", {
            method: "POST",
            headers: authHeaders(),
            body: JSON.stringify({ email })
        });
        const data = await res.json();
        
        if (!res.ok) throw new Error(data.error || "Failed to send test email");
        
        showToast("Test email sent! Check your inbox/spam folder. 📨", "success");
        loadEmailLogs();
    } catch (e) {
        showToast(e.message, "error");
    }
}

async function resendEmail(logId) {
    showToast("Resending email...", "success");
    try {
        const res = await fetch(API + `/api/email-status/${logId}/resend`, {
            method: "POST",
            headers: authHeaders()
        });
        const data = await res.json();
        
        if (!res.ok) throw new Error(data.error || "Failed to resend email");
        
        showToast("Email resent successfully! 🚀", "success");
        loadEmailLogs();
    } catch (e) {
        showToast(e.message, "error");
    }
}
