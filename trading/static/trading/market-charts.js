(() => {
  const dataElement = document.getElementById("market-chart-data");
  if (!dataElement || typeof Chart === "undefined") return;

  const charts = JSON.parse(dataElement.textContent);
  Chart.defaults.color = "#6c757d";
  Chart.defaults.borderColor = "#dee2e6";
  Chart.defaults.font.family = "Inter, ui-sans-serif, system-ui, sans-serif";

  const dateLabel = (milliseconds) => new Intl.DateTimeFormat("en-US", {
    month: "short", day: "numeric", hour: "2-digit", minute: "2-digit"
  }).format(new Date(milliseconds));

  charts.forEach((market) => {
    const canvas = document.getElementById(market.canvas_id);
    if (!canvas || !market.price_points.length) return;

    new Chart(canvas, {
      type: "line",
      data: {
        datasets: [
          {
            label: "Price",
            data: market.price_points,
            parsing: false,
            borderColor: "#2ee6a6",
            backgroundColor: "rgba(46,230,166,.10)",
            borderWidth: 2,
            pointRadius: market.price_points.length < 25 ? 2 : 0,
            pointHoverRadius: 5,
            tension: 0,
            fill: true,
            order: 3
          },
          {
            type: "scatter",
            label: "Buy",
            data: market.buy_points,
            parsing: false,
            pointStyle: "triangle",
            pointRadius: 8,
            pointHoverRadius: 10,
            rotation: 0,
            backgroundColor: "#69f2c2",
            borderColor: "#092c20",
            borderWidth: 2,
            order: 1
          },
          {
            type: "scatter",
            label: "Sell",
            data: market.sell_points,
            parsing: false,
            pointStyle: "triangle",
            pointRadius: 8,
            pointHoverRadius: 10,
            rotation: 180,
            backgroundColor: "#ff6b7d",
            borderColor: "#3a0e16",
            borderWidth: 2,
            order: 1
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 450 },
        interaction: { mode: "nearest", intersect: false },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: "#17212b",
            borderColor: "#344653",
            borderWidth: 1,
            titleColor: "#edf4f7",
            callbacks: {
              title: (items) => items.length ? dateLabel(items[0].parsed.x) : "",
              label: (context) => `${context.dataset.label}: ${context.parsed.y}`
            }
          }
        },
        scales: {
          x: {
            type: "linear",
            grid: { display: false },
            ticks: { maxTicksLimit: 6, callback: (value) => dateLabel(value) }
          },
          y: {
            position: "right",
            grid: { color: "rgba(38,51,64,.55)" },
            ticks: { maxTicksLimit: 6 }
          }
        }
      }
    });
  });
})();
