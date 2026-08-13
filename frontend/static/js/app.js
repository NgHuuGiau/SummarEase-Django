(function () {
    "use strict";

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
        if (!sourceSelect) {
            return;
        }
        const type = sourceSelect.value;
        textWrap.classList.toggle("is-hidden", type !== "text");
        fileWrap.classList.toggle("is-hidden", type !== "file");
        urlWrap.classList.toggle("is-hidden", type !== "url");
        Object.values(errorMap).forEach(function (el) {
            if (el) el.textContent = "";
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
        themeToggle.addEventListener("click", function () {
            const nextTheme = root.dataset.theme === "dark" ? "light" : "dark";
            applyTheme(nextTheme);
        });
    }

    if (form) {
        form.addEventListener("submit", submitSummary);
    }
})();
