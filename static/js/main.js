/* Banking Management System — Frontend JS */

document.addEventListener("DOMContentLoaded", () => {
  // Mark active sidebar link
  const path = window.location.pathname.replace(/\/$/, "");
  document.querySelectorAll(".sidebar-link").forEach(link => {
    const href = link.getAttribute("href").replace(/\/$/, "");
    if (href === path || (href !== "/" && path.startsWith(href))) {
      link.classList.add("active");
    }
  });

  // Amount formatting — visual commas, submit raw value
  document.querySelectorAll(".amount-input").forEach(input => {
    input.addEventListener("input", () => {
      const raw = input.value.replace(/[^0-9.]/g, "");
      const parts = raw.split(".");
      parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ",");
      input.value = parts.slice(0, 2).join(".");
    });

    // Strip commas before submit
    input.closest("form")?.addEventListener("submit", () => {
      input.value = input.value.replace(/,/g, "");
    });
  });

  // Transfer: same-account guard
  const fromSel = document.getElementById("from_account");
  const toSel   = document.getElementById("to_account");
  const sameErr = document.getElementById("same-account-error");
  const submitBtn = document.getElementById("transfer-submit");

  function checkSameAccount() {
    if (!fromSel || !toSel) return;
    const same = fromSel.value && toSel.value && fromSel.value === toSel.value;
    if (sameErr) sameErr.style.display = same ? "block" : "none";
    if (submitBtn) submitBtn.disabled = same;
  }

  fromSel?.addEventListener("change", checkSameAccount);
  toSel?.addEventListener("change", checkSameAccount);

  // Confirm dialogs for transfers and withdrawals
  document.querySelectorAll("[data-confirm]").forEach(btn => {
    btn.addEventListener("click", e => {
      const msg = btn.dataset.confirm;
      if (!confirm(msg)) e.preventDefault();
    });
  });

  // Prevent double submit
  document.querySelectorAll("form[data-once]").forEach(form => {
    form.addEventListener("submit", () => {
      form.querySelectorAll("[type=submit]").forEach(b => {
        b.disabled = true;
        b.textContent = "Processing…";
      });
    });
  });

  // Auto-dismiss flash messages after 5 s
  document.querySelectorAll(".flash-msg").forEach(el => {
    setTimeout(() => {
      el.style.transition = "opacity 0.5s";
      el.style.opacity = "0";
      setTimeout(() => el.remove(), 500);
    }, 5000);
  });

});
