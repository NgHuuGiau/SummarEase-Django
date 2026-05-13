const sourceSelect = document.querySelector("#source_type");
const textWrap = document.querySelector("#text-wrap");
const fileWrap = document.querySelector("#file-wrap");
const urlWrap = document.querySelector("#url-wrap");
const form = document.querySelector("#summary-form");
const message = document.querySelector("#form-message");
const resultTitle = document.querySelector("#result-title");
const resultMeta = document.querySelector("#result-meta");
const resultKeywords = document.querySelector("#result-keywords");
const summaryOutput = document.querySelector("#summary-output");
const detailLink = document.querySelector("#detail-link");
const root = document.documentElement;
const themeToggle = document.querySelector("[data-theme-toggle]");
const themeLabel = document.querySelector("[data-theme-label]");
const themeIcon = document.querySelector("[data-theme-icon]");
const themeBadge = document.querySelector("[data-theme-badge]");
const themeCopy = document.querySelector("[data-theme-copy]");
const ratioSlider = document.querySelector("#ratio_slider");
const ratioInput = document.querySelector("#ratio_input");
const ratioValue = document.querySelector("#ratio_value");

function getPreferredTheme() {
    const storedTheme = window.localStorage.getItem("summarease-theme");
    if (storedTheme === "light" || storedTheme === "dark") {
        return storedTheme;
    }
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function syncThemeUi(theme) {
    const isDark = theme === "dark";
    if (themeLabel) {
        themeLabel.textContent = isDark ? "Ch\u1ebf \u0111\u1ed9 t\u1ed1i" : "Ch\u1ebf \u0111\u1ed9 s\u00e1ng";
    }
    if (themeIcon) {
        themeIcon.textContent = isDark ? "\u263e" : "\u2600";
    }
    if (themeBadge) {
        themeBadge.textContent = isDark ? "Ch\u1ebf \u0111\u1ed9 t\u1ed1i" : "Ch\u1ebf \u0111\u1ed9 s\u00e1ng";
    }
    if (themeCopy) {
        themeCopy.textContent = isDark
            ? "H\u1ec7 th\u1ed1ng \u0111ang hi\u1ec3n th\u1ecb theme t\u1ed1i \u0111\u1ec3 t\u1eadp trung v\u00e0o n\u1ed9i dung v\u00e0 thao t\u00e1c bu\u1ed5i t\u1ed1i."
            : "H\u1ec7 th\u1ed1ng \u0111ang hi\u1ec3n th\u1ecb theme s\u00e1ng \u0111\u1ec3 \u0111\u1ecdc v\u00e0 thao t\u00e1c r\u00f5 r\u00e0ng.";
    }
}

function applyTheme(theme) {
    root.dataset.theme = theme;
    window.localStorage.setItem("summarease-theme", theme);
    syncThemeUi(theme);
}

function updateSourceFields() {
    if (!sourceSelect) {
        return;
    }
    const type = sourceSelect.value;
    textWrap.classList.toggle("is-hidden", type !== "text");
    fileWrap.classList.toggle("is-hidden", type !== "file");
    urlWrap.classList.toggle("is-hidden", type !== "url");
}

function updateRatioUi() {
    if (!ratioSlider || !ratioInput) {
        return;
    }
    const percent = Number(ratioSlider.value);
    ratioInput.value = (percent / 100).toFixed(2);
    if (ratioValue) {
        ratioValue.textContent = `${percent}%`;
    }
}

async function submitSummary(event) {
    event.preventDefault();
    message.textContent = "\u0110ang x\u1eed l\u00fd...";

    try {
        const formData = new FormData(form);
        const response = await fetch(form.action, {
            method: "POST",
            body: formData,
            headers: {
                "X-Requested-With": "XMLHttpRequest",
            },
        });

        const payload = await response.json();
        if (!response.ok || !payload.ok) {
            const errors = payload.errors
                ? Object.values(payload.errors).flat().join(" ")
                : payload.message;
            message.textContent = errors || "Kh\u00f4ng th\u1ec3 t\u00f3m t\u1eaft.";
            return;
        }

        const { data } = payload;
        resultTitle.textContent = data.title;
        resultMeta.textContent = `${data.method} | ${data.language} | t\u1ec9 l\u1ec7 ${Math.round(Number(data.ratio) * 100)}% | ${data.created_at}`;
        resultKeywords.innerHTML = data.keywords.map((keyword) => `<span>${keyword}</span>`).join("");
        summaryOutput.innerHTML = data.highlighted_summary;
        detailLink.href = data.history_url;
        detailLink.classList.remove("is-hidden");
        message.textContent = "\u0110\u00e3 l\u01b0u b\u1ea3n t\u00f3m t\u1eaft v\u00e0o h\u1ec7 th\u1ed1ng.";
    } catch (error) {
        message.textContent = "Kh\u00f4ng th\u1ec3 k\u1ebft n\u1ed1i t\u1edbi m\u00e1y ch\u1ee7.";
    }
}

if (sourceSelect) {
    sourceSelect.addEventListener("change", updateSourceFields);
    updateSourceFields();
}

if (ratioSlider && ratioInput) {
    const initialPercent = Math.round(Number(ratioInput.value || "0.2") * 100);
    ratioSlider.value = String(initialPercent);
    ratioSlider.addEventListener("input", updateRatioUi);
    updateRatioUi();
}

applyTheme(getPreferredTheme());

if (themeToggle) {
    themeToggle.addEventListener("click", () => {
        const nextTheme = root.dataset.theme === "dark" ? "light" : "dark";
        applyTheme(nextTheme);
    });
}

if (form) {
    form.addEventListener("submit", submitSummary);
}
