const TERRAIN_LABEL = {
  g: "Grass",
  w: "Water",
  r: "Rock",
  f: "Forest",
};

function fmt(value, digits = 0) {
  return Number(value).toLocaleString(undefined, {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  });
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function rgb(color) {
  const clamp = (value) => Math.max(0, Math.min(255, Math.round(value * 255)));
  return `rgb(${clamp(color[0])}, ${clamp(color[1])}, ${clamp(color[2])})`;
}

export class Hud {
  constructor({
    catalog,
    categories,
    meta,
    onCommand,
    onSelect,
    onDemolish,
    onSave,
    onLoad,
  }) {
    this.catalog = catalog;
    this.categories = categories;
    this.meta = meta;
    this.onCommand = onCommand;
    this.onSelect = onSelect;
    this.onDemolish = onDemolish;
    this.onSave = onSave;
    this.onLoad = onLoad;

    this.state = null;
    this.selected = null;
    this.demolish = false;
    this.hover = null;
    this.buildingMap = new Map();
    this.warVisible = false;
    this.buttons = new Map();

    this.dom = {
      topbar: document.getElementById("topbar"),
      tips: document.getElementById("tip-panel"),
      build: document.getElementById("build-panel"),
      war: document.getElementById("war-panel"),
      banner: document.getElementById("banner"),
      toasts: document.getElementById("toasts"),
    };

    this._buildTopbar();
    this._buildBuildPanel();
    this._updateStatus();
  }

  _buildTopbar() {
    this.dom.topbar.innerHTML = `
      <div class="brand">
        <div class="brand-mark">C</div>
        <div class="brand-text">
          <strong>Carbon City</strong>
          <span>Energy &amp; climate</span>
        </div>
      </div>
      <div class="stats">
        <div class="stat eco">
          <div class="stat-label">Eco Points</div>
          <div class="stat-value" data-k="eco">0</div>
          <div class="stat-sub" data-k="eco-sub">+0 / tick</div>
        </div>
        <div class="stat money">
          <div class="stat-label">Money</div>
          <div class="stat-value" data-k="money">$0</div>
          <div class="stat-sub" data-k="money-sub">+0 / tick</div>
        </div>
        <div class="stat materials">
          <div class="stat-label">Materials</div>
          <div class="stat-value" data-k="materials">0</div>
          <div class="stat-sub" data-k="materials-sub">+0 / tick</div>
        </div>
        <div class="stat power">
          <div class="stat-label">Power</div>
          <div class="stat-value" data-k="power">0 kW</div>
          <div class="stat-sub" data-k="power-sub">demand 0 kW</div>
          <div class="meter"><i data-k="power-fill"></i></div>
        </div>
        <div class="stat climate">
          <div class="stat-label">Climate</div>
          <div class="stat-value" data-k="climate">+0.0 °C</div>
          <div class="stat-sub" data-k="climate-sub">420 ppm CO2</div>
          <div class="meter"><i data-k="climate-fill"></i></div>
        </div>
        <div class="stat population">
          <div class="stat-label">Population</div>
          <div class="stat-value" data-k="population">0</div>
          <div class="stat-sub" data-k="population-sub">happiness 0%</div>
        </div>
      </div>
      <div class="actions">
        <button class="btn" type="button" data-action="war">War Room</button>
        <button class="btn" type="button" data-action="save">Save</button>
        <button class="btn" type="button" data-action="load">Load</button>
        <span class="status-dot" data-k="status">Connecting</span>
      </div>
    `;

    this.refs = {};
    for (const node of this.dom.topbar.querySelectorAll("[data-k]")) {
      this.refs[node.dataset.k] = node;
    }
    this.powerStat = this.dom.topbar.querySelector(".stat.power");
    this.climateStat = this.dom.topbar.querySelector(".stat.climate");
    this.warButton = this.dom.topbar.querySelector('[data-action="war"]');

    this.warButton.addEventListener("click", () => this.toggleWar());
    this.dom.topbar
      .querySelector('[data-action="save"]')
      .addEventListener("click", () => this.onSave?.());
    this.dom.topbar
      .querySelector('[data-action="load"]')
      .addEventListener("click", () => this.onLoad?.());
  }

  _buildBuildPanel() {
    this.dom.build.innerHTML = "";

    const actions = el("div", "build-actions");
    this.expandBtn = this._actionButton("Expand Land");
    this.buyBtn = this._actionButton("Buy Materials");
    this.demolishBtn = this._actionButton("Demolish");

    this.expandBtn.addEventListener("click", () =>
      this.onCommand?.("expand", {}, "Land expanded."),
    );
    this.buyBtn.addEventListener("click", () =>
      this.onCommand?.(
        "buy_materials",
        {},
        `Bought ${fmt(this.meta.materials_buy_amount)} materials.`,
      ),
    );
    this.demolishBtn.addEventListener("click", () => this.onDemolish?.());

    this.statusEl = el("div", "build-status", "Select a building");
    actions.append(this.expandBtn, this.buyBtn, this.demolishBtn);

    const main = el("div", "build-main");
    const scroll = el("div", "build-scroll");
    const groups = el("div", "build-groups");

    for (const category of this.categories) {
      const entries = Object.entries(this.catalog).filter(
        ([, stats]) => stats.category === category.id,
      );
      if (!entries.length) continue;

      const group = el("div", "build-group");
      group.append(el("div", "group-label", category.label));
      const row = el("div", "group-buttons");

      for (const [type, stats] of entries) {
        const button = el("button", "build-btn");
        button.type = "button";
        button.title = stats.description ?? stats.name;
        const swatch = el("span", "b-swatch");
        const swatchColor = rgb(stats.color ?? [0.8, 0.8, 0.8]);
        swatch.style.background = swatchColor;
        swatch.style.boxShadow = `0 0 8px ${swatchColor}`;
        button.append(
          swatch,
          el("span", "b-name", stats.name),
          el("span", "b-cost", ""),
        );
        button.addEventListener("click", () => this.onSelect?.(type));
        row.append(button);
        this.buttons.set(type, button);
      }

      group.append(row);
      groups.append(group);
    }

    scroll.append(groups);
    main.append(scroll, this.statusEl);
    this.dom.build.append(actions, main);
  }

  _actionButton(label) {
    const button = el("button", "btn");
    button.type = "button";
    button.append(el("span", "", label), el("small", "", ""));
    return button;
  }

  setState(state) {
    this.state = state;
    this.buildingMap = new Map(
      state.buildings.map((building) => [
        `${building.x},${building.z}`,
        building,
      ]),
    );
    this._updateStats();
    this._updateBuild();
    this._renderTips();
    this._renderWar();
    this._updateBanner();
    this._updateStatus();

    const attackedRecently =
      state.last_attack &&
      state.tick - state.last_attack.tick <= 12 &&
      !state.victory;
    this.warButton.classList.toggle("alert", Boolean(attackedRecently));
  }

  setConnection(connected) {
    if (!this.refs.status) return;
    this.refs.status.textContent = connected ? "Live" : "Reconnecting…";
    this.refs.status.classList.toggle("reconnecting", !connected);
  }

  setTool(type, demolish) {
    this.selected = type;
    this.demolish = demolish;
    for (const [buttonType, button] of this.buttons) {
      button.classList.toggle("selected", buttonType === type && !demolish);
    }
    this.demolishBtn.classList.toggle("selected", demolish);
    this._updateStatus();
  }

  setHover(tile) {
    this.hover = tile;
    this._updateStatus();
  }

  toggleWar(force) {
    this.warVisible = force === undefined ? !this.warVisible : Boolean(force);
    this.dom.war.hidden = !this.warVisible;
    this.warButton.classList.toggle("selected", this.warVisible);
    document.body.classList.toggle("war-open", this.warVisible);
  }

  closeWar() {
    this.toggleWar(false);
  }

  toast(message, kind = "info") {
    const node = el("div", `toast ${kind}`, message);
    this.dom.toasts.append(node);
    while (this.dom.toasts.children.length > 4) {
      this.dom.toasts.firstElementChild.remove();
    }
    window.setTimeout(() => node.remove(), 4600);
  }

  _updateStats() {
    if (!this.state) return;
    const { resources, stats, climate } = this.state;

    this.refs.eco.textContent = fmt(resources.eco_points);
    this.refs["eco-sub"].textContent = `+${fmt(stats.eco_rate, 1)} / tick`;
    this.refs.money.textContent = `$${fmt(resources.money)}`;
    this.refs["money-sub"].textContent = `+${fmt(stats.income, 1)} / tick`;
    this.refs.materials.textContent = fmt(resources.materials);
    this.refs["materials-sub"].textContent = `+${fmt(stats.materials_rate, 1)} / tick`;

    const hasDemand = stats.power_demand > 0;
    const powerShort = hasDemand && stats.power_ratio < 0.999;
    this.refs.power.textContent = `${fmt(stats.power_output)} kW`;
    this.refs["power-sub"].textContent = `demand ${fmt(stats.power_demand)} kW`;
    this.refs["power-fill"].style.width = `${
      hasDemand ? Math.round(stats.power_ratio * 100) : 0
    }%`;
    this.refs["power-fill"].style.background = powerShort
      ? "var(--bad)"
      : "var(--power)";
    this.powerStat.classList.toggle("danger", powerShort);

    const warming = climate.warming_c;
    this.refs.climate.textContent = `+${warming.toFixed(1)} °C`;
    this.refs["climate-sub"].textContent = `${fmt(climate.co2_ppm)} ppm CO2`;
    this.refs["climate-fill"].style.width = `${Math.min(100, (warming / 4) * 100)}%`;
    this.climateStat.classList.toggle("danger", warming >= 2);

    this.refs.population.textContent = fmt(stats.population);
    this.refs["population-sub"].textContent = `happiness ${Math.round(stats.happiness)}%`;
  }

  _updateBuild() {
    if (!this.state) return;
    const { resources, grid } = this.state;

    for (const [type, button] of this.buttons) {
      const stats = this.catalog[type];
      const unlock = stats.unlock_eco_earned ?? 0;
      const locked = resources.eco_earned < unlock;
      const affordable =
        resources.money >= (stats.cost_money ?? 0) &&
        resources.materials >= (stats.cost_materials ?? 0) &&
        resources.eco_points >= (stats.cost_eco ?? 0);

      button.disabled = locked;
      button.classList.toggle("locked", locked);
      button.classList.toggle("unaffordable", !locked && !affordable);
      button.classList.toggle(
        "selected",
        type === this.selected && !this.demolish,
      );
      button.querySelector(".b-cost").textContent = locked
        ? `Unlocks at ${fmt(unlock)} eco`
        : this._costText(stats);
      button.title = locked
        ? `${stats.description ?? stats.name} Unlocks at ${fmt(unlock)} total Eco Points.`
        : stats.description ?? stats.name;
    }

    const expand = grid.expand_cost;
    this.expandBtn.disabled = !grid.can_expand;
    this.expandBtn.querySelector("span").textContent = grid.can_expand
      ? "Expand Land"
      : "Max land";
    this.expandBtn.querySelector("small").textContent = grid.can_expand
      ? `${fmt(expand.eco)} eco · ${fmt(expand.materials)} mat`
      : "You own the whole map";

    this.buyBtn.querySelector(
      "small",
    ).textContent = `${fmt(this.meta.materials_buy_amount)} mats · ${fmt(
      this.meta.materials_buy_cost_eco,
    )} eco`;

    this.demolishBtn.classList.toggle("selected", this.demolish);
  }

  _costText(stats) {
    const parts = [];
    if (stats.cost_money) parts.push(`$${fmt(stats.cost_money)}`);
    if (stats.cost_materials) parts.push(`${fmt(stats.cost_materials)} mat`);
    if (stats.cost_eco) parts.push(`${fmt(stats.cost_eco)} eco`);
    return parts.length ? parts.join(" · ") : "Free";
  }

  _renderTips() {
    if (!this.state) return;
    this.dom.tips.innerHTML = "";
    this.dom.tips.append(el("div", "panel-title", "Advisor"));

    if (!this.state.tips.length) {
      this.dom.tips.append(
        el("div", "tip-empty", "No advice right now. Keep building."),
      );
      return;
    }

    for (const tip of this.state.tips) {
      const card = el("div", `tip ${tip.level}`);
      card.append(el("h3", "", tip.title), el("p", "", tip.body));
      this.dom.tips.append(card);
    }
  }

  _renderWar() {
    if (!this.state) return;
    const { war, civs } = this.state;
    this.dom.war.innerHTML = "";
    this.dom.war.append(
      el("div", "panel-title", `War Room · ${fmt(war.silos)} silo${war.silos === 1 ? "" : "s"}`),
    );

    const note = el("p", "war-note");
    if (war.silos === 0) {
      note.textContent = `Build a Missile Silo (unlocks at ${fmt(
        this.meta.silo_unlock_earned,
      )} total Eco Points) before launching anything.`;
    } else if (this.state.victory) {
      note.textContent = "Both rivals are defeated. Keep an eye on your own emissions.";
    } else {
      note.textContent =
        "Missiles damage a rival. Nukes do far more damage and add much more CO2 and fallout.";
    }
    this.dom.war.append(note);

    for (const civ of civs) {
      const card = el("div", `civ${civ.defeated ? " defeated" : ""}`);
      const head = el("div", "civ-head");
      head.append(
        el("div", "civ-name", civ.name),
        el("div", "civ-power", `Power ${fmt(civ.power)}`),
      );
      card.append(head, el("div", "civ-desc", civ.description));

      const health = el("div", "health");
      const fill = el("i", "");
      fill.style.width = `${Math.max(0, Math.min(100, (civ.health / civ.max_health) * 100))}%`;
      fill.style.background = rgb(civ.color);
      fill.style.boxShadow = `0 0 10px ${rgb(civ.color)}`;
      health.append(fill);
      card.append(health);

      const metaRow = el("div", "civ-meta");
      metaRow.append(
        el("span", "", civ.defeated ? "Defeated" : `Health ${fmt(civ.health)} / ${fmt(civ.max_health)}`),
        el("span", "", `${fmt(civ.emissions, 1)} CO2 / tick`),
      );
      card.append(metaRow);

      const row = el("div", "launch-row");
      const missile = el(
        "button",
        "btn",
        `Missile · ${fmt(war.missile_cost.eco)} eco`,
      );
      missile.type = "button";
      missile.title = `Damage ${fmt(war.damage.missile)} · ${fmt(
        war.missile_cost.materials,
      )} materials`;
      missile.disabled = civ.defeated || !war.can_launch;
      missile.addEventListener("click", () =>
        this.onCommand?.(
          "launch",
          { target: civ.id, kind: "missile" },
          `Missile launched at ${civ.name}.`,
        ),
      );

      const nuke = el(
        "button",
        "btn nuke",
        war.nuke_unlocked
          ? `Nuke · ${fmt(war.nuke_cost.eco)} eco`
          : `Nuke locked · ${fmt(this.meta.nuke_unlock_earned)} eco`,
      );
      nuke.type = "button";
      nuke.title = `Damage ${fmt(war.damage.nuke)} · ${fmt(
        war.nuke_cost.materials,
      )} materials`;
      nuke.disabled =
        civ.defeated || !war.can_launch || !war.nuke_unlocked;
      nuke.addEventListener("click", () =>
        this.onCommand?.(
          "launch",
          { target: civ.id, kind: "nuke" },
          `Nuke launched at ${civ.name}.`,
        ),
      );

      row.append(missile, nuke);
      card.append(row);
      this.dom.war.append(card);
    }
  }

  _updateBanner() {
    if (!this.state) return;
    if (this.state.victory) {
      this.dom.banner.hidden = false;
      this.dom.banner.innerHTML =
        "Victory!<small>Both rivals are defeated. Now get your city to zero emissions.</small>";
    } else {
      this.dom.banner.hidden = true;
    }
  }

  _updateStatus() {
    if (!this.statusEl) return;
    let text;
    if (this.demolish) {
      text = "Demolish: click a building";
    } else if (this.selected) {
      text = `Placing ${this.catalog[this.selected]?.name ?? this.selected}`;
    } else {
      text = "Drag to orbit · wheel to zoom · right-drag to pan";
    }

    if (this.hover) {
      const { x, z } = this.hover;
      const building = this.buildingMap.get(`${x},${z}`);
      const terrain = this.state?.grid.terrain[z]?.[x];
      const label = building
        ? this.catalog[building.type]?.name ?? "Building"
        : TERRAIN_LABEL[terrain] ?? "Land";
      text += ` · ${label} (${x}, ${z})`;
    }
    this.statusEl.textContent = text;
  }
}
