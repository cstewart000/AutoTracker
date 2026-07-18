async function loadLists() {
  const [vRes, dRes] = await Promise.all([
    fetch("/api/vehicles"),
    fetch("/api/demos"),
  ]);
  const vData = await vRes.json();
  const dData = await dRes.json();
  const veh = document.getElementById("vehicle");
  veh.innerHTML = "";
  for (const v of vData.vehicles || []) {
    const opt = document.createElement("option");
    opt.value = v.id;
    opt.textContent = v.name;
    if (v.id === "ap_g34_prime_mover_semi_19m") opt.selected = true;
    veh.appendChild(opt);
  }
  const demo = document.getElementById("demo");
  for (const d of dData.demos || []) {
    const opt = document.createElement("option");
    opt.value = d.id;
    opt.textContent = d.name + (d.vertical ? " (vertical)" : "");
    if (d.id === "rectangle_20x60") opt.selected = true;
    demo.appendChild(opt);
  }
}

function drawCanvas(data) {
  const canvas = document.getElementById("canvas");
  const ctx = canvas.getContext("2d");
  const path = data.path_pts || [];
  const env = data.envelope_outer || [];
  const cw = data.carriageway_xy || [];
  const pos = data.positions_sample || [];

  const all = [...path, ...env, ...cw, ...pos.map((p) => [p[0], p[1]])];
  if (!all.length) {
    canvas.hidden = true;
    return;
  }
  canvas.hidden = false;

  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const p of all) {
    const x = p[0], y = p[1];
    if (x < minX) minX = x;
    if (y < minY) minY = y;
    if (x > maxX) maxX = x;
    if (y > maxY) maxY = y;
  }
  const pad = 24;
  const w = canvas.width, h = canvas.height;
  const dx = maxX - minX || 1;
  const dy = maxY - minY || 1;
  const scale = Math.min((w - 2 * pad) / dx, (h - 2 * pad) / dy);

  function tx(x, y) {
    const sx = pad + (x - minX) * scale;
    const sy = h - pad - (y - minY) * scale;
    return [sx, sy];
  }

  ctx.fillStyle = "#0a0e12";
  ctx.fillRect(0, 0, w, h);

  function strokePoly(pts, color, width, close) {
    if (!pts || pts.length < 2) return;
    ctx.beginPath();
    const [x0, y0] = tx(pts[0][0], pts[0][1]);
    ctx.moveTo(x0, y0);
    for (let i = 1; i < pts.length; i++) {
      const [x, y] = tx(pts[i][0], pts[i][1]);
      ctx.lineTo(x, y);
    }
    if (close) ctx.closePath();
    ctx.strokeStyle = color;
    ctx.lineWidth = width;
    ctx.stroke();
  }

  if (cw.length) {
    ctx.fillStyle = "rgba(61, 156, 240, 0.08)";
    ctx.beginPath();
    const [x0, y0] = tx(cw[0][0], cw[0][1]);
    ctx.moveTo(x0, y0);
    for (let i = 1; i < cw.length; i++) {
      const [x, y] = tx(cw[i][0], cw[i][1]);
      ctx.lineTo(x, y);
    }
    ctx.closePath();
    ctx.fill();
    strokePoly(cw, "rgba(61,156,240,0.5)", 1.5, true);
  }

  if (env.length) {
    ctx.fillStyle = "rgba(240, 113, 120, 0.18)";
    ctx.beginPath();
    const [x0, y0] = tx(env[0][0], env[0][1]);
    ctx.moveTo(x0, y0);
    for (let i = 1; i < env.length; i++) {
      const [x, y] = tx(env[i][0], env[i][1]);
      ctx.lineTo(x, y);
    }
    ctx.closePath();
    ctx.fill();
    strokePoly(env, "#f07178", 2, true);
  }

  strokePoly(path, "#3ecf8e", 2, false);

  if (pos.length) {
    strokePoly(pos.map((p) => [p[0], p[1]]), "#e7eef5", 1, false);
  }
}

function showReport(data) {
  const el = document.getElementById("report");
  const r = data.report || {};
  const pass = r.pass === true || r.pass_clearance === true;
  const badge = pass
    ? '<span class="pass">PASS</span>'
    : '<span class="fail">CHECK / FAIL</span>';
  const rows = Object.entries(r)
    .filter(([k]) => !["pass", "pass_clearance"].includes(k))
    .map(
      ([k, v]) =>
        `<dt>${k.replace(/_/g, " ")}</dt><dd>${
          typeof v === "number" ? (Number.isInteger(v) ? v : v.toFixed(3)) : v
        }</dd>`
    )
    .join("");
  el.classList.remove("empty");
  el.innerHTML = `<div>${badge} · ${data.mode || "plan"} · ${
    data.vehicle_name || ""
  }</div><dl>${rows}</dl>`;
}

function showDownloads(files) {
  const box = document.getElementById("downloads");
  const links = box.querySelector(".dl-links");
  links.innerHTML = "";
  let any = false;
  for (const [key, url] of Object.entries(files || {})) {
    if (!url) continue;
    any = true;
    const a = document.createElement("a");
    a.href = url;
    a.target = "_blank";
    a.rel = "noopener";
    a.download = "";
    a.textContent = key.replace(/_/g, " ");
    links.appendChild(a);
  }
  box.hidden = !any;
}

async function runSim() {
  const btn = document.getElementById("run");
  const status = document.getElementById("status");
  const plot = document.getElementById("plot");
  btn.disabled = true;
  status.className = "status";
  status.textContent = "Running simulation…";
  plot.hidden = true;

  const fd = new FormData();
  fd.append("vehicle", document.getElementById("vehicle").value);
  const demo = document.getElementById("demo").value;
  if (demo) fd.append("demo", demo);
  fd.append("vertical_plane", document.getElementById("vertical").checked);
  fd.append("step_size_m", document.getElementById("step").value);
  fd.append("max_steer_angle_deg", document.getElementById("steer").value);
  fd.append("design_speed_kmh", document.getElementById("speed").value);
  fd.append("stop_lock", document.getElementById("stop_lock").checked);
  fd.append("animation", document.getElementById("animation").checked);
  const file = document.getElementById("dxf").files[0];
  if (file) fd.append("dxf", file);

  try {
    const res = await fetch("/api/simulate", { method: "POST", body: fd });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || res.statusText);
    }
    status.className = "status ok";
    status.textContent = data.message || "Done.";
    showReport(data);
    showDownloads(data.files);
    if (data.files && data.files.plot) {
      plot.src = data.files.plot + "?t=" + Date.now();
      plot.hidden = false;
    }
    drawCanvas(data);
  } catch (err) {
    status.className = "status error";
    status.textContent = String(err.message || err);
  } finally {
    btn.disabled = false;
  }
}

document.getElementById("run").addEventListener("click", runSim);
loadLists().catch((e) => {
  document.getElementById("status").textContent = "Failed to load lists: " + e;
});
