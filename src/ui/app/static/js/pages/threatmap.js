// Threatmap — the operator's own blocked traffic, replayed on a world map.
//
// Deliberately standalone rather than sharing home.js's choropleth: the home map stays a plain
// static "history" view, this one adds arcs, a ticker and polling. If a third map ever appears,
// extract the shared init then.
(function () {
  "use strict";

  var CONFIG = window.__threatmapConfig || {};
  // Derived rather than passed in: main.py's custom_url_for shim turns any endpoint that does not
  // end in "_page" into "#", so a url_for() for the data route would silently produce a dead link.
  // Reading our own path also survives the reverse-proxy prefix the UI supports.
  var DATA_URL = window.location.pathname.replace(/\/+$/, "") + "/data";
  var POLL_MS = 30000;
  var WINDOW_SECONDS = 24 * 3600;
  var TOP_N = 5;
  // This page is meant to be left running on a wall display for days, so a frozen board has to
  // announce itself: nobody watches a screen closely enough to notice numbers that stopped
  // moving. Three missed polls is late enough not to flap on one slow response.
  var STALE_AFTER_MS = POLL_MS * 3;
  // Arcs are the point of the page, but a poll can return 50 events at once: firing them all
  // together is a flash, not a threatmap. They are queued and released on a steady beat instead,
  // which is also what keeps the board moving between two polls 30 s apart.
  var MAX_ARCS = 14;
  var ARC_EMIT_MS = 650;
  var ARC_TRAVEL_MS = 2400;
  // The head keeps travelling after the trail starts fading, so the layer must outlive the trip.
  var ARC_LIFETIME_MS = ARC_TRAVEL_MS + 900;
  var IMPACT_LIFETIME_MS = 900;
  // Symbolic "your infrastructure" node. Deliberately offshore: nothing in the data carries a
  // location, and a dot sitting on a country would be read as one.
  var CENTER = [20, -24];

  var reduceMotion =
    window.matchMedia &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  var map = null;
  var geoLayer = null;
  var centroids = {}; // ISO2 -> [lat, lng]
  var counts = {}; // ISO2 -> blocked count
  var thresholds = []; // quantile cuts between the five choropleth steps
  var arcs = [];
  // Countries waiting to be launched, and the last window's worth to loop over when nothing new
  // has arrived — a threatmap that goes still every quiet minute reads as broken.
  var arcQueue = [];
  var replayPool = [];
  var seenEvents = Object.create(null);
  var firstLoad = true;
  var palette = {};
  var lastSuccess = 0;
  // Kept so expanding a panel can re-render from the data already on screen rather than waiting
  // up to 30 s for the next poll.
  var lastPayload = null;

  // ── palette ─────────────────────────────────────────────────────────────

  function cssVar(name, fallback) {
    var value = getComputedStyle(document.documentElement)
      .getPropertyValue(name)
      .trim();
    return value || fallback;
  }

  function refreshPalette() {
    palette = {
      land: cssVar("--bw-map-land", "#d9dfe4"),
      landBorder: cssVar("--bw-map-land-border", "#7c8890"),
      border: cssVar("--bw-map-border", "#ffffff"),
      steps: [
        cssVar("--bw-map-step-1", "#6a8999"),
        cssVar("--bw-map-step-2", "#3f6c88"),
        cssVar("--bw-map-step-3", "#215778"),
        cssVar("--bw-map-step-4", "#114360"),
        cssVar("--bw-map-step-5", "#0b354a"),
      ],
    };
  }

  // Band boundaries on a LOG scale, not a linear slice of the maximum.
  //
  // Attack traffic is a power law: one country routinely carries most of the volume. Against
  // `count / max` every other country collapses into the first step and the map becomes one
  // bright shape on a flat field. Quantiles fix that but bring their own failure — with few
  // distinct values the cuts collapse and the busiest country ends up sharing a band with the
  // quiet ones, which is exactly the fact the map exists to show. Log bands spread the middle
  // *and* always leave the maximum alone in the top band.
  function computeThresholds(values) {
    var max = 0;
    for (var i = 0; i < values.length; i++) {
      if (values[i] > max) max = values[i];
    }
    if (max <= 1) return [];
    var steps = palette.steps.length;
    var cuts = [];
    for (var band = 1; band < steps; band++) {
      var edge = Math.ceil(Math.pow(max, band / steps));
      if (!cuts.length || edge > cuts[cuts.length - 1]) cuts.push(edge);
    }
    return cuts;
  }

  function stepFor(count) {
    var index = 0;
    while (index < thresholds.length && count >= thresholds[index]) index++;
    return Math.min(palette.steps.length - 1, index);
  }

  function fillFor(count) {
    if (!count) return palette.land;
    return palette.steps[stepFor(count)];
  }

  function styleFor(feature) {
    var count = (feature.properties && counts[feature.properties.ISO_A2]) || 0;
    return {
      fillColor: fillFor(count),
      fillOpacity: 1,
      color: count ? palette.border : palette.landBorder,
      weight: count ? 1 : 0.5,
    };
  }

  // ── centroids, derived from the topojson we already load for the choropleth ──

  // ponytail: bounds-centre of the country's largest ring, not a true area centroid. Taking the
  // largest ring rather than the whole multipolygon is what keeps the US off the Pacific and
  // France out of the Atlantic. Good enough for an illustrative arc; if one looks wrong, bundle
  // a real Natural Earth ISO2→lat/long table instead.
  function centroidOf(geometry) {
    // 30 of the 255 features in the bundled countries.topojson carry a null geometry — small
    // island territories (Aruba, Bermuda, Maldives, Seychelles, Vatican, Antarctica…). They draw
    // no polygon and get no centroid, so a block from one appears in the top-origins list but
    // traces no arc. Dereferencing them instead took down the whole map, layer included.
    if (!geometry) return null;
    var rings =
      geometry.type === "Polygon"
        ? [geometry.coordinates[0]]
        : geometry.type === "MultiPolygon"
          ? geometry.coordinates.map(function (polygon) {
              return polygon[0];
            })
          : [];
    var best = null;
    var bestArea = -1;
    for (var i = 0; i < rings.length; i++) {
      var ring = rings[i];
      if (!ring || ring.length < 3) continue;
      var minX = Infinity,
        maxX = -Infinity,
        minY = Infinity,
        maxY = -Infinity;
      for (var j = 0; j < ring.length; j++) {
        var x = ring[j][0];
        var y = ring[j][1];
        if (x < minX) minX = x;
        if (x > maxX) maxX = x;
        if (y < minY) minY = y;
        if (y > maxY) maxY = y;
      }
      var area = (maxX - minX) * (maxY - minY);
      if (area > bestArea) {
        bestArea = area;
        best = [(minY + maxY) / 2, (minX + maxX) / 2];
      }
    }
    return best;
  }

  // ── arcs ────────────────────────────────────────────────────────────────

  // Quadratic bezier in lat/lng space, sampled into a polyline so Leaflet reprojects it on pan
  // and zoom for free. The control point is pushed perpendicular to the chord, scaled by its
  // length, so a short hop stays flat and a long one bows.
  function arcPoints(from, to) {
    var dLat = to[0] - from[0];
    var dLng = to[1] - from[1];
    var distance = Math.sqrt(dLat * dLat + dLng * dLng);
    var control = [
      (from[0] + to[0]) / 2 - dLng * 0.22,
      (from[1] + to[1]) / 2 + dLat * 0.22,
    ];
    var steps = Math.max(12, Math.min(48, Math.round(distance)));
    var points = [];
    for (var i = 0; i <= steps; i++) {
      var t = i / steps;
      var inv = 1 - t;
      points.push([
        inv * inv * from[0] + 2 * inv * t * control[0] + t * t * to[0],
        inv * inv * from[1] + 2 * inv * t * control[1] + t * t * to[1],
      ]);
    }
    return points;
  }

  function spawnArc(iso) {
    if (reduceMotion || !map) return;
    var origin = centroids[iso];
    // 30 countries in the bundled topojson have no geometry, so they have no centroid and get
    // no arc. They still show up in the top-origins list.
    if (!origin) return;
    while (arcs.length >= MAX_ARCS) {
      removeArc(arcs[0]);
    }

    var points = arcPoints(origin, CENTER);
    // Two layers, because one cannot both persist and travel: the trail is the whole route,
    // faint, fading out; the head is a short dash running along that same route.
    var trail = L.polyline(points, {
      className: "threatmap-arc-trail",
      interactive: false,
    });
    var head = L.polyline(points, {
      className: "threatmap-arc-head",
      interactive: false,
    });
    var group = L.layerGroup([
      trail,
      head,
      L.circleMarker(origin, {
        className: "threatmap-origin",
        radius: 3,
        interactive: false,
      }),
    ]).addTo(map);

    // Normalise the path to a unit length so the CSS dash animation takes the same time on a
    // 12000 km arc as on a 300 km one. Without it the dash values are in raw user units and the
    // long shots crawl while the short ones snap. Leaflet exposes no public getter for the SVG
    // element, hence _path — guarded, since the canvas renderer has none.
    if (head._path && head._path.setAttribute) {
      head._path.setAttribute("pathLength", "1");
    }

    arcs.push(group);
    // The ripple fires when the head lands, not when the arc launches — otherwise the impact
    // reads as coming before the attack.
    var impactTimer = setTimeout(function () {
      impact();
    }, ARC_TRAVEL_MS);
    group._bwTimers = [
      impactTimer,
      setTimeout(function () {
        removeArc(group);
      }, ARC_LIFETIME_MS),
    ];
  }

  function impact() {
    if (!map) return;
    var ripple = L.circleMarker(CENTER, {
      className: "threatmap-impact",
      radius: 4,
      interactive: false,
    }).addTo(map);
    setTimeout(function () {
      if (map) map.removeLayer(ripple);
    }, IMPACT_LIFETIME_MS);
  }

  function removeArc(arc) {
    var index = arcs.indexOf(arc);
    if (index === -1) return;
    arcs.splice(index, 1);
    // Clearing the timers matters on a page that runs for days: an arc evicted early by MAX_ARCS
    // would otherwise still fire its impact against a layer that is already gone.
    (arc._bwTimers || []).forEach(clearTimeout);
    if (map) map.removeLayer(arc);
  }

  // One arc at a time, on a steady beat. Fresh events jump the queue; when they run out the last
  // window is replayed so the map keeps breathing through a quiet spell.
  function emitArc() {
    if (document.visibilityState !== "visible") return;
    if (!arcQueue.length) {
      if (!replayPool.length) return;
      arcQueue = replayPool.slice();
    }
    spawnArc(arcQueue.shift());
  }

  // ── rendering ───────────────────────────────────────────────────────────

  function setText(id, value) {
    var node = document.getElementById(id);
    if (!node) return;
    var target = node.querySelector(".bw-kpi-value") || node;
    target.textContent = value;
    // A server_name or a reason can be 256 characters. The tile ellipsises them (see the page
    // CSS), so the full value has to stay reachable somewhere.
    target.setAttribute("title", value);
  }

  // A choropleth with no key is decoration: you can see that one country is darker, and nothing
  // else. The five swatches carry the actual counts each band stands for.
  function renderLegend() {
    var legend = document.getElementById("threatmap-legend");
    if (!legend) return;
    legend.textContent = "";
    if (!Object.keys(counts).length) return;

    var bounds = [1].concat(thresholds);
    palette.steps.forEach(function (colour, index) {
      if (index >= bounds.length) return;
      var item = document.createElement("span");
      item.className = "threatmap-legend__item";

      var swatch = document.createElement("span");
      swatch.className = "threatmap-legend__swatch";
      swatch.style.background = colour;

      var label = document.createElement("span");
      var lower = bounds[index];
      var upper = index + 1 < bounds.length ? bounds[index + 1] - 1 : null;
      label.textContent =
        upper === null || upper <= lower
          ? lower.toLocaleString() + "+"
          : lower.toLocaleString() + "–" + upper.toLocaleString();

      item.appendChild(swatch);
      item.appendChild(label);
      legend.appendChild(item);
    });
  }

  // The tooltip is the one place this page builds markup from a string, and ADMIN comes out of a
  // bundled file rather than from the DB — escaped anyway, so the rule "nothing reaches innerHTML
  // unescaped" holds without exception.
  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function isNA(code) {
    return window.BWCountryFlag
      ? window.BWCountryFlag.isNA(code)
      : !/^[A-Za-z]{2}$/.test(String(code || ""));
  }

  function countryCell(code) {
    var span = document.createElement("span");
    if (window.BWCountryFlag) {
      span.innerHTML = window.BWCountryFlag.html(code, {
        tooltip: false,
        flagBase: CONFIG.flagBase,
      });
    } else {
      span.textContent = isNA(code) ? "N/A" : String(code).toUpperCase();
    }
    return span;
  }

  // Which panels the operator has expanded. Kept outside render() so a poll every 30 s does not
  // silently collapse a list someone is reading.
  var expanded = Object.create(null);

  // Only the three panels. Expanding one must not run the full render(), which would stamp
  // lastSuccess and clear a stale warning on what is nothing more than a click.
  function renderTops(payload) {
    var distinct = payload.distinct || {};
    renderTop(
      "threatmap-top-country",
      payload.by_country || [],
      true,
      distinct.country,
    );
    renderTop(
      "threatmap-top-server",
      payload.by_server || [],
      false,
      distinct.server,
    );
    renderTop(
      "threatmap-top-reason",
      payload.by_reason || [],
      false,
      distinct.reason,
    );
  }

  function renderTop(elementId, facets, withFlag, distinct) {
    var list = document.getElementById(elementId);
    if (!list) return;
    list.textContent = "";
    if (!facets.length) {
      emptyRow(list);
      return;
    }

    var open = !!expanded[elementId];
    list.classList.toggle("threatmap-top--expanded", open);
    var shown = open ? facets : facets.slice(0, TOP_N);
    shown.forEach(function (facet) {
      var item = document.createElement("li");
      item.className = "threatmap-top__row";
      var label = document.createElement("span");
      label.className = "threatmap-top__label";
      if (withFlag) {
        label.appendChild(countryCell(facet.name));
        if (isNA(facet.name)) {
          // The sentinels (local / unknown / "") never join a map polygon. Naming the bucket
          // keeps the counter and the map honest instead of quietly losing the difference.
          var hint = document.createElement("small");
          hint.className = "text-muted ms-1";
          hint.setAttribute("data-i18n", "threatmap.not_localised");
          hint.textContent = t("threatmap.not_localised", "not localised");
          label.appendChild(hint);
        }
      } else {
        // Service names and block reasons are operator- and WAF-supplied strings; never innerHTML.
        label.textContent = facet.name || "—";
      }
      var value = document.createElement("span");
      value.className = "threatmap-top__count";
      value.textContent = facet.count.toLocaleString();
      item.appendChild(label);
      item.appendChild(value);
      list.appendChild(item);
    });

    if (facets.length > TOP_N)
      appendToggle(list, elementId, facets.length, distinct);
  }

  // "Top 5" with nothing saying so is a half-truth. The toggle names the real total, and when the
  // payload itself was capped it says that too rather than presenting 25 of 5 000 as the whole set.
  function appendToggle(list, elementId, fetched, distinct) {
    var open = !!expanded[elementId];
    var row = document.createElement("li");
    row.className = "threatmap-top__more";

    var button = document.createElement("button");
    button.type = "button";
    button.className = "btn btn-link btn-sm p-0 text-decoration-none";
    button.setAttribute("aria-expanded", open ? "true" : "false");
    button.setAttribute(
      "data-i18n",
      open ? "threatmap.show_less" : "threatmap.show_more",
    );
    var fallback = open ? "Show top " + TOP_N : "Show all " + fetched;
    button.textContent =
      window.i18next && window.i18next.t
        ? window.i18next.t(button.getAttribute("data-i18n"), {
            count: open ? TOP_N : fetched,
          })
        : fallback;
    button.addEventListener("click", function () {
      expanded[elementId] = !expanded[elementId];
      if (lastPayload) renderTops(lastPayload);
      // renderTops replaces this button with a new node, which drops focus to <body> — a
      // keyboard user would land back at the top of the document after every toggle.
      var replacement = document.querySelector(
        "#" + elementId + " .threatmap-top__more button",
      );
      if (replacement) replacement.focus();
    });
    row.appendChild(button);

    // Shown collapsed as well as expanded: "Show all 25" is not true when the payload itself was
    // capped at 25 of 30, and the operator has to know that before they read the list, not after.
    if (distinct && distinct > fetched) {
      var note = document.createElement("small");
      note.className = "text-muted ms-2";
      note.setAttribute("data-i18n", "threatmap.more_hidden");
      note.textContent =
        distinct - fetched + " " + t("threatmap.more_hidden", "more not shown");
      row.appendChild(note);
    }

    list.appendChild(row);
  }

  function emptyRow(list) {
    var none = document.createElement("li");
    none.className = "text-muted small";
    none.setAttribute("data-i18n", "status.no_data");
    none.textContent = t("status.no_data", "No data");
    list.appendChild(none);
  }

  function renderTicker(events) {
    var list = document.getElementById("threatmap-ticker");
    if (!list) return;
    list.textContent = "";
    if (!events.length) {
      emptyRow(list);
      return;
    }
    events.slice(0, CONFIG.recentLimit || 50).forEach(function (event) {
      var item = document.createElement("li");
      item.className = "threatmap-ticker__row";

      var time = document.createElement("span");
      time.className = "threatmap-ticker__time";
      time.textContent = new Date(
        (event.date || 0) * 1000,
      ).toLocaleTimeString();

      var country = countryCell(event.country);
      country.className = "threatmap-ticker__country";

      var ip = document.createElement("code");
      ip.className = "threatmap-ticker__ip";
      ip.textContent = event.ip || "—";

      var reason = document.createElement("span");
      reason.className = "threatmap-ticker__reason badge bg-label-danger";
      reason.textContent = event.reason || "—";

      var target = document.createElement("span");
      target.className = "threatmap-ticker__target text-muted";
      target.textContent = event.server_name || "—";

      [time, country, ip, reason, target].forEach(function (node) {
        item.appendChild(node);
      });
      list.appendChild(item);
    });
  }

  function show(id, visible) {
    var node = document.getElementById(id);
    if (node) node.classList.toggle("d-none", !visible);
  }

  function render(payload) {
    lastPayload = payload;
    var byCountry = payload.by_country || [];
    var byServer = payload.by_server || [];
    var byReason = payload.by_reason || [];
    var recent = payload.recent || [];

    counts = {};
    var painted = [];
    byCountry.forEach(function (facet) {
      if (isNA(facet.name)) return; // no polygon to paint — surfaced in the top-origins list
      counts[String(facet.name).toUpperCase()] = facet.count;
      painted.push(facet.count);
    });
    thresholds = computeThresholds(painted);
    renderLegend();

    setText("threatmap-tile-count", (payload.count || 0).toLocaleString());
    setText("threatmap-tile-countries", String(Object.keys(counts).length));
    setText("threatmap-tile-target", byServer.length ? byServer[0].name : "—");
    setText("threatmap-tile-reason", byReason.length ? byReason[0].name : "—");

    renderTops(payload);
    renderTicker(recent);

    if (geoLayer) geoLayer.setStyle(styleFor);

    // Everything with a country becomes replay material, so a board opened mid-shift starts
    // animating immediately instead of waiting up to 30 s for the next blocked request.
    replayPool = recent
      .filter(function (event) {
        return !isNA(event.country);
      })
      .map(function (event) {
        return String(event.country).toUpperCase();
      });

    // New events since the last poll jump ahead of the replay: what is actually happening should
    // be what you see, with the loop only filling the silence.
    var fresh = [];
    recent.forEach(function (event) {
      var key = event.request_id || event.id;
      if (!key || seenEvents[key]) return;
      seenEvents[key] = true;
      if (!firstLoad && !isNA(event.country)) {
        fresh.push(String(event.country).toUpperCase());
      }
    });
    if (fresh.length) arcQueue = fresh.concat(arcQueue);
    firstLoad = false;

    // The set only ever needs to answer "did I already draw this?" for the events still inside
    // the window; the API returns at most `recentLimit`, so anything older can never come back.
    var keys = Object.keys(seenEvents);
    if (keys.length > 500) {
      var fresh = Object.create(null);
      recent.forEach(function (event) {
        var key = event.request_id || event.id;
        if (key) fresh[key] = true;
      });
      seenEvents = fresh;
    }

    show("threatmap-empty", !payload.count);
    show("threatmap-error", false);
    lastSuccess = Date.now();
    paintFreshness();
  }

  // ── freshness ───────────────────────────────────────────────────────────

  // The one thing a wall display cannot do without: a heartbeat that says the numbers on screen
  // are current. Without it a board that lost its API looks exactly like a quiet night.
  function paintFreshness() {
    var node = document.getElementById("threatmap-updated");
    if (!node) return;
    var stale = lastSuccess && Date.now() - lastSuccess > STALE_AFTER_MS;
    node.classList.toggle("threatmap-updated--stale", !!stale);
    var time = document.getElementById("threatmap-updated-time");
    if (time && lastSuccess)
      time.textContent = new Date(lastSuccess).toLocaleTimeString();
    show("threatmap-stale", !!stale);
  }

  // ── data ────────────────────────────────────────────────────────────────

  // A reload wipes every in-page guard, so the rate limit has to outlive the document. Without
  // it, a login page that itself bounces back here would spin an unattended screen forever.
  function reloadOnce() {
    var key = "bwThreatmapReloadedAt";
    var last = 0;
    try {
      last = parseInt(sessionStorage.getItem(key) || "0", 10) || 0;
      if (Date.now() - last < 60000) return;
      sessionStorage.setItem(key, String(Date.now()));
    } catch (e) {
      /* private mode / storage disabled — fall through and reload at most this once */
    }
    window.location.reload();
  }

  function fetchData() {
    var end = Math.floor(Date.now() / 1000);
    var start = end - WINDOW_SECONDS;
    var url =
      DATA_URL +
      "?start=" +
      start +
      "&end=" +
      end +
      "&limit=" +
      (CONFIG.recentLimit || 50);
    return fetch(url, {
      headers: { "X-Requested-With": "XMLHttpRequest" },
      credentials: "same-origin",
    })
      .then(function (response) {
        // A UI session does expire (SESSION_LIFETIME_HOURS, 12 by default). Flask-Login answers
        // an expired one with a *redirect to the login page*, so the fetch succeeds with 200 and
        // HTML — left alone, a display parked overnight would sit on a stuck error panel forever.
        // Reloading puts a login screen on the wall instead, which is at least actionable.
        //
        // Only a redirect or a 401 counts. "Not JSON" deliberately does not: a proxy 502 in front
        // of the UI is also not JSON, and reloading on that would put an unattended screen into a
        // permanent reload loop against a service that is already down.
        if (response.redirected || response.status === 401) {
          reloadOnce();
          throw new Error("session expired");
        }
        if (!response.ok) throw new Error("HTTP " + response.status);
        return response.json();
      })
      .then(render)
      .catch(function () {
        // Keep whatever is on screen: a transient API blip should not blank a wall display.
        // The freshness stamp is what tells a viewer the figures stopped being current.
        show("threatmap-error", true);
        paintFreshness();
      });
  }

  function poll() {
    setInterval(function () {
      // reports.js's auto-refresh keeps firing on a hidden tab; an animated map must not. A wall
      // display is always visible, so this only ever costs a backgrounded browser.
      if (document.visibilityState === "visible") fetchData();
    }, POLL_MS);
    // Independent of the fetch: a board whose polls are failing must still age its own stamp.
    setInterval(paintFreshness, 5000);
    // The arc beat runs on its own clock, not the poll's — 50 events arriving at once should
    // spread across the next half-minute rather than flash and vanish.
    if (!reduceMotion) setInterval(emitArc, ARC_EMIT_MS);
    document.addEventListener("visibilitychange", function () {
      if (document.visibilityState === "visible") fetchData();
    });
  }

  // ── fullscreen ──────────────────────────────────────────────────────────

  function initFullscreen() {
    var button = document.getElementById("threatmap-fullscreen");
    var board = document.getElementById("threatmap-board");
    if (!button || !board) return;
    // `requestFullscreen` exists as a function even when Permissions-Policy forbids the feature,
    // so testing for it shows a button whose every click is rejected. `document.fullscreenEnabled`
    // is the property that actually reflects the policy — hide the control rather than lie about
    // it. (Deployments that re-tighten the header get a page with no dead button; F11 still works,
    // browser chrome fullscreen is not governed by Permissions-Policy.)
    if (!document.fullscreenEnabled || !board.requestFullscreen) {
      button.classList.add("d-none");
      return;
    }

    var label = button.querySelector("[data-i18n]");
    button.addEventListener("click", function () {
      if (document.fullscreenElement) {
        document.exitFullscreen();
      } else {
        board.requestFullscreen().catch(function () {
          // Rejected despite the policy allowing it (an odd kiosk shell, a denied gesture) —
          // stop advertising a control that does not work here.
          button.classList.add("d-none");
        });
      }
    });

    document.addEventListener("fullscreenchange", function () {
      var on = !!document.fullscreenElement;
      if (label) {
        label.setAttribute(
          "data-i18n",
          on ? "threatmap.exit_fullscreen" : "threatmap.fullscreen",
        );
        label.textContent = on ? "Exit fullscreen" : "Fullscreen";
        if (window.i18next && window.i18next.t) {
          label.textContent = window.i18next.t(label.getAttribute("data-i18n"));
        }
      }
      // Leaflet caches the container size; without this the map keeps its windowed dimensions
      // and renders into a corner of the screen.
      if (map) map.invalidateSize();
    });
  }

  // A monitor left on this page will blank on the OS idle timer, which is the one failure mode a
  // wall display cannot recover from by itself. The lock is dropped by the browser whenever the
  // page is hidden, so it has to be re-taken on the way back.
  function initWakeLock() {
    if (!navigator.wakeLock) return;
    var sentinel = null;
    var acquire = function () {
      if (document.visibilityState !== "visible" || sentinel) return;
      navigator.wakeLock
        .request("screen")
        .then(function (lock) {
          sentinel = lock;
          lock.addEventListener("release", function () {
            sentinel = null;
          });
        })
        .catch(function () {
          /* policy, battery saver or an unsupported surface — the page works regardless */
        });
    };
    acquire();
    document.addEventListener("visibilitychange", acquire);
  }

  // ── boot ────────────────────────────────────────────────────────────────

  function initMap() {
    map = L.map("threatmap-map", {
      minZoom: 2,
      maxZoom: 4,
      center: [30, 10],
      zoom: 2,
      worldCopyJump: false,
      zoomControl: true,
      attributionControl: false,
      maxBounds: [
        [-85, -180],
        [85, 180],
      ],
      maxBoundsViscosity: 1.0,
    });

    L.circleMarker(CENTER, {
      className: "threatmap-core",
      radius: 6,
      interactive: false,
    }).addTo(map);

    return fetch(CONFIG.topojsonUrl, { credentials: "same-origin" })
      .then(function (response) {
        return response.json();
      })
      .then(function (topo) {
        var geojson = topojson.feature(topo, topo.objects.countries);
        geojson.features.forEach(function (feature) {
          var iso = feature.properties && feature.properties.ISO_A2;
          var centroid = centroidOf(feature.geometry);
          // ISO_A2 is "-" for a handful of disputed/unassigned entries; those join nothing.
          if (iso && iso !== "-" && centroid) centroids[iso] = centroid;
        });
        // Interactive so a country outside the top-five list is still readable: the panels only
        // show five, and the legend gives bands rather than a figure.
        geoLayer = L.geoJson(geojson, {
          style: styleFor,
          onEachFeature: function (feature, layer) {
            var iso = feature.properties && feature.properties.ISO_A2;
            if (!iso || iso === "-") return;
            layer.bindTooltip(
              function () {
                var name = feature.properties.ADMIN || iso;
                var hits = counts[iso] || 0;
                return (
                  "<strong>" +
                  escapeHtml(name) +
                  "</strong><br>" +
                  hits.toLocaleString() +
                  " " +
                  (hits === 1
                    ? t("threatmap.blocked_request", "blocked request")
                    : t("threatmap.blocked_requests", "blocked requests"))
                );
              },
              {
                sticky: true,
                className: "threatmap-tooltip",
                direction: "top",
              },
            );
          },
        }).addTo(map);
      });
  }

  document.addEventListener("DOMContentLoaded", function () {
    if (!document.getElementById("threatmap-map")) return;
    refreshPalette();
    new MutationObserver(function () {
      refreshPalette();
      if (geoLayer) geoLayer.setStyle(styleFor);
    }).observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["data-bs-theme", "class"],
    });

    initFullscreen();
    initWakeLock();
    initMap()
      .then(fetchData)
      .then(poll)
      .catch(function () {
        show("threatmap-error", true);
      });
  });
})();
