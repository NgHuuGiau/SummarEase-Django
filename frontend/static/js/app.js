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
    const fileInput = document.querySelector("#file-input");
    const form = document.querySelector("#summary-form");
    const message = document.querySelector("#form-message");
    const resultTitle = document.querySelector("#result-title");
    const resultDesc = document.querySelector("#result-desc");
    const resultMeta = document.querySelector("#result-meta");
    const resultKeywords = document.querySelector("#result-keywords");
    const summaryEmpty = document.querySelector("#summary-empty");
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
            themeLabel.textContent = isDark ? "Tối" : "Sáng";
        }
        if (themeIcon) {
            themeIcon.textContent = isDark ? "\u263e" : "\u2600";
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
        if (textWrap) textWrap.classList.toggle("is-hidden", type !== "text");
        if (fileWrap) fileWrap.classList.toggle("is-hidden", type !== "file");
        if (urlWrap) urlWrap.classList.toggle("is-hidden", type !== "url");
        Object.values(errorMap).forEach(function (el) {
            if (el) el.textContent = "";
        });
    }

    function bindSegmented(buttons, input, onActivate) {
        buttons.forEach(function (btn) {
            btn.addEventListener("click", function () {
                buttons.forEach(function (b) {
                    b.classList.remove("is-active");
                    b.setAttribute("aria-selected", "false");
                });
                btn.classList.add("is-active");
                btn.setAttribute("aria-selected", "true");
                if (input) {
                    input.value = btn.dataset.source || btn.dataset.method;
                }
                if (onActivate) onActivate(btn.dataset.source || btn.dataset.method);
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
        if (btnText) btnText.classList.toggle("is-hidden", loading);
        if (btnSpinner) btnSpinner.classList.toggle("is-hidden", !loading);
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
                message.style.color = "var(--danger)";
                return;
            }

            const data = payload.data;
            if (resultTitle) resultTitle.textContent = data.title;
            if (resultDesc) resultDesc.textContent = "Đã xử lý lúc " + data.created_at;
            if (resultMeta) {
                resultMeta.innerHTML = "<span class=\"badge textrank\">" + data.method + "</span>" +
                    "<span class=\"badge source-badge\">" + data.language + "</span>" +
                    "<span class=\"badge-ratio\">Tỉ lệ " + Math.round(Number(data.ratio) * 100) + "%</span>";
            }
            if (resultKeywords && data.keywords) {
                resultKeywords.innerHTML = data.keywords.map(function (kw) {
                    return "<span class=\"keyword-chip\"># " + kw + "</span>";
                }).join("");
            }
            if (summaryEmpty) summaryEmpty.classList.add("is-hidden");
            if (summaryOutput) {
                summaryOutput.innerHTML = data.highlighted_summary;
                summaryOutput.classList.remove("is-hidden");
            }
            if (detailLink) {
                detailLink.href = data.history_url;
                detailLink.classList.remove("is-hidden");
            }
            if (copyBtn) copyBtn.classList.remove("is-hidden");
            message.textContent = "✨ Đã tạo và lưu bản tóm tắt vào hệ thống.";
            message.style.color = "var(--success)";
        } catch (error) {
            message.textContent = "Không thể kết nối tới máy chủ.";
            message.style.color = "var(--danger)";
        } finally {
            setLoading(false);
        }
    }

    // Init segmented buttons
    bindSegmented(sourceBtns, sourceInput, updateSourceFields);
    bindSegmented(methodBtns, methodInput, function (method) {
        if (methodHint) {
            methodHint.textContent = method === "gemini"
                ? "Gemini AI phân tích ngữ nghĩa sâu, hiểu câu đa tầng — cần cấu hình khóa API Gemini."
                : "TextRank phân tích câu tự động, xử lý cực nhanh trên máy chủ nội bộ mà không cần API key ngoài.";
        }
    });
    updateSourceFields();

    // File input change feedback
    if (fileInput) {
        fileInput.addEventListener("change", function () {
            if (fileInput.files && fileInput.files[0]) {
                const dropzoneStrong = fileInput.parentElement.querySelector("strong");
                if (dropzoneStrong) {
                    dropzoneStrong.textContent = "📄 " + fileInput.files[0].name;
                }
            }
        });
    }

    if (copyBtn) {
        copyBtn.addEventListener("click", function () {
            const text = (summaryOutput.textContent || "").trim();
            if (!text) return;
            navigator.clipboard.writeText(text).then(function () {
                const label = copyBtn.querySelector("span");
                if (label) label.textContent = "Đã sao chép!";
                setTimeout(function () {
                    if (label) label.textContent = "Sao chép";
                }, 1600);
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

