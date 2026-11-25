/* Feifood · interface web
 * Conversa com os dois microsserviços:
 *   Catalog Service (porta 8001) -> restaurantes e produtos
 *   Orders Service  (porta 8002) -> pedidos
 */
(() => {
  "use strict";

  const HOST = location.hostname || "localhost";
  const CATALOG = `http://${HOST}:8001`;
  const ORDERS = `http://${HOST}:8002`;

  const STATUS_LABEL = {
    CRIADO: "Pedido recebido",
    PREPARANDO: "Preparando",
    A_CAMINHO: "A caminho",
    ENTREGUE: "Entregue",
    CANCELADO: "Cancelado",
  };
  const FLOW = ["CRIADO", "PREPARANDO", "A_CAMINHO", "ENTREGUE"];
  const NEXT = { CRIADO: "PREPARANDO", PREPARANDO: "A_CAMINHO", A_CAMINHO: "ENTREGUE" };
  const CAN_CANCEL = new Set(["CRIADO", "PREPARANDO"]);

  const SAMPLE = [
    { name: "Burger Dev", category: "Lanches", products: [["X-Burguer", 22.5], ["X-Salada", 24.5], ["Batata frita", 14], ["Refrigerante", 7]] },
    { name: "Pizzaria do Zé", category: "Pizza", products: [["Margherita", 42], ["Calabresa", 46], ["Guaraná 2L", 12]] },
    { name: "Sushi Byte", category: "Japonesa", products: [["Combo 20 peças", 59.9], ["Temaki de salmão", 28], ["Hot roll", 32]] },
    { name: "Doce Código", category: "Sobremesas", products: [["Brownie", 12], ["Pudim", 10.5], ["Milkshake", 18]] },
  ];

  const state = {
    view: "restaurants",
    restaurants: [],
    products: {}, // restaurant_id -> lista de produtos
    currentRestaurant: null,
    search: "",
    category: "Todos",
    orders: [],
    statusFilter: "",
    cart: { restaurantId: null, items: {} }, // items: product_id -> { product, qty }
    catalogError: false,
  };

  /* ---------- utilidades ---------- */
  const money = (v) => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v);
  const $ = (sel) => document.querySelector(sel);

  function el(tag, props = {}, ...children) {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(props)) {
      if (key === "class") node.className = value;
      else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
      else if (value === true) node.setAttribute(key, "");
      else if (value !== false && value != null) node.setAttribute(key, value);
    }
    for (const child of children.flat()) {
      if (child == null || child === false) continue;
      node.append(child.nodeType ? child : document.createTextNode(String(child)));
    }
    return node;
  }

  function emojiFor(category = "") {
    const c = category.toLowerCase();
    if (/lanche|burger|hamb/.test(c)) return "🍔";
    if (/pizza/.test(c)) return "🍕";
    if (/japon|sushi/.test(c)) return "🍣";
    if (/sobremesa|doce|sorvete|a[çc]a[ií]/.test(c)) return "🍰";
    if (/bebida|suco|drink/.test(c)) return "🥤";
    if (/salada|saud|vegan/.test(c)) return "🥗";
    if (/brasil|marmit|prato/.test(c)) return "🍛";
    if (/mexic|taco/.test(c)) return "🌮";
    if (/caf[eé]|padaria/.test(c)) return "☕";
    return "🍽️";
  }

  function toast(message, kind = "info") {
    const node = el("div", { class: `toast toast--${kind === "ok" ? "ok" : kind === "err" ? "err" : "info"}` }, message);
    $("#toasts").append(node);
    setTimeout(() => node.remove(), 4200);
  }

  function parseDate(value) {
    // A API devolve horário UTC, às vezes sem o "Z" no final.
    const hasZone = /(Z|[+-]\d{2}:?\d{2})$/.test(value);
    return new Date(hasZone ? value : value + "Z");
  }

  /* ---------- acesso às APIs ---------- */
  class ApiError extends Error {
    constructor(status, message) {
      super(message);
      this.status = status;
    }
  }

  function errorMessage(data) {
    if (!data) return "";
    if (typeof data.detail === "string") return data.detail;
    if (Array.isArray(data.detail)) {
      return data.detail.map((d) => `${(d.loc || []).slice(1).join(".")}: ${d.msg}`).join("; ");
    }
    return "";
  }

  async function api(base, path, options = {}) {
    let response;
    try {
      response = await fetch(base + path, { headers: { "Content-Type": "application/json" }, ...options });
    } catch {
      throw new ApiError(0, "Não foi possível conectar ao serviço. Ele está no ar?");
    }
    const text = await response.text();
    let data = null;
    try { data = text ? JSON.parse(text) : null; } catch { /* resposta sem JSON */ }
    if (!response.ok) throw new ApiError(response.status, errorMessage(data) || `Erro ${response.status}`);
    return data;
  }

  const post = (base, path, body) => api(base, path, { method: "POST", body: JSON.stringify(body) });

  async function loadCatalog() {
    try {
      state.restaurants = await api(CATALOG, "/restaurants");
      const lists = await Promise.all(state.restaurants.map((r) => api(CATALOG, `/restaurants/${r.id}/products`)));
      state.products = {};
      state.restaurants.forEach((r, i) => { state.products[r.id] = lists[i]; });
      state.catalogError = false;
    } catch (error) {
      state.catalogError = true;
      throw error;
    }
  }

  async function loadOrders() {
    const query = state.statusFilter ? `?status=${state.statusFilter}` : "";
    state.orders = await api(ORDERS, `/orders${query}`);
  }

  async function ping() {
    for (const [base, id] of [[CATALOG, "#dot-catalog"], [ORDERS, "#dot-orders"]]) {
      let up = false;
      try {
        const signal = AbortSignal.timeout ? AbortSignal.timeout(2500) : undefined;
        const response = await fetch(base + "/health", { signal });
        up = response.ok;
      } catch { up = false; }
      const dot = $(id);
      dot.classList.toggle("is-up", up);
      dot.classList.toggle("is-down", !up);
    }
  }

  /* ---------- carrinho ---------- */
  function saveCart() {
    try { localStorage.setItem("feifood-cart", JSON.stringify(state.cart)); } catch { /* sem storage */ }
  }

  function restoreCart() {
    try {
      const saved = JSON.parse(localStorage.getItem("feifood-cart") || "null");
      if (saved && saved.items) state.cart = saved;
    } catch { /* ignora */ }
  }

  const cartLines = () => Object.values(state.cart.items);
  const cartCount = () => cartLines().reduce((sum, l) => sum + l.qty, 0);
  const cartTotal = () => cartLines().reduce((sum, l) => sum + l.qty * l.product.price, 0);

  function addToCart(product, restaurant) {
    if (state.cart.restaurantId && state.cart.restaurantId !== restaurant.id && cartCount() > 0) {
      const ok = window.confirm("Seu carrinho tem itens de outro restaurante. Esvaziar e começar um novo pedido?");
      if (!ok) return;
      state.cart.items = {};
    }
    state.cart.restaurantId = restaurant.id;
    const line = state.cart.items[product.id] || { product, qty: 0 };
    line.qty = Math.min(50, line.qty + 1);
    state.cart.items[product.id] = line;
    saveCart();
    renderCart();
    toast(`${product.name} adicionado ao carrinho`, "ok");
  }

  function changeQty(productId, delta) {
    const line = state.cart.items[productId];
    if (!line) return;
    line.qty = Math.min(50, line.qty + delta);
    if (line.qty <= 0) delete state.cart.items[productId];
    if (!cartCount()) state.cart.restaurantId = null;
    saveCart();
    renderCart();
  }

  function openCart(open) {
    $("#cart").classList.toggle("is-open", open);
    $("#overlay").classList.toggle("is-open", open);
  }

  function renderCart() {
    $("#cart-count").textContent = cartCount();
    const body = $("#cart-body");
    const foot = $("#cart-foot");
    body.replaceChildren();
    foot.replaceChildren();

    if (!cartCount()) {
      body.append(el("div", { class: "empty" }, el("div", { class: "empty__emoji" }, "🛒"), el("h3", {}, "Seu carrinho está vazio"), el("span", {}, "Escolha um restaurante e adicione pratos.")));
      return;
    }

    const restaurant = state.restaurants.find((r) => r.id === state.cart.restaurantId);
    if (restaurant) body.append(el("div", { class: "page-sub" }, `Pedindo de ${restaurant.name}`));

    for (const line of cartLines()) {
      body.append(
        el("div", { class: "cart-item" },
          el("div", { class: "cart-item__info" },
            el("div", { class: "cart-item__name" }, line.product.name),
            el("div", { class: "cart-item__price" }, `${money(line.product.price)} cada`)),
          el("div", { class: "qty" },
            el("button", { class: "icon-btn", "aria-label": "Diminuir", onclick: () => changeQty(line.product.id, -1) }, "−"),
            el("b", {}, line.qty),
            el("button", { class: "icon-btn", "aria-label": "Aumentar", onclick: () => changeQty(line.product.id, 1) }, "+"))));
    }

    const nameInput = el("input", { class: "input", id: "customer", placeholder: "Seu nome", maxlength: "100", autocomplete: "name" });
    foot.append(
      el("div", { class: "totals" }, el("span", {}, "Total"), el("span", {}, money(cartTotal()))),
      el("label", { class: "field" }, "Nome para o pedido", nameInput),
      el("button", { class: "btn btn--block", onclick: checkout }, "Finalizar pedido"),
      el("button", { class: "btn btn--ghost btn--block btn--sm", onclick: clearCart }, "Esvaziar carrinho"));
  }

  function clearCart() {
    state.cart = { restaurantId: null, items: {} };
    saveCart();
    renderCart();
  }

  async function checkout() {
    const customer = ($("#customer").value || "").trim();
    if (!customer) {
      toast("Digite o seu nome para finalizar o pedido.", "err");
      $("#customer").focus();
      return;
    }
    const items = cartLines().map((l) => ({ product_id: l.product.id, quantity: l.qty }));
    try {
      const order = await post(ORDERS, "/orders", { customer, items });
      clearCart();
      openCart(false);
      toast(`Pedido #${order.id} criado! Total ${money(order.total)}`, "ok");
      setView("orders");
    } catch (error) {
      toast(error.message, "err");
    }
  }

  /* ---------- telas ---------- */
  function setView(view, restaurantId = null) {
    state.view = view;
    state.currentRestaurant = restaurantId;
    document.querySelectorAll(".nav__btn").forEach((b) => b.classList.toggle("is-active", b.dataset.view === (view === "menu" ? "restaurants" : view)));
    render();
    window.scrollTo({ top: 0 });
  }

  async function render() {
    const app = $("#app");
    app.replaceChildren();
    if (state.view === "restaurants") return viewRestaurants(app);
    if (state.view === "menu") return viewMenu(app);
    if (state.view === "orders") return viewOrders(app);
    if (state.view === "admin") return viewAdmin(app);
  }

  function emptyCatalog() {
    return el("div", { class: "empty" },
      el("div", { class: "empty__emoji" }, "🍽️"),
      el("h3", {}, "Ainda não há restaurantes"),
      el("span", {}, "Cadastre os seus na aba Gerenciar ou carregue restaurantes de exemplo para testar."),
      el("button", { class: "btn", id: "seed-empty", onclick: seed }, "Carregar dados de exemplo"));
  }

  function viewRestaurants(app) {
    app.append(
      el("section", { class: "hero" },
        el("h1", {}, "Peça sua comida favorita, ", el("b", {}, "rápido"), "."),
        el("p", {}, "Escolha um restaurante, monte o pedido e acompanhe cada etapa até chegar na sua mesa.")));

    if (state.catalogError) {
      app.append(el("div", { class: "banner" }, "Não consegui falar com o Catalog Service (porta 8001). Confira se os serviços estão rodando."));
    }

    const categories = ["Todos", ...new Set(state.restaurants.map((r) => r.category))];
    const search = el("input", {
      class: "search", id: "search", type: "search", placeholder: "Buscar restaurante, categoria ou prato…", value: state.search,
      oninput: (e) => { state.search = e.target.value; renderList(); },
    });
    const chips = el("div", { class: "chips" }, categories.map((c) =>
      el("button", { class: `chip${state.category === c ? " is-active" : ""}`, onclick: () => { state.category = c; render(); } }, c)));
    const list = el("div", { class: "grid", id: "restaurant-list" });

    app.append(el("div", { class: "toolbar" }, search, chips), list);
    renderList();

    function renderList() {
      const term = state.search.trim().toLowerCase();
      const shown = state.restaurants.filter((r) => {
        const inCategory = state.category === "Todos" || r.category === state.category;
        const dishes = (state.products[r.id] || []).map((p) => p.name.toLowerCase());
        const inSearch = !term || r.name.toLowerCase().includes(term) || r.category.toLowerCase().includes(term) || dishes.some((d) => d.includes(term));
        return inCategory && inSearch;
      });
      list.replaceChildren();
      if (!state.restaurants.length) { list.replaceWith(emptyCatalog()); return; }
      if (!shown.length) { list.append(el("div", { class: "empty", style: "grid-column: 1 / -1" }, el("h3", {}, "Nada encontrado"), el("span", {}, "Tente outro termo ou categoria."))); return; }
      for (const r of shown) {
        const count = (state.products[r.id] || []).length;
        list.append(
          el("article", { class: "card card--click", tabindex: "0", role: "button", "aria-label": `Abrir ${r.name}`, onclick: () => setView("menu", r.id), onkeydown: (e) => { if (e.key === "Enter") setView("menu", r.id); } },
            el("div", { class: "card__emoji" }, emojiFor(r.category)),
            el("div", { class: "card__title" }, r.name),
            el("div", { class: "card__meta" }, el("span", { class: "tag" }, r.category), el("span", {}, `${count} ${count === 1 ? "prato" : "pratos"}`))));
      }
    }
  }

  function viewMenu(app) {
    const restaurant = state.restaurants.find((r) => r.id === state.currentRestaurant);
    if (!restaurant) return setView("restaurants");
    const products = state.products[restaurant.id] || [];

    app.append(
      el("button", { class: "back", onclick: () => setView("restaurants") }, "← Voltar aos restaurantes"),
      el("div", { class: "section-head" },
        el("div", {}, el("h1", { class: "page-title" }, `${emojiFor(restaurant.category)} ${restaurant.name}`), el("p", { class: "page-sub" }, restaurant.category))));

    if (!products.length) {
      app.append(el("div", { class: "empty" }, el("h3", {}, "Cardápio vazio"), el("span", {}, "Adicione pratos na aba Gerenciar.")));
      return;
    }
    app.append(el("div", { class: "grid" }, products.map((p) =>
      el("article", { class: "card" },
        el("div", { class: "card__emoji" }, emojiFor(restaurant.category)),
        el("div", { class: "card__title" }, p.name),
        el("div", { class: "row" }, el("span", { class: "price" }, money(p.price)),
          el("button", { class: "btn btn--sm", onclick: () => addToCart(p, restaurant) }, "+ Adicionar"))))));
  }

  async function viewOrders(app) {
    const select = el("select", { class: "input", style: "max-width: 220px", "aria-label": "Filtrar por status", onchange: async (e) => { state.statusFilter = e.target.value; await refreshOrders(); } },
      el("option", { value: "" }, "Todos os status"),
      Object.entries(STATUS_LABEL).map(([value, label]) => el("option", { value, selected: state.statusFilter === value }, label)));
    const holder = el("div", { class: "orders", id: "orders-list" });

    app.append(
      el("div", { class: "section-head" },
        el("div", {}, el("h1", { class: "page-title" }, "Meus pedidos"), el("p", { class: "page-sub" }, "Acompanhe cada etapa. A lista atualiza sozinha a cada 5 segundos.")),
        select),
      holder);
    await refreshOrders();
  }

  async function refreshOrders() {
    const holder = $("#orders-list");
    if (!holder) return;
    try {
      await loadOrders();
    } catch (error) {
      holder.replaceChildren(el("div", { class: "banner" }, `Não consegui carregar os pedidos: ${error.message}`));
      return;
    }
    holder.replaceChildren();
    if (!state.orders.length) {
      holder.append(el("div", { class: "empty" }, el("div", { class: "empty__emoji" }, "🧾"), el("h3", {}, "Nenhum pedido por aqui"), el("span", {}, "Faça um pedido na aba Restaurantes."),
        el("button", { class: "btn", onclick: () => setView("restaurants") }, "Ver restaurantes")));
      return;
    }
    for (const order of [...state.orders].reverse()) holder.append(orderCard(order));
  }

  function orderCard(order) {
    const cancelled = order.status === "CANCELADO";
    const index = FLOW.indexOf(order.status);

    const stepper = cancelled ? null : el("div", { class: "stepper" }, FLOW.map((s, i) =>
      el("div", { class: `step${i <= index ? " is-done" : ""}${i === index ? " is-current" : ""}` }, el("div", { class: "step__bar" }), STATUS_LABEL[s])));

    const actions = el("div", { class: "actions" });
    if (NEXT[order.status]) {
      actions.append(el("button", { class: "btn btn--sm", onclick: () => changeStatus(order.id, NEXT[order.status]) }, `Avançar: ${STATUS_LABEL[NEXT[order.status]]}`));
    }
    if (CAN_CANCEL.has(order.status)) {
      actions.append(el("button", { class: "btn btn--danger btn--sm", onclick: () => changeStatus(order.id, "CANCELADO") }, "Cancelar"));
    }

    return el("article", { class: "order" },
      el("div", { class: "order__head" },
        el("div", {}, el("div", { class: "order__id" }, `Pedido #${order.id}`), el("div", { class: "order__date" }, `${order.customer} · ${parseDate(order.created_at).toLocaleString("pt-BR")}`)),
        el("span", { class: `badge badge--${order.status}` }, STATUS_LABEL[order.status])),
      stepper,
      el("ul", { class: "order__items" }, order.items.map((i) =>
        el("li", {}, el("span", {}, `${i.quantity}× ${i.product_name}`), el("span", {}, money(i.quantity * i.unit_price))))),
      el("div", { class: "order__foot" }, el("div", { class: "price" }, money(order.total)), actions));
  }

  async function changeStatus(orderId, status) {
    try {
      await api(ORDERS, `/orders/${orderId}/status`, { method: "PATCH", body: JSON.stringify({ status }) });
      toast(`Pedido #${orderId}: ${STATUS_LABEL[status]}`, "ok");
    } catch (error) {
      toast(error.message, "err");
    }
    await refreshOrders();
  }

  function viewAdmin(app) {
    const rName = el("input", { class: "input", id: "r-name", placeholder: "Ex.: Burger Dev", maxlength: "100", required: true });
    const rCat = el("input", { class: "input", id: "r-cat", placeholder: "Ex.: Lanches", maxlength: "50", list: "cats", required: true });
    const datalist = el("datalist", { id: "cats" }, ["Lanches", "Pizza", "Japonesa", "Sobremesas", "Bebidas", "Saudável"].map((c) => el("option", { value: c })));

    const pRest = el("select", { class: "input", id: "p-rest" }, state.restaurants.map((r) => el("option", { value: r.id }, r.name)));
    const pName = el("input", { class: "input", id: "p-name", placeholder: "Ex.: X-Burguer", maxlength: "100" });
    const pPrice = el("input", { class: "input", id: "p-price", type: "number", min: "0.01", step: "0.01", placeholder: "22.50" });

    app.append(
      el("div", { class: "section-head" }, el("div", {}, el("h1", { class: "page-title" }, "Gerenciar catálogo"), el("p", { class: "page-sub" }, "Cadastre restaurantes e pratos. Tudo é salvo pelo Catalog Service."))),
      el("div", { class: "admin-grid" },
        el("form", { class: "panel", id: "form-restaurant", onsubmit: async (e) => {
          e.preventDefault();
          try {
            await post(CATALOG, "/restaurants", { name: rName.value.trim(), category: rCat.value.trim() });
            toast("Restaurante cadastrado!", "ok");
            await loadCatalog();
            render();
          } catch (error) { toast(error.message, "err"); }
        } },
          el("h3", {}, "🏪 Novo restaurante"),
          el("label", { class: "field" }, "Nome", rName),
          el("label", { class: "field" }, "Categoria", rCat, datalist),
          el("button", { class: "btn", type: "submit" }, "Cadastrar restaurante")),

        el("form", { class: "panel", id: "form-product", onsubmit: async (e) => {
          e.preventDefault();
          if (!pRest.value) { toast("Cadastre um restaurante primeiro.", "err"); return; }
          try {
            await post(CATALOG, `/restaurants/${pRest.value}/products`, { name: pName.value.trim(), price: Number(pPrice.value) });
            toast("Prato cadastrado!", "ok");
            await loadCatalog();
            render();
          } catch (error) { toast(error.message, "err"); }
        } },
          el("h3", {}, "🍽️ Novo prato"),
          el("label", { class: "field" }, "Restaurante", pRest),
          el("label", { class: "field" }, "Nome do prato", pName),
          el("label", { class: "field" }, "Preço (R$)", pPrice),
          el("button", { class: "btn", type: "submit" }, "Cadastrar prato")),

        el("div", { class: "panel" },
          el("h3", {}, "⚡ Dados de exemplo"),
          el("p", {}, "Cria 4 restaurantes com cardápio para você testar rápido. Pode clicar mais de uma vez: nada é duplicado."),
          el("button", { class: "btn btn--ghost", id: "seed-admin", onclick: seed }, "Carregar dados de exemplo"))));
  }

  async function seed() {
    try {
      await loadCatalog().catch(() => { state.restaurants = []; });
      for (const sample of SAMPLE) {
        let restaurant = state.restaurants.find((r) => r.name === sample.name);
        if (!restaurant) restaurant = await post(CATALOG, "/restaurants", { name: sample.name, category: sample.category });
        const existing = await api(CATALOG, `/restaurants/${restaurant.id}/products`);
        for (const [name, price] of sample.products) {
          if (!existing.some((p) => p.name === name)) await post(CATALOG, `/restaurants/${restaurant.id}/products`, { name, price });
        }
        await loadCatalog();
      }
      toast("Dados de exemplo carregados! 🍔", "ok");
      setView("restaurants");
    } catch (error) {
      toast(error.message, "err");
    }
  }

  /* ---------- início ---------- */
  async function init() {
    $("#doc-catalog").href = `${CATALOG}/docs`;
    $("#doc-orders").href = `${ORDERS}/docs`;

    document.querySelectorAll(".nav__btn").forEach((b) => b.addEventListener("click", () => setView(b.dataset.view)));
    $("#brand").addEventListener("click", (e) => { e.preventDefault(); setView("restaurants"); });
    $("#cart-open").addEventListener("click", () => openCart(true));
    $("#cart-close").addEventListener("click", () => openCart(false));
    $("#overlay").addEventListener("click", () => openCart(false));
    document.addEventListener("keydown", (e) => { if (e.key === "Escape") openCart(false); });

    restoreCart();
    renderCart();
    ping();
    setInterval(ping, 10000);
    setInterval(() => { if (state.view === "orders") refreshOrders(); }, 5000);

    try { await loadCatalog(); } catch (error) { toast(error.message, "err"); }
    render();
  }

  init();
})();
