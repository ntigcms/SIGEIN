/**
 * SIGEN — DataTables, filtros por coluna e exclusão (listagens).
 */
window.SIGENModList = (function () {
  var PAGE = ".mod-page, .users-page";

  var dtLang = {
    emptyTable: "Nenhum registro encontrado",
    info: "Mostrando _START_ a _END_ de _TOTAL_",
    infoEmpty: "Nenhum registro",
    lengthMenu: "Exibir _MENU_",
    zeroRecords: "Nenhum resultado para os filtros",
    paginate: {
      first: "Primeira",
      last: "Última",
      next: "Próxima",
      previous: "Anterior",
    },
    search: "",
  };

  function cellValue(node) {
    var $c = $(node);
    var v = $c.attr("data-search");
    return (v !== undefined && v !== "" ? String(v) : $c.text()).trim();
  }

  function cellLabel(node) {
    var $c = $(node);
    var l = $c.attr("data-filter-label");
    return l !== undefined && l !== "" ? String(l) : cellValue(node);
  }

  function registerDataSearchFilter() {
    if (window._sigenDataSearchFilterRegistered) return;
    window._sigenDataSearchFilterRegistered = true;

    $.fn.dataTable.ext.search.push(function (settings, data, dataIndex) {
      var filters = settings._sigenColFilters;
      if (!filters) return true;

      var active = Object.keys(filters).filter(function (k) {
        return filters[k] && filters[k].length;
      });
      if (!active.length) return true;

      var api = new $.fn.dataTable.Api(settings);
      var row = api.row(dataIndex).node();
      if (!row) return true;

      for (var i = 0; i < active.length; i++) {
        var colIdx = parseInt(active[i], 10);
        var sel = filters[active[i]];
        var cell = $(row).find("td").eq(colIdx)[0];
        if (!cell || sel.indexOf(cellValue(cell)) === -1) return false;
      }
      return true;
    });
  }

  function initTable(selector, options) {
    var opts = options || {};
    var $t = $(selector);
    if (!$t.length) return null;
    var dtOpts = {
      order: opts.order || [[0, "asc"]],
      columnDefs: opts.columnDefs || [],
      language: dtLang,
      pageLength: opts.pageLength || 10,
      dom: opts.dom || 'rt<"bottom"lip><"clear">',
      drawCallback: opts.drawCallback,
    };
    if (opts.ajax) dtOpts.ajax = opts.ajax;
    if (opts.columns) dtOpts.columns = opts.columns;
    if (opts.processing !== undefined) dtOpts.processing = opts.processing;
    if (opts.autoWidth === false) dtOpts.autoWidth = false;
    var table = $t.DataTable(dtOpts);
    if (opts.countSelector) {
      table.on("draw", function () {
        var info = table.page.info();
        $(opts.countSelector).text(info.recordsDisplay + " registro(s)");
      });
    }
    return table;
  }

  function keysToItems(map) {
    return Object.keys(map)
      .sort(function (a, b) {
        return map[a].localeCompare(map[b], "pt-BR");
      })
      .map(function (key) {
        return { key: key, label: map[key] };
      });
  }

  function collectColumnValues(table, colIndexes, useDataSearch) {
    var map = {};

    if (useDataSearch) {
      table.rows().every(function () {
        var row = this.node();
        colIndexes.forEach(function (colIdx) {
          var cell = $(row).find("td").eq(colIdx)[0];
          if (!cell) return;
          var key = cellValue(cell);
          if (!key) return;
          if (!map[key]) map[key] = cellLabel(cell);
        });
      });
      return keysToItems(map);
    }

    colIndexes.forEach(function (colIdx) {
      table
        .column(colIdx)
        .data()
        .unique()
        .sort()
        .toArray()
        .forEach(function (v) {
          v = String(v).trim();
          if (!v || v === "—") return;
          if (!map[v]) map[v] = v;
        });
    });
    return keysToItems(map);
  }

  function initColumnFilters(table, options) {
    var opts = options || {};
    var useDataSearch = opts.useDataSearch === true;

    if (useDataSearch) {
      var settings = table.settings()[0];
      settings._sigenColFilters = settings._sigenColFilters || {};
      registerDataSearchFilter();
    }

    $(PAGE + " .search-container").each(function () {
      var container = $(this);
      var input = container.find(".filter-search");
      var optionsDiv = container.find(".options");
      var arrow = container.find(".arrow");
      var colAttr = container.data("col");
      if (colAttr === undefined) return;

      var colIndexes = String(colAttr)
        .split(",")
        .map(function (c) {
          return parseInt(c.trim(), 10);
        });

      var selecionados = [];

      function columns() {
        return colIndexes.map(function (i) {
          return table.column(i);
        });
      }

      function getValores() {
        return collectColumnValues(table, colIndexes, useDataSearch);
      }

      function renderOptions(lista) {
        optionsDiv.empty();
        if (!lista.length) {
          optionsDiv.append(
            '<div class="option option--empty">Nenhum valor disponível</div>'
          );
        } else {
          lista.forEach(function (item) {
            var checked = selecionados.indexOf(item.key) !== -1 ? "checked" : "";
            optionsDiv.append(
              '<div class="option"><input type="checkbox" value="' +
                $('<div>').text(item.key).html() +
                '" ' +
                checked +
                '><label>' +
                item.label +
                "</label></div>"
            );
          });
        }
        optionsDiv.css("display", "block");
        arrow.addClass("open");
      }

      input.on("click", function (e) {
        e.stopPropagation();
        $(PAGE + " .search-container")
          .not(container)
          .find(".options")
          .hide()
          .end()
          .find(".arrow")
          .removeClass("open");
        if (optionsDiv.is(":visible")) {
          optionsDiv.hide();
          arrow.removeClass("open");
        } else {
          renderOptions(getValores());
        }
      });

      input.on("input", function () {
        var q = input.val().toLowerCase();
        renderOptions(
          getValores().filter(function (item) {
            return item.label.toLowerCase().indexOf(q) !== -1;
          })
        );
      });

      optionsDiv.on("change", 'input[type="checkbox"]', function () {
        var val = $(this).val();
        if (this.checked) {
          if (selecionados.indexOf(val) === -1) selecionados.push(val);
        } else {
          selecionados = selecionados.filter(function (v) {
            return v !== val;
          });
        }
        var labels = selecionados.map(function (key) {
          var found = getValores().find(function (item) {
            return item.key === key;
          });
          return found ? found.label : key;
        });
        input.val(labels.join(", "));
        aplicarFiltro();
      });

      function aplicarFiltro() {
        if (useDataSearch) {
          var settings = table.settings()[0];
          settings._sigenColFilters = settings._sigenColFilters || {};
          colIndexes.forEach(function (idx) {
            settings._sigenColFilters[String(idx)] = selecionados.slice();
          });
        } else {
          columns().forEach(function (col) {
            col.search("");
          });
          if (selecionados.length > 0) {
            var regex = selecionados
              .map(function (v) {
                return (
                  "^" + $.fn.dataTable.util.escapeRegex(v) + "$"
                );
              })
              .join("|");
            columns().forEach(function (col) {
              col.search(regex, true, false);
            });
          }
        }
        table.draw();
      }

      container.data("reset", function () {
        selecionados = [];
        if (useDataSearch) {
          var settings = table.settings()[0];
          colIndexes.forEach(function (idx) {
            if (settings._sigenColFilters) {
              settings._sigenColFilters[String(idx)] = [];
            }
          });
        } else {
          columns().forEach(function (col) {
            col.search("");
          });
        }
        input.val("");
        table.draw();
        optionsDiv.hide();
        arrow.removeClass("open");
      });
    });

    $(document)
      .off("click.sigenModFilter")
      .on("click.sigenModFilter", function (e) {
        if (!$(e.target).closest(PAGE + " .search-container").length) {
          $(PAGE + " .search-container .options").hide();
          $(PAGE + " .search-container .arrow").removeClass("open");
        }
      });
  }

  function initClearFilters() {
    $("#clear-filters").off("click.sigenClear").on("click.sigenClear", function () {
      $(PAGE + " .search-container").each(function () {
        var resetFn = $(this).data("reset");
        if (typeof resetFn === "function") resetFn();
      });
      $(PAGE + " .filter-search[data-dt-col]").each(function () {
        var $i = $(this);
        var col = $i.data("dtCol");
        if (col !== undefined) {
          $i.val("");
          $i.trigger("keyup");
        }
      });
    });
  }

  function initTextFilter(table, colIndex, inputSelector) {
    $(inputSelector).on("keyup change", function () {
      table.column(colIndex).search(this.value).draw();
    });
    var container = $(inputSelector).closest(".search-container");
    if (container.length) {
      container.data("reset", function () {
        $(inputSelector).val("");
        table.column(colIndex).search("").draw();
      });
    }
  }

  function initDelete(deleteUrlBuilder, options) {
    var opts = options || {};
    var method = (opts.method || "POST").toUpperCase();

    $(document).on("submit", ".delete-form", function (e) {
      e.preventDefault();
      var form = $(this);
      var id = form.data("id");
      var url =
        typeof deleteUrlBuilder === "function"
          ? deleteUrlBuilder(id)
          : deleteUrlBuilder.replace("{id}", id);

      Swal.fire({
        title: opts.title || "Excluir registro?",
        text: opts.text || "Esta ação não pode ser desfeita.",
        icon: "warning",
        showCancelButton: true,
        confirmButtonColor: "#ef4444",
        cancelButtonColor: "#64748b",
        confirmButtonText: "Sim, excluir",
        cancelButtonText: "Cancelar",
      }).then(function (result) {
        if (!result.isConfirmed) return;
        if (method === "GET") {
          window.location.href = url;
          return;
        }
        fetch(url, { method: "POST" })
          .then(function (r) {
            return r.json();
          })
          .then(function (data) {
            if (data.success) {
              Swal.fire({
                icon: "success",
                title: "Excluído",
                timer: 1500,
                showConfirmButton: false,
              }).then(function () {
                location.reload();
              });
            } else {
              Swal.fire({
                icon: "error",
                title: "Não permitido",
                text: data.message || "Operação não permitida.",
              });
            }
          });
      });
    });
  }

  return {
    dtLang: dtLang,
    initTable: initTable,
    initColumnFilters: initColumnFilters,
    initClearFilters: initClearFilters,
    initTextFilter: initTextFilter,
    initDelete: initDelete,
  };
})();
