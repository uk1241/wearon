(function () {
  function timeToMinutes(value) {
    if (!value) return null;
    var parts = value.split(":");
    if (parts.length < 2) return null;
    var hours = parseInt(parts[0], 10);
    var minutes = parseInt(parts[1], 10);
    if (isNaN(hours) || isNaN(minutes)) return null;
    return hours * 60 + minutes;
  }

  function recalcRow(row) {
    var checkOutInput = row.querySelector(".segment-check-out");
    var checkInInput = row.querySelector(".segment-check-in");
    var hoursEl = row.querySelector(".row-hours");
    if (!checkOutInput || !checkInInput || !hoursEl) return;
    var a = timeToMinutes(checkOutInput.value);
    var b = timeToMinutes(checkInInput.value);
    if (a === null || b === null) {
      hoursEl.textContent = "0h 0m";
      return;
    }
    var diffMinutes = Math.abs(b - a);
    var hours = Math.floor(diffMinutes / 60);
    var minutes = diffMinutes % 60;
    hoursEl.textContent = hours + "h " + minutes + "m";
  }

  function recalcAllRows() {
    document.querySelectorAll("#segments-body .segment-row").forEach(recalcRow);
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
  };

  function addSegmentRow() {
    var totalFormsInput = document.getElementById("id_segments-TOTAL_FORMS");
    if (!totalFormsInput) return;
    var index = parseInt(totalFormsInput.value, 10);
    var templateEl = document.getElementById("empty-segment-row");
    var html = templateEl.innerHTML.split("__prefix__").join(index);

    var wrapper = document.createElement("tbody");
    wrapper.innerHTML = html.trim();
    var newRow = wrapper.querySelector("tr");

    document.getElementById("segments-body").appendChild(newRow);
    totalFormsInput.value = index + 1;
  }

  document.addEventListener("DOMContentLoaded", function () {
    recalcAllRows();

    var addBtn = document.getElementById("add-segment-row");
    if (addBtn) addBtn.addEventListener("click", addSegmentRow);

    var segmentsBody = document.getElementById("segments-body");
    if (segmentsBody) {
      segmentsBody.addEventListener("input", function (e) {
        if (
          e.target.classList.contains("segment-check-out") ||
          e.target.classList.contains("segment-check-in")
        ) {
          recalcRow(e.target.closest("tr"));
        }
      });
    }
  });
})();
