(function () {
  function num(value) {
    var n = parseFloat(value);
    return isNaN(n) ? 0 : n;
  }

  function recalcRow(row) {
    var qtyInput = row.querySelector(".item-qty");
    var rateInput = row.querySelector(".item-rate");
    var amountEl = row.querySelector(".row-amount");
    if (!qtyInput || !rateInput || !amountEl) return 0;
    var amount = num(qtyInput.value) * num(rateInput.value);
    amountEl.textContent = amount.toFixed(2);
    return amount;
  }

  function recalcTotals() {
    var subtotal = 0;
    document.querySelectorAll("#items-body .item-row").forEach(function (row) {
      subtotal += recalcRow(row);
    });
    var discountInput = document.querySelector('input[name="discount_percent"]');
    var discountPct = discountInput ? num(discountInput.value) : 0;
    var grand = subtotal - subtotal * (discountPct / 100);
    var amountPaidInput = document.querySelector('input[name="amount_paid"]');
    var amountPaid = amountPaidInput ? num(amountPaidInput.value) : 0;
    var amountDue = grand - amountPaid;

    var subtotalEl = document.getElementById("subtotal-display");
    var grandEl = document.getElementById("grand-total-display");
    var dueEl = document.getElementById("amount-due-display");
    if (subtotalEl) subtotalEl.textContent = "₹" + subtotal.toFixed(2);
    if (grandEl) grandEl.textContent = "₹" + grand.toFixed(2);
    if (dueEl) dueEl.textContent = "₹" + amountDue.toFixed(2);
  }

  window.removeFormRow = function (button, tbodyId) {
    var row = button.closest("tr");
    var deleteCheckbox = row.querySelector('input[type="checkbox"][name$="-DELETE"]');
    if (deleteCheckbox) {
      deleteCheckbox.checked = true;
      row.style.display = "none";
    } else {
      row.remove();
    }
    recalcTotals();
  };

  function addItemRow() {
    var totalFormsInput = document.getElementById("id_items-TOTAL_FORMS");
    if (!totalFormsInput) return;
    var index = parseInt(totalFormsInput.value, 10);
    var templateEl = document.getElementById("empty-item-row");
    var html = templateEl.innerHTML.split("__prefix__").join(index);

    var wrapper = document.createElement("tbody");
    wrapper.innerHTML = html.trim();
    var newRow = wrapper.querySelector("tr");
    var rowNum = newRow.querySelector(".row-num");
    if (rowNum) rowNum.textContent = index + 1;

    document.getElementById("items-body").appendChild(newRow);
    totalFormsInput.value = index + 1;
    recalcTotals();
  }

  function addPaymentRow() {
    var totalFormsInput = document.getElementById("id_payments-TOTAL_FORMS");
    if (!totalFormsInput) return;
    var index = parseInt(totalFormsInput.value, 10);
    var templateEl = document.getElementById("empty-payment-row");
    var html = templateEl.innerHTML.split("__prefix__").join(index);

    var wrapper = document.createElement("tbody");
    wrapper.innerHTML = html.trim();
    var newRow = wrapper.querySelector("tr");
    var rowNum = newRow.querySelector(".row-num");
    if (rowNum) rowNum.textContent = index + 1;

    document.getElementById("payments-body").appendChild(newRow);
    totalFormsInput.value = index + 1;
  }

  document.addEventListener("DOMContentLoaded", function () {
    recalcTotals();

    document.getElementById("items-body").addEventListener("input", function (e) {
        if (e.target.classList.contains("item-qty") || e.target.classList.contains("item-rate")) {
          recalcTotals();
        }
        // when item name is entered/selected try to fetch product price
        if (e.target.classList.contains("item-name")) {
          var name = e.target.value && e.target.value.trim();
          if (!name) return;
          var row = e.target.closest("tr");
          // fetch price from server
          fetch("/products/price/?name=" + encodeURIComponent(name)).then(function (resp) {
            if (!resp.ok) return null;
            return resp.json();
          }).then(function (data) {
            if (!data || !data.price) return;
            var rateInput = row.querySelector('.item-rate');
            if (rateInput) {
              rateInput.value = parseFloat(data.price).toFixed(2);
              recalcTotals();
            }
          }).catch(function (err) {
            // ignore fetch errors silently
            console.warn('price fetch failed', err);
          });
        }
    });

    var discountInput = document.querySelector('input[name="discount_percent"]');
    if (discountInput) discountInput.addEventListener("input", recalcTotals);
    var amountPaidInput = document.querySelector('input[name="amount_paid"]');
    if (amountPaidInput) amountPaidInput.addEventListener("input", recalcTotals);

    var paymentMethodSelect = document.querySelector('select[name="payment_method"]');
    var paymentDetailsRow = document.getElementById("payment-details-row");
    if (paymentMethodSelect) {
      function updatePaymentDetailsVisibility() {
        if (paymentMethodSelect.value === "other") {
          paymentDetailsRow.style.display = "flex";
        } else {
          paymentDetailsRow.style.display = "none";
        }
      }
      paymentMethodSelect.addEventListener("change", updatePaymentDetailsVisibility);
      updatePaymentDetailsVisibility();
    }

    var addBtn = document.getElementById("add-item-row");
    if (addBtn) addBtn.addEventListener("click", addItemRow);
    var addPaymentBtn = document.getElementById("add-payment-row");
    if (addPaymentBtn) addPaymentBtn.addEventListener("click", addPaymentRow);
  });
})();
