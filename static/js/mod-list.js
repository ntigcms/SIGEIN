/**
 * SIGEN — DataTables, filtros por coluna e exclusão (listagens).
 */
window.SIGENModList = (function () {
  var FILTER_CONTAINERS =
    ".mod-page .search-container, .users-page .search-container";

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
    if (v !== undefined && v !== null && String(v).trim() !== "") {
      return String(v).trim();
    }
    return $c.text().trim();
  }

  /** Comparação de filtro: ignora maiúsculas/minúsculas e acentos. */
  function normalizeFilterText(value) {
    return String(value || "")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/\s+/g, " ")
      .toLowerCase()
      .trim();
  }

  function cellMatchesFilter(cell, selectedValues) {
    var cellKey = normalizeFilterText(cellValue(cell));
    if (!cellKey || cellKey === "—" || cellKey === "-") {
      return false;
    }
    for (var i = 0; i < selectedValues.length; i++) {
      if (normalizeFilterText(selectedValues[i]) === cellKey) {
        return true;
      }
    }
    return false;
  }

  function cellLabel(node) {
    var $c = $(node);
    var l = $c.attr("data-filter-label");
    return l !== undefined && l !== "" ? String(l) : cellValue(node);
  }

  function isEmptyFilterValue(value) {
    var v = String(value || "").trim();
    return !v || v === "—" || v === "-";
  }

  function getCellNode(api, dataIndex, colIdx) {
    var cell = api.cell({ row: dataIndex, column: colIdx }).node();
    if (cell) return cell;
    var row = api.row(dataIndex).node();
    if (row) return $(row).find("td").eq(colIdx)[0] || null;
    return null;
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
        var key = active[i];
        var sel = filters[key];
        var colIndexes = String(key).split("|").map(function (c) {
          return parseInt(c.trim(), 10);
        });
        if (!colIndexes.length || isNaN(colIndexes[0])) continue;

        if (colIndexes.length > 1) {
          var matched = false;
          for (var j = 0; j < colIndexes.length; j++) {
            var orCell = getCellNode(api, dataIndex, colIndexes[j]);
            if (orCell && cellMatchesFilter(orCell, sel)) {
              matched = true;
              break;
            }
          }
          if (!matched) return false;
        } else {
          var cell = getCellNode(api, dataIndex, colIndexes[0]);
          if (!cell || !cellMatchesFilter(cell, sel)) return false;
        }
      }
      return true;
    });
  }

  function bindFilterOptionClick(optionsDiv) {
    optionsDiv.on("click.sigenOption", ".option", function (e) {
      var $row = $(this);
      if ($row.hasClass("option--empty")) return;
      var cb = $row.find('input[type="checkbox"]').first();
      if (!cb.length) return;
      if ($(e.target).is('input[type="checkbox"]')) return;
      if ($row.is("label")) return;
      e.preventDefault();
      cb.prop("checked", !cb.prop("checked")).trigger("change");
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
      $(table.table().body())
        .find("tr")
        .each(function () {
          var $row = $(this);
          colIndexes.forEach(function (colIdx) {
            var cell = $row.children("td").eq(colIdx)[0];
            if (!cell) return;
            var key = cellValue(cell);
            if (isEmptyFilterValue(key)) return;
            if (!map[key]) map[key] = cellLabel(cell);
          });
        });
      if (!Object.keys(map).length) {
        colIndexes.forEach(function (colIdx) {
          table.column(colIdx).data().each(function (val) {
            var v = $("<div>").html(String(val)).text().trim();
            if (isEmptyFilterValue(v)) return;
            if (!map[v]) map[v] = v;
          });
        });
      }
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

    $(FILTER_CONTAINERS).each(function () {
      var container = $(this);
      var input = container.find(".filter-search");
      var optionsDiv = container.find(".options");
      var arrow = container.find(".arrow");
      var colAttr = container.attr("data-col");
      if (colAttr === undefined || colAttr === "") return;

      var colIndexes = String(colAttr)
        .split(",")
        .map(function (c) {
          return parseInt(c.trim(), 10);
        });

      var selecionados = [];

      function filterStorageKey() {
        return colIndexes.length > 1
          ? colIndexes.join("|")
          : String(colIndexes[0]);
      }

      function clearFilterStorage(settings) {
        if (!settings || !settings._sigenColFilters) return;
        delete settings._sigenColFilters[filterStorageKey()];
        colIndexes.forEach(function (idx) {
          delete settings._sigenColFilters[String(idx)];
        });
      }

      function columns() {
        return colIndexes.map(function (i) {
          return table.column(i);
        });
      }

      var hasStaticOptions =
        optionsDiv.find('input[type="checkbox"]').length > 0;

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
              '<label class="option"><input type="checkbox" value="' +
                $('<div>').text(item.key).html() +
                '" ' +
                checked +
                '><span>' +
                item.label +
                "</span></label>"
            );
          });
        }
        optionsDiv.css("display", "block");
        arrow.addClass("open");
      }

      function showStaticOptions(query) {
        var q = (query || "").toLowerCase();
        optionsDiv.find(".option").each(function () {
          var $opt = $(this);
          if ($opt.hasClass("option--empty")) {
            $opt.hide();
            return;
          }
          var val = ($opt.find("input").val() || "").toLowerCase();
          var label = ($opt.find("span").text() || "").toLowerCase();
          $opt.toggle(!q || val.indexOf(q) !== -1 || label.indexOf(q) !== -1);
        });
        optionsDiv.css("display", "block");
        arrow.addClass("open");
      }

      input.on("click", function (e) {
        e.stopPropagation();
        $(FILTER_CONTAINERS)
          .not(container)
          .find(".options")
          .hide()
          .end()
          .find(".arrow")
          .removeClass("open");
        if (optionsDiv.is(":visible")) {
          optionsDiv.hide();
          arrow.removeClass("open");
        } else if (hasStaticOptions) {
          showStaticOptions("");
        } else {
          renderOptions(getValores());
        }
      });

      input.on("input", function () {
        var q = input.val().toLowerCase();
        if (hasStaticOptions) {
          showStaticOptions(q);
        } else {
          renderOptions(
            getValores().filter(function (item) {
              return item.label.toLowerCase().indexOf(q) !== -1;
            })
          );
        }
      });

      bindFilterOptionClick(optionsDiv);

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
          clearFilterStorage(settings);
          settings._sigenColFilters[filterStorageKey()] = selecionados.slice();
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

      container.data("reset", function (skipDraw) {
        selecionados = [];
        if (useDataSearch) {
          clearFilterStorage(table.settings()[0]);
        } else {
          columns().forEach(function (col) {
            col.search("", false, false);
          });
        }
        input.val("");
        optionsDiv.find('input[type="checkbox"]').prop("checked", false);
        optionsDiv.hide();
        arrow.removeClass("open");
        if (!skipDraw) {
          table.draw();
        }
      });
    });

    $(document)
      .off("click.sigenModFilter")
      .on("click.sigenModFilter", function (e) {
        if (!$(e.target).closest(".search-container").length) {
          $(FILTER_CONTAINERS).find(".options").hide();
          $(FILTER_CONTAINERS).find(".arrow").removeClass("open");
        }
      });
  }

  function initClearFilters(options) {
    var opts = options || {};
    var deferDraw = !!(opts.table && opts.columnIndexes && opts.columnIndexes.length);
    $("#clear-filters").off("click.sigenClear").on("click.sigenClear", function () {
      $(FILTER_CONTAINERS).each(function () {
        var resetFn = $(this).data("reset");
        if (typeof resetFn === "function") {
          resetFn(deferDraw ? true : undefined);
        }
      });
      $(".mod-page .filter-search[data-dt-col], .users-page .filter-search[data-dt-col]").each(
        function () {
        var $i = $(this);
        var col = $i.data("dtCol");
        if (col !== undefined) {
          $i.val("");
          $i.trigger("keyup");
        }
      });
      if (opts.table) {
        var settings = opts.table.settings()[0];
        if (settings._sigenColFilters) {
          settings._sigenColFilters = {};
        }
        opts.table.draw();
      } else if (deferDraw) {
        opts.columnIndexes.forEach(function (idx) {
          opts.table.column(idx).search("", false, false);
        });
        opts.table.draw();
      }
    });
  }

  function initTextFilter(table, colIndex, inputSelector) {
    $(inputSelector).on("keyup change", function () {
      table.column(colIndex).search(this.value).draw();
    });
    var container = $(inputSelector).closest(".search-container");
    if (container.length) {
      container.data("reset", function (skipDraw) {
        $(inputSelector).val("");
        table.column(colIndex).search("", false, false);
        if (!skipDraw) {
          table.draw();
        }
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
    bindFilterOptionClick: bindFilterOptionClick,
    initTextFilter: initTextFilter,
    initDelete: initDelete,
    registerDataSearchFilter: registerDataSearchFilter,
  };
})();
