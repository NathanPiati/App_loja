// Produto
const buscaProduto = document.getElementById('buscaProduto');
const resultadoProduto = document.getElementById('resultadoBuscaProduto');
const loadingProduto = document.getElementById('loadingBuscaProduto');
const tabelaProdutosBody = document.getElementById('tabelaProdutosBody');

// Serviço
const buscaServico = document.getElementById('buscaServico');
const resultadoServico = document.getElementById('resultadoBuscaServico');
const loadingServico = document.getElementById('loadingBuscaServico');
const tabelaServicosBody = document.getElementById('tabelaServicosBody');

// Totais
const subtotalPedidoSpan = document.getElementById('subtotalPedido');
const descontoPercentualInput = document.getElementById('id_desconto_percentual');
const descontoPercentualDisplaySpan = document.getElementById('descontoPercentualDisplay');
const valorDescontoSpan = document.getElementById('valorDesconto');
const totalPedidoSpan = document.getElementById('totalPedido');

let totalForms = document.getElementById('id_itenspedido_set-TOTAL_FORMS');

function abrirModal() {
    const modal = new bootstrap.Modal(document.getElementById('modalProduto'));
    modal.show();
}

function abrirModalServico() {
    const modal = new bootstrap.Modal(document.getElementById('modalServico'));
    modal.show();
}

// Buscar produtos
buscaProduto.addEventListener('input', () => {
    const termo = buscaProduto.value.trim();
    if (!termo) {
        resultadoProduto.innerHTML = '<tr><td colspan="4">Digite algo</td></tr>';
        return;
    }
    loadingProduto.style.display = 'block';

    fetch(`/buscar-produtos/?term=${termo}`)
        .then(res => res.json())
        .then(data => {
            resultadoProduto.innerHTML = '';
            if (data.length === 0) {
                resultadoProduto.innerHTML = '<tr><td colspan="4">Nenhum encontrado</td></tr>';
            } else {
                data.forEach(p => {
                    resultadoProduto.innerHTML += `
                    <tr>
                      <td>${p.id}</td>
                      <td>${p.nome}</td>
                      <td>R$ ${p.preco.toFixed(2)}</td>
                      <td><button type="button" class="btn btn-success btn-sm"
                        onclick="adicionarProduto(${p.id}, '${p.nome}', ${p.preco})">Selecionar</button></td>
                    </tr>`;
                });
            }
            loadingProduto.style.display = 'none';
        });
});

// Buscar serviços
buscaServico.addEventListener('input', () => {
    const termo = buscaServico.value.trim();
    if (!termo) {
        resultadoServico.innerHTML = '<tr><td colspan="4">Digite algo</td></tr>';
        return;
    }
    loadingServico.style.display = 'block';

    fetch(`/buscar-servicos/?term=${termo}`)
        .then(res => res.json())
        .then(data => {
            resultadoServico.innerHTML = '';
            if (data.length === 0) {
                resultadoServico.innerHTML = '<tr><td colspan="4">Nenhum encontrado</td></tr>';
            } else {
                data.forEach(s => {
                    resultadoServico.innerHTML += `
                    <tr>
                      <td>${s.id}</td>
                      <td>${s.nome}</td>
                      <td>R$ ${s.preco.toFixed(2)}</td>
                      <td><button type="button" class="btn btn-success btn-sm"
                        onclick="adicionarServico(${s.id}, '${s.nome}', ${s.preco})">Selecionar</button></td>
                    </tr>`;
                });
            }
            loadingServico.style.display = 'none';
        });
});

function adicionarProduto(id, nome, preco) {
    const qtd = document.getElementById('quantidadeProduto').value;
    const index = parseInt(totalForms.value);

    const newRow = document.createElement('tr');
    newRow.innerHTML = `
        <td>${id} - ${nome}<input type="hidden" name="itenspedido_set-${index}-produto" value="${id}">
        <input type="hidden" name="itenspedido_set-${index}-descricao" value="${nome}"></td>
        <td><input type="number" name="itenspedido_set-${index}-quantidade" value="${qtd}" class="form-control form-control-sm item-quantidade" min="1"></td>
        <td><input type="number" name="itenspedido_set-${index}-preco_unitario" value="${preco}" class="form-control form-control-sm item-preco" step="0.01" min="0"></td>
        <td><button type="button" class="btn btn-danger btn-sm" onclick="this.closest('tr').remove(); atualizarTotal();">Remover</button></td>
    `;
    tabelaProdutosBody.appendChild(newRow);
    totalForms.value = index + 1;
    atualizarTotal();
    bootstrap.Modal.getInstance(document.getElementById('modalProduto')).hide();
}

function adicionarServico(id, nome, preco) {
    const qtd = document.getElementById('quantidadeServico').value;

    const newRow = document.createElement('tr');
    newRow.innerHTML = `
        <td>${nome}<input type="hidden" name="servicos-descricao" value="${nome}"></td>
        <td><input type="number" value="${qtd}" class="form-control form-control-sm item-quantidade-servico" min="1"></td>
        <td><input type="number" value="${preco}" class="form-control form-control-sm item-preco-servico" step="0.01" min="0"></td>
        <td><button type="button" class="btn btn-danger btn-sm" onclick="this.closest('tr').remove(); atualizarTotal();">Remover</button></td>
    `;
    tabelaServicosBody.appendChild(newRow);
    atualizarTotal();
    bootstrap.Modal.getInstance(document.getElementById('modalServico')).hide();
}

function atualizarTotal() {
    let subtotal = 0;

    tabelaProdutosBody.querySelectorAll('tr').forEach(tr => {
        const qtd = Number(tr.querySelector('.item-quantidade')?.value) || 0;
        const preco = Number(tr.querySelector('.item-preco')?.value) || 0;
        subtotal += qtd * preco;
    });

    tabelaServicosBody.querySelectorAll('tr').forEach(tr => {
        const qtd = Number(tr.querySelector('.item-quantidade-servico')?.value) || 0;
        const preco = Number(tr.querySelector('.item-preco-servico')?.value) || 0;
        subtotal += qtd * preco;
    });

    const descontoPercentual = Number(descontoPercentualInput.value) || 0;
    const valorDesconto = (subtotal * descontoPercentual) / 100;
    const totalFinal = subtotal - valorDesconto;

    subtotalPedidoSpan.textContent = subtotal.toFixed(2);
    descontoPercentualDisplaySpan.textContent = descontoPercentual.toFixed(2);
    valorDescontoSpan.textContent = valorDesconto.toFixed(2);
    totalPedidoSpan.textContent = totalFinal.toFixed(2);
}

descontoPercentualInput.addEventListener('input', atualizarTotal);
