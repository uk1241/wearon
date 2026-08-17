(function () {
  var lastSummary = null;

  function fetchSummary() {
    var employeeSelect = document.querySelector('select[name="employee"]');
    var startInput = document.querySelector('input[name="pay_period_start"]');
    var endInput = document.querySelector('input[name="pay_period_end"]');
    var card = document.getElementById("attendance-summary-card");
    if (!employeeSelect || !startInput || !endInput || !card) return;

    var employeeId = employeeSelect.value;
    var start = startInput.value;
    var end = endInput.value;
    if (!employeeId || !start || !end) {
      card.style.display = "none";
      return;
    }

    var url =
      "/employees/payroll/attendance-summary/?employee=" +
      encodeURIComponent(employeeId) +
      "&start=" +
      encodeURIComponent(start) +
      "&end=" +
      encodeURIComponent(end);

    fetch(url)
      .then(function (resp) {
        return resp.ok ? resp.json() : null;
      })
      .then(function (data) {
        if (!data || data.error) {
          card.style.display = "none";
          return;
        }
        lastSummary = data;
        card.style.display = "block";
        document.getElementById("summary-present-days").textContent = data.present_days;
        document.getElementById("summary-working-days").textContent = data.working_days;
        document.getElementById("summary-total-hours").textContent = data.total_hours;

        var body = document.getElementById("attendance-summary-body");
        body.innerHTML = "";
        if (!data.records.length) {
          var emptyRow = document.createElement("tr");
          emptyRow.innerHTML = '<td colspan="5" class="empty-row">No attendance recorded in this period.</td>';
          body.appendChild(emptyRow);
          return;
        }
        data.records.forEach(function (row) {
          var tr = document.createElement("tr");
          var cells = [row.date, row.status, row.check_in || "—", row.check_out || "—", row.hours];
          cells.forEach(function (value) {
            var td = document.createElement("td");
            td.textContent = value;
            tr.appendChild(td);
          });
          body.appendChild(tr);
        });
      })
      .catch(function () {
        card.style.display = "none";
      });
  }

  document.addEventListener("DOMContentLoaded", function () {
    var employeeSelect = document.querySelector('select[name="employee"]');
    var startInput = document.querySelector('input[name="pay_period_start"]');
    var endInput = document.querySelector('input[name="pay_period_end"]');
    [employeeSelect, startInput, endInput].forEach(function (el) {
      if (el) el.addEventListener("change", fetchSummary);
    });
    fetchSummary();

    var useBtn = document.getElementById("use-attendance-days");
    if (useBtn) {
      useBtn.addEventListener("click", function () {
        if (!lastSummary) return;
        var presentInput = document.querySelector('input[name="present_days"]');
        var workingInput = document.querySelector('input[name="working_days"]');
        if (presentInput) presentInput.value = lastSummary.present_days;
        if (workingInput) workingInput.value = lastSummary.working_days;
      });
    }
  });
})();
