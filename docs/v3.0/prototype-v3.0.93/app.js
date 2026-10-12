const pageButtons = document.querySelectorAll("[data-page]");
const receiptPage = document.querySelector("#receipt-page");
const paymentPage = document.querySelector("#payment-page");
const analysisPage = document.querySelector("#analysis-page");
const receiptDrawer = document.querySelector("#receipt-drawer");
const paymentModal = document.querySelector("#payment-modal");

function setPage(page) {
  pageButtons.forEach((button) => {
    button.classList.toggle("active", button.dataset.page === page);
  });
  receiptPage.classList.toggle("active", page === "receipt");
  paymentPage.classList.toggle("active", page === "payment");
  analysisPage.classList.toggle("active", page === "analysis");
}

pageButtons.forEach((button) => {
  button.addEventListener("click", () => setPage(button.dataset.page));
});

document.querySelectorAll("[data-open-receipt]").forEach((button) => {
  button.addEventListener("click", () => {
    receiptDrawer.classList.add("open");
    receiptDrawer.setAttribute("aria-hidden", "false");
  });
});

document.querySelectorAll("[data-open-payment]").forEach((button) => {
  button.addEventListener("click", () => {
    setPage("payment");
    paymentModal.classList.add("open");
    paymentModal.setAttribute("aria-hidden", "false");
  });
});

document.querySelectorAll("[data-close]").forEach((button) => {
  button.addEventListener("click", () => {
    receiptDrawer.classList.remove("open");
    receiptDrawer.setAttribute("aria-hidden", "true");
    paymentModal.classList.remove("open");
    paymentModal.setAttribute("aria-hidden", "true");
  });
});

[receiptDrawer, paymentModal].forEach((overlay) => {
  overlay.addEventListener("click", (event) => {
    if (event.target === overlay) {
      overlay.classList.remove("open");
      overlay.setAttribute("aria-hidden", "true");
    }
  });
});

document.querySelectorAll("[data-payee]").forEach((button) => {
  button.addEventListener("click", () => {
    const type = button.dataset.payee;
    document.querySelectorAll("[data-payee]").forEach((item) => {
      item.classList.toggle("active", item === button);
    });
    document.querySelectorAll(".payee-pane").forEach((pane) => {
      pane.classList.toggle("active", pane.id === `payee-${type}`);
    });
  });
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    receiptDrawer.classList.remove("open");
    receiptDrawer.setAttribute("aria-hidden", "true");
    paymentModal.classList.remove("open");
    paymentModal.setAttribute("aria-hidden", "true");
  }
});
