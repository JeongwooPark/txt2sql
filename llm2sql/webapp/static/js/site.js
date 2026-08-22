(function () {
  const ui = document.body.getAttribute("data-ui") || "";
  const navKey = ui.startsWith("data") ? "data" : ui;
  document.querySelectorAll("[data-nav]").forEach((el) => {
    if (el.getAttribute("data-nav") === navKey) {
      el.classList.add("active");
    }
  });

  document.querySelectorAll(".nav-drop-btn").forEach((btn) => {
    btn.addEventListener("click", (event) => {
      event.stopPropagation();
      const drop = btn.closest(".nav-drop");
      const open = drop.classList.toggle("open");
      btn.setAttribute("aria-expanded", open ? "true" : "false");
    });
  });

  document.addEventListener("click", () => {
    document.querySelectorAll(".nav-drop.open").forEach((el) => {
      el.classList.remove("open");
      el.querySelector(".nav-drop-btn")?.setAttribute("aria-expanded", "false");
    });
  });
})();
