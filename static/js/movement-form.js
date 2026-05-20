/**
 * Formulário de movimentação (página /movements/nova ou modal no estoque).
 */
window.SIGENMovementForm = (function () {
  function $(prefix, name) {
    return document.getElementById(prefix + name);
  }

  function init(config) {
    var prefix = config.prefix || "";
    var productsData = config.productsData || [];
    var prefillData = config.prefill || {};
    var movimentoData = config.movimento || {};
    var activePrefill = null;
    var isPrefilling = false;

    var categorySelect = $(prefix, "category");
    var productSelect = $(prefix, "product");
    var serieContainer = $(prefix, "serie-container");
    var serieSelect = $(prefix, "serie-select");
    var tomboContainer = $(prefix, "tombo-container");
    var tomboSelect = $(prefix, "tombo-select");
    var unitOrigemSelect = $(prefix, "unit_origem");
    var quantidadeInput = $(prefix, "quantidade");
    var itemIdInput = $(prefix, "item_id");
    var productIdHidden = $(prefix, "product_id_hidden");
    var itensFisicosWrapper = $(prefix, "itens-fisicos-wrapper");
    var itemFiltroInput = $(prefix, "item-filtro");
    var form = config.form;

    if (!categorySelect || !productSelect || !form) return;

    function atualizarUnidadeOrigem(unit_id, unit_name, item_id) {
      unitOrigemSelect.innerHTML = "";
      if (!unit_id || !unit_name) return;
      var opt = document.createElement("option");
      opt.value = unit_id;
      opt.text = unit_name;
      unitOrigemSelect.appendChild(opt);
      unitOrigemSelect.value = unit_id;
      itemIdInput.value = item_id || "";
    }

    function resetItems() {
      itensFisicosWrapper.style.display = "none";
      if (itemFiltroInput) itemFiltroInput.value = "";
      serieContainer.style.display = "none";
      tomboContainer.style.display = "none";
      serieSelect.innerHTML = '<option value="">— Selecione —</option>';
      tomboSelect.innerHTML = '<option value="">— Selecione —</option>';
      itemIdInput.value = "";
    }

    function resetUnidade() {
      unitOrigemSelect.innerHTML = '<option value="">— Selecione —</option>';
    }

    function aplicarFiltroItem() {
      var filtro =
        itemFiltroInput && itemFiltroInput.value
          ? itemFiltroInput.value.trim().toLowerCase()
          : "";
      [serieSelect, tomboSelect].forEach(function (select) {
        for (var i = 0; i < select.options.length; i++) {
          var opt = select.options[i];
          if (!opt.value) continue;
          var show =
            !filtro ||
            (opt.text && opt.text.toLowerCase().indexOf(filtro) !== -1);
          opt.style.display = show ? "" : "none";
        }
      });
    }

    async function carregarItensFisicos(type_id, opts) {
      opts = opts || {};
      serieSelect.innerHTML = '<option value="">— Selecione —</option>';
      tomboSelect.innerHTML = '<option value="">— Selecione —</option>';
      if (itemFiltroInput) itemFiltroInput.value = "";

      itensFisicosWrapper.style.display = "none";
      serieContainer.style.display = "none";
      tomboContainer.style.display = "none";
      itemIdInput.value = "";

      var params = new URLSearchParams();
      if (opts.product_id) params.set("product_id", opts.product_id);
      if (opts.unit_id) params.set("unit_id", opts.unit_id);
      var qs = params.toString();
      var url = "/movements/items/" + type_id + (qs ? "?" + qs : "");
      var res = await fetch(url);
      if (!res.ok) return;
      var itens = await res.json();
      if (!Array.isArray(itens) || !itens.length) return;

      var itensNormalizados = itens.map(function (i) {
        return Object.assign({}, i, {
          isTombo:
            i.tombo === true ||
            i.tombo === "true" ||
            i.tombo === 1 ||
            i.tombo === "1",
        });
      });

      var temSerie = itensNormalizados.some(function (i) {
        return !i.isTombo;
      });
      var temTombo = itensNormalizados.some(function (i) {
        return i.isTombo;
      });

      if (temSerie) {
        serieContainer.style.display = "block";
        itensNormalizados
          .filter(function (i) {
            return !i.isTombo;
          })
          .forEach(function (i) {
            var opt = document.createElement("option");
            opt.value = i.id;
            opt.text = i.num;
            opt.dataset.unitId = i.unit_id;
            opt.dataset.unitName = i.unit_name;
            serieSelect.appendChild(opt);
          });
      }
      if (temTombo) {
        tomboContainer.style.display = "block";
        itensNormalizados
          .filter(function (i) {
            return i.isTombo;
          })
          .forEach(function (i) {
            var opt = document.createElement("option");
            opt.value = i.id;
            opt.text = i.num;
            opt.dataset.unitId = i.unit_id;
            opt.dataset.unitName = i.unit_name;
            tomboSelect.appendChild(opt);
          });
      }
      if (temSerie || temTombo) {
        itensFisicosWrapper.style.display = "block";
        aplicarFiltroItem();
        if (temSerie && serieSelect.options.length === 2) {
          serieSelect.selectedIndex = 1;
          serieSelect.dispatchEvent(new Event("change", { bubbles: true }));
        } else if (temTombo && tomboSelect.options.length === 2) {
          tomboSelect.selectedIndex = 1;
          tomboSelect.dispatchEvent(new Event("change", { bubbles: true }));
        }
      }
    }

    categorySelect.addEventListener("change", function () {
      var cat = parseInt(categorySelect.value, 10);
      productSelect.innerHTML = '<option value="">— Selecione —</option>';
      productSelect.disabled = !cat;
      resetItems();
      resetUnidade();
      quantidadeInput.value = "1";
      quantidadeInput.disabled = true;
      if (!isPrefilling && productIdHidden) productIdHidden.value = "";
      if (!cat) return;

      var filtered = productsData.filter(function (p) {
        return p.category_id === cat;
      });
      var grouped = {};
      filtered.forEach(function (p) {
        if (!grouped[p.type_id]) {
          grouped[p.type_id] = {
            type_id: p.type_id,
            type_name: p.type_name,
            controla_por_serie: p.controla_por_serie,
          };
        }
      });
      Object.values(grouped).forEach(function (p) {
        var opt = document.createElement("option");
        opt.value = p.type_id;
        opt.text = p.type_name;
        opt.dataset.controlaPorSerie = p.controla_por_serie;
        productSelect.appendChild(opt);
      });
    });

    productSelect.addEventListener("change", async function () {
      resetItems();
      resetUnidade();
      quantidadeInput.value = "1";
      quantidadeInput.disabled = true;
      itemIdInput.value = "";
      if (!isPrefilling && productIdHidden) productIdHidden.value = "";

      var opt = productSelect.selectedOptions[0];
      if (!opt || !opt.value) return;

      var controlaSerie = opt.dataset.controlaPorSerie === "true";

      if (controlaSerie) {
        quantidadeInput.disabled = true;
        var ctx = activePrefill;
        activePrefill = null;
        await carregarItensFisicos(opt.value, ctx);
      } else {
        quantidadeInput.disabled = false;
        var produtosDaCategoria = productsData.filter(function (p) {
          return p.type_id == opt.value;
        });
        var unitsMap = {};
        produtosDaCategoria.forEach(function (p) {
          if (p.units_options) {
            p.units_options.forEach(function (u) {
              if (!unitsMap[u.unit_id]) unitsMap[u.unit_id] = u.unit_name;
            });
          }
        });
        Object.entries(unitsMap).forEach(function (entry) {
          var optUnit = document.createElement("option");
          optUnit.value = entry[0];
          optUnit.text = entry[1];
          unitOrigemSelect.appendChild(optUnit);
        });
      }
    });

    if (itemFiltroInput) {
      itemFiltroInput.addEventListener("input", aplicarFiltroItem);
    }

    serieSelect.addEventListener("change", function () {
      tomboSelect.value = "";
      var opt = serieSelect.selectedOptions[0];
      if (!opt || !opt.value) return;
      atualizarUnidadeOrigem(opt.dataset.unitId, opt.dataset.unitName, opt.value);
    });

    tomboSelect.addEventListener("change", function () {
      serieSelect.value = "";
      var opt = tomboSelect.selectedOptions[0];
      if (!opt || !opt.value) return;
      atualizarUnidadeOrigem(opt.dataset.unitId, opt.dataset.unitName, opt.value);
    });

    async function applyPrefill(p) {
      if (!p || !p.type_id) return;
      if (movimentoData && movimentoData.id) return;

      isPrefilling = true;
      try {
        activePrefill = {
          product_id: p.product_id,
          unit_id: p.unit_origem_id,
        };
        if (productIdHidden && p.product_id) {
          productIdHidden.value = p.product_id;
        }

        if (p.category_id) {
          categorySelect.value = p.category_id;
          categorySelect.dispatchEvent(new Event("change", { bubbles: true }));
          await new Promise(function (r) {
            setTimeout(r, 50);
          });
        }

        productSelect.value = p.type_id;
        productSelect.dispatchEvent(new Event("change", { bubbles: true }));
        await new Promise(function (r) {
          setTimeout(r, 350);
        });

        var optSel = productSelect.selectedOptions[0];
        var controlaSerie =
          optSel && optSel.dataset.controlaPorSerie === "true";

        if (!controlaSerie && p.unit_origem_id) {
          quantidadeInput.disabled = false;
          if (
            unitOrigemSelect.querySelector(
              'option[value="' + p.unit_origem_id + '"]'
            )
          ) {
            unitOrigemSelect.value = p.unit_origem_id;
          } else {
            var prod = productsData.find(function (x) {
              return x.id === p.product_id;
            });
            var unitOpt =
              prod && prod.units_options
                ? prod.units_options.find(function (u) {
                    return u.unit_id == p.unit_origem_id;
                  })
                : null;
            if (unitOpt) {
              var optUnit = document.createElement("option");
              optUnit.value = unitOpt.unit_id;
              optUnit.text = unitOpt.unit_name;
              unitOrigemSelect.appendChild(optUnit);
              unitOrigemSelect.value = p.unit_origem_id;
            }
          }
        }
        if (productIdHidden && p.product_id) {
          productIdHidden.value = p.product_id;
        }
      } finally {
        isPrefilling = false;
        activePrefill = null;
      }
    }

    async function applyEdit(m) {
      if (!m || !m.id) return;
      categorySelect.value = m.product.category_id;
      categorySelect.dispatchEvent(new Event("change"));
      await new Promise(function (r) {
        setTimeout(r, 50);
      });
      productSelect.value = m.product.type_id;
      productSelect.dispatchEvent(new Event("change"));
      await new Promise(function (r) {
        setTimeout(r, 300);
      });
      if (m.item) {
        if (m.item.tombo) {
          tomboSelect.value = m.item.id;
          tomboSelect.dispatchEvent(new Event("change"));
        } else {
          serieSelect.value = m.item.id;
          serieSelect.dispatchEvent(new Event("change"));
        }
      } else {
        quantidadeInput.value = m.quantidade;
        quantidadeInput.disabled = false;
        if (m.unit_origem_id) {
          unitOrigemSelect.value = m.unit_origem_id;
          if (
            !unitOrigemSelect.value ||
            unitOrigemSelect.value != m.unit_origem_id
          ) {
            var opt = document.createElement("option");
            opt.value = m.unit_origem_id;
            opt.text = "Unidade atual";
            unitOrigemSelect.appendChild(opt);
            unitOrigemSelect.value = m.unit_origem_id;
          }
        }
      }
      $(prefix, "unit_destino").value = m.unit_destino_id;
      $(prefix, "tipo").value = m.tipo;
      $(prefix, "observacao").value = m.observacao || "";
    }

    function resetForm() {
      form.reset();
      productSelect.innerHTML = '<option value="">— Selecione —</option>';
      productSelect.disabled = true;
      resetItems();
      resetUnidade();
      quantidadeInput.disabled = true;
      if (productIdHidden) productIdHidden.value = "";
    }

    if (config.ajax) {
      form.addEventListener("submit", async function (e) {
        e.preventDefault();
        var errEl = config.errorEl;
        var submitBtn = config.submitBtn;
        if (errEl) {
          errEl.style.display = "none";
          errEl.textContent = "";
        }
        if (submitBtn) submitBtn.disabled = true;

        var fd = new FormData(form);
        fd.set("ajax", "1");
        if (!fd.get("product_id")) fd.delete("product_id");

        try {
          var res = await fetch(form.action, {
            method: "POST",
            body: fd,
            headers: { Accept: "application/json" },
          });
          var data = await res.json();
          if (!res.ok || !data.success) {
            throw new Error(data.message || "Erro ao salvar movimentação");
          }
          if (typeof config.onSuccess === "function") {
            config.onSuccess(data);
          }
        } catch (err) {
          if (errEl) {
            errEl.style.display = "block";
            errEl.textContent = err.message || String(err);
          } else {
            alert(err.message || String(err));
          }
        } finally {
          if (submitBtn) submitBtn.disabled = false;
        }
      });
    }

    applyEdit(movimentoData);
    applyPrefill(prefillData);

    return {
      reset: resetForm,
      applyPrefill: applyPrefill,
    };
  }

  return { init: init };
})();
