// Testes das funções puras de rule_explain.js. Executar com: node --test "tests/js/*.test.js"
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const { estado, formatarValor, trechosDaRegra, tabelaDaCondicao } = require(
    path.join(__dirname, '..', '..', 'src', 'django_rule_engine', 'static', 'rule_widget', 'rule_explain.js'),
);

const linha = (atomo, campo, operador, esperado, extra) => ({
    atomo, campo, rotulo: campo, operador, esperado, sensivel: false, erro: '', ...extra,
});

test('estado mapeia atendido para classe', () => {
    assert.equal(estado(true), 'atendido');
    assert.equal(estado(false), 'nao-atendido');
    assert.equal(estado(null), 'erro');
});

test('formatarValor usa JSON e travessão para indefinido', () => {
    assert.equal(formatarValor('a'), '"a"');
    assert.equal(formatarValor(null), 'null');
    assert.equal(formatarValor([1, true]), '[1,true]');
    assert.equal(formatarValor(undefined), '—');
});

test('trechosDaRegra colore cada condição e mantém o resto sem estado', () => {
    const regra = "idade >= 18 and status == 'ativo'";
    const explicacao = {
        condicoes: [
            { condicao: 'idade >= 18', atendido: false, erro: '', detalhes: { tipo: 'simples', linhas: [linha('idade >= 18', 'idade', '>=', '18')] } },
            { condicao: "status == 'ativo'", atendido: true, erro: '', detalhes: { tipo: 'simples', linhas: [] } },
        ],
    };
    assert.deepEqual(trechosDaRegra(regra, explicacao), [
        { texto: 'idade >= 18', atendido: false },
        { texto: ' and ' },
        { texto: "status == 'ativo'", atendido: true },
    ]);
    assert.equal(trechosDaRegra(regra, explicacao).map((t) => t.texto).join(''), regra);
});

test('trechosDaRegra detalha comparações de condição entre parênteses e marca erro', () => {
    const regra = 'x and (a == 1 or b == 2)';
    const explicacao = {
        condicoes: [
            { condicao: 'x', atendido: null, erro: 'SymbolResolutionError: x', detalhes: { tipo: 'simples', linhas: [linha('x', 'x', '', 'verdadeiro')] } },
            {
                condicao: '(a == 1 or b == 2)', atendido: true, erro: '',
                detalhes: { tipo: 'simples', linhas: [linha('a == 1', 'a', '==', '1', { atendido: false }), linha('b == 2', 'b', '==', '2', { atendido: true })] },
            },
        ],
    };
    assert.deepEqual(trechosDaRegra(regra, explicacao), [
        { texto: 'x', atendido: null },
        { texto: ' and (' },
        { texto: 'a == 1', atendido: false },
        { texto: ' or ' },
        { texto: 'b == 2', atendido: true },
        { texto: ')' },
    ]);
});

test('trechosDaRegra sem explicação devolve a regra inteira', () => {
    assert.deepEqual(trechosDaRegra('a', null), [{ texto: 'a' }]);
});

test('tabelaDaCondicao simples: Campo | Esperado | Valor e oculta sensíveis', () => {
    const tabela = tabelaDaCondicao({
        condicao: "a == 1 or cpf == '1'",
        detalhes: {
            tipo: 'simples',
            linhas: [
                linha('a == 1', 'a', '==', '1', { valor: 0, atendido: false }),
                linha("cpf == '1'", 'cpf', '==', "'1'", { valor: null, atendido: true, sensivel: true }),
            ],
        },
    });
    assert.deepEqual(tabela.cabecalhos, ['Campo', 'Esperado', 'Valor']);
    assert.deepEqual(tabela.linhas[0].map((c) => c.texto), ['a', '== 1', '0']);
    assert.equal(tabela.linhas[0][2].atendido, false);
    assert.equal(tabela.linhas[1][2].texto, '(oculto)');
    assert.equal(tabela.linhas[1][2].atendido, true);
});

test('tabelaDaCondicao simples com erro mostra a mensagem em amarelo', () => {
    const tabela = tabelaDaCondicao({
        detalhes: { tipo: 'simples', linhas: [linha('x == 1', 'x', '==', '1', { valor: null, atendido: null, erro: 'SymbolResolutionError: x' })] },
    });
    assert.equal(tabela.linhas[0][2].texto, 'SymbolResolutionError: x');
    assert.equal(tabela.linhas[0][2].atendido, null);
});

test('tabelaDaCondicao por_item: uma coluna por item', () => {
    const tabela = tabelaDaCondicao({
        condicao: '$any(...)',
        erro: '',
        detalhes: {
            tipo: 'por_item', funcao: 'any', variavel: 'm', lista: 'outras_matriculas', filtro: '', itens: 2, erro: '',
            linhas: [
                { ...linha("m['tipo'] == 'aluno'", "m['tipo']", '==', "'aluno'"), rotulo: 'tipo', valores: ['aluno', 'servidor'], resultados: [true, false], atendido: true },
                { ...linha("m['cpf'] != ''", "m['cpf']", '!=', "''"), rotulo: 'cpf', sensivel: true, valores: null, resultados: [true, true], atendido: true },
            ],
        },
    });
    assert.deepEqual(tabela.cabecalhos, ['Campo', 'Esperado', 'm 1', 'm 2']);
    assert.match(tabela.titulo, /^\$any\(… for m in outras_matriculas\) — 2 item/);
    assert.deepEqual(tabela.linhas[0].map((c) => c.texto), ['tipo', "== 'aluno'", '"aluno"', '"servidor"']);
    assert.deepEqual(tabela.linhas[0].slice(2).map((c) => c.atendido), [true, false]);
    assert.deepEqual(tabela.linhas[1].slice(2).map((c) => c.texto), ['(oculto)', '(oculto)']);
});

test('tabelaDaCondicao por_item sem itens mostra coluna Valor', () => {
    const tabela = tabelaDaCondicao({
        erro: 'SymbolResolutionError: lista',
        detalhes: {
            tipo: 'por_item', funcao: 'all', variavel: 'x', lista: 'lista', filtro: 'x', itens: null, erro: 'SymbolResolutionError: lista',
            linhas: [{ ...linha('x > 1', 'x', '>', '1'), valores: null, resultados: null, atendido: null, erro: 'SymbolResolutionError: lista' }],
        },
    });
    assert.deepEqual(tabela.cabecalhos, ['Campo', 'Esperado', 'Valor']);
    assert.equal(tabela.erro, 'SymbolResolutionError: lista');
    assert.match(tabela.titulo, /if x\)/);
    assert.equal(tabela.linhas[0][2].atendido, null);
});
