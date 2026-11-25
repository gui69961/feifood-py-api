/* Feifood · interface web
 * Conversa com os três microsserviços:
 *   Auth Service    (8003) -> contas, login e tokens
 *   Catalog Service (8001) -> restaurantes e produtos
 *   Orders Service  (8002) -> pedidos
 *
 * Dois perfis:
 *   CLIENTE -> vê restaurantes, monta o carrinho e acompanha os seus pedidos
 *   LOJISTA -> (conta criada com CNPJ) gerencia a sua loja e conduz os pedidos recebidos
 */
(() => {
  "use strict";

  const HOST = location.hostname || "localhost";
  const CATALOG = `http://${HOST}:8001`;
  const ORDERS = `http://${HOST}:8002`;
  const AUTH = `http://${HOST}:8003`;

  const STATUS_LABEL = {
    CRIADO: "Pedido recebido", PREPARANDO: "Preparando", A_CAMINHO: "A caminho", ENTREGUE: "Entregue", CANCELADO: "Cancelado",
  };
  const FLOW = ["CRIADO", "PREPARANDO", "A_CAMINHO", "ENTREGUE"];
  // O que cada perfil pode fazer em cada etapa: [novo status, texto do botão, é ação de risco?]
  const OWNER_ACTIONS = {
    CRIADO: [["PREPARANDO", "Aceitar pedido", false], ["CANCELADO", "Recusar", true]],
    PREPARANDO: [["A_CAMINHO", "Saiu para entrega", false], ["CANCELADO", "Cancelar", true]],
    A_CAMINHO: [["ENTREGUE", "Marcar como entregue", false]],
  };
  const CUSTOMER_ACTIONS = { CRIADO: [["CANCELADO", "Cancelar pedido", true]] };

  const DEMO_CUSTOMER = { name: "Cliente Demo", email: "cliente@demo.feifood", password: "demo12345" };
  const DEMO_OWNER = {
    name: "Lojista Demo", email: "lojista@demo.feifood", password: "demo12345",
    company_name: "Rede Demo Alimentos", cnpj: "12.345.678/0001-95",
  };

  const SAMPLE = [
    { name: "Burger Dev", category: "Lanches", products: [["X-Burguer", 22.5], ["X-Salada", 24.5], ["Batata frita", 14], ["Refrigerante", 7]] },
    { name: "Pizzaria do Zé", category: "Pizza", products: [["Margherita", 42], ["Calabresa", 46], ["Guaraná 2L", 12]] },
    { name: "Sushi Byte", category: "Japonesa", products: [["Combo 20 peças", 59.9], ["Temaki de salmão", 28], ["Hot roll", 32]] },
    { name: "Doce Código", category: "Sobremesas", products: [["Brownie", 12], ["Pudim", 10.5], ["Milkshake", 18]] },
  ];

  const state = {
    auth: null, // { token, user }
    view: "login",
    authTab: "login", // login | register
    authKind: "CLIENTE", // CLIENTE | LOJISTA (no cadastro)
    restaurants: [], products: {}, // visão do cliente
    myRestaurants: [], myProducts: {}, // visão do lojista
    currentRestaurant: null,
    search: "", category: "Todos",
    orders: [], statusFilter: "",
    cart: { restaurantId: null, items: {} },
    catalogError: false,
  };

  /* ---------- utilidades ---------- */
  const money = (v) => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v);
  const $ = (sel) => document.querySelector(sel);
  const isOwner = () => state.auth && state.auth.user.role === "LOJISTA";
  const isCustomer = () => state.auth && state.auth.user.role === "CLIENTE";

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
    setTimeout(() => node.remove(), 4500);
  }

  function parseDate(value) {
    const hasZone = /(Z|[+-]\d{2}:?\d{2})$/.test(value); // a API devolve UTC, às vezes sem o "Z"
    return new Date(hasZone ? value : value + "Z");
  }

  /* ---------- CNPJ (mesmo cálculo do servidor, só para dar retorno rápido) ---------- */
  const normalizeCnpj = (v) => v.replace(/[.\-/\s]/g, "").toUpperCase();

  function maskCnpj(value) {
    const c = value.replace(/[^0-9a-zA-Z]/g, "").toUpperCase().slice(0, 14);
    let out = c.slice(0, 2);
    if (c.length > 2) out += "." + c.slice(2, 5);
    if (c.length > 5) out += "." + c.slice(5, 8);
    if (c.length > 8) out += "/" + c.slice(8, 12);
    if (c.length > 12) out += "-" + c.slice(12, 14);
    return out;
  }

  function isValidCnpj(value) {
    const c = normalizeCnpj(value);
    if (!/^[0-9A-Z]{12}[0-9]{2}$/.test(c) || new Set(c).size === 1) return false;
    const digit = (chars, weights) => {
      const total = [...chars].reduce((sum, ch, i) => sum + (ch.charCodeAt(0) - 48) * weights[i], 0);
      const r = total % 11;
      return r < 2 ? 0 : 11 - r;
    };
    const w1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2];
    const d1 = digit(c.slice(0, 12), w1);
    const d2 = digit(c.slice(0, 12) + d1, [6, ...w1]);
    return c.slice(12) === `${d1}${d2}`;
  }

  /* ---------- acesso às APIs ---------- */
  class ApiError extends Error {
    constructor(status, message) { super(message); this.status = status; }
  }

  const FIELD = { cnpj: "CNPJ", password: "Senha", email: "E-mail", name: "Nome", company_name: "Nome da empresa", price: "Preço", category: "Categoria" };

  function errorMessage(data) {
    if (!data) return "";
    if (typeof data.detail === "string") return data.detail;
    if (Array.isArray(data.detail)) {
      return data.detail.map((d) => {
        const field = (d.loc || []).slice(1).join(".");
        const msg = String(d.msg || "").replace(/^Value error, /, "");
        return FIELD[field] && !msg.includes(FIELD[field]) ? `${FIELD[field]}: ${msg}` : msg;
      }).join("; ");
    }
    return "";
  }

  /* options.token: usa outro token em vez do da sessão (usado nos dados de demonstração) */
  async function api(base, path, options = {}) {
    const { token, ...fetchOptions } = options;
    const bearer = token || (state.auth && state.auth.token);
    const headers = { "Content-Type": "application/json", ...(bearer ? { Authorization: `Bearer ${bearer}` } : {}) };
    let response;
    try {
      response = await fetch(base + path, { ...fetchOptions, headers });
    } catch {
      throw new ApiError(0, "Não foi possível conectar ao serviço. Ele está no ar?");
    }
    const text = await response.text();
    let data = null;
    try { data = text ? JSON.parse(text) : null; } catch { /* sem JSON */ }
    if (!response.ok) {
      if (response.status === 401 && state.auth && !token) logout("Sua sessão expirou. Entre novamente.");
      throw new ApiError(response.status, errorMessage(data) || `Erro ${response.status}`);
    }
    return data;
  }
  const post = (base, path, body, token) => api(base, path, { method: "POST", body: JSON.stringify(body), token });

  async function loadCatalog() {
    try {
      state.restaurants = await api(CATALOG, "/restaurants");
      const lists = await Promise.all(state.restaurants.map((r) => api(CATALOG, `/restaurants/${r.id}/products`)));
      state.products = {};
      state.restaurants.forEach((r, i) => { state.products[r.id] = lists[i]; });
      state.catalogError = false;
    } catch (error) { state.catalogError = true; throw error; }
  }

  async function loadMyStore() {
    state.myRestaurants = await api(CATALOG, "/restaurants/mine");
    const lists = await Promise.all(state.myRestaurants.map((r) => api(CATALOG, `/restaurants/${r.id}/products`)));
    state.myProducts = {};
    state.myRestaurants.forEach((r, i) => { state.myProducts[r.id] = lists[i]; });
  }

  const loadOrders = async () => { state.orders = await api(ORDERS, "/orders"); };

  async function ping() {
    for (const [base, id] of [[CATALOG, "#dot-catalog"], [ORDERS, "#dot-orders"], [AUTH, "#dot-auth"]]) {
      let up = false;
      try {
        const signal = AbortSignal.timeout ? AbortSignal.timeout(2500) : undefined;
        up = (await fetch(base + "/health", { signal })).ok;
      } catch { up = false; }
      const dot = $(id);
      dot.classList.toggle("is-up", up);
      dot.classList.toggle("is-down", !up);
    }
  }

  /* ---------- sessão ---------- */
  const SESSION_KEY = "feifood-session";
  const cartKey = () => `feifood-cart-${state.auth ? state.auth.user.id : "anon"}`;

  function saveSession() {
    try {
      if (state.auth) localStorage.setItem(SESSION_KEY, JSON.stringify(state.auth));
      else localStorage.removeItem(SESSION_KEY);
    } catch { /* sem storage */ }
  }

  function loadSession() {
    try {
      const saved = JSON.parse(localStorage.getItem(SESSION_KEY) || "null");
      if (saved && saved.token && saved.user) state.auth = saved;
    } catch { /* ignora */ }
  }

  function resetData() {
    Object.assign(state, {
      restaurants: [], products: {}, myRestaurants: [], myProducts: {}, orders: [],
      currentRestaurant: null, search: "", category: "Todos", statusFilter: "",
      cart: { restaurantId: null, items: {} }, catalogError: false,
    });
  }

  function startSession(tokenOut) {
    resetData();
    state.auth = { token: tokenOut.access_token, user: tokenOut.user };
    saveSession();
    restoreCart();
    setupShell();
    toast(`Bem-vindo(a), ${tokenOut.user.name.split(" ")[0]}!`, "ok");
    setView(isOwner() ? "store" : "restaurants");
  }

  function logout(message) {
    state.auth = null;
    saveSession();
    resetData();
    openCart(false);
    setupShell();
    setView("login");
    if (message) toast(message, message.startsWith("Sua sessão") ? "err" : "info");
  }

  /* ---------- cabeçalho (muda conforme o perfil) ---------- */
  function setupShell() {
    const nav = $("#nav");
    nav.replaceChildren();
    const items = !state.auth ? [] : isOwner()
      ? [["store", "Minha loja"], ["received", "Pedidos recebidos"]]
      : [["restaurants", "Restaurantes"], ["orders", "Meus pedidos"]];
    for (const [view, label] of items) {
      nav.append(el("button", { class: "nav__btn", "data-view": view, onclick: () => setView(view) }, label));
    }

    $("#cart-open").classList.toggle("hidden", !isCustomer());

    const box = $("#user-box");
    box.replaceChildren();
    box.classList.toggle("hidden", !state.auth);
    if (state.auth) {
      const u = state.auth.user;
      box.append(
        el("div", { class: "avatar", "aria-hidden": "true" }, u.name.trim().charAt(0).toUpperCase()),
        el("div", {}, el("div", { class: "user-box__name" }, u.name), el("div", { class: "role" }, isOwner() ? "Lojista" : "Cliente")),
        el("button", { class: "btn btn--ghost btn--sm", id: "logout", onclick: () => logout("Você saiu da sua conta.") }, "Sair"));
    }
    renderCart();
  }

  /* ---------- carrinho (só cliente) ---------- */
  function saveCart() { try { localStorage.setItem(cartKey(), JSON.stringify(state.cart)); } catch { /* ignora */ } }
  function restoreCart() {
    try {
      const saved = JSON.parse(localStorage.getItem(cartKey()) || "null");
      if (saved && saved.items) state.cart = saved;
    } catch { /* ignora */ }
  }

  const cartLines = () => Object.values(state.cart.items);
  const cartCount = () => cartLines().reduce((sum, l) => sum + l.qty, 0);
  const cartTotal = () => cartLines().reduce((sum, l) => sum + l.qty * l.product.price, 0);

  function addToCart(product, restaurant) {
    if (state.cart.restaurantId && state.cart.restaurantId !== restaurant.id && cartCount() > 0) {
      if (!window.confirm("Seu carrinho tem itens de outro restaurante. Esvaziar e começar um novo pedido?")) return;
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
    foot.append(
      el("div", { class: "totals" }, el("span", {}, "Total"), el("span", {}, money(cartTotal()))),
      el("div", { class: "notice" }, `Pedido em nome de ${state.auth ? state.auth.user.name : ""}`),
      el("button", { class: "btn btn--block", id: "checkout", onclick: checkout }, "Finalizar pedido"),
      el("button", { class: "btn btn--ghost btn--block btn--sm", onclick: clearCart }, "Esvaziar carrinho"));
  }

  function clearCart() {
    state.cart = { restaurantId: null, items: {} };
    saveCart();
    renderCart();
  }

  async function checkout() {
    const items = cartLines().map((l) => ({ product_id: l.product.id, quantity: l.qty }));
    try {
      const order = await post(ORDERS, "/orders", { items });
      clearCart();
      openCart(false);
      toast(`Pedido #${order.id} enviado ao restaurante! Total ${money(order.total)}`, "ok");
      setView("orders");
    } catch (error) { toast(error.message, "err"); }
  }

  /* ---------- navegação ---------- */
  function setView(view, restaurantId = null) {
    state.view = view;
    state.currentRestaurant = restaurantId;
    const activeNav = view === "menu" ? "restaurants" : view;
    document.querySelectorAll(".nav__btn").forEach((b) => b.classList.toggle("is-active", b.dataset.view === activeNav));
    render();
    window.scrollTo({ top: 0 });
  }

  async function render() {
    const app = $("#app");
    app.replaceChildren();
    if (!state.auth) return viewAuth(app);
    if (state.view === "restaurants" && isCustomer()) return viewRestaurants(app);
    if (state.view === "menu" && isCustomer()) return viewMenu(app);
    if (state.view === "orders" && isCustomer()) return viewOrders(app, "customer");
    if (state.view === "store" && isOwner()) return viewStore(app);
    if (state.view === "received" && isOwner()) return viewOrders(app, "owner");
    return setView(isOwner() ? "store" : "restaurants"); // tela que o perfil não pode abrir
  }

  /* ---------- login e cadastro ---------- */
  function viewAuth(app) {
    const registering = state.authTab === "register";
    const owner = state.authKind === "LOJISTA";

    const pitch = el("section", { class: "auth__pitch" },
      el("h1", {}, "Comida boa, ", el("b", {}, "um clique"), " de distância."),
      el("p", {}, "Entre para pedir dos seus restaurantes favoritos ou cadastre a sua loja e comece a vender."),
      el("ul", { class: "pitch-list" },
        el("li", {}, el("span", {}, "🛵"), el("div", {}, el("b", {}, "Para clientes"), el("small", {}, "Veja os restaurantes, monte o carrinho e acompanhe cada etapa do pedido."))),
        el("li", {}, el("span", {}, "🏪"), el("div", {}, el("b", {}, "Para donos de loja"), el("small", {}, "Cadastre o seu CNPJ, monte o cardápio e gerencie os pedidos recebidos.")))));

    const tabs = el("div", { class: "tabs", role: "tablist" },
      el("button", { class: `tab${!registering ? " is-active" : ""}`, id: "tab-login", role: "tab", onclick: () => { state.authTab = "login"; render(); } }, "Entrar"),
      el("button", { class: `tab${registering ? " is-active" : ""}`, id: "tab-register", role: "tab", onclick: () => { state.authTab = "register"; render(); } }, "Criar conta"));

    const card = el("section", { class: "auth__card" }, tabs, registering ? registerForm(owner) : loginForm(),
      el("div", { class: "divider" }, "ou teste agora"),
      el("div", { class: "demo" },
        el("button", { class: "btn btn--ghost btn--sm", id: "demo-customer", onclick: () => demoLogin("CLIENTE") }, "👤 Cliente de demonstração"),
        el("button", { class: "btn btn--ghost btn--sm", id: "demo-owner", onclick: () => demoLogin("LOJISTA") }, "🏪 Lojista de demonstração")),
      el("div", { class: "notice" }, "As contas de demonstração são criadas automaticamente, com restaurantes de exemplo."));

    app.append(el("div", { class: "auth" }, pitch, card));
  }

  function field(label, input, hint) {
    return el("label", { class: "field" }, label, input, hint);
  }

  function loginForm() {
    const email = el("input", { class: "input", id: "login-email", type: "email", placeholder: "voce@email.com", autocomplete: "username", required: true });
    const password = el("input", { class: "input", id: "login-password", type: "password", placeholder: "Sua senha", autocomplete: "current-password", required: true });
    return el("form", { class: "form", id: "form-login", onsubmit: async (e) => {
      e.preventDefault();
      try { startSession(await post(AUTH, "/auth/login", { email: email.value, password: password.value })); }
      catch (error) { toast(error.message, "err"); }
    } },
      field("E-mail", email), field("Senha", password),
      el("button", { class: "btn btn--block", type: "submit" }, "Entrar"));
  }

  function registerForm(owner) {
    const kind = el("div", { class: "kind" },
      el("button", { type: "button", class: `kind__opt${!owner ? " is-active" : ""}`, id: "kind-customer", onclick: () => { state.authKind = "CLIENTE"; render(); } }, el("span", {}, "🛵"), "Sou cliente"),
      el("button", { type: "button", class: `kind__opt${owner ? " is-active" : ""}`, id: "kind-owner", onclick: () => { state.authKind = "LOJISTA"; render(); } }, el("span", {}, "🏪"), "Sou dono de loja"));

    const name = el("input", { class: "input", id: "reg-name", placeholder: owner ? "Nome do responsável" : "Seu nome", maxlength: "100", autocomplete: "name" });
    const email = el("input", { class: "input", id: "reg-email", type: "email", placeholder: "voce@email.com", autocomplete: "username" });
    const password = el("input", { class: "input", id: "reg-password", type: "password", placeholder: "Mínimo de 8 caracteres", autocomplete: "new-password" });
    const company = el("input", { class: "input", id: "reg-company", placeholder: "Ex.: Burger Dev Ltda", maxlength: "100" });
    const cnpj = el("input", { class: "input", id: "reg-cnpj", placeholder: "00.000.000/0000-00", inputmode: "text", autocomplete: "off", maxlength: "18" });
    const cnpjHint = el("span", { class: "hint", id: "cnpj-hint" }, "Digite os 14 caracteres do CNPJ.");

    cnpj.addEventListener("input", () => {
      cnpj.value = maskCnpj(cnpj.value);
      const size = normalizeCnpj(cnpj.value).length;
      cnpjHint.className = "hint";
      if (size < 14) cnpjHint.textContent = size ? `${size}/14 caracteres` : "Digite os 14 caracteres do CNPJ.";
      else if (isValidCnpj(cnpj.value)) { cnpjHint.textContent = "✓ Formato de CNPJ válido"; cnpjHint.classList.add("is-ok"); }
      else { cnpjHint.textContent = "✗ CNPJ inválido: confira os números"; cnpjHint.classList.add("is-bad"); }
    });

    return el("form", { class: "form", id: "form-register", novalidate: true, onsubmit: async (e) => {
      e.preventDefault();
      if (name.value.trim().length < 2) return toast("Informe o seu nome.", "err");
      if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email.value.trim())) return toast("Informe um e-mail válido.", "err");
      if (password.value.length < 8) return toast("A senha precisa ter pelo menos 8 caracteres.", "err");
      let path = "/auth/register/customer";
      const body = { name: name.value, email: email.value, password: password.value };
      if (owner) {
        if (company.value.trim().length < 2) return toast("Informe o nome da empresa.", "err");
        if (!isValidCnpj(cnpj.value)) return toast("CNPJ inválido. Confira os números.", "err");
        path = "/auth/register/owner";
        Object.assign(body, { company_name: company.value, cnpj: cnpj.value });
      }
      try { startSession(await post(AUTH, path, body)); }
      catch (error) { toast(error.message, "err"); }
    } },
      kind,
      field(owner ? "Responsável" : "Nome", name),
      owner ? field("Nome da empresa", company) : null,
      owner ? field("CNPJ", cnpj, cnpjHint) : null,
      field("E-mail", email), field("Senha", password),
      owner ? el("div", { class: "notice" }, "O CNPJ é obrigatório para criar uma conta de lojista. Conferimos o formato e os dígitos verificadores.") : null,
      el("button", { class: "btn btn--block", type: "submit" }, owner ? "Criar conta de lojista" : "Criar conta de cliente"));
  }

  /* Entra numa conta de demonstração; se ela ainda não existir, cria. */
  async function loginOrRegister(creds, role) {
    try {
      return await post(AUTH, "/auth/login", { email: creds.email, password: creds.password });
    } catch (error) {
      if (error.status !== 401) throw error;
      return post(AUTH, role === "LOJISTA" ? "/auth/register/owner" : "/auth/register/customer", creds);
    }
  }

  async function demoLogin(role) {
    try {
      if (role === "CLIENTE") {
        // O cliente precisa ter o que ver: garantimos antes os restaurantes do lojista de demonstração.
        toast("Preparando os dados de demonstração…");
        const owner = await loginOrRegister(DEMO_OWNER, "LOJISTA");
        await seedSamples(owner.access_token);
        startSession(await loginOrRegister(DEMO_CUSTOMER, "CLIENTE"));
      } else {
        startSession(await loginOrRegister(DEMO_OWNER, "LOJISTA"));
      }
    } catch (error) { toast(error.message, "err"); }
  }

  /* Cria (sem duplicar) os restaurantes de exemplo na conta dona do token. */
  async function seedSamples(token) {
    const mine = await api(CATALOG, "/restaurants/mine", { token });
    for (const sample of SAMPLE) {
      let restaurant = mine.find((r) => r.name === sample.name);
      if (!restaurant) {
        try { restaurant = await post(CATALOG, "/restaurants", { name: sample.name, category: sample.category }, token); }
        catch (error) { if (error.status === 409) continue; throw error; } // nome já usado por outra loja
      }
      const existing = await api(CATALOG, `/restaurants/${restaurant.id}/products`, { token });
      for (const [name, price] of sample.products) {
        if (!existing.some((p) => p.name === name)) await post(CATALOG, `/restaurants/${restaurant.id}/products`, { name, price }, token);
      }
    }
  }

  /* ---------- cliente: restaurantes e cardápio ---------- */
  function emptyCatalog() {
    return el("div", { class: "empty" },
      el("div", { class: "empty__emoji" }, "🍽️"),
      el("h3", {}, "Ainda não há restaurantes"),
      el("span", {}, "Assim que um dono de loja cadastrar o cardápio, ele aparece aqui."));
  }

  async function viewRestaurants(app) {
    app.append(
      el("section", { class: "hero" },
        el("h1", {}, `Olá, ${state.auth.user.name.split(" ")[0]}! Peça sua comida favorita, `, el("b", {}, "rápido"), "."),
        el("p", {}, "Escolha um restaurante, monte o pedido e acompanhe cada etapa até chegar na sua mesa.")));

    try { await loadCatalog(); } catch (error) { toast(error.message, "err"); }
    if (state.catalogError) app.append(el("div", { class: "banner" }, "Não consegui falar com o Catalog Service (porta 8001). Confira se os serviços estão rodando."));

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
        const match = !term || r.name.toLowerCase().includes(term) || r.category.toLowerCase().includes(term) || dishes.some((d) => d.includes(term));
        return inCategory && match;
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
      el("div", { class: "section-head" }, el("div", {}, el("h1", { class: "page-title" }, `${emojiFor(restaurant.category)} ${restaurant.name}`), el("p", { class: "page-sub" }, restaurant.category))));
    if (!products.length) { app.append(el("div", { class: "empty" }, el("h3", {}, "Cardápio vazio"), el("span", {}, "Este restaurante ainda não cadastrou pratos."))); return; }
    app.append(el("div", { class: "grid" }, products.map((p) =>
      el("article", { class: "card" },
        el("div", { class: "card__emoji" }, emojiFor(restaurant.category)),
        el("div", { class: "card__title" }, p.name),
        el("div", { class: "row" }, el("span", { class: "price" }, money(p.price)),
          el("button", { class: "btn btn--sm", onclick: () => addToCart(p, restaurant) }, "+ Adicionar"))))));
  }

  /* ---------- pedidos (cliente e lojista) ---------- */
  async function viewOrders(app, mode) {
    const select = el("select", { class: "input", id: "status-filter", style: "max-width: 220px", "aria-label": "Filtrar por status", onchange: (e) => { state.statusFilter = e.target.value; renderOrdersList(mode); } },
      el("option", { value: "" }, "Todos os status"),
      Object.entries(STATUS_LABEL).map(([value, label]) => el("option", { value, selected: state.statusFilter === value }, label)));

    app.append(
      el("div", { class: "section-head" },
        el("div", {},
          el("h1", { class: "page-title" }, mode === "owner" ? "Pedidos recebidos" : "Meus pedidos"),
          el("p", { class: "page-sub" }, mode === "owner" ? "Pedidos feitos nos seus restaurantes. Atualiza sozinho a cada 5 segundos." : "Acompanhe cada etapa. Atualiza sozinho a cada 5 segundos.")),
        select),
      mode === "owner" ? el("div", { class: "stats", id: "stats" }) : null,
      el("div", { class: "orders", id: "orders-list" }));
    await refreshOrders(mode);
  }

  async function refreshOrders(mode) {
    if (!$("#orders-list")) return;
    try { await loadOrders(); }
    catch (error) {
      if ($("#orders-list")) $("#orders-list").replaceChildren(el("div", { class: "banner" }, `Não consegui carregar os pedidos: ${error.message}`));
      return;
    }
    renderOrdersList(mode);
  }

  function renderOrdersList(mode) {
    const holder = $("#orders-list");
    if (!holder) return;

    const stats = $("#stats");
    if (stats) {
      const count = (...s) => state.orders.filter((o) => s.includes(o.status)).length;
      const sales = state.orders.filter((o) => o.status === "ENTREGUE").reduce((sum, o) => sum + o.total, 0);
      stats.replaceChildren(
        ...[[count("CRIADO"), "Novos pedidos"], [count("PREPARANDO", "A_CAMINHO"), "Em andamento"], [count("ENTREGUE"), "Entregues"], [money(sales), "Vendas concluídas"]]
          .map(([value, label]) => el("div", { class: "stat" }, el("b", {}, value), el("span", {}, label))));
    }

    const shown = state.orders.filter((o) => !state.statusFilter || o.status === state.statusFilter);
    holder.replaceChildren();
    if (!shown.length) {
      holder.append(el("div", { class: "empty" }, el("div", { class: "empty__emoji" }, "🧾"),
        el("h3", {}, state.orders.length ? "Nenhum pedido com esse status" : "Nenhum pedido por aqui"),
        el("span", {}, mode === "owner" ? "Quando um cliente pedir de uma das suas lojas, o pedido aparece aqui." : "Faça um pedido na aba Restaurantes."),
        mode === "customer" ? el("button", { class: "btn", onclick: () => setView("restaurants") }, "Ver restaurantes") : null));
      return;
    }
    for (const order of [...shown].reverse()) holder.append(orderCard(order, mode));
  }

  function orderCard(order, mode) {
    const cancelled = order.status === "CANCELADO";
    const index = FLOW.indexOf(order.status);
    const stepper = cancelled ? null : el("div", { class: "stepper" }, FLOW.map((s, i) =>
      el("div", { class: `step${i <= index ? " is-done" : ""}${i === index ? " is-current" : ""}` }, el("div", { class: "step__bar" }), STATUS_LABEL[s])));

    const options = (mode === "owner" ? OWNER_ACTIONS : CUSTOMER_ACTIONS)[order.status] || [];
    const actions = el("div", { class: "actions" }, options.map(([next, label, risky]) =>
      el("button", { class: `btn btn--sm${risky ? " btn--danger" : ""}`, "data-next": next, onclick: () => changeStatus(order.id, next, mode) }, label)));
    if (mode === "customer" && !options.length && !["ENTREGUE", "CANCELADO"].includes(order.status)) {
      actions.append(el("span", { class: "notice" }, "O restaurante já aceitou o pedido."));
    }

    const who = mode === "owner" ? `Cliente: ${order.customer}` : order.restaurant_name;
    return el("article", { class: "order" },
      el("div", { class: "order__head" },
        el("div", {}, el("div", { class: "order__id" }, `Pedido #${order.id}`), el("div", { class: "order__date" }, `${who} · ${parseDate(order.created_at).toLocaleString("pt-BR")}`)),
        el("span", { class: `badge badge--${order.status}` }, STATUS_LABEL[order.status])),
      stepper,
      el("ul", { class: "order__items" }, order.items.map((i) =>
        el("li", {}, el("span", {}, `${i.quantity}× ${i.product_name}`), el("span", {}, money(i.quantity * i.unit_price))))),
      el("div", { class: "order__foot" }, el("div", { class: "price" }, money(order.total)), actions));
  }

  async function changeStatus(orderId, status, mode) {
    try {
      await api(ORDERS, `/orders/${orderId}/status`, { method: "PATCH", body: JSON.stringify({ status }) });
      toast(`Pedido #${orderId}: ${STATUS_LABEL[status]}`, "ok");
    } catch (error) { toast(error.message, "err"); }
    await refreshOrders(mode);
  }

  /* ---------- lojista: minha loja ---------- */
  async function viewStore(app) {
    const u = state.auth.user;
    app.append(el("div", { class: "section-head" },
      el("div", {}, el("h1", { class: "page-title" }, `🏪 ${u.company_name || "Minha loja"}`), el("p", { class: "page-sub" }, `CNPJ ${u.cnpj || "—"} · Responsável: ${u.name}`))));

    try { await loadMyStore(); } catch (error) { app.append(el("div", { class: "banner" }, error.message)); return; }

    const rName = el("input", { class: "input", id: "r-name", placeholder: "Ex.: Burger Dev", maxlength: "100" });
    const rCat = el("input", { class: "input", id: "r-cat", placeholder: "Ex.: Lanches", maxlength: "50", list: "cats" });
    const datalist = el("datalist", { id: "cats" }, ["Lanches", "Pizza", "Japonesa", "Sobremesas", "Bebidas", "Saudável"].map((c) => el("option", { value: c })));

    const newStore = el("form", { class: "panel", id: "form-restaurant", onsubmit: async (e) => {
      e.preventDefault();
      try {
        await post(CATALOG, "/restaurants", { name: rName.value.trim(), category: rCat.value.trim() });
        toast("Restaurante cadastrado!", "ok");
        render();
      } catch (error) { toast(error.message, "err"); }
    } },
      el("h3", {}, "➕ Novo restaurante"),
      el("div", { class: "admin-grid" }, field("Nome", rName), field("Categoria", rCat, datalist)),
      el("div", { class: "actions" },
        el("button", { class: "btn", type: "submit" }, "Cadastrar restaurante"),
        el("button", { class: "btn btn--ghost", type: "button", id: "seed-store", onclick: async () => {
          try { await seedSamples(state.auth.token); toast("Lojas de exemplo criadas!", "ok"); render(); }
          catch (error) { toast(error.message, "err"); }
        } }, "⚡ Criar lojas de exemplo")));

    const stores = el("div", { class: "stack", id: "my-stores" });
    if (!state.myRestaurants.length) {
      stores.append(el("div", { class: "empty" }, el("div", { class: "empty__emoji" }, "🏪"), el("h3", {}, "Você ainda não tem restaurantes"), el("span", {}, "Cadastre o primeiro acima ou crie lojas de exemplo para testar.")));
    }
    for (const r of state.myRestaurants) stores.append(storePanel(r));
    app.append(newStore, stores);
  }

  function storePanel(restaurant) {
    const products = state.myProducts[restaurant.id] || [];
    const pName = el("input", { class: "input", placeholder: "Nome do prato", maxlength: "100", "aria-label": "Nome do prato", "data-role": "p-name" });
    const pPrice = el("input", { class: "input", type: "number", min: "0.01", step: "0.01", placeholder: "Preço", "aria-label": "Preço", "data-role": "p-price" });

    return el("section", { class: "store", "data-restaurant": restaurant.id },
      el("div", { class: "store__head" },
        el("div", {}, el("h3", { class: "card__title" }, `${emojiFor(restaurant.category)} ${restaurant.name}`), el("span", { class: "tag" }, restaurant.category)),
        el("span", { class: "chip-id" }, `${products.length} ${products.length === 1 ? "prato" : "pratos"}`)),
      products.length
        ? el("ul", { class: "menu-list" }, products.map((p) => el("li", {}, el("span", {}, p.name), el("b", {}, money(p.price)))))
        : el("span", { class: "notice" }, "Cardápio vazio. Adicione o primeiro prato abaixo."),
      el("form", { class: "inline-form", onsubmit: async (e) => {
        e.preventDefault();
        try {
          await post(CATALOG, `/restaurants/${restaurant.id}/products`, { name: pName.value.trim(), price: Number(pPrice.value) });
          toast("Prato cadastrado!", "ok");
          render();
        } catch (error) { toast(error.message, "err"); }
      } }, pName, pPrice, el("button", { class: "btn btn--sm", type: "submit" }, "+ Adicionar prato")));
  }

  /* ---------- início ---------- */
  async function init() {
    $("#doc-catalog").href = `${CATALOG}/docs`;
    $("#doc-orders").href = `${ORDERS}/docs`;
    $("#doc-auth").href = `${AUTH}/docs`;

    $("#brand").addEventListener("click", (e) => { e.preventDefault(); if (state.auth) setView(isOwner() ? "store" : "restaurants"); });
    $("#cart-open").addEventListener("click", () => openCart(true));
    $("#cart-close").addEventListener("click", () => openCart(false));
    $("#overlay").addEventListener("click", () => openCart(false));
    document.addEventListener("keydown", (e) => { if (e.key === "Escape") openCart(false); });

    ping();
    setInterval(ping, 10000);
    setInterval(() => {
      if (!state.auth) return;
      if (state.view === "orders") refreshOrders("customer");
      if (state.view === "received") refreshOrders("owner");
    }, 5000);

    loadSession();
    if (state.auth) {
      restoreCart();
      try { // confere se a sessão guardada ainda vale
        state.auth.user = await api(AUTH, "/auth/me");
        saveSession();
      } catch { state.auth = null; saveSession(); }
    }
    setupShell();
    setView(!state.auth ? "login" : isOwner() ? "store" : "restaurants");
  }

  init();
})();
