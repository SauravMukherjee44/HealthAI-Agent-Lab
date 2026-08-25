(() => {
  const header = document.querySelector("[data-header]");
  const menuButton = document.querySelector("[data-menu-toggle]");
  const navigation = document.querySelector("[data-nav]");

  const syncHeader = () => header?.classList.toggle("scrolled", window.scrollY > 24);
  syncHeader();
  window.addEventListener("scroll", syncHeader, { passive: true });

  const closeMenu = () => {
    if (!menuButton || !navigation) return;
    menuButton.setAttribute("aria-expanded", "false");
    menuButton.setAttribute("aria-label", "Open navigation");
    navigation.classList.remove("open");
    document.body.classList.remove("menu-open");
  };

  menuButton?.addEventListener("click", () => {
    const isOpen = menuButton.getAttribute("aria-expanded") === "true";
    menuButton.setAttribute("aria-expanded", String(!isOpen));
    menuButton.setAttribute("aria-label", isOpen ? "Open navigation" : "Close navigation");
    navigation?.classList.toggle("open", !isOpen);
    document.body.classList.toggle("menu-open", !isOpen);
  });
  navigation?.querySelectorAll("a").forEach((link) => link.addEventListener("click", closeMenu));
  window.addEventListener("resize", () => { if (window.innerWidth > 980) closeMenu(); });

  const revealItems = document.querySelectorAll(".reveal");
  if ("IntersectionObserver" in window && !window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("visible");
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.08, rootMargin: "0px 0px -30px" });
    revealItems.forEach((item) => observer.observe(item));
  } else {
    revealItems.forEach((item) => item.classList.add("visible"));
  }

  const assessmentForm = document.querySelector("[data-assessment-form]");
  if (assessmentForm) {
    const fields = [...assessmentForm.querySelectorAll("[data-track-field]")];
    const progressBar = document.querySelector("[data-progress-bar]");
    const progressText = document.querySelector("[data-progress-text]");
    const completedText = document.querySelector("[data-completed]");
    const updateProgress = () => {
      const completed = fields.filter((field) => field.value !== "").length;
      const percentage = Math.round((completed / fields.length) * 100);
      if (progressBar) progressBar.style.width = `${percentage}%`;
      if (progressText) progressText.textContent = `${percentage}%`;
      if (completedText) completedText.textContent = String(completed);
    };
    fields.forEach((field) => {
      field.addEventListener("input", updateProgress);
      field.addEventListener("change", updateProgress);
    });
    updateProgress();
  }

  const input = document.querySelector("[data-file-input]");
  const dropZone = document.querySelector("[data-drop-zone]");
  const preview = document.querySelector("[data-upload-preview]");
  const title = document.querySelector("[data-upload-title]");
  const subtitle = document.querySelector("[data-upload-subtitle]");

  const showFile = (file) => {
    if (!file || !preview || !title || !subtitle) return;
    if (!file.type.match(/^image\/(jpeg|png)$/)) {
      input.setCustomValidity("Please choose a JPG or PNG image.");
      input.reportValidity();
      return;
    }
    input.setCustomValidity("");
    preview.src = URL.createObjectURL(file);
    preview.classList.add("has-preview");
    title.textContent = file.name;
    subtitle.textContent = `${(file.size / (1024 * 1024)).toFixed(2)} MB · ready to analyse`;
  };

  input?.addEventListener("change", () => showFile(input.files?.[0]));
  ["dragenter", "dragover"].forEach((eventName) => dropZone?.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropZone.classList.add("dragging");
  }));
  ["dragleave", "drop"].forEach((eventName) => dropZone?.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropZone.classList.remove("dragging");
  }));
  dropZone?.addEventListener("drop", (event) => {
    const file = event.dataTransfer?.files?.[0];
    if (!file || !input) return;
    const transfer = new DataTransfer();
    transfer.items.add(file);
    input.files = transfer.files;
    showFile(file);
  });
})();
