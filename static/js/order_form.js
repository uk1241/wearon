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

    var subtotalEl = document.getElementById("subtotal-display");
    var grandEl = document.getElementById("grand-total-display");
    if (subtotalEl) subtotalEl.textContent = "₹" + subtotal.toFixed(2);
    if (grandEl) grandEl.textContent = "₹" + grand.toFixed(2);
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

  document.addEventListener("DOMContentLoaded", function () {
    recalcTotals();

    document.getElementById("items-body").addEventListener("input", function (e) {
      if (e.target.classList.contains("item-qty") || e.target.classList.contains("item-rate")) {
        recalcTotals();
      }
    });

    var discountInput = document.querySelector('input[name="discount_percent"]');
    if (discountInput) discountInput.addEventListener("input", recalcTotals);

    var addBtn = document.getElementById("add-item-row");
    if (addBtn) addBtn.addEventListener("click", addItemRow);
  });
})();
