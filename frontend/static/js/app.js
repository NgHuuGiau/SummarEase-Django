(function () {
    "use strict";

    const sourceBtns = document.querySelectorAll("[data-source]");
    const methodBtns = document.querySelectorAll("[data-method]");
    const sourceInput = document.querySelector("#source_type");
    const methodInput = document.querySelector("#method");
    const methodHint = document.querySelector("#method-hint");
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
    const copyBtn = document.querySelector("#copy-btn");
    const submitBtn = document.querySelector("#submit-btn");
    const btnText = submitBtn && submitBtn.querySelector(".btn-text");
    const btnSpinner = submitBtn && submitBtn.querySelector(".btn-spinner");
    const root = document.documentElement;
    const themeToggle = document.querySelector("[data-theme-toggle]");
    const themeLabel = document.querySelector("[data-theme-label]");
    const themeIcon = document.querySelector("[data-theme-icon]");
    const themeBadge = document.querySelector("[data-theme-badge]");
    const themeCopy = document.querySelector("[data-theme-copy]");
    const ratioSlider = document.querySelector("#ratio_slider");
    const ratioInput = document.querySelector("#ratio_input");
    const ratioValue = document.querySelector("#ratio_value");

    const errorMap = {
        text: document.querySelector("#error-text"),
        upload: document.querySelector("#error-upload"),
        source_url: document.querySelector("#error-source_url"),
    };

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
            themeLabel.textContent = isDark ? "Chế độ tối" : "Chế độ sáng";
        }
        if (themeIcon) {
            themeIcon.textContent = isDark ? "\u263e" : "\u2600";
        }
        if (themeBadge) {
            themeBadge.textContent = isDark ? "Chế độ tối" : "Chế độ sáng";
        }
        if (themeCopy) {
            themeCopy.textContent = isDark
                ? "Hệ thống đang hiển thị theme tối để tập trung vào nội dung và thao tác buổi tối."
                : "Hệ thống đang hiển thị theme sáng để đọc và thao tác rõ ràng.";
        }
    }

    function applyTheme(theme) {
        root.dataset.theme = theme;
        window.localStorage.setItem("summarease-theme", theme);
        syncThemeUi(theme);
    }

    function updateSourceFields() {
        if (!sourceInput) {
            return;
        }
        const type = sourceInput.value;
        textWrap.classList.toggle("is-hidden", type !== "text");
        fileWrap.classList.toggle("is-hidden", type !== "file");
        urlWrap.classList.toggle("is-hidden", type !== "url");
        Object.values(errorMap).forEach(function (el) {
            if (el) el.textContent = "";
        });
    }

    function bindSegmented(buttons, input, onActivate) {
        buttons.forEach(function (btn) {
            btn.addEventListener("click", function () {
                buttons.forEach(function (b) { b.classList.remove("is-active"); b.setAttribute("aria-selected", "false"); });
                btn.classList.add("is-active");
                btn.setAttribute("aria-selected", "true");
                input.value = btn.dataset.source || btn.dataset.method;
                if (onActivate) onActivate(input.value);
            });
        });
    }

    function updateRatioUi() {
        if (!ratioSlider || !ratioInput) {
            return;
        }
        const percent = Number(ratioSlider.value);
        ratioInput.value = (percent / 100).toFixed(2);
        if (ratioValue) {
            ratioValue.textContent = percent + "%";
        }
    }

    function setLoading(loading) {
        if (!submitBtn) return;
        submitBtn.disabled = loading;
        btnText.classList.toggle("is-hidden", loading);
        btnSpinner.classList.toggle("is-hidden", !loading);
    }

    function clearErrors() {
        Object.values(errorMap).forEach(function (el) {
            if (el) el.textContent = "";
        });
        if (message) message.textContent = "";
    }

    function showFieldErrors(errors) {
        if (!errors) return;
        Object.keys(errors).forEach(function (field) {
            const el = errorMap[field];
            if (el && errors[field].length) {
                el.textContent = errors[field].join(" ");
            }
        });
    }

    async function submitSummary(event) {
        event.preventDefault();
        clearErrors();
        setLoading(true);

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
                if (payload.errors) {
                    showFieldErrors(payload.errors);
                    message.textContent = "Vui lòng sửa các lỗi trong form.";
                } else {
                    message.textContent = payload.message || "Không thể tóm tắt.";
                }
                return;
            }

            const data = payload.data;
            resultTitle.textContent = data.title;
            resultMeta.textContent = data.method + " | " + data.language + " | tỉ lệ " + Math.round(Number(data.ratio) * 100) + "% | " + data.created_at;
            resultKeywords.innerHTML = data.keywords.map(function (kw) { return "<span>" + kw + "</span>"; }).join("");
            summaryOutput.innerHTML = data.highlighted_summary;
            detailLink.href = data.history_url;
            detailLink.classList.remove("is-hidden");
            if (copyBtn) copyBtn.classList.remove("is-hidden");
            message.textContent = "Đã lưu bản tóm tắt vào hệ thống.";
            message.style.color = "";
        } catch (error) {
            message.textContent = "Không thể kết nối tới máy chủ.";
            message.style.color = "var(--danger)";
        } finally {
            setLoading(false);
        }
    }

    // Init
    bindSegmented(sourceBtns, sourceInput, updateSourceFields);
    bindSegmented(methodBtns, methodInput, function (method) {
        if (methodHint) {
            methodHint.textContent = method === "gemini"
                ? "Gemini nâng cao, hiểu ngữ nghĩa — cần khóa API Gemini."
                : "TextRank hoạt động nhanh, không cần API — phù hợp văn bản tiếng Việt.";
        }
    });
    updateSourceFields();

    if (copyBtn) {
        copyBtn.addEventListener("click", function () {
            const text = (summaryOutput.textContent || "").trim();
            if (!text) return;
            navigator.clipboard.writeText(text).then(function () {
                copyBtn.textContent = "✓ Đã sao chép";
                setTimeout(function () { copyBtn.textContent = "📋 Sao chép"; }, 1600);
            });
        });
    }

    if (ratioSlider && ratioInput) {
        const initialPercent = Math.round(Number(ratioInput.value || "0.2") * 100);
        ratioSlider.value = String(initialPercent);
        ratioSlider.addEventListener("input", updateRatioUi);
        updateRatioUi();
    }

    applyTheme(getPreferredTheme());

    if (themeToggle) {
        themeToggle.addEventListener("click", function () {
            const nextTheme = root.dataset.theme === "dark" ? "light" : "dark";
            applyTheme(nextTheme);
        });
    }

    if (form) {
        form.addEventListener("submit", submitSummary);
    }
})();
