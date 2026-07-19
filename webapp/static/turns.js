/**
 * 90° / 180° turn profile viewer — 1 m grid + inscribed / exscribed circles.
 */
(function () {
  function setStatus(msg, ok) {
    const el = document.getElementById("tp-status");
    if (!el) return;
    el.className = "status " + (ok === true ? "ok" : ok === false ? "error" : "");
    el.textContent = msg || "";
  }

  function drawGrid(ctx, view) {
    const step = 1; // 1 m
    const x0 = Math.floor(view.minX) - 1;
    const x1 = Math.ceil(view.maxX) + 1;
    const y0 = Math.floor(view.minY) - 1;
    const y1 = Math.ceil(view.maxY) + 1;

    // Minor 1 m lines
    ctx.strokeStyle = "rgba(255,255,255,0.06)";
    ctx.lineWidth = 1;
    for (let x = x0; x <= x1; x += step) {
      const [sx0, sy0] = view.toScreen(x, y0);
      const [sx1, sy1] = view.toScreen(x, y1);
      ctx.beginPath();
      ctx.moveTo(sx0, sy0);
      ctx.lineTo(sx1, sy1);
      ctx.stroke();
    }
    for (let y = y0; y <= y1; y += step) {
      const [sx0, sy0] = view.toScreen(x0, y);
      const [sx1, sy1] = view.toScreen(x1, y);
      ctx.beginPath();
      ctx.moveTo(sx0, sy0);
      ctx.lineTo(sx1, sy1);
      ctx.stroke();
    }

    // Major 5 m lines
    ctx.strokeStyle = "rgba(255,255,255,0.12)";
    ctx.lineWidth = 1.25;
    for (let x = Math.ceil(x0 / 5) * 5; x <= x1; x += 5) {
      const [sx0, sy0] = view.toScreen(x, y0);
      const [sx1, sy1] = view.toScreen(x, y1);
      ctx.beginPath();
      ctx.moveTo(sx0, sy0);
      ctx.lineTo(sx1, sy1);
      ctx.stroke();
    }
    for (let y = Math.ceil(y0 / 5) * 5; y <= y1; y += 5) {
      const [sx0, sy0] = view.toScreen(x0, y);
      const [sx1, sy1] = view.toScreen(x1, y);
      ctx.beginPath();
      ctx.moveTo(sx0, sy0);
      ctx.lineTo(sx1, sy1);
      ctx.stroke();
    }

    // Axes through origin if visible
    if (view.minX <= 0 && view.maxX >= 0) {
      const [a, b] = view.toScreen(0, y0);
      const [c, d] = view.toScreen(0, y1);
      ctx.strokeStyle = "rgba(62, 207, 142, 0.2)";
      ctx.beginPath();
      ctx.moveTo(a, b);
      ctx.lineTo(c, d);
      ctx.stroke();
    }
    if (view.minY <= 0 && view.maxY >= 0) {
      const [a, b] = view.toScreen(x0, 0);
      const [c, d] = view.toScreen(x1, 0);
      ctx.strokeStyle = "rgba(62, 207, 142, 0.2)";
      ctx.beginPath();
      ctx.moveTo(a, b);
      ctx.lineTo(c, d);
      ctx.stroke();
    }
  }

  function drawCircle(ctx, view, cx, cy, r, color, dash, label, labelAngle) {
    if (!isFinite(r) || r <= 0) return;
    const [sx, sy] = view.toScreen(cx, cy);
    const radPx = r * view.scale;
    ctx.beginPath();
    ctx.arc(sx, sy, radPx, 0, Math.PI * 2);
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.75;
    ctx.setLineDash(dash || []);
    ctx.stroke();
    ctx.setLineDash([]);

    // Radius tick + label
    const ang = labelAngle != null ? labelAngle : -Math.PI / 4;
    const lx = cx + r * Math.cos(ang);
    const ly = cy + r * Math.sin(ang);
    const [ex, ey] = view.toScreen(lx, ly);
    ctx.beginPath();
    ctx.moveTo(sx, sy);
    ctx.lineTo(ex, ey);
    ctx.strokeStyle = color;
    ctx.lineWidth = 1;
    ctx.setLineDash([3, 3]);
    ctx.stroke();
    ctx.setLineDash([]);

    ctx.fillStyle = color;
    ctx.font = "11px system-ui,sans-serif";
    const text = label || `R=${r.toFixed(2)} m`;
    ctx.fillText(text, ex + 4, ey - 4);

    // Centre mark
    ctx.beginPath();
    ctx.arc(sx, sy, 3, 0, Math.PI * 2);
    ctx.fillStyle = color;
    ctx.fill();
  }

  function drawProfile(canvasId, profile, title) {
    const c = document.getElementById(canvasId);
    if (!c || !profile) return;
    const ctx = c.getContext("2d");
    const path = profile.path || [];
    const env = profile.envelope || [];
    const pos = profile.positions_sample || [];
    const center = profile.turn_center || [0, profile.radius_m || 12.5];
    const rIn = profile.inscribed_radius_m;
    const rOut = profile.exscribed_radius_m;
    const rPath = profile.path_radius_m ?? profile.radius_m;

    // Include full circles in view fit so they aren't clipped
    const circlePts = [];
    for (const r of [rIn, rOut, rPath]) {
      if (!r || !isFinite(r)) continue;
      for (let i = 0; i < 24; i++) {
        const a = (i / 24) * Math.PI * 2;
        circlePts.push([center[0] + r * Math.cos(a), center[1] + r * Math.sin(a)]);
      }
    }
    const all = [
      ...path,
      ...env,
      ...pos.map((p) => [p[0], p[1]]),
      ...circlePts,
      center,
    ];
    const view = window.GeoCanvas.fit(
      all.length ? all : [[0, 0], [10, 10]],
      c.width,
      c.height,
      36
    );

    ctx.fillStyle = "#0a0e12";
    ctx.fillRect(0, 0, c.width, c.height);

    drawGrid(ctx, view);

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

    // Circles under envelope so path reads on top: path R (faint), outer, inner
    if (rPath) {
      drawCircle(
        ctx,
        view,
        center[0],
        center[1],
        rPath,
        "rgba(62, 207, 142, 0.55)",
        [6, 4],
        `path R=${Number(rPath).toFixed(2)} m`,
        Math.PI * 0.15
      );
    }
    if (rOut) {
      drawCircle(
        ctx,
        view,
        center[0],
        center[1],
        rOut,
        "#f07178",
        [],
        `exscribed R=${Number(rOut).toFixed(2)} m`,
        -Math.PI * 0.35
      );
    }
    if (rIn) {
      drawCircle(
        ctx,
        view,
        center[0],
        center[1],
        rIn,
        "#3d9cf0",
        [2, 3],
        `inscribed R=${Number(rIn).toFixed(2)} m`,
        Math.PI * 0.65
      );
    }

    if (env.length) {
      stroke(env, "rgba(240,113,120,0.85)", 2, true, "rgba(240,113,120,0.14)");
    }
    stroke(path, "#3ecf8e", 2.5, false);
    if (pos.length) {
      stroke(
        pos.map((p) => [p[0], p[1]]),
        "rgba(231,238,245,0.5)",
        1.2,
        false
      );
    }

    if (pos.length >= 2) {
      const samples = [0, Math.floor(pos.length / 2), pos.length - 1];
      for (const i of samples) {
        const p = pos[i];
        const [sx, sy] = view.toScreen(p[0], p[1]);
        const h = p[2] || 0;
        ctx.save();
        ctx.translate(sx, sy);
        ctx.rotate(-h);
        ctx.fillStyle = "rgba(61,156,240,0.85)";
        ctx.fillRect(-6, -4, 14, 8);
        ctx.restore();
      }
    }

    // Title + legend strip
    ctx.fillStyle = "rgba(10,14,18,0.72)";
    ctx.fillRect(0, 0, c.width, 44);
    ctx.fillStyle = "#e7eef5";
    ctx.font = "12px system-ui,sans-serif";
    ctx.fillText(
      `${title} · centreline R=${Number(profile.radius_m).toFixed(1)} m · max steer ${
        profile.max_steer_deg?.toFixed?.(1) ?? "—"
      }°` + (profile.saturated ? " · SATURATED" : ""),
      12,
      16
    );
    ctx.font = "11px system-ui,sans-serif";
    ctx.fillStyle = "#3d9cf0";
    ctx.fillText(
      `inscribed ${rIn != null ? Number(rIn).toFixed(2) : "—"} m`,
      12,
      34
    );
    ctx.fillStyle = "#f07178";
    ctx.fillText(
      `exscribed ${rOut != null ? Number(rOut).toFixed(2) : "—"} m`,
      150,
      34
    );
    ctx.fillStyle = "#8b9aab";
    ctx.fillText("grid 1 m (major 5 m)", 300, 34);
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
        <dt>90° inscribed R</dt><dd>${Number(p90.inscribed_radius_m).toFixed(2)} m</dd>
        <dt>90° exscribed R</dt><dd>${Number(p90.exscribed_radius_m).toFixed(2)} m</dd>
        <dt>90° path R</dt><dd>${Number(p90.path_radius_m ?? p90.radius_m).toFixed(2)} m</dd>
        <dt>180° max steer</dt><dd class="${p180.saturated ? "warn" : ""}">${p180.max_steer_deg.toFixed(1)}° ${p180.saturated ? "(limit)" : ""}</dd>
        <dt>180° inscribed R</dt><dd>${Number(p180.inscribed_radius_m).toFixed(2)} m</dd>
        <dt>180° exscribed R</dt><dd>${Number(p180.exscribed_radius_m).toFixed(2)} m</dd>
        <dt>180° path R</dt><dd>${Number(p180.path_radius_m ?? p180.radius_m).toFixed(2)} m</dd>
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
