/* ==========================================
   AI Health Assistant - Frontend Logic
   ========================================== */

const API = "";  // Same origin

// ========== STATE ==========
let currentUser = null;
let allMedicines = [];

// ========== INIT ==========
document.addEventListener("DOMContentLoaded", () => {
    const saved = localStorage.getItem("healthai_user");
    if (saved) {
        currentUser = JSON.parse(saved);
        updateAuthUI();
    }
    setupNavigation();
    loadMedicines();
});

// ========== NAVIGATION ==========
function setupNavigation() {
    document.querySelectorAll(".nav-link").forEach(link => {
        link.addEventListener("click", e => {
            e.preventDefault();
            navigateTo(link.dataset.page);
        });
    });
}

function navigateTo(page) {
    document.querySelectorAll(".page").forEach(p => p.classList.remove("active"));
    document.querySelectorAll(".nav-link").forEach(l => l.classList.remove("active"));
    const target = document.getElementById("page-" + page);
    if (target) target.classList.add("active");
    const navLink = document.querySelector(`.nav-link[data-page="${page}"]`);
    if (navLink) navLink.classList.add("active");

    if (page === "history") loadHistory();
    window.scrollTo({ top: 0, behavior: "smooth" });
}

// ========== AUTH ==========
function showModal(type) {
    document.getElementById("modal-overlay").classList.remove("hidden");
    document.getElementById("login-form").classList.toggle("hidden", type !== "login");
    document.getElementById("register-form").classList.toggle("hidden", type !== "register");
    document.querySelectorAll(".form-error").forEach(e => e.classList.add("hidden"));
}
function closeModal() { document.getElementById("modal-overlay").classList.add("hidden"); }

async function handleLogin() {
    const email = document.getElementById("login-email").value.trim();
    const password = document.getElementById("login-password").value;
    if (!email || !password) return showFormError("login-error", "All fields are required");

    try {
        const res = await fetch(API + "/api/auth/login", {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, password })
        });
        const data = await res.json();
        if (!res.ok) return showFormError("login-error", data.error);
        currentUser = data.user;
        localStorage.setItem("healthai_user", JSON.stringify(currentUser));
        updateAuthUI();
        closeModal();
        showToast("Welcome back, " + currentUser.full_name + "!", "success");
    } catch { showFormError("login-error", "Connection error"); }
}

