Yuhen.api("/api/stats")
  .then((stats) => Yuhen.updateStats(stats))
  .catch((error) => {
    const status = document.getElementById("home-status");
    if (status) status.textContent = error.message;
  });
