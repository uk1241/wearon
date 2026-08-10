(function () {
  function num(value) {
    var n = parseFloat(value);
    return isNaN(n) ? 0 : n;
  }

  function recalcRow(row) {
    var qtyInput = row.querySelector(".exp-qty");
    var costInput = row.querySelector(".exp-cost");
    var amountEl = row.querySelector(".row-amount");
    if (!qtyInput || !costInput || !amountEl) return 0;
    var amount = num(qtyInput.value) * num(costInput.value);
    amountEl.textContent = amount.toFixed(2);
    return amount;
  }

  function formatMoney(value) {
    return "₹" + value.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  function recalcTotals() {
    var totalExpenses = 0;
    document.querySelectorAll("#expenses-body .expense-row").forEach(function (row) {
      totalExpenses += recalcRow(row);
    });

    var revenue = window.ORDER_REVENUE || 0;
    var netProfit = revenue - totalExpenses;
    var margin = revenue > 0 ? (netProfit / revenue) * 100 : 0;

    var totalExpEl = document.getElementById("total-expenses-display");
    var netProfitEl = document.getElementById("net-profit-display");
    var marginEl = document.getElementById("profit-margin-display");
    var marginMsgEl = document.getElementById("profit-margin-message");

    if (totalExpEl) totalExpEl.textContent = formatMoney(totalExpenses);
    if (netProfitEl) netProfitEl.textContent = formatMoney(netProfit);
    if (marginEl) marginEl.textContent = margin.toFixed(1) + "%";
    if (marginMsgEl) {
      marginMsgEl.textContent =
        margin >= 45 ? "Healthy margin. Target is >45%." : "Below target margin of 45%.";
    }
  }

  window.removeFormRow = function (button) {
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

  function addExpenseRow() {
    var totalFormsInput = document.getElementById("id_expenses-TOTAL_FORMS");
    if (!totalFormsInput) return;
    var index = parseInt(totalFormsInput.value, 10);
    var templateEl = document.getElementById("empty-expense-row");
    var html = templateEl.innerHTML.split("__prefix__").join(index);

    var wrapper = document.createElement("tbody");
    wrapper.innerHTML = html.trim();
    var newRow = wrapper.querySelector("tr");

    document.getElementById("expenses-body").appendChild(newRow);
    totalFormsInput.value = index + 1;
    recalcTotals();
  }

  document.addEventListener("DOMContentLoaded", function () {
    recalcTotals();

    document.getElementById("expenses-body").addEventListener("input", function (e) {
      if (e.target.classList.contains("exp-qty") || e.target.classList.contains("exp-cost")) {
        recalcTotals();
      }
    });

    var addBtn = document.getElementById("add-expense-row");
    if (addBtn) addBtn.addEventListener("click", addExpenseRow);
  });
})();