async function handleRegister() {
    const name = document.getElementById("reg-name").value.trim();
    const email = document.getElementById("reg-email").value.trim();
    const password = document.getElementById("reg-password").value;
    if (!name || !email || !password) return showFormError("register-error", "Name, email and password are required");
    if (password.length < 6) return showFormError("register-error", "Password must be at least 6 characters");

    const payload = {
        full_name: name, email, password,
        age: document.getElementById("reg-age").value || null,
        gender: document.getElementById("reg-gender").value || null,
        existing_conditions: document.getElementById("reg-conditions").value || null,
        allergies: document.getElementById("reg-allergies").value || null,
    };

    try {
        const res = await fetch(API + "/api/auth/register", {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (!res.ok) return showFormError("register-error", data.error);
        currentUser = data.user;
        localStorage.setItem("healthai_user", JSON.stringify(currentUser));
        updateAuthUI();
        closeModal();
        showToast("Account created successfully!", "success");
    } catch { showFormError("register-error", "Connection error"); }
}

function logout() {
    currentUser = null;
    localStorage.removeItem("healthai_user");
    updateAuthUI();
    navigateTo("home");
    showToast("Logged out", "success");
}

function updateAuthUI() {
    const authDiv = document.getElementById("nav-auth");
    const userDiv = document.getElementById("nav-user");
    if (currentUser) {
        authDiv.classList.add("hidden");
        userDiv.classList.remove("hidden");
        document.getElementById("user-greeting").textContent = "Hi, " + currentUser.full_name.split(" ")[0];
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

// ========== CONSULTATION ==========
function addTag(tag) {
    const ta = document.getElementById("symptoms-input");
    ta.value = ta.value ? ta.value + ", " + tag : tag;
    ta.focus();
}

async function analyzeSymptoms() {
    const ageInput = document.getElementById("patient-age").value.trim();
    const genderInput = document.getElementById("patient-gender").value;
    const symptoms = document.getElementById("symptoms-input").value.trim();

    if (!ageInput || !genderInput) {
        return showToast("Please specify your age and gender for accurate medical analysis.", "error");
    }
    if (!symptoms) {
        return showToast("Please describe your symptoms", "error");
    }

    const age = parseInt(ageInput, 10);
    if (isNaN(age) || age < 1 || age > 120) {
        return showToast("Please enter a valid age between 1 and 120", "error");
    }

    const btn = document.getElementById("btn-analyze");
    btn.disabled = true;
    btn.innerHTML = "Analyzing...";

    const panel = document.getElementById("results-panel");
    const loading = document.getElementById("loading-state");
    const report = document.getElementById("report");
    panel.classList.remove("hidden");
    loading.classList.remove("hidden");
    report.classList.add("hidden");

    resetSteps();
    activateStep(1);

    try {
        // Simulate step progression
        setTimeout(() => { completeStep(1); activateStep(2); }, 2000);
        setTimeout(() => { completeStep(2); activateStep(3); }, 5000);

        const res = await fetch(API + "/api/consult", {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ 
                symptoms, 
                age, 
                gender: genderInput,
                user_id: currentUser?.id || null 
            })
        });
        const data = await res.json();

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
    if (el) {
        el.classList.remove("active");
        el.classList.add("done");
    }
}

function renderReport(data) {
    // Fallback Banner
    const fBanner = document.getElementById("fallback-banner");
    if (data.is_fallback) {
        if (fBanner) fBanner.classList.remove("hidden");
    } else {
        if (fBanner) fBanner.classList.add("hidden");
    }

    // Emergency
    const eBanner = document.getElementById("emergency-banner");
    if (data.is_emergency) eBanner.classList.remove("hidden");
    else eBanner.classList.add("hidden");

    // Severity
    const sev = (data.severity || "Unknown").toLowerCase();
    const sevSection = document.getElementById("severity-section");
    const sevMap = { low: "severity-low", medium: "severity-medium", high: "severity-high", emergency: "severity-emergency" };
    const sevIcons = { low: "🟢", medium: "🟡", high: "🟠", emergency: "🔴" };
    sevSection.innerHTML = `<span class="severity-badge ${sevMap[sev] || ''}">${sevIcons[sev] || "⚪"} Severity: ${data.severity || "Unknown"}</span>`;

    // Unified Report Body
    const urb = document.getElementById("unified-report-body");
    urb.innerHTML = buildUnifiedReportHTML(data);

    document.getElementById("results-panel").scrollIntoView({ behavior: "smooth", block: "start" });
}

function buildUnifiedReportHTML(data) {
    let html = "";
    const g = data.gemini_response || {};
    const q = data.groq_response || {};

    // 1. Patient Case Presentation & Discussion Notes
    const intake = g.junior_clinician_assessment || {};
    const presentation = intake.presentation_summary || g.patient_summary;
    if (presentation) {
        html += sec("Patient Intake & Case Presentation", `<p>${presentation}</p>`);
    }

    const discussion = q.clinical_discussion_notes || q.doctor_review;
    if (discussion) {
        html += sec("Clinical Board Assessment Notes", `
            <div class="discussion-bubble" style="background: rgba(99, 102, 241, 0.08); border-left: 4px solid var(--primary); padding: 14px 18px; border-radius: 6px; font-style: italic; line-height: 1.6;">
                <p>${discussion}</p>
            </div>
        `);
    }

    // 2. Validated Differentials
    const valDiagnoses = q.validated_diagnoses || q.validated_conditions;
    if (valDiagnoses?.length) {
        html += sec("Provisional Diagnoses", valDiagnoses.map(c =>
            `<div class="condition-card" style="margin-bottom: 12px; padding: 14px; border-radius: 8px; background: rgba(255, 255, 255, 0.03); border: 1px solid var(--border);">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 6px;">
                    <span class="cond-name" style="font-weight: 600; font-size: 1.05rem; color: var(--text);">${c.condition}</span> 
                    <span class="cond-prob" style="font-size:0.85rem; padding: 2px 8px; border-radius: 12px; background: rgba(99,102,241,0.2); color: var(--primary-light); font-weight: 500;">Confidence: ${c.confidence || c.probability || "Medium"}</span>
                </div>
                <div class="cond-reason" style="font-size:0.9rem; color: var(--text-muted); line-height: 1.5;">${c.clinical_notes || c.reason || c.rationale || ""}</div>
            </div>`
        ).join(""));
    }

    // 3. Attending's Final Treatment Protocol
    const attendingPlan = q.attending_treatment_plan || q.approved_treatment_plan;
    if (attendingPlan) {
        let planHtml = "";
        
        // Proposed Rest Plan
        if (attendingPlan.bed_rest_routine) {
            planHtml += `
                <div class="protocol-section" style="margin-bottom: 18px;">
                    <h5 style="margin-bottom: 8px; display: flex; align-items: center; gap: 8px; font-size: 1rem; color: var(--text); font-weight: 600;">
                        <span>🛏️</span> Recommended Rest & Activity Routine
                    </h5>
                    <p style="line-height: 1.6; color: var(--text-muted); font-size: 0.95rem;">${attendingPlan.bed_rest_routine}</p>
                </div>
            `;
        }

        // Proposed Diet Plan
        if (attendingPlan.diet_and_hydration) {
            planHtml += `
                <div class="protocol-section" style="margin-bottom: 18px;">
                    <h5 style="margin-bottom: 8px; display: flex; align-items: center; gap: 8px; font-size: 1rem; color: var(--text); font-weight: 600;">
                        <span>🍵</span> Recommended Diet & Hydration Plan
                    </h5>
                    <p style="line-height: 1.6; color: var(--text-muted); font-size: 0.95rem;">${attendingPlan.diet_and_hydration}</p>
                </div>
            `;
        }

        // What NOT to Do (Avoidances / Contraindications)
        const avoidList = attendingPlan.things_to_avoid || (intake.proposed_treatment && intake.proposed_treatment.things_to_avoid);
        if (avoidList) {
            planHtml += `
                <div class="protocol-section" style="margin-bottom: 18px; padding: 14px; border-radius: 8px; background: rgba(239, 68, 68, 0.06); border: 1px solid rgba(239, 68, 68, 0.2);">
                    <h5 style="margin-bottom: 8px; display: flex; align-items: center; gap: 8px; font-size: 1rem; color: #fca5a5; font-weight: 600;">
                        <span>🚫</span> Important Contraindications & Avoidances (What NOT to Do)
                    </h5>
                    <p style="line-height: 1.6; color: #fcd34d; font-size: 0.95rem; font-weight: 500;">${avoidList}</p>
                </div>
            `;
        }

        // Proposed OTC Medicines
        if (attendingPlan.approved_otc_medicines?.length) {
            planHtml += `
                <div class="protocol-section" style="margin-bottom: 18px;">
                    <h5 style="margin-bottom: 10px; font-size: 1rem; color: var(--text); font-weight: 600;">💊 Approved OTC Medicines (India Whitelist)</h5>
                    <div style="display: flex; flex-direction: column; gap: 10px;">
            ` + attendingPlan.approved_otc_medicines.map(m => {
                if (typeof m === "string") return `<div class="medicine-pill" style="padding: 10px 14px; border-radius: 6px; background: rgba(16,185,129,0.08); border-left: 3px solid #10b981;"><span class="med-name" style="font-weight:600; color:#34d399;">✅ ${m}</span></div>`;
                return `
                    <div class="medicine-pill" style="padding: 12px 16px; border-radius: 6px; background: rgba(16,185,129,0.06); border-left: 4px solid #10b981; margin-bottom: 4px;">
                        <div style="font-weight: 600; color: #34d399; font-size: 1rem; margin-bottom: 4px;">✅ ${m.medicine_name}</div>
                        <div style="font-size: 0.9rem; color: var(--text-muted); margin-bottom: 4px;"><strong>Purpose:</strong> ${m.purpose || ""}</div>
                        ${m.clinical_justification ? `<div style="font-size: 0.85rem; color: var(--text-muted); font-style: italic; border-top: 1px dashed rgba(255,255,255,0.08); padding-top: 4px; margin-top: 4px;">🩺 Clinical Justification: ${m.clinical_justification}</div>` : ""}
                    </div>
                `;
            }).join("") + `
                    </div>
                </div>
            `;
        }

        // Additional Self-care guidelines
        const selfCare = attendingPlan.additional_care_guidelines || attendingPlan.other_approved_self_care;
        if (selfCare?.length) {
            planHtml += `
                <div class="protocol-section">
                    <h5 style="margin-bottom: 8px; font-size: 1rem; color: var(--text); font-weight: 600;">📋 Practical Care Guidelines</h5>
                    <ul style="padding-left: 20px; line-height: 1.6; color: var(--text-muted); font-size: 0.95rem;">
                        ${selfCare.map(s => `<li>${s}</li>`).join("")}
                    </ul>
                </div>
            `;
        }

        html += sec("Consolidated Treatment Protocol", planHtml);
    }

    // 4. Red Flags & Warning Signs
    const flags = q.red_flags || g.when_to_seek_care || g.when_to_see_doctor;
    if (flags) {
        let flagsHtml = "";
        if (Array.isArray(flags)) {
            flagsHtml = flags.map(r => `<div class="red-flag" style="margin-bottom: 8px; padding: 12px; border-radius: 6px; background: rgba(239, 68, 68, 0.08); border-left: 4px solid var(--red); color: #fca5a5; font-size: 0.95rem; font-weight: 500;">⚠ ${r}</div>`).join("");
        } else {
            flagsHtml = `<div class="red-flag" style="padding: 12px; border-radius: 6px; background: rgba(239, 68, 68, 0.08); border-left: 4px solid var(--red); color: #fca5a5; font-size: 0.95rem; font-weight: 500;">⚠ ${flags}</div>`;
        }
        html += sec("⚠️ Critical Warning Signs (Red Flags)", flagsHtml);
    }

    // 5. Urgent Advice & Referral
    const rec = q.doctor_recommendation || g.when_to_see_doctor;
    const attention = q.seek_medical_attention || g.when_to_seek_care;
    if (rec || attention) {
        let recHtml = "";
        if (rec) recHtml += `<p style="line-height: 1.6; font-size: 0.95rem; margin-bottom: 8px;"><strong>Referral:</strong> ${rec}</p>`;
        if (attention) recHtml += `<p style="line-height: 1.6; font-size: 0.95rem; color: var(--yellow); font-weight: 500;"><strong>Follow-up:</strong> ${attention}</p>`;
        html += sec("Urgency & Follow-up Guidance", recHtml);
    }

    // Disclaimer
    const disclaimer = q.final_disclaimer || g.disclaimer || "This consultation provides educational guidance and is not a substitute for in-person evaluation by a licensed healthcare provider.";
    html += `<p style="font-size: 0.8rem; color: var(--text-muted); margin-top: 18px; font-style: italic; border-top: 1px solid var(--border); padding-top: 12px;">⚕️ ${disclaimer}</p>`;

    if (g.error || q.error) {
        html += `<p style="color:var(--red); font-weight:600; margin-top: 10px;">Error: ${g.message || q.message || "Consultation completed with warnings."}</p>`;
    }

    return html;
}

function buildGroqHTML(q) { return ""; }

function sec(title, content) {
    return `<div class="report-section"><h4>${title}</h4>${content}</div>`;
}

function resetConsultation() {
    document.getElementById("symptoms-input").value = "";
    document.getElementById("results-panel").classList.add("hidden");
    document.getElementById("report").classList.add("hidden");
    document.getElementById("loading-state").classList.remove("hidden");
    resetSteps();
}

// ========== HISTORY ==========
async function loadHistory() {
    const prompt = document.getElementById("history-login-prompt");
    const list = document.getElementById("history-list");
    if (!currentUser) {
        prompt.classList.remove("hidden");
        list.innerHTML = "";
        return;
    }
    prompt.classList.add("hidden");
    try {
        const res = await fetch(API + "/api/consultations/" + currentUser.id);
        const data = await res.json();
        if (!data.consultations?.length) {
            list.innerHTML = `<div class="glass-card text-center"><p style="color:var(--text-muted);">No consultations yet. Start your first consultation!</p></div>`;
            return;
        }
        list.innerHTML = data.consultations.map(c => {
            const date = new Date(c.created_at).toLocaleString();
            const sevClass = (c.severity || "").toLowerCase();
            return `<div class="history-card" onclick="viewConsultation(${c.id})">
                <div class="hc-top">
                    <span class="severity-badge severity-${sevClass}">${c.severity || "N/A"}</span>
                    <span class="hc-date">${date}</span>
                </div>
                <p class="hc-symptoms">${c.symptoms_input.substring(0, 150)}${c.symptoms_input.length > 150 ? "..." : ""}</p>
            </div>`;
        }).join("");
    } catch { list.innerHTML = `<p style="color:var(--red)">Failed to load history.</p>`; }
}

async function viewConsultation(id) {
    try {
        const res = await fetch(API + "/api/consultation/" + id);
        const data = await res.json();
        if (data.consultation) {
            navigateTo("consult");
            const c = data.consultation;
            document.getElementById("symptoms-input").value = c.symptoms_input;
            const panel = document.getElementById("results-panel");
            const loading = document.getElementById("loading-state");
            const report = document.getElementById("report");
            panel.classList.remove("hidden");
            loading.classList.add("hidden");
            report.classList.remove("hidden");
            renderReport({
                severity: c.severity, is_emergency: c.is_emergency,
                gemini_response: c.gemini_analysis, groq_response: c.groq_validation
            });
        }
    } catch { showToast("Failed to load consultation", "error"); }
}

// ========== MEDICINES ==========
async function loadMedicines() {
    try {
        const res = await fetch(API + "/api/medicines");
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
            <h4>${m.name}</h4>
            <div class="generic">${m.generic_name || ""}</div>
            <div class="purpose">${m.purpose || ""}</div>
            <div class="dosage">📋 ${m.common_dosage || "N/A"}</div>
            ${m.warnings ? `<div class="warning">⚠ ${m.warnings}</div>` : ""}
            ${m.price_range ? `<span class="price">${m.price_range}</span>` : ""}
        </div>
    `).join("");
}

function filterMedicines(cat) {
    document.querySelectorAll(".filter-tab").forEach(t => t.classList.remove("active"));
    event.target.classList.add("active");
    const filtered = cat ? allMedicines.filter(m => m.category === cat) : allMedicines;
    renderMedicines(filtered);
}

function searchMedicines() {
    const q = document.getElementById("medicine-search").value.toLowerCase();
    const filtered = allMedicines.filter(m =>
        m.name.toLowerCase().includes(q) || (m.generic_name || "").toLowerCase().includes(q)
    );
    renderMedicines(filtered);
}

// ========== TOAST ==========
function showToast(msg, type = "success") {
    const container = document.getElementById("toast-container");
    const toast = document.createElement("div");
    toast.className = "toast " + type;
    toast.textContent = msg;
    container.appendChild(toast);
    setTimeout(() => { toast.style.opacity = "0"; setTimeout(() => toast.remove(), 300); }, 3500);
}
