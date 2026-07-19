/**
 * Drag-and-drop vehicle configuration editor (plan view).
 * Vehicle frame: x = forward (m), y = left (m). Canvas y is flipped.
 */
(function () {
  const state = {
    vehicle: null, // editor JSON
    drag: null, // { type, index, startWorld, orig }
    view: null,
  };

  function defaultRigid() {
    return {
      name: "Custom rigid",
      version: "1.0",
      body: {
        width: 2.5,
        front_overhang: 1.2,
        rear_overhang: 2.0,
      },
      axles: [
        {
          index: 0,
          longitudinal_pos: 0,
          is_steering: true,
          track_width: 2.05,
          tyre_width: 0.35,
          max_steer_angle_deg: 42,
        },
        {
          index: 1,
          longitudinal_pos: -4.2,
          is_steering: false,
          track_width: 2.05,
          tyre_width: 0.35,
        },
      ],
      articulation_positions_m: [],
    };
  }

  function canvas() {
    return document.getElementById("ed-canvas");
  }

  function body() {
    return state.vehicle.body || state.vehicle;
  }

  function setStatus(msg, ok) {
    const el = document.getElementById("ed-status");
    if (!el) return;
    el.className = "status " + (ok === true ? "ok" : ok === false ? "error" : "");
    el.textContent = msg || "";
  }

  function syncFormFromState() {
    if (!state.vehicle) return;
    const b = body();
    document.getElementById("ed-name").value = state.vehicle.name || "";
    document.getElementById("ed-width").value = b.width ?? 2.5;
    document.getElementById("ed-front").value = b.front_overhang ?? 1.2;
    document.getElementById("ed-rear").value = b.rear_overhang ?? 2.0;
    const steer = (state.vehicle.axles || []).find((a) => a.is_steering);
    document.getElementById("ed-maxsteer").value =
      (steer && steer.max_steer_angle_deg) || 42;
    const arts = state.vehicle.articulation_positions_m || [];
    document.getElementById("ed-artic-on").checked = arts.length > 0;
    document.getElementById("ed-artic").value =
      arts.length ? arts[0] : -3.8;
    renderAxleList();
  }

  function readFormIntoState() {
    if (!state.vehicle) state.vehicle = defaultRigid();
    if (!state.vehicle.body) state.vehicle.body = {};
    state.vehicle.name = document.getElementById("ed-name").value || "Custom";
    state.vehicle.body.width = +document.getElementById("ed-width").value || 2.5;
    state.vehicle.body.front_overhang =
      +document.getElementById("ed-front").value || 0;
    state.vehicle.body.rear_overhang =
      +document.getElementById("ed-rear").value || 0;
    const maxSteer = +document.getElementById("ed-maxsteer").value || 42;
    for (const a of state.vehicle.axles || []) {
      if (a.is_steering) a.max_steer_angle_deg = maxSteer;
    }
    if (document.getElementById("ed-artic-on").checked) {
      const p = +document.getElementById("ed-artic").value;
      state.vehicle.articulation_positions_m = [isFinite(p) ? p : -3.8];
      // Simple tractor/trailer bodies when articulated
      const art = state.vehicle.articulation_positions_m[0];
      const w = state.vehicle.body.width;
      const front = state.vehicle.body.front_overhang;
      const rear = state.vehicle.body.rear_overhang;
      const rearmost = Math.min(
        ...state.vehicle.axles.map((a) => a.longitudinal_pos),
        art - rear
      );
      state.vehicle.front_body = {
        width: w,
        front_longitudinal: front,
        rear_longitudinal: art,
      };
      state.vehicle.rear_body = {
        width: w,
        front_longitudinal: art,
        rear_longitudinal: rearmost - 0.5,
      };
    } else {
      state.vehicle.articulation_positions_m = [];
      delete state.vehicle.front_body;
      delete state.vehicle.rear_body;
      delete state.vehicle.body_segments;
    }
  }

  function renderAxleList() {
    const list = document.getElementById("ed-axle-list");
    if (!list || !state.vehicle) return;
    list.innerHTML = "";
    (state.vehicle.axles || []).forEach((a, i) => {
      const row = document.createElement("div");
      row.className = "axle-row";
      row.innerHTML = `
        <span>${a.is_steering ? '<span class="tag-steer">STEER</span> ' : ""}x=
          <input type="number" step="0.05" data-i="${i}" data-f="pos" value="${a.longitudinal_pos.toFixed(2)}" ${a.is_steering && a.longitudinal_pos === 0 ? "title='Primary steer at 0'" : ""} />
        </span>
        <span>track
          <input type="number" step="0.05" data-i="${i}" data-f="track" value="${a.track_width}" />
        </span>
        <button type="button" class="x" data-del="${i}" title="Remove">×</button>
      `;
      list.appendChild(row);
    });
    list.querySelectorAll("input").forEach((inp) => {
      inp.addEventListener("change", () => {
        const i = +inp.dataset.i;
        const f = inp.dataset.f;
        const a = state.vehicle.axles[i];
        if (!a) return;
        if (f === "pos") {
          let v = +inp.value;
          if (a.is_steering && Math.abs(state.vehicle.axles[0]?.longitudinal_pos) < 1e-9 && i === 0) {
            // keep primary at 0 if first steer
          }
          a.longitudinal_pos = v;
        }
        if (f === "track") a.track_width = Math.max(0.5, +inp.value);
        draw();
      });
    });
    list.querySelectorAll("button[data-del]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const i = +btn.dataset.del;
        if (state.vehicle.axles.length <= 1) return;
        state.vehicle.axles.splice(i, 1);
        state.vehicle.axles.forEach((a, j) => (a.index = j));
        renderAxleList();
        draw();
      });
    });
  }

  function bodyExtents() {
    const b = body();
    const front = b.front_overhang ?? 1.2;
    const rear = b.rear_overhang ?? 2.0;
    // If articulated with longitudinal bodies, use those for outline
    if (state.vehicle.front_body && state.vehicle.rear_body) {
      const fl = state.vehicle.front_body.front_longitudinal ?? front;
      const rr = state.vehicle.rear_body.rear_longitudinal ?? -rear;
      return { xFront: fl, xRear: rr, width: b.width || 2.5 };
    }
    return { xFront: front, xRear: -rear, width: b.width || 2.5 };
  }

  function collectPoints() {
    const pts = [];
    const e = bodyExtents();
    const w2 = e.width / 2;
    pts.push([e.xRear, -w2], [e.xFront, -w2], [e.xFront, w2], [e.xRear, w2]);
    for (const a of state.vehicle.axles || []) {
      pts.push([a.longitudinal_pos, a.track_width / 2]);
      pts.push([a.longitudinal_pos, -a.track_width / 2]);
    }
    for (const art of state.vehicle.articulation_positions_m || []) {
      pts.push([art, 0]);
    }
    return pts;
  }

  function hitTest(worldX, worldY) {
    if (!state.view || !state.vehicle) return null;
    const thr = 12 / state.view.scale; // ~12 px
    const e = bodyExtents();
    const w2 = e.width / 2;

    // Axles (priority)
    for (let i = 0; i < state.vehicle.axles.length; i++) {
      const a = state.vehicle.axles[i];
      const dx = worldX - a.longitudinal_pos;
      const dy = worldY; // centreline
      if (Math.abs(dx) < thr && Math.abs(dy) < Math.max(thr, a.track_width / 2 + thr)) {
        // Prefer centre of axle bar
        if (Math.hypot(dx, dy) < thr * 1.5 || Math.abs(dx) < thr * 0.8) {
          return { type: "axle", index: i };
        }
      }
    }

    // Articulation
    for (let i = 0; i < (state.vehicle.articulation_positions_m || []).length; i++) {
      const ax = state.vehicle.articulation_positions_m[i];
      if (Math.hypot(worldX - ax, worldY) < thr * 1.2) {
        return { type: "artic", index: i };
      }
    }

    // Width handles (mid-sides of body)
    const midX = (e.xFront + e.xRear) / 2;
    if (Math.hypot(worldX - midX, worldY - w2) < thr) return { type: "width", sign: 1 };
    if (Math.hypot(worldX - midX, worldY + w2) < thr) return { type: "width", sign: -1 };

    // Front / rear overhang handles
    if (Math.hypot(worldX - e.xFront, worldY) < thr) return { type: "front" };
    if (Math.hypot(worldX - e.xRear, worldY) < thr) return { type: "rear" };

    return null;
  }

  function draw() {
    const c = canvas();
    if (!c || !state.vehicle) return;
    const ctx = c.getContext("2d");
    const w = c.width;
    const h = c.height;
    const pts = collectPoints();
    // padding in metres via fit
    state.view = window.GeoCanvas.fit(pts, w, h, 40);
    const view = state.view;

    ctx.fillStyle = "#0a0e12";
    ctx.fillRect(0, 0, w, h);

    // Grid
    ctx.strokeStyle = "rgba(255,255,255,0.04)";
    ctx.lineWidth = 1;
    const step = 1; // 1 m
    for (let x = Math.floor(view.minX) - 1; x <= view.maxX + 1; x += step) {
      const [sx0, sy0] = view.toScreen(x, view.minY);
      const [sx1, sy1] = view.toScreen(x, view.maxY);
      ctx.beginPath();
      ctx.moveTo(sx0, sy0);
      ctx.lineTo(sx1, sy1);
      ctx.stroke();
    }
    for (let y = Math.floor(view.minY) - 1; y <= view.maxY + 1; y += step) {
      const [sx0, sy0] = view.toScreen(view.minX, y);
      const [sx1, sy1] = view.toScreen(view.maxX, y);
      ctx.beginPath();
      ctx.moveTo(sx0, sy0);
      ctx.lineTo(sx1, sy1);
      ctx.stroke();
    }

    // Centreline
    {
      const e = bodyExtents();
      const [x0, y0] = view.toScreen(e.xRear - 1, 0);
      const [x1, y1] = view.toScreen(e.xFront + 1, 0);
      ctx.strokeStyle = "rgba(62, 207, 142, 0.35)";
      ctx.setLineDash([6, 4]);
      ctx.beginPath();
      ctx.moveTo(x0, y0);
      ctx.lineTo(x1, y1);
      ctx.stroke();
      ctx.setLineDash([]);
    }

    // Body
    const e = bodyExtents();
    const w2 = e.width / 2;
    const corners = [
      [e.xRear, -w2],
      [e.xFront, -w2],
      [e.xFront, w2],
      [e.xRear, w2],
    ];
    ctx.beginPath();
    corners.forEach((p, i) => {
      const [sx, sy] = view.toScreen(p[0], p[1]);
      if (i === 0) ctx.moveTo(sx, sy);
      else ctx.lineTo(sx, sy);
    });
    ctx.closePath();
    ctx.fillStyle = "rgba(61, 156, 240, 0.18)";
    ctx.fill();
    ctx.strokeStyle = "#3d9cf0";
    ctx.lineWidth = 2;
    ctx.stroke();

    // Cab hint (front third tint)
    if (!state.vehicle.articulation_positions_m?.length) {
      const cabRear = e.xFront - Math.min(2.2, (e.xFront - e.xRear) * 0.35);
      const cab = [
        [cabRear, -w2],
        [e.xFront, -w2],
        [e.xFront, w2],
        [cabRear, w2],
      ];
      ctx.beginPath();
      cab.forEach((p, i) => {
        const [sx, sy] = view.toScreen(p[0], p[1]);
        if (i === 0) ctx.moveTo(sx, sy);
        else ctx.lineTo(sx, sy);
      });
      ctx.closePath();
      ctx.fillStyle = "rgba(124, 92, 255, 0.15)";
      ctx.fill();
    }

    // Axles
    for (const a of state.vehicle.axles) {
      const [cx, cy] = view.toScreen(a.longitudinal_pos, 0);
      const [lx, ly] = view.toScreen(a.longitudinal_pos, a.track_width / 2);
      const [rx, ry] = view.toScreen(a.longitudinal_pos, -a.track_width / 2);
      ctx.strokeStyle = a.is_steering ? "#3d9cf0" : "#e7eef5";
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.moveTo(lx, ly);
      ctx.lineTo(rx, ry);
      ctx.stroke();
      // Wheels
      const tyre = Math.max(0.25, a.tyre_width || 0.35);
      for (const [wx, wy] of [
        [a.longitudinal_pos, a.track_width / 2],
        [a.longitudinal_pos, -a.track_width / 2],
      ]) {
        const [sx, sy] = view.toScreen(wx, wy);
        const hw = tyre * view.scale * 0.9;
        const hh = tyre * view.scale * 0.55;
        ctx.fillStyle = a.is_steering ? "#3d9cf0" : "#8b9aab";
        ctx.fillRect(sx - hw, sy - hh, hw * 2, hh * 2);
      }
      // Drag handle
      ctx.beginPath();
      ctx.arc(cx, cy, 7, 0, Math.PI * 2);
      ctx.fillStyle = a.is_steering ? "#3d9cf0" : "#e7eef5";
      ctx.fill();
      ctx.strokeStyle = "#0a0e12";
      ctx.lineWidth = 2;
      ctx.stroke();
    }

    // Articulation diamond
    for (const art of state.vehicle.articulation_positions_m || []) {
      const [sx, sy] = view.toScreen(art, 0);
      ctx.fillStyle = "#e6b450";
      ctx.beginPath();
      ctx.moveTo(sx, sy - 9);
      ctx.lineTo(sx + 9, sy);
      ctx.lineTo(sx, sy + 9);
      ctx.lineTo(sx - 9, sy);
      ctx.closePath();
      ctx.fill();
    }

    // Handles: front, rear, width
    function handle(x, y, color) {
      const [sx, sy] = view.toScreen(x, y);
      ctx.beginPath();
      ctx.arc(sx, sy, 6, 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.fill();
      ctx.strokeStyle = "#fff";
      ctx.lineWidth = 1.5;
      ctx.stroke();
    }
    handle(e.xFront, 0, "#3ecf8e");
    handle(e.xRear, 0, "#f07178");
    handle((e.xFront + e.xRear) / 2, w2, "#7c5cff");
    handle((e.xFront + e.xRear) / 2, -w2, "#7c5cff");

    // Origin cross
    {
      const [ox, oy] = view.toScreen(0, 0);
      ctx.strokeStyle = "rgba(62,207,142,0.8)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(ox - 10, oy);
      ctx.lineTo(ox + 10, oy);
      ctx.moveTo(ox, oy - 10);
      ctx.lineTo(ox, oy + 10);
      ctx.stroke();
    }

    // Dims
    const dims = document.getElementById("ed-dims");
    if (dims) {
      const len = e.xFront - e.xRear;
      const wb =
        state.vehicle.axles.length >= 2
          ? Math.abs(
              Math.max(...state.vehicle.axles.map((a) => a.longitudinal_pos)) -
                Math.min(...state.vehicle.axles.map((a) => a.longitudinal_pos))
            )
          : 0;
      dims.textContent = `Length ≈ ${len.toFixed(2)} m · Width ${e.width.toFixed(
        2
      )} m · Wheelbase span ${wb.toFixed(2)} m · Steering origin at 0 m`;
    }
  }

  function pointerWorld(evt) {
    const c = canvas();
    const rect = c.getBoundingClientRect();
    const scaleX = c.width / rect.width;
    const scaleY = c.height / rect.height;
    const sx = (evt.clientX - rect.left) * scaleX;
    const sy = (evt.clientY - rect.top) * scaleY;
    return state.view.toWorld(sx, sy);
  }

  function onDown(evt) {
    if (!state.vehicle || !state.view) return;
    const [wx, wy] = pointerWorld(evt);
    const hit = hitTest(wx, wy);
    if (!hit) return;
    evt.preventDefault();
    state.drag = {
      ...hit,
      start: { x: wx, y: wy },
      orig: JSON.parse(JSON.stringify(state.vehicle)),
    };
    canvas().style.cursor = "grabbing";
  }

  function onMove(evt) {
    const c = canvas();
    if (!state.view) return;
    const [wx, wy] = pointerWorld(evt);
    if (!state.drag) {
      const hit = hitTest(wx, wy);
      c.style.cursor = hit ? "grab" : "crosshair";
      return;
    }
    evt.preventDefault();
    const d = state.drag;
    const b = body();
    if (d.type === "axle") {
      const a = state.vehicle.axles[d.index];
      // Keep first steering axle near 0 if it started at 0
      if (a.is_steering && Math.abs(d.orig.axles[d.index].longitudinal_pos) < 1e-6) {
        a.longitudinal_pos = 0;
      } else {
        a.longitudinal_pos = Math.round(wx * 20) / 20;
      }
      renderAxleList();
    } else if (d.type === "front") {
      b.front_overhang = Math.max(0.1, Math.round(wx * 20) / 20);
      document.getElementById("ed-front").value = b.front_overhang;
    } else if (d.type === "rear") {
      b.rear_overhang = Math.max(0.1, Math.round(-wx * 20) / 20);
      document.getElementById("ed-rear").value = b.rear_overhang;
    } else if (d.type === "width") {
      b.width = Math.max(0.8, Math.round(Math.abs(wy) * 2 * 20) / 20);
      document.getElementById("ed-width").value = b.width;
    } else if (d.type === "artic") {
      const p = Math.round(wx * 20) / 20;
      state.vehicle.articulation_positions_m[d.index] = p;
      document.getElementById("ed-artic").value = p;
      readFormIntoState();
    }
    draw();
  }

  function onUp() {
    if (state.drag) {
      state.drag = null;
      readFormIntoState();
      draw();
      setStatus("Updated — generate turn profiles to verify", true);
    }
  }

  async function loadFromLibrary(id) {
    setStatus("Loading…");
    const res = await fetch("/api/vehicles/" + encodeURIComponent(id));
    if (!res.ok) throw new Error("Load failed");
    const data = await res.json();
    state.vehicle = {
      name: data.name,
      version: data.version,
      body: data.body,
      axles: data.axles,
      articulation_positions_m: data.articulation_positions_m || [],
      front_body: data.front_body,
      rear_body: data.rear_body,
      body_segments: data.body_segments,
    };
    // Normalize overhangs from longitudinal if needed
    if (
      state.vehicle.body &&
      state.vehicle.body.front_longitudinal != null &&
      !state.vehicle.body.front_overhang
    ) {
      state.vehicle.body.front_overhang = state.vehicle.body.front_longitudinal;
    }
    if (
      state.vehicle.body &&
      state.vehicle.body.rear_longitudinal != null &&
      !state.vehicle.body.rear_overhang
    ) {
      state.vehicle.body.rear_overhang = Math.abs(state.vehicle.body.rear_longitudinal);
    }
    // For articulated AP-G34 vehicles, synthesize overhangs for drag handles
    if (state.vehicle.front_body && state.vehicle.rear_body) {
      const fl = state.vehicle.front_body.front_longitudinal ?? 1.2;
      const rr = state.vehicle.rear_body.rear_longitudinal ?? -10;
      state.vehicle.body = state.vehicle.body || {};
      state.vehicle.body.width =
        state.vehicle.front_body.width || state.vehicle.body.width || 2.5;
      state.vehicle.body.front_overhang = fl;
      state.vehicle.body.rear_overhang = Math.abs(rr);
    }
    syncFormFromState();
    draw();
    setStatus("Loaded " + state.vehicle.name, true);
  }

  function newRigid() {
    state.vehicle = defaultRigid();
    syncFormFromState();
    draw();
    setStatus("New rigid vehicle", true);
  }

  async function exportXml() {
    readFormIntoState();
    try {
      const res = await fetch("/api/vehicles/export-xml", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ vehicle: state.vehicle }),
      });
      if (!res.ok) {
        const j = await res.json().catch(() => ({}));
        throw new Error(j.detail || res.statusText);
      }
      const blob = await res.blob();
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = (state.vehicle.name || "vehicle").replace(/\s+/g, "_") + ".xml";
      a.click();
      URL.revokeObjectURL(a.href);
      setStatus("XML downloaded", true);
    } catch (e) {
      setStatus(String(e.message || e), false);
    }
  }

  function getVehicle() {
    readFormIntoState();
    return state.vehicle;
  }

  function bind() {
    const c = canvas();
    if (!c) return;
    c.addEventListener("pointerdown", onDown);
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);

    document.getElementById("ed-load")?.addEventListener("click", () => {
      const id = document.getElementById("ed-vehicle").value;
      loadFromLibrary(id).catch((e) => setStatus(String(e), false));
    });
    document.getElementById("ed-new")?.addEventListener("click", newRigid);
    document.getElementById("ed-export")?.addEventListener("click", exportXml);
    document.getElementById("ed-to-turns")?.addEventListener("click", () => {
      readFormIntoState();
      switchTab("turns");
      if (window.TurnProfiles) window.TurnProfiles.run();
    });
    document.getElementById("ed-add-axle")?.addEventListener("click", () => {
      const axles = state.vehicle.axles;
      const last = axles[axles.length - 1];
      axles.push({
        index: axles.length,
        longitudinal_pos: (last ? last.longitudinal_pos : 0) - 1.4,
        is_steering: false,
        track_width: last?.track_width || 2.05,
        tyre_width: 0.35,
      });
      renderAxleList();
      draw();
    });
    document.getElementById("ed-add-steer")?.addEventListener("click", () => {
      state.vehicle.axles.push({
        index: state.vehicle.axles.length,
        longitudinal_pos: -1.5,
        is_steering: true,
        track_width: 2.05,
        tyre_width: 0.35,
        max_steer_angle_deg: +document.getElementById("ed-maxsteer").value || 42,
      });
      renderAxleList();
      draw();
    });

    [
      "ed-name",
      "ed-width",
      "ed-front",
      "ed-rear",
      "ed-maxsteer",
      "ed-artic",
      "ed-artic-on",
    ].forEach((id) => {
      document.getElementById(id)?.addEventListener("change", () => {
        readFormIntoState();
        draw();
      });
      document.getElementById(id)?.addEventListener("input", () => {
        if (id === "ed-name") return;
        readFormIntoState();
        draw();
      });
    });
  }

  window.VehicleEditor = {
    getVehicle,
    setVehicleList() {},
    onShow() {
      if (!state.vehicle) {
        const id = document.getElementById("ed-vehicle")?.value || "semi_wb50";
        loadFromLibrary(id).catch(() => newRigid());
      } else {
        draw();
      }
    },
    loadFromLibrary,
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bind);
  } else {
    bind();
  }
})();
