/**
 * 90° / 180° turn profile viewer.
 */
(function () {
  function setStatus(msg, ok) {
    const el = document.getElementById("tp-status");
    if (!el) return;
    el.className = "status " + (ok === true ? "ok" : ok === false ? "error" : "");
    el.textContent = msg || "";
  }

  function drawProfile(canvasId, profile, title) {
    const c = document.getElementById(canvasId);
    if (!c || !profile) return;
    const ctx = c.getContext("2d");
    const path = profile.path || [];
    const env = profile.envelope || [];
    const pos = profile.positions_sample || [];
    const all = [
      ...path,
      ...env,
      ...pos.map((p) => [p[0], p[1]]),
    ];
    const view = window.GeoCanvas.fit(all.length ? all : [[0, 0], [10, 10]], c.width, c.height, 32);

    ctx.fillStyle = "#0a0e12";
    ctx.fillRect(0, 0, c.width, c.height);

    function stroke(pts, color, width, close, fill) {
      if (!pts || pts.length < 2) return;
      ctx.beginPath();
      pts.forEach((p, i) => {
        const [x, y] = view.toScreen(p[0], p[1]);
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      if (close) ctx.closePath();
      if (fill) {
        ctx.fillStyle = fill;
        ctx.fill();
      }
      ctx.strokeStyle = color;
      ctx.lineWidth = width;
      ctx.stroke();
    }

    if (env.length) {
      stroke(env, "#f07178", 2, true, "rgba(240,113,120,0.2)");
    }
    stroke(path, "#3ecf8e", 2.5, false);
    if (pos.length) {
      stroke(
        pos.map((p) => [p[0], p[1]]),
        "rgba(231,238,245,0.55)",
        1.2,
        false
      );
    }

    // Vehicle snapshots at start / mid / end
    if (pos.length >= 2) {
      const samples = [0, Math.floor(pos.length / 2), pos.length - 1];
      for (const i of samples) {
        const p = pos[i];
        const [sx, sy] = view.toScreen(p[0], p[1]);
        const h = p[2] || 0;
        ctx.save();
        ctx.translate(sx, sy);
        ctx.rotate(-h); // screen y-down; world heading from +x
        // Simple body stub
        ctx.fillStyle = "rgba(61,156,240,0.85)";
        ctx.fillRect(-6, -4, 14, 8);
        ctx.restore();
      }
    }

    ctx.fillStyle = "#8b9aab";
    ctx.font = "12px system-ui,sans-serif";
    ctx.fillText(
      `${title} · R=${profile.radius_m} m · max steer ${profile.max_steer_deg?.toFixed?.(1) ?? "—"}°` +
        (profile.saturated ? " · SATURATED" : ""),
      12,
      18
    );
  }

  function showMetrics(data) {
    const el = document.getElementById("tp-metrics");
    if (!el || !data?.profiles) return;
    const p90 = data.profiles["90"];
    const p180 = data.profiles["180"];
    el.classList.remove("empty");
    el.innerHTML = `
      <div><strong>${data.vehicle_name || "Vehicle"}</strong></div>
      <dl>
        <dt>90° max steer</dt><dd class="${p90.saturated ? "warn" : ""}">${p90.max_steer_deg.toFixed(1)}° ${p90.saturated ? "(limit)" : ""}</dd>
        <dt>90° min radius (approx)</dt><dd>${p90.min_radius_m.toFixed(2)} m</dd>
        <dt>180° max steer</dt><dd class="${p180.saturated ? "warn" : ""}">${p180.max_steer_deg.toFixed(1)}° ${p180.saturated ? "(limit)" : ""}</dd>
        <dt>180° min radius (approx)</dt><dd>${p180.min_radius_m.toFixed(2)} m</dd>
        <dt>Wheelbase (tractor)</dt><dd>${p90.wheelbase_m.toFixed(2)} m</dd>
        <dt>Steer limit</dt><dd>${p90.steer_limit_deg.toFixed(1)}°</dd>
      </dl>
    `;
  }

  async function run() {
    const btn = document.getElementById("tp-run");
    btn.disabled = true;
    setStatus("Simulating turn templates…");
    const source = document.getElementById("tp-source").value;
    const payload = {
      radius_90_m: +document.getElementById("tp-r90").value,
      radius_180_m: +document.getElementById("tp-r180").value,
      step_m: +document.getElementById("tp-step").value,
      stop_lock: document.getElementById("tp-stoplock").checked,
    };
    if (source === "editor" && window.VehicleEditor) {
      payload.vehicle = window.VehicleEditor.getVehicle();
    } else {
      payload.vehicle_id = document.getElementById("tp-vehicle").value;
    }
    try {
      const res = await fetch("/api/turn-profiles", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || res.statusText);
      drawProfile("tp-c90", data.profiles["90"], "90°");
      drawProfile("tp-c180", data.profiles["180"], "180°");
      showMetrics(data);
      setStatus("Turn profiles ready", true);
    } catch (e) {
      setStatus(String(e.message || e), false);
    } finally {
      btn.disabled = false;
    }
  }

  function onShow() {
    const src = document.getElementById("tp-source");
    const wrap = document.getElementById("tp-lib-wrap");
    function sync() {
      if (wrap) wrap.style.display = src.value === "library" ? "" : "none";
    }
    src?.addEventListener("change", sync);
    sync();
  }

  document.getElementById("tp-run")?.addEventListener("click", run);

  window.TurnProfiles = { run, onShow };
})();
