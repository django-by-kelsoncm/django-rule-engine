/**
 * Rule Blocks - desenha a explicação em árvore de uma regra (django_rule_engine.explain_tree)
 * como blocos encaixados, no estilo Scratch.
 *
 * - modelo(explicacao): função pura que converte a árvore num modelo de elementos
 *   ({tag, classe, texto, atributos, filhos}); o template tag `regra_em_blocos` gera o mesmo
 *   modelo em Python, então servidor e navegador desenham o mesmo HTML;
 * - render(alvo, explicacao): limpa `alvo` e desenha o modelo no DOM.
 *
 * Todo texto vindo do servidor entra com textContent (nunca innerHTML).
 * Script clássico: no navegador expõe window.RuleBlocks; no Node, module.exports (testes).
 */
(function (root) {
    'use strict';

    const OPERADORES = {
        '==': '=',
        '!=': '≠',
        '<': '<',
        '<=': '≤',
        '>': '>',
        '>=': '≥',
        '=~': 'casa com',
        '=~~': 'contém o padrão',
        '!~': 'não casa com',
        '!~~': 'não contém o padrão',
        in: 'está em',
        'not in': 'não está em',
    };
    const LOGICOS = { and: 'todas estas condições', or: 'alguma destas condições' };
    const FUNCOES = { $any: 'pelo menos um é verdadeiro', $all: 'todos são verdadeiros' };
    const ICONES = { sim: '✓', nao: '✗', indef: '?' };
    const TITULOS = { sim: 'Atendido', nao: 'Não atendido', indef: 'Indefinido' };
    const COMPOSTOS = ['logico', 'nao', 'funcao', 'compreensao', 'ternario'];

    function estado(atendido) {
        if (atendido === true) {
            return 'sim';
        }
        if (atendido === false) {
            return 'nao';
        }
        return 'indef';
    }

    function formatarValor(valor) {
        if (valor === undefined || valor === null) {
            return 'nulo';
        }
        if (valor === true) {
            return 'verdadeiro';
        }
        if (valor === false) {
            return 'falso';
        }
        if (Array.isArray(valor)) {
            return '[' + valor.map(formatarValor).join(', ') + ']';
        }
        if (typeof valor === 'object') {
            return JSON.stringify(valor);
        }
        return String(valor);
    }

    // Comparações atendidas e totais de uma subárvore (sem descer nos lados das comparações).
    function contarComparacoes(no) {
        const conta = { atendidas: 0, total: 0 };
        (function visitar(n) {
            if (Array.isArray(n)) {
                n.forEach(visitar);
                return;
            }
            if (!n || typeof n !== 'object') {
                return;
            }
            if (n.tipo === 'comparacao' || n.tipo === 'contem') {
                conta.total += 1;
                if (n.atendido === true) {
                    conta.atendidas += 1;
                }
                return;
            }
            Object.keys(n).forEach((k) => visitar(n[k]));
        })(no);
        return conta;
    }

    // --- Modelo ----------------------------------------------------------------------------------

    function e(tag, classe, texto, filhos, atributos) {
        return { tag, classe: classe || '', texto: texto === undefined ? null : texto, atributos: atributos || {}, filhos: filhos || [] };
    }

    function icone(atendido) {
        const st = estado(atendido);
        return e('span', 'dre-icone', ICONES[st], [], { title: TITULOS[st], 'aria-label': TITULOS[st] });
    }

    function valor(no) {
        if (no.sensivel) {
            return e('span', 'dre-valor dre-oculto', 'oculto', [], { title: 'Campo sensível: valor não exibido' });
        }
        return e('span', 'dre-valor', formatarValor(no.valor));
    }

    // Um lado de uma comparação: rótulo e valor do campo, só o valor do literal, ou trecho e valor.
    function termo(no) {
        if (no.tipo === 'campo') {
            return [e('span', 'dre-rotulo', no.rotulo), valor(no)];
        }
        if (no.tipo === 'literal') {
            return [valor(no)];
        }
        return [e('code', 'dre-trecho', no.trecho), valor(no)];
    }

    function erro(no) {
        return no.erro ? [e('div', 'dre-erro', no.erro)] : [];
    }

    function bloco(no, cabeca, filhos, extra) {
        const classe = `dre-bloco dre-tipo-${no.tipo} dre-${estado(no.atendido)}` + (extra ? ` ${extra}` : '');
        const partes = [e('div', 'dre-cabeca', null, [icone(no.atendido)].concat(cabeca))].concat(erro(no));
        if (filhos && filhos.length) {
            partes.push(e('div', 'dre-filhos', null, filhos));
        }
        return e('div', classe, null, partes);
    }

    function ramo(titulo, no) {
        return e('div', 'dre-ramo', null, [e('span', 'dre-titulo', titulo), noModelo(no)]);
    }

    function item(no, it) {
        const st = estado(it.atendido);
        const resumo = [icone(it.atendido), e('span', 'dre-titulo', `item ${it.indice}`)];
        if (it.rotulo) {
            resumo.push(e('span', 'dre-rotulo', it.rotulo));
        }
        if (!it.incluido) {
            resumo.push(e('span', 'dre-meta', 'fora do filtro'));
        } else {
            const conta = contarComparacoes(it.expressao);
            if (conta.total) {
                resumo.push(e('span', 'dre-meta', `${conta.atendidas} de ${conta.total}`));
            }
        }
        if (it.indice === no.melhor_item) {
            resumo.push(e('span', 'dre-meta dre-destaque', it.atendido === true ? 'atende' : 'mais perto'));
        }
        const corpo = [];
        if (it.filtro) {
            corpo.push(ramo('se', it.filtro));
        }
        corpo.push(noModelo(it.expressao));
        const atributos = it.indice === no.melhor_item ? { open: '' } : {};
        return e('details', `dre-bloco dre-tipo-item dre-${st}`, null, [
            e('summary', 'dre-cabeca', null, resumo),
            e('div', 'dre-filhos', null, corpo),
        ], atributos);
    }

    function noModelo(no) {
        if (!no) {
            return e('div', 'dre-bloco dre-tipo-expressao dre-indef', null, []);
        }
        switch (no.tipo) {
            case 'logico':
                return bloco(no, [e('span', 'dre-titulo', LOGICOS[no.operador] || no.operador)], no.filhos.map(noModelo));
            case 'nao':
                return bloco(no, [e('span', 'dre-titulo', 'não é verdade que')], [noModelo(no.filho)]);
            case 'comparacao':
            case 'contem': {
                const cabeca = termo(no.esquerda)
                    .concat([e('span', 'dre-op', OPERADORES[no.operador] || no.operador)])
                    .concat(termo(no.direita));
                const filhos = [no.esquerda, no.direita].filter((n) => COMPOSTOS.indexOf(n.tipo) >= 0).map(noModelo);
                return bloco(no, cabeca, filhos);
            }
            case 'funcao':
                return bloco(
                    no,
                    [e('span', 'dre-titulo', FUNCOES[no.nome] || `${no.nome}(…)`), valor(no)],
                    no.argumentos.map(noModelo),
                );
            case 'compreensao': {
                const cabeca = [
                    e('span', 'dre-titulo', `para cada ${no.variavel} em`),
                    e('span', 'dre-rotulo', no.lista.rotulo || no.lista.trecho),
                ];
                if (no.total !== null && no.total !== undefined) {
                    cabeca.push(e('span', 'dre-meta', `${no.total} ${no.total === 1 ? 'item' : 'itens'}`));
                }
                if (no.filtro) {
                    cabeca.push(e('span', 'dre-meta', 'se'), e('code', 'dre-trecho', no.filtro));
                }
                const filhos = no.itens.map((it) => item(no, it));
                if (no.truncado) {
                    filhos.push(e('div', 'dre-meta', `mais ${no.total - no.itens.length} itens não exibidos`));
                }
                return bloco(no, cabeca, filhos);
            }
            case 'ternario':
                return bloco(no, [e('span', 'dre-titulo', 'se… então… senão'), valor(no)], [
                    ramo('se', no.condicao),
                    ramo('então', no.se_verdadeiro),
                    ramo('senão', no.se_falso),
                ]);
            case 'campo':
                return bloco(no, termo(no));
            default:
                return bloco(no, [e('code', 'dre-trecho', no.trecho), valor(no)]);
        }
    }

    function modelo(explicacao) {
        const atendido = explicacao ? explicacao.atendido : null;
        const filhos = [];
        if (explicacao && explicacao.raiz) {
            filhos.push(noModelo(explicacao.raiz));
        } else if (explicacao && explicacao.erro) {
            filhos.push(e('div', 'dre-erro', explicacao.erro));
        }
        return e('div', `dre-blocos dre-${estado(atendido)}`, null, filhos);
    }

    // --- DOM -------------------------------------------------------------------------------------

    function paraDom(doc, m) {
        const no = doc.createElement(m.tag);
        if (m.classe) {
            no.className = m.classe;
        }
        Object.keys(m.atributos).forEach((k) => no.setAttribute(k, m.atributos[k]));
        if (m.texto !== null) {
            no.textContent = String(m.texto);
        }
        m.filhos.forEach((f) => no.appendChild(paraDom(doc, f)));
        return no;
    }

    function render(alvo, explicacao) {
        const doc = alvo.ownerDocument || document;
        while (alvo.firstChild) {
            alvo.removeChild(alvo.firstChild);
        }
        const no = paraDom(doc, modelo(explicacao));
        alvo.appendChild(no);
        return no;
    }

    const api = { OPERADORES, estado, formatarValor, contarComparacoes, modelo, render };
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = api;
    } else {
        root.RuleBlocks = api;
    }
})(typeof window !== 'undefined' ? window : globalThis);
