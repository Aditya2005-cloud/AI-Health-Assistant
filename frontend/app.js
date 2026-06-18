/* ==========================================
   AI Health Assistant — Frontend Logic
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
    loadMedicines();
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
    // Consult and History require login
    const protectedPages = ["consult", "history"];
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
    window.scrollTo({ top: 0, behavior: "smooth" });
}

// ── Auth Modals ────────────────────────────
function showModal(type) {
    document.getElementById("modal-overlay").classList.remove("hidden");
    document.getElementById("login-form").classList.toggle("hidden", type !== "login");
    document.getElementById("register-form").classList.toggle("hidden", type !== "register");
    document.querySelectorAll(".form-error").forEach(e => e.classList.add("hidden"));
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

    const symptoms = document.getElementById("symptoms-input").value.trim();
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
            body: JSON.stringify({ symptoms }),  // patient profile is injected server-side
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
    const fBanner = document.getElementById("fallback-banner");
    if (data.is_fallback) fBanner?.classList.remove("hidden");
    else fBanner?.classList.add("hidden");

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
    const diagnoses = q.validated_diagnoses || g.possible_causes || [];
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
    const plan = q.attending_treatment_plan || q.approved_treatment_plan || g.recommended_actions;
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

        const meds = plan.approved_otc_medicines || plan.otc_medicines || [];
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
    document.getElementById("results-panel").classList.add("hidden");
    document.getElementById("report").classList.add("hidden");
    document.getElementById("loading-state").classList.remove("hidden");
    resetSteps();
}

// ── History ────────────────────────────────
async function loadHistory() {
    const prompt = document.getElementById("history-login-prompt");
    const list   = document.getElementById("history-list");

    if (!currentUser) {
        prompt.classList.remove("hidden");
        list.innerHTML = "";
        return;
    }
    prompt.classList.add("hidden");
    list.innerHTML = `<div style="text-align:center;padding:2rem;color:var(--text-muted);">Loading…</div>`;

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
            document.getElementById("results-panel").classList.remove("hidden");
            document.getElementById("loading-state").classList.add("hidden");
            document.getElementById("report").classList.remove("hidden");
            renderReport({
                severity:        c.severity,
                is_emergency:    c.is_emergency,
                gemini_response: c.gemini_analysis,
                groq_response:   c.groq_validation,
            });
        }
    } catch {
        showToast("Failed to load consultation", "error");
    }
}

// ── Medicines ──────────────────────────────
async function loadMedicines() {
    try {
        const res  = await fetch(API + "/api/medicines", { headers: authHeaders() });
        const data = await res.json();
        allMedicines = data.medicines || [];
        renderMedicines(allMedicines);
    } catch { /* silent */ }
}

function renderMedicines(meds) {
    const grid = document.getElementById("medicines-grid");
    if (!meds.length) {
        grid.innerHTML = `<p style="color:var(--text-muted);grid-column:1/-1;text-align:center;">No medicines found.</p>`;
        return;
    }
    grid.innerHTML = meds.map(m => `
        <div class="med-card">
            <span class="category-tag">${m.category || "General"}</span>
            ${m.conflict_warning
                ? `<div style="background:rgba(239,68,68,.15);border:1px solid rgba(239,68,68,.4);padding:6px 10px;border-radius:6px;font-size:.8rem;color:#fca5a5;margin-bottom:8px;">⚠ ${m.conflict_warning}</div>`
                : ""}
            <h4>${m.name}</h4>
            <div class="generic">${m.generic_name || ""}</div>
            <div class="purpose">${m.purpose || ""}</div>
            <div class="dosage">📋 ${m.common_dosage || "N/A"}</div>
            ${m.warnings   ? `<div class="warning">⚠ ${m.warnings}</div>` : ""}
            ${m.price_range ? `<span class="price">${m.price_range}</span>` : ""}
        </div>
    `).join("");
}

function filterMedicines(cat) {
    document.querySelectorAll(".filter-tab").forEach(t => t.classList.remove("active"));
    event.target.classList.add("active");
    renderMedicines(cat ? allMedicines.filter(m => m.category === cat) : allMedicines);
}

function searchMedicines() {
    const q        = document.getElementById("medicine-search").value.toLowerCase();
    const filtered = allMedicines.filter(m =>
        m.name.toLowerCase().includes(q) || (m.generic_name || "").toLowerCase().includes(q)
    );
    renderMedicines(filtered);
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
