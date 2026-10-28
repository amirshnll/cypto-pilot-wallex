(() => {
  const element = document.getElementById("analytics-chart-data");
  const canvas = document.getElementById("performance-chart");
  if (!element || !canvas || typeof Chart === "undefined") return;
  const data = JSON.parse(element.textContent);
  if (!data.equity.length) {
    canvas.parentElement.innerHTML = '<div class="chart-empty">The equity and drawdown chart will appear after a few cycles.</div>';
    return;
  }
  const label = (value) => new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }).format(new Date(value));
  new Chart(canvas, {
    type: "line",
    data: {
      datasets: [
        { label: "Equity", data: data.equity, parsing: false, borderColor: "#2ee6a6", backgroundColor: "rgba(46,230,166,.08)", fill: true, pointRadius: 0, yAxisID: "equity" },
        { label: "Drawdown %", data: data.drawdown, parsing: false, borderColor: "#ff6b7d", backgroundColor: "transparent", pointRadius: 0, yAxisID: "drawdown" }
      ]
    },
    options: { responsive: true, maintainAspectRatio: false, interaction: { mode: "index", intersect: false }, plugins: { legend: { position: "bottom" } }, scales: { x: { type: "linear", ticks: { maxTicksLimit: 7, callback: label } }, equity: { position: "right" }, drawdown: { position: "left", grid: { display: false }, ticks: { callback: (v) => `${v}%` } } } }
  });
})();
