const CATALOG = "http://localhost:8001";
    const ORDER = "http://localhost:8002";
    const PAYMENT = "http://localhost:8003";
    const NOTIF = "http://localhost:8004";

    let socket = null;
    let pendingOrder = null;
    let pendingItem = null;
    let favoriteIds = new Set();
    let currentUser = localStorage.getItem("shc_user") || "carol";

    const $ = (id) => document.getElementById(id);

    function esc(s) {
      return String(s ?? "").replace(/[&<>"']/g, c => ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;" }[c]));
    }
    function money(n) { return "$" + Number(n).toFixed(2); }
    function toast(msg, type = "") {
      const el = document.createElement("div");
      el.className = "toast " + type;
      el.innerHTML = msg;
      $("toasts").appendChild(el);
      setTimeout(() => el.remove(), 4200);
    }
    async function api(url, opts = {}) {
      const res = await fetch(url, opts);
      if (!res.ok) {
        let detail = res.statusText;
        try { detail = (await res.json()).detail || detail; } catch (_) {}
        throw new Error(detail);
      }
      if (res.status === 204) return null;
      return res.json();
    }
    const jsonOpts = (body, method = "POST") => ({ method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

    //Navigation
    function showPage(name) {
      document.querySelectorAll(".page").forEach(p => p.classList.remove("active"));
      const pg = $("page-" + name);
      if (pg) pg.classList.add("active");
      document.querySelectorAll(".nav-btn").forEach(b => b.classList.toggle("active", b.dataset.page === name));
      if (name === "catalog") loadCatalog();
      if (name === "sell") loadMyListings();
      if (name === "profile") { loadFavorites(); loadSoldItems(); loadHistory(); loadMyListings(); loadNotifications(); }
    }

    //Account/socket
    function updateAccountUI() {
      const inp = $("accountName");
      if (inp) inp.value = currentUser;
      const rt = $("rtStatus");
      if (rt) { rt.className = "badge offline"; rt.textContent = "Offline"; }
    }

    function connectSocket() {
      if (socket) socket.disconnect();
      socket = io(NOTIF, { query: { user: currentUser, role: "buyer" } });
      socket.on("connect", () => {
        socket.emit("join", { room: "seller-" + currentUser });
        const rt = $("rtStatus");
        if (rt) { rt.className = "badge online"; rt.textContent = "Online - " + currentUser; }
        toast("Connected as " + esc(currentUser), "ok");
        loadFavorites();
        loadSoldItems();
        loadHistory();
        loadMyListings();
        loadNotifications();
      });
      socket.on("disconnect", () => {
        const rt = $("rtStatus");
        if (rt) { rt.className = "badge offline"; rt.textContent = "Offline"; }
      });
      socket.on("item-sold", (data) => {
        const id = data.item_id || data.itemId;
        const name = data.item_name || data.itemName || id;
        const isSeller = data.seller === currentUser;
        const isBuyer = data.buyer === currentUser;
        const isFav = favoriteIds.has(id);
        if (isSeller) {
          toast("Your item was sold.", "ok");
        }
        if (isBuyer) {
          toast("An item in your favorites was sold.", "ok");
        }
        if (isFav && !isBuyer && !isSeller) {
          toast('Your favorite item "' + esc(name) + '" has been sold', "bad");
        }
        loadCatalog();
        loadFavorites();
        loadSoldItems();
        loadHistory();
        loadMyListings();
        loadNotifications();
      });
      socket.on("item-deleted", (data) => {
        const id = data.item_id || data.itemId;
        const name = data.item_name || data.itemName || id;
        if (favoriteIds.has(id)) {
          toast('Your favorite item "' + esc(name) + '" has been removed', "bad");
        } else {
          toast("An item in your favorites was removed.", "bad");
        }
        loadCatalog();
        loadFavorites();
        loadNotifications();
      });
    }

    function changeAccount() {
      const name = ($("accountName").value || "").trim();
      if (!name) return toast("Enter a username.", "bad");
      currentUser = name;
      localStorage.setItem("shc_user", currentUser);
      updateAccountUI();
      connectSocket();
      loadCatalog();
      loadFavorites();
      loadSoldItems();
      loadHistory();
      loadMyListings();
      loadNotifications();
    }

    //Sell
    function updateSizeOptions() {
      const cat = $("itemCategory").value;
      const sizeSel = $("itemSize");
      let sizes = [];
      if (cat === "Shoes" || cat === "Sneakers") {
        for (let i = 30; i <= 45; i++) sizes.push("EUR " + i);
      } else if (cat === "Accessories" || cat === "Other") {
        sizes = ["One size"];
      } else {
        sizes = ["XXS", "XS", "S", "M", "L", "XL", "XXL", "One size"];
      }
      sizeSel.innerHTML = sizes.map(s => `<option value="${esc(s)}">${esc(s)}</option>`).join("");
    }

    async function publishItem() {
      const name = $("itemName").value.trim();
      const price = parseFloat($("itemPrice").value);
      const category = $("itemCategory").value;
      const size = $("itemSize").value;
      const condition = $("itemCondition").value;
      if (!name || !(price > 0)) return toast("Enter a name and a valid price.", "bad");
      try {
        await api(CATALOG + "/clothes", jsonOpts({ name, price, seller: currentUser, category, size, condition }));
        toast("Item published: " + esc(name), "ok");
        $("itemName").value = "";
        loadCatalog();
        loadMyListings();
        showPage("sell");
      } catch (e) { toast("Could not publish: " + esc(e.message), "bad"); }
    }

    async function deleteItem(id) {
      if (!confirm("Delete this item?")) return;
      try {
        await api(CATALOG + "/clothes/" + encodeURIComponent(id), { method: "DELETE" });
        toast("Item deleted", "ok");
        loadCatalog();
        loadMyListings();
        loadSoldItems();
      } catch (e) { toast("Could not delete: " + esc(e.message), "bad"); }
    }
    async function loadMyListings() {
      try {
        const items = await api(CATALOG + "/clothes?seller=" + encodeURIComponent(currentUser));
        const available = items.filter(i => i.status !== "Sold");
        const el = $("myListings");
        const cnt = $("myListingsCount");
        if (cnt) cnt.textContent = available.length;
        if (el) el.innerHTML = available.length ? available.map(i => `
          <div class="list-row">
            <div>
              <div class="main">${esc(i.name)}</div>
              <div class="sub">${money(i.price)} - ${esc(i.category || "uncategorized")} - ${esc(i.size || "")} - ${esc(i.condition || "")}</div>
            </div>
            <div style="display:flex;gap:6px;align-items:center;">
              <span class="badge available">For sale</span>
              <button class="danger small" onclick="deleteItem('${esc(i.id)}')">Delete</button>
            </div>
          </div>`).join("") : `<div class="empty">You have no items for sale.</div>`;
      } catch (e) {
        const el = $("myListings");
        if (el) el.innerHTML = `<div class="empty">Error: ${esc(e.message)}</div>`;
      }
    }

    async function loadSoldItems() {
      try {
        const items = await api(CATALOG + "/clothes?seller=" + encodeURIComponent(currentUser));
        const sold = items.filter(i => i.status === "Sold");
        const el = $("soldItems");
        const cnt = $("soldCount");
        if (cnt) cnt.textContent = sold.length;
        if (el) el.innerHTML = sold.length ? sold.map(i => `
          <div class="list-row">
            <div>
              <div class="main">${esc(i.name)}</div>
              <div class="sub">${money(i.price)} - ${esc(i.category || "uncategorized")} - ${esc(i.size || "")} - ${esc(i.condition || "")}</div>
            </div>
            <span class="badge sold">Sold</span>
          </div>`).join("") : `<div class="empty">You have not sold anything yet.</div>`;
      } catch (e) {
        const el = $("soldItems");
        if (el) el.innerHTML = `<div class="empty">Error: ${esc(e.message)}</div>`;
      }
    }

    async function deleteNotification(id) {
      try {
        await api(NOTIF + "/notifications/" + encodeURIComponent(id), { method: "DELETE" });
        await loadNotifications();
      } catch (e) { toast("Could not delete: " + esc(e.message), "bad"); }
    }
    async function clearNotifications() {
      try {
        await api(NOTIF + "/notifications/user/" + encodeURIComponent(currentUser), { method: "DELETE" });
        await loadNotifications();
        toast("Notifications cleared", "ok");
      } catch (e) { toast("Could not clear: " + esc(e.message), "bad"); }
    }
    function renderNotification(n) {
      if (n.event === "favorite_sold" || n.event === "favorite_deleted" || (n.seller == null && n.buyer === currentUser)) {
        return `Your favorite item "${esc(n.item_name || n.item_id)}" has been sold or removed`;
      }
      if (String(n.seller) === String(currentUser)) {
        return `Your item <b>${esc(n.item_name || n.item_id)}</b> was sold to <b>${esc(n.buyer)}</b> for ${money(n.amount)}`;
      }
      return `Update: ${esc(n.item_name || n.item_id)}`;
    }
    async function loadNotifications() {
      try {
        const items = await api(NOTIF + "/notifications/user/" + encodeURIComponent(currentUser));
        // Only show: favorite updates and sales of the user's own items.
        const relevant = items.filter(n => {
          if (n.event === "favorite_sold" || n.event === "favorite_deleted") return true;
          if (n.seller === currentUser) return true;
          return false;
        });
        const feed = $("notificationsFeed");
        if (!feed) return;
        if (!relevant.length) {
          feed.innerHTML = `<div class="empty">You will see your notifications here.</div>`;
          return;
        }
        feed.innerHTML = relevant.map(n => `
          <div class="feed-item" style="display:flex;justify-content:space-between;align-items:center;gap:8px;">
            <span>${renderNotification(n)}</span>
            <button class="ghost small" onclick="deleteNotification('${esc(n.id)}')">Delete</button>
          </div>`).join("");
      } catch (e) {
        const feed = $("notificationsFeed");
        if (feed) feed.innerHTML = `<div class="empty">Error: ${esc(e.message)}</div>`;
      }
    }

    //Catalog
    function itemCard(i) {
      const isFav = favoriteIds.has(i.id);
      const favLabel = isFav ? "Favorited" : "Favorite";
      const own = i.seller === currentUser;
      return `<div class="item-card" id="card-${esc(i.id)}">
        <div class="item-thumb">Item</div>
        <div class="item-name">${esc(i.name)}</div>
        <div class="item-meta">by ${esc(i.seller || "unknown")}${i.size ? " · " + esc(i.size) : ""}${i.condition ? " · " + esc(i.condition) : ""}</div>
        <span class="badge ${i.status === "Sold" ? "sold" : "available"}">${i.status}</span>
        <div class="item-price">${money(i.price)}</div>
        <div class="card-actions">
          <button class="fav-btn small ${isFav ? "active" : ""}" onclick="toggleFavorite('${esc(i.id)}')">${favLabel}</button>
          ${i.status !== "Sold" && !own
            ? `<button class="small" onclick="openPayment('${esc(i.id)}','${esc(i.name)}',${i.price},'${esc(i.seller)}')">Buy</button>` : ""}
          ${own && i.status !== "Sold" ? `<span class="badge pending">Your item</span>` : ""}
        </div>
      </div>`;
    }

    async function loadCatalog() {
      try {
        // Keep favorite state in sync with the catalog.
        try {
          const favs = await api(CATALOG + "/favorites/" + encodeURIComponent(currentUser));
          favoriteIds = new Set(favs.map(i => i.id));
        } catch (_) {}
        const term = $("searchInput").value.trim();
        const url = term
          ? CATALOG + "/clothes?q=" + encodeURIComponent(term)
          : CATALOG + "/clothes?status=Available";
        const items = await api(url);
        $("catalogCount").textContent = items.length + (items.length === 1 ? " item" : " items");
        $("catalog").innerHTML = items.length
          ? items.map(i => itemCard(i)).join("")
          : `<div class="empty">${term ? "No items match." : "The catalog is empty. Publish the first one."}</div>`;
      } catch (e) { $("catalog").innerHTML = `<div class="empty">Error: ${esc(e.message)}</div>`; }
    }
    function onSearch() { loadCatalog(); }

    //Favorites
    async function addFavorite(itemId) {
      await api(CATALOG + "/favorites", jsonOpts({ user: currentUser, item_id: itemId }));
    }
    async function removeFavorite(itemId) {
      await api(CATALOG + "/favorites/" + encodeURIComponent(currentUser) + "/" + encodeURIComponent(itemId), { method: "DELETE" });
    }
    async function toggleFavorite(itemId) {
      try {
        if (favoriteIds.has(itemId)) {
          favoriteIds.delete(itemId);
          await removeFavorite(itemId);
          toast("Removed from favorites", "ok");
        } else {
          favoriteIds.add(itemId);
          await addFavorite(itemId);
          toast("Added to favorites", "ok");
        }
        await loadFavorites();
        await loadCatalog();
      } catch (e) {
        toast("Could not update favorites: " + esc(e.message), "bad");
        await loadFavorites();
        await loadCatalog();
      }
    }
    async function loadFavorites() {
      try {
        const all = await api(CATALOG + "/favorites/" + encodeURIComponent(currentUser));
        favoriteIds = new Set(all.map(i => i.id));
        const items = all.filter(i => i.status !== "Sold");
        $("favCount").textContent = items.length;
        $("favorites").innerHTML = items.length
          ? items.map(i => itemCard(i)).join("")
          : `<div class="empty">No favorites yet. Favorite any item.</div>`;
      } catch (e) { $("favorites").innerHTML = `<div class="empty">Error: ${esc(e.message)}</div>`; }
    }

    //History
    async function loadHistory() {
      try {
        const orders = await api(ORDER + "/orders/buyer/" + encodeURIComponent(currentUser));
        const purchased = orders.filter(o => o.paid === true || o.status === "Paid");
        $("historyCount").textContent = purchased.length;
        $("history").innerHTML = purchased.length ? purchased.map(o => `
          <div class="list-row">
            <div>
              <div class="main">${esc(o.item_name || o.item_id)} - ${money(o.amount)}</div>
              <div class="sub">Order ${esc(o.id).slice(-8)} - ${new Date(o.created_at).toLocaleString()}</div>
            </div>
            <span class="badge paid">Purchased</span>
          </div>`).join("") : `<div class="empty">No purchases yet.</div>`;
      } catch (e) { $("history").innerHTML = `<div class="empty">Error: ${esc(e.message)}</div>`; }
    }

    //Payment flow
    function formatCard() {
      const el = $("cardNumber");
      let digits = el.value.replace(/\D/g, "").slice(0, 19);
      el.value = digits.replace(/(.{4})/g, "$1 ").trim();
      $("previewNumber").textContent = el.value || ".... .... .... ....";
    }
    function formatExpiry() {
      const el = $("cardExpiry");
      let d = el.value.replace(/\D/g, "").slice(0, 4);
      if (d.length > 2) d = d.slice(0, 2) + "/" + d.slice(2);
      el.value = d;
      $("previewExpiry").textContent = d || "MM/YY";
    }
    function formatCvv() {
      const el = $("cardCvv");
      el.value = el.value.replace(/\D/g, "").slice(0, 4);
      $("previewCvv").textContent = el.value || "...";
    }

    function openPayment(itemId, itemName, price, seller) {
      $("payError").textContent = "";
      $("payBtn").disabled = false;
      $("payBtn").textContent = "Pay " + money(price);
      pendingItem = { itemId, itemName, price, seller };
      $("sumItem").textContent = itemName;
      $("sumSeller").textContent = seller || "unknown";
      $("sumOrder").textContent = "-";
      $("sumTotal").textContent = money(price);
      $("paymentModal").classList.remove("hidden");
    }
    function closePayment() {
      $("paymentModal").classList.add("hidden");
      pendingItem = null;
    }
    async function confirmPayment() {
      if (!pendingItem) return;
      const btn = $("payBtn");
      btn.disabled = true;
      btn.textContent = "Processing...";
      $("payError").textContent = "";
      const cardNumber = $("cardNumber").value.replace(/\D/g, "");
      const cvv = $("cardCvv").value;
      if (cardNumber.length !== 16) {
        $("payError").textContent = "Card number must be 16 digits.";
        btn.disabled = false;
        btn.textContent = "Retry payment";
        return;
      }
      try {
        const order = await api(ORDER + "/orders", jsonOpts({
          item_id: pendingItem.itemId, item_name: pendingItem.itemName, item_price: pendingItem.price,
          buyer: currentUser, seller: pendingItem.seller, amount: pendingItem.price
        }));
        const pay = await api(PAYMENT + "/payments", jsonOpts({
          orderId: order.id,
          amount: order.amount,
          cardNumber,
          cvv
        }));
        if (pay.status === "Approved") {
          toast("Payment approved. Item marked as sold.", "ok");
          $("paymentModal").classList.add("hidden");
          pendingItem = null;
          loadCatalog();
          loadFavorites();
          loadSoldItems();
          loadHistory();
          loadMyListings();
        } else {
          $("payError").textContent = "Payment declined. Try another card.";
          btn.disabled = false;
          btn.textContent = "Retry payment";
          loadHistory();
        }
      } catch (e) {
        $("payError").textContent = e.message;
        btn.disabled = false;
        btn.textContent = "Retry payment";
      }
    }

    //Init
    updateAccountUI();
    connectSocket();
    updateSizeOptions();
    loadCatalog();
    loadMyListings();
    loadNotifications();
