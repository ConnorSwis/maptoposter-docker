document.getElementById("radius").addEventListener("input", (e) => {
  document.getElementById("radiusVal").textContent =
    Math.round(e.target.value / 100) / 10;
});

function getSelectedFeatureIds() {
  return Array.from(document.querySelectorAll(".feature-checkbox:checked")).map(
    (cb) => cb.value,
  );
}

const defaultSteps = [
  { id: "start", label: "Starting job" },
  { id: "geocode", label: "Resolving location" },
  { id: "street", label: "Downloading street network" },
  { id: "data", label: "Preparing map data" },
  { id: "render", label: "Rendering map" },
  { id: "save", label: "Saving image" },
  { id: "complete", label: "Finalizing" },
];

let lastStageIndex = 0;
let lastStageLabel = defaultSteps[0].label;
let stageTotal = defaultSteps.length;

function renderSteps(steps) {
  const list = document.getElementById("stageList");
  list.innerHTML = "";
  stageTotal = steps.length;
  steps.forEach((step, idx) => {
    const li = document.createElement("li");
    li.className = "stage-item";
    li.dataset.index = idx;
    li.dataset.stageId = step.id;
    li.innerHTML = `
      <span class="stage-label">${step.label}</span>
      <span class="stage-status" data-state="queued" aria-label="Queued"></span>
    `;
    list.appendChild(li);
  });
}

function updateStage(index, label) {
  const items = Array.from(document.querySelectorAll("#stageList .stage-item"));
  items.forEach((li, idx) => {
    li.classList.remove("stage-done", "stage-active");
    const status = li.querySelector(".stage-status");
    if (idx < index) {
      li.classList.add("stage-done");
      status.dataset.state = "done";
      status.setAttribute("aria-label", "Done");
    } else if (idx === index) {
      li.classList.add("stage-active");
      status.dataset.state = "active";
      status.setAttribute("aria-label", "In progress");
    } else {
      status.dataset.state = "queued";
      status.setAttribute("aria-label", "Queued");
    }
  });
  const current = document.getElementById("progressCurrent");
  current.textContent = label ? `Step ${index + 1} of ${stageTotal}` : "";
  lastStageIndex = index;
  lastStageLabel = label;
}

function completeStages() {
  const items = Array.from(document.querySelectorAll("#stageList .stage-item"));
  items.forEach((li) => {
    li.classList.remove("stage-active");
    li.classList.add("stage-done");
    const status = li.querySelector(".stage-status");
    status.dataset.state = "done";
    status.setAttribute("aria-label", "Done");
  });
  const current = document.getElementById("progressCurrent");
  current.textContent = "All steps complete";
  lastStageIndex = stageTotal - 1;
  lastStageLabel = "All steps complete";
}

document.getElementById("mapForm").addEventListener("submit", async (e) => {
  e.preventDefault();

  const btn = document.getElementById("generateBtn");
  const loader = document.getElementById("loader");
  const img = document.getElementById("resultImage");
  const link = document.getElementById("downloadLink");
  const err = document.getElementById("errorMsg");
  const progressPanel = document.getElementById("progressPanel");

  btn.disabled = true;
  loader.classList.remove("hidden");
  img.classList.add("hidden");
  link.classList.add("hidden");
  err.textContent = "";

  progressPanel.classList.remove("hidden");
  renderSteps(defaultSteps);
  updateStage(0, defaultSteps[0].label);

  let es = null;

  try {
    const latRaw = document.getElementById("lat").value.trim();
    const lonRaw = document.getElementById("lon").value.trim();
    const starLatRaw = document.getElementById("starLat").value.trim();
    const starLonRaw = document.getElementById("starLon").value.trim();
    let lat = null;
    let lon = null;
    let starLat = null;
    let starLon = null;
    if (latRaw || lonRaw) {
      if (!latRaw || !lonRaw) {
        err.textContent = "Provide both latitude and longitude.";
        loader.classList.add("hidden");
        btn.disabled = false;
        return;
      }
      lat = Number(latRaw);
      lon = Number(lonRaw);
      if (Number.isNaN(lat) || Number.isNaN(lon)) {
        err.textContent = "Latitude and longitude must be valid numbers.";
        loader.classList.add("hidden");
        btn.disabled = false;
        return;
      }
    }
    if (starLatRaw || starLonRaw) {
      if (!starLatRaw || !starLonRaw) {
        err.textContent = "Provide both star latitude and star longitude.";
        loader.classList.add("hidden");
        btn.disabled = false;
        return;
      }
      starLat = Number(starLatRaw);
      starLon = Number(starLonRaw);
      if (Number.isNaN(starLat) || Number.isNaN(starLon)) {
        err.textContent = "Star coordinates must be valid numbers.";
        loader.classList.add("hidden");
        btn.disabled = false;
        return;
      }
    }

    const res = await fetch("/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        city: document.getElementById("city").value,
        country: document.getElementById("country").value,
        theme: document.getElementById("theme").value,
        radius: document.getElementById("radius").value,
        features: getSelectedFeatureIds(),
        lat: lat,
        lon: lon,
        star_lat: starLat,
        star_lon: starLon,
      }),
    });

    const startData = await res.json();
    if (!res.ok || !startData.success) {
      throw new Error(startData.error || "Failed to start generation.");
    }

    const job_id = startData.job_id;

    es = new EventSource(`/jobs/${job_id}/logs`);

    es.addEventListener("steps", (evt) => {
      try {
        const payload = JSON.parse(evt.data);
        if (payload && Array.isArray(payload.steps) && payload.steps.length) {
          renderSteps(payload.steps);
          updateStage(lastStageIndex, lastStageLabel);
        }
      } catch {
        // ignore malformed steps payload
      }
    });

    es.addEventListener("stage", (evt) => {
      try {
        const payload = JSON.parse(evt.data);
        if (payload && Number.isInteger(payload.index)) {
          updateStage(payload.index, payload.label || "");
        }
      } catch {
        // ignore malformed stage payload
      }
    });

    es.addEventListener("error", async (evt) => {
      try {
        const status = await fetch(`/jobs/${job_id}`).then((r) => r.json());
        if (status.success && status.done && !status.ok) {
          err.textContent = status.error || "Poster generation failed.";
          updateStage(lastStageIndex, "Failed");
        } else {
          err.textContent = "Connection issue while streaming logs.";
          updateStage(lastStageIndex, "Connection issue");
        }
      } catch {
        err.textContent = "Connection issue while streaming logs.";
        updateStage(lastStageIndex, "Connection issue");
      } finally {
        loader.classList.add("hidden");
        if (es) es.close();
        btn.disabled = false;
      }
    });

    es.addEventListener("done", (evt) => {
      const filename = evt.data;
      completeStages();

      img.src = `/posters/${filename}`;
      img.classList.remove("hidden");

      link.href = `/posters/${filename}`;
      link.download = filename;
      link.classList.remove("hidden");

      loader.classList.add("hidden");
      progressPanel.classList.add("hidden");
    });

    es.addEventListener("end", () => {
      if (es) es.close();
      btn.disabled = false;
    });
  } catch (ex) {
    err.textContent = ex.message || "Connection error.";
    loader.classList.add("hidden");
    btn.disabled = false;
    if (es) es.close();
  }
});
