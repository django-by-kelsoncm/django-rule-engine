/**
 * Rule Explain - renderiza a explicação de uma regra (ver django_rule_engine.explain).
 *
 * - regra colorida: verde = atendido, vermelho = não atendido, amarelo = erro;
 * - tabela "Campo | Esperado | Valor" por condição, com uma coluna por item em $any/$all.
 *
 * Todo texto vindo do servidor entra com textContent (nunca innerHTML).
 * Script clássico: no navegador expõe window.RuleExplain; no Node, module.exports (testes).
 */
(function (root) {
    'use strict';

    const OCULTO = '(oculto)';

    function estado(atendido) {
        if (atendido === true) {
            return 'atendido';
        }
        if (atendido === false) {
            return 'nao-atendido';
        }
        return 'erro';
    }

    function formatarValor(valor) {
        if (valor === undefined) {
            return '—';
        }
        return JSON.stringify(valor);
    }

    // Trechos a destacar de uma condição: a condição inteira em $any/$all ou com uma só linha;
    // senão, cada comparação (ex.: "(a or b)" dentro de um "and" colore "a" e "b").
    function destaquesDaCondicao(condicao) {
        const detalhes = condicao.detalhes || {};
        const linhas = detalhes.linhas || [];
        if (detalhes.tipo === 'simples' && linhas.length > 1) {
            return linhas.map((l) => ({ texto: l.atomo, atendido: l.erro ? null : l.atendido }));
        }
        return [{ texto: condicao.condicao, atendido: condicao.erro ? null : condicao.atendido }];
    }

    // Fatia a regra em trechos [{texto, atendido?}] na ordem em que aparecem; o que não foi
    // avaliado (operadores, parênteses, espaços) fica sem "atendido".
    function trechosDaRegra(regra, explicacao) {
        const trechos = [];
        let cursor = 0;
        const condicoes = (explicacao && explicacao.condicoes) || [];
        condicoes.flatMap(destaquesDaCondicao).forEach((destaque) => {
            const inicio = destaque.texto ? regra.indexOf(destaque.texto, cursor) : -1;
            if (inicio < 0) {
                return;
            }
            if (inicio > cursor) {
                trechos.push({ texto: regra.slice(cursor, inicio) });
            }
            trechos.push({ texto: destaque.texto, atendido: destaque.atendido });
            cursor = inicio + destaque.texto.length;
        });
        if (cursor < regra.length) {
            trechos.push({ texto: regra.slice(cursor) });
        }
        return trechos;
    }

    // Dados da tabela de uma condição: {titulo, cabecalhos, linhas: [[{texto, atendido?, title?}]]}.
    function tabelaDaCondicao(condicao) {
        const detalhes = condicao.detalhes || {};
        const linhas = detalhes.linhas || [];
        const esperado = (l) => ({ texto: l.operador ? `${l.operador} ${l.esperado}` : l.esperado });
        const campo = (l) => ({ texto: l.rotulo || l.campo, title: l.atomo });

        if (detalhes.tipo === 'por_item') {
            const total = Math.max(
                detalhes.itens || 0,
                ...linhas.map((l) => (Array.isArray(l.resultados) ? l.resultados.length : 0)),
            );
            const cabecalhos = ['Campo', 'Esperado'];
            for (let i = 0; i < total; i++) {
                cabecalhos.push(`${detalhes.variavel} ${i + 1}`);
            }
            if (!total) {
                cabecalhos.push('Valor');
            }
            const filtro = detalhes.filtro ? ` if ${detalhes.filtro}` : '';
            return {
                titulo: `$${detalhes.funcao}(… for ${detalhes.variavel} in ${detalhes.lista}${filtro}) — ${total} item(ns)`,
                erro: detalhes.erro || condicao.erro || '',
                cabecalhos,
                linhas: linhas.map((l) => {
                    const celulas = [campo(l), esperado(l)];
                    if (!total) {
                        celulas.push({ texto: l.erro || '—', atendido: l.erro ? null : undefined });
                    }
                    for (let i = 0; i < total; i++) {
                        const resultado = Array.isArray(l.resultados) ? l.resultados[i] : undefined;
                        const valor = l.sensivel ? OCULTO : formatarValor(Array.isArray(l.valores) ? l.valores[i] : undefined);
                        celulas.push({
                            texto: valor,
                            atendido: typeof resultado === 'boolean' ? resultado : null,
                            title: l.erro || undefined,
                        });
                    }
                    return celulas;
                }),
            };
        }

        return {
            titulo: '',
            erro: '',
            cabecalhos: ['Campo', 'Esperado', 'Valor'],
            linhas: linhas.map((l) => [
                campo(l),
                esperado(l),
                {
                    texto: l.sensivel ? OCULTO : l.erro && l.valor === null ? l.erro : formatarValor(l.valor),
                    atendido: l.erro ? null : l.atendido,
                    title: l.erro || undefined,
                },
            ]),
        };
    }

    // --- DOM -------------------------------------------------------------------------------------

    function el(doc, tag, texto, classe) {
        const no = doc.createElement(tag);
        if (texto !== undefined && texto !== null) {
            no.textContent = String(texto);
        }
        if (classe) {
            no.className = classe;
        }
        return no;
    }

    function regraColorida(doc, regra, explicacao) {
        const bloco = el(doc, 'pre', null, 'rule-explain-rule');
        trechosDaRegra(regra, explicacao).forEach((t) => {
            if (!('atendido' in t)) {
                bloco.appendChild(doc.createTextNode(t.texto));
                return;
            }
            const span = el(doc, 'span', t.texto, `rule-explain-${estado(t.atendido)}`);
            span.title = t.atendido === true ? 'Atendido' : t.atendido === false ? 'Não atendido' : 'Erro';
            bloco.appendChild(span);
        });
        return bloco;
    }

    function tabelaComparacoes(doc, condicao) {
        const dados = tabelaDaCondicao(condicao);
        const bloco = el(doc, 'div', null, 'rule-explain-condition');
        if (dados.titulo) {
            bloco.appendChild(el(doc, 'div', dados.titulo, 'rule-explain-title'));
        }
        if (dados.erro) {
            bloco.appendChild(el(doc, 'div', dados.erro, 'rule-explain-error'));
        }
        const tabela = el(doc, 'table', null, 'rule-explain-table');
        const cabecalho = tabela.createTHead().insertRow();
        dados.cabecalhos.forEach((c) => cabecalho.appendChild(el(doc, 'th', c)));
        const corpo = tabela.createTBody();
        dados.linhas.forEach((linha) => {
            const tr = corpo.insertRow();
            linha.forEach((celula) => {
                const td = tr.insertCell();
                td.textContent = celula.texto;
                if ('atendido' in celula && celula.atendido !== undefined) {
                    td.className = `rule-explain-${estado(celula.atendido)}`;
                }
                if (celula.title) {
                    td.title = celula.title;
                }
            });
        });
        bloco.appendChild(tabela);
        return bloco;
    }

    function renderizar(doc, explicacao) {
        const bloco = el(doc, 'div', null, 'rule-explain');
        if (!explicacao) {
            return bloco;
        }
        bloco.appendChild(regraColorida(doc, explicacao.regra || '', explicacao));
        (explicacao.condicoes || []).forEach((c) => bloco.appendChild(tabelaComparacoes(doc, c)));
        return bloco;
    }

    const api = { estado, formatarValor, trechosDaRegra, tabelaDaCondicao, renderizar };
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = api;
    } else {
        root.RuleExplain = api;
    }
})(typeof window !== 'undefined' ? window : globalThis);
