import "./styles.css";

const form = document.querySelector("#query-form");
const modeSelect = document.querySelector("#mode");
const routeList = document.querySelector("#route-list");
const submitButton = document.querySelector("#submit-button");
const errorMessage = document.querySelector("#error-message");
const resultPanel = document.querySelector("#result-panel");

const routes = {
  customer: [
    "Client",
    "Customer Agent",
    "Registry discovery",
    "Law Agent",
    "Tax + Compliance · parallel",
    "Law aggregate",
    "Customer response",
  ],
  "direct-law": [
    "Client",
    "Registry discovery",
    "Law Agent",
    "Tax + Compliance · parallel",
    "Law aggregate",
  ],
};

const modeNotes = {
  customer:
    "Tuyến đầy đủ dùng Customer Agent để phân loại và định dạng phản hồi.",
  "direct-law":
    "Tuyến tối ưu dành cho đầu vào đã biết chắc là câu hỏi pháp lý.",
};

function renderRoute(mode, activeRoute = null) {
  const route = activeRoute || routes[mode];
  routeList.replaceChildren(
    ...route.map((step, index) => {
      const item = document.createElement("li");
      const number = document.createElement("span");
      const label = document.createElement("strong");
      number.textContent = String(index + 1).padStart(2, "0");
      label.textContent = step;
      item.append(number, label);
      return item;
    }),
  );
}

function setLoading(isLoading) {
  submitButton.disabled = isLoading;
  submitButton.querySelector("span").textContent = isLoading
    ? "Agents đang xử lý"
    : "Chạy hệ thống";
  document.body.classList.toggle("is-loading", isLoading);
}

function updateServiceCards(health) {
  document.querySelectorAll("[data-service]").forEach((card) => {
    const status = health.services[card.dataset.service];
    card.classList.toggle("is-online", Boolean(status?.online));
    card.classList.toggle("is-offline", !status?.online);
    card.title = status?.online
      ? `Online · ${status.latency_ms} ms`
      : status?.error || "Offline";
  });

  const statusText = document.querySelector("#system-status-text");
  const statusBadge = document.querySelector("[data-testid='system-status']");
  statusText.textContent = health.ready
    ? "5 services online"
    : "Hệ thống chưa sẵn sàng";
  statusBadge.classList.toggle("is-ready", health.ready);
}

async function refreshHealth() {
  try {
    const response = await fetch("/api/health");
    if (!response.ok) throw new Error("Không đọc được trạng thái hệ thống.");
    updateServiceCards(await response.json());
  } catch {
    updateServiceCards({ ready: false, services: {} });
  }
}

modeSelect.addEventListener("change", () => {
  renderRoute(modeSelect.value);
  document.querySelector("#mode-note").textContent = modeNotes[modeSelect.value];
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  errorMessage.textContent = "";
  resultPanel.hidden = true;
  setLoading(true);

  try {
    const response = await fetch("/api/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question: document.querySelector("#question").value,
        mode: modeSelect.value,
      }),
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || "Yêu cầu Stage 5 thất bại.");
    }

    document.querySelector("#latency-value").textContent =
      `${payload.total_seconds.toFixed(2)}s`;
    document.querySelector("#result-mode").textContent = payload.mode;
    document.querySelector("#trace-id").textContent = payload.trace_id;
    document.querySelector("#context-id").textContent = payload.context_id;
    document.querySelector("#response-text").textContent =
      payload.answer || "Không nhận được nội dung phản hồi.";
    renderRoute(payload.mode, payload.route);
    resultPanel.hidden = false;
    resultPanel.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    errorMessage.textContent = error.message;
  } finally {
    setLoading(false);
    refreshHealth();
  }
});

renderRoute("customer");
refreshHealth();
