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
    var controlaSerieAtual = false;

    var categorySelect = $(prefix, "category");
    var productSelect = $(prefix, "product");
    var itensSelect = $(prefix, "itens-select");
    var itensSelectContainer = $(prefix, "itens-select-container");
    var unitOrigemSelect = $(prefix, "unit_origem");
    var unitDestinoSelect = $(prefix, "unit_destino");
    var quantidadeInput = $(prefix, "quantidade");
    var itemIdInput = $(prefix, "item_id");
    var productIdHidden = $(prefix, "product_id_hidden");
    var itensFisicosWrapper = $(prefix, "itens-fisicos-wrapper");
    var itemFiltroInput = $(prefix, "item-filtro");
    var form = config.form;

    if (!categorySelect || !productSelect || !form) return;

    var allDestUnits = [];
    if (unitDestinoSelect) {
      Array.prototype.forEach.call(unitDestinoSelect.options, function (opt) {
        if (opt.value) {
          allDestUnits.push({ id: opt.value, name: opt.text });
        }
      });
    }

    function validarUnidadesDistintas() {
      var origem = unitOrigemSelect && unitOrigemSelect.value;
      var destino = unitDestinoSelect && unitDestinoSelect.value;
      if (origem && destino && String(origem) === String(destino)) {
        return "Unidade de origem e destino devem ser diferentes.";
      }
      return null;
    }

    function renderUnidadesDestino(excludeUnitId, selectedId) {
      if (!unitDestinoSelect) return;
      unitDestinoSelect.innerHTML = '<option value="">— Selecione —</option>';
      allDestUnits.forEach(function (u) {
        if (excludeUnitId && String(u.id) === String(excludeUnitId)) return;
        var opt = document.createElement("option");
        opt.value = u.id;
        opt.text = u.name;
        unitDestinoSelect.appendChild(opt);
      });
      if (
        selectedId &&
        String(selectedId) !== String(excludeUnitId) &&
        unitDestinoSelect.querySelector('option[value="' + selectedId + '"]')
      ) {
        unitDestinoSelect.value = selectedId;
      }
    }

    function atualizarUnidadesDestino() {
      var origemId = unitOrigemSelect ? unitOrigemSelect.value : "";
      var prev =
        unitDestinoSelect && unitDestinoSelect.value
          ? unitDestinoSelect.value
          : "";
      renderUnidadesDestino(origemId || null, prev);
    }

    function resetItems() {
      itensFisicosWrapper.style.display = "none";
      itensSelectContainer.style.display = "none";
      if (itemFiltroInput) itemFiltroInput.value = "";
      itensSelect.innerHTML = '<option value="">— Selecione —</option>';
      itemIdInput.value = "";
      if (productIdHidden) productIdHidden.value = "";
    }

    function resetUnidade() {
      unitOrigemSelect.innerHTML = '<option value="">— Selecione —</option>';
      unitOrigemSelect.disabled = true;
      renderUnidadesDestino(null, "");
    }

    function popularUnidadesOrigem(typeId) {
      resetUnidade();
      if (!typeId) return;

      var produtosDoTipo = productsData.filter(function (p) {
        return String(p.type_id) === String(typeId);
      });
      var unitsMap = {};
      produtosDoTipo.forEach(function (p) {
        (p.units_options || []).forEach(function (u) {
          if (u.unit_id && !unitsMap[u.unit_id]) {
            unitsMap[u.unit_id] = u.unit_name;
          }
        });
      });

      var entries = Object.entries(unitsMap);
      if (!entries.length) return;

      entries.forEach(function (entry) {
        var optUnit = document.createElement("option");
        optUnit.value = entry[0];
        optUnit.text = entry[1];
        unitOrigemSelect.appendChild(optUnit);
      });
      unitOrigemSelect.disabled = false;
    }

    function aplicarFiltroItem() {
      var filtro =
        itemFiltroInput && itemFiltroInput.value
          ? itemFiltroInput.value.trim().toLowerCase()
          : "";
      for (var i = 0; i < itensSelect.options.length; i++) {
        var opt = itensSelect.options[i];
        if (!opt.value) continue;
        var show =
          !filtro ||
          (opt.text && opt.text.toLowerCase().indexOf(filtro) !== -1);
        opt.style.display = show ? "" : "none";
      }
    }

    function atualizarQuantidade() {
      if (controlaSerieAtual) {
        quantidadeInput.value = "1";
        quantidadeInput.disabled = true;
        return;
      }
      var temItem = !!itemIdInput.value;
      var temProduto = productIdHidden && productIdHidden.value;
      quantidadeInput.disabled = !(temItem || temProduto);
      if (quantidadeInput.disabled) quantidadeInput.value = "1";
    }

    async function carregarItens(type_id, unit_id, opts) {
      opts = opts || {};
      resetItems();

      if (!type_id || !unit_id) return;

      var params = new URLSearchParams({ unit_id: unit_id });
      if (opts.product_id) params.set("product_id", opts.product_id);
      var url = "/movements/items/" + type_id + "?" + params.toString();
      var res = await fetch(url);
      if (!res.ok) return;
      var itens = await res.json();
      if (!Array.isArray(itens) || !itens.length) {
        if (!controlaSerieAtual) {
          var prod = productsData.find(function (p) {
            return String(p.type_id) === String(type_id);
          });
          if (prod && productIdHidden) productIdHidden.value = prod.id;
        }
        atualizarQuantidade();
        return;
      }

      itens.forEach(function (i) {
        var opt = document.createElement("option");
        if (i.id != null) {
          opt.value = String(i.id);
        } else if (i.product_id) {
          opt.value = "prod-" + i.product_id;
        } else {
          return;
        }
        opt.text = i.num || "—";
        if (i.product_id) opt.dataset.productId = i.product_id;
        itensSelect.appendChild(opt);
      });

      itensSelectContainer.style.display = "block";
      itensFisicosWrapper.style.display = "block";
      aplicarFiltroItem();

      if (opts.item_id) {
        var alvo = String(opts.item_id);
        for (var j = 0; j < itensSelect.options.length; j++) {
          if (itensSelect.options[j].value === alvo) {
            itensSelect.selectedIndex = j;
            itensSelect.dispatchEvent(new Event("change", { bubbles: true }));
            break;
          }
        }
      } else if (itensSelect.options.length === 2) {
        itensSelect.selectedIndex = 1;
        itensSelect.dispatchEvent(new Event("change", { bubbles: true }));
      }

      atualizarQuantidade();
    }

    categorySelect.addEventListener("change", function () {
      var cat = parseInt(categorySelect.value, 10);
      productSelect.innerHTML = '<option value="">— Selecione —</option>';
      productSelect.disabled = !cat;
      resetItems();
      resetUnidade();
      controlaSerieAtual = false;
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

    productSelect.addEventListener("change", function () {
      resetItems();
      resetUnidade();
      quantidadeInput.value = "1";
      quantidadeInput.disabled = true;
      itemIdInput.value = "";
      if (!isPrefilling && productIdHidden) productIdHidden.value = "";

      var opt = productSelect.selectedOptions[0];
      if (!opt || !opt.value) {
        controlaSerieAtual = false;
        return;
      }

      controlaSerieAtual = opt.dataset.controlaPorSerie === "true";
      popularUnidadesOrigem(opt.value);

      if (isPrefilling && activePrefill && activePrefill.unit_id) {
        var uid = String(activePrefill.unit_id);
        if (!unitOrigemSelect.querySelector('option[value="' + uid + '"]')) {
          var prodRef = productsData.find(function (x) {
            return x.id === activePrefill.product_id;
          });
          var uo =
            prodRef && prodRef.units_options
              ? prodRef.units_options.find(function (u) {
                  return String(u.unit_id) === uid;
                })
              : null;
          if (uo) {
            var optUnit = document.createElement("option");
            optUnit.value = uo.unit_id;
            optUnit.text = uo.unit_name;
            unitOrigemSelect.appendChild(optUnit);
          }
        }
        unitOrigemSelect.disabled = false;
        unitOrigemSelect.value = uid;
        unitOrigemSelect.dispatchEvent(new Event("change", { bubbles: true }));
      }
    });

    unitOrigemSelect.addEventListener("change", async function () {
      atualizarUnidadesDestino();
      resetItems();
      itemIdInput.value = "";
      if (!isPrefilling && productIdHidden) productIdHidden.value = "";
      quantidadeInput.value = "1";
      quantidadeInput.disabled = true;

      var typeOpt = productSelect.selectedOptions[0];
      var unitId = unitOrigemSelect.value;
      if (!typeOpt || !typeOpt.value || !unitId) return;

      var ctx = null;
      if (isPrefilling && activePrefill) {
        ctx = {
          product_id: activePrefill.product_id,
          item_id: activePrefill.item_id,
        };
      }
      await carregarItens(typeOpt.value, unitId, ctx || {});
    });

    itensSelect.addEventListener("change", function () {
      var opt = itensSelect.selectedOptions[0];
      if (!opt || !opt.value) {
        itemIdInput.value = "";
        if (productIdHidden) productIdHidden.value = "";
        atualizarQuantidade();
        return;
      }
      if (opt.value.indexOf("prod-") === 0) {
        itemIdInput.value = "";
        if (productIdHidden) {
          productIdHidden.value = opt.dataset.productId || opt.value.slice(5);
        }
      } else {
        itemIdInput.value = opt.value;
        if (productIdHidden && opt.dataset.productId) {
          productIdHidden.value = opt.dataset.productId;
        }
      }
      atualizarQuantidade();
    });

    if (itemFiltroInput) {
      itemFiltroInput.addEventListener("input", aplicarFiltroItem);
    }

    async function applyPrefill(p) {
      if (!p || !p.type_id) return;
      if (movimentoData && movimentoData.id) return;

      isPrefilling = true;
      try {
        activePrefill = {
          product_id: p.product_id,
          unit_id: p.unit_origem_id,
          item_id: p.item_id,
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
          setTimeout(r, 400);
        });

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
      isPrefilling = true;
      try {
        categorySelect.value = m.product.category_id;
        categorySelect.dispatchEvent(new Event("change"));
        await new Promise(function (r) {
          setTimeout(r, 50);
        });
        productSelect.value = m.product.type_id;
        productSelect.dispatchEvent(new Event("change"));
        await new Promise(function (r) {
          setTimeout(r, 100);
        });

        if (m.unit_origem_id) {
          unitOrigemSelect.disabled = false;
          if (
            !unitOrigemSelect.querySelector(
              'option[value="' + m.unit_origem_id + '"]'
            )
          ) {
            var optU = document.createElement("option");
            optU.value = m.unit_origem_id;
            optU.text = m.unit_origem_name || "Unidade atual";
            unitOrigemSelect.appendChild(optU);
          }
          unitOrigemSelect.value = m.unit_origem_id;
          renderUnidadesDestino(m.unit_origem_id, m.unit_destino_id);
          await carregarItens(m.product.type_id, m.unit_origem_id, {
            item_id: m.item ? m.item.id : null,
          });
        }

        if (m.item) {
          itemIdInput.value = m.item.id;
          if (productIdHidden && m.product.id) {
            productIdHidden.value = m.product.id;
          }
        } else {
          quantidadeInput.value = m.quantidade;
          quantidadeInput.disabled = false;
          if (productIdHidden && m.product.id) {
            productIdHidden.value = m.product.id;
          }
        }

        if (unitDestinoSelect && m.unit_destino_id) {
          unitDestinoSelect.value = m.unit_destino_id;
        }
        $(prefix, "tipo").value = m.tipo;
        $(prefix, "observacao").value = m.observacao || "";
      } finally {
        isPrefilling = false;
      }
    }

    function resetForm() {
      form.reset();
      productSelect.innerHTML = '<option value="">— Selecione —</option>';
      productSelect.disabled = true;
      resetItems();
      resetUnidade();
      controlaSerieAtual = false;
      quantidadeInput.disabled = true;
      if (productIdHidden) productIdHidden.value = "";
    }

    form.addEventListener("submit", function (e) {
      var errUnidades = validarUnidadesDistintas();
      if (errUnidades) {
        e.preventDefault();
        alert(errUnidades);
        return;
      }
      if (!config.ajax) return;
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

      fetch(form.action, {
        method: "POST",
        body: fd,
        headers: { Accept: "application/json" },
      })
        .then(function (res) {
          return res.json().then(function (data) {
            return { res: res, data: data };
          });
        })
        .then(function (result) {
          if (!result.res.ok || !result.data.success) {
            throw new Error(result.data.message || "Erro ao salvar movimentação");
          }
          if (typeof config.onSuccess === "function") {
            config.onSuccess(result.data);
          }
        })
        .catch(function (err) {
          if (errEl) {
            errEl.style.display = "block";
            errEl.textContent = err.message || String(err);
          } else {
            alert(err.message || String(err));
          }
        })
        .finally(function () {
          if (submitBtn) submitBtn.disabled = false;
        });
    });

    applyEdit(movimentoData);
    applyPrefill(prefillData);

    return {
      reset: resetForm,
      applyPrefill: applyPrefill,
    };
  }

  return { init: init };
})();
