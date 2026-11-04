// Testes de rule_blocks.js. Executar com: node --test "tests/js/*.test.js"
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const RuleBlocks = require(
    path.join(__dirname, '..', '..', 'src', 'django_rule_engine', 'static', 'rule_widget', 'rule_blocks.js'),
);

// Mesma fixture do teste Python (tests/test_blocks.py): servidor e navegador geram o mesmo modelo.
const casos = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'fixtures', 'blocos.json'), 'utf8'));

casos.forEach((caso) => {
    test(`modelo igual ao do Python: ${caso.nome}`, () => {
        assert.deepEqual(RuleBlocks.modelo(caso.explicacao), caso.modelo);
    });
});

test('estado e formatarValor', () => {
    assert.deepEqual([true, false, null].map(RuleBlocks.estado), ['sim', 'nao', 'indef']);
    assert.equal(RuleBlocks.formatarValor(null), 'nulo');
    assert.equal(RuleBlocks.formatarValor(undefined), 'nulo');
    assert.equal(RuleBlocks.formatarValor(true), 'verdadeiro');
    assert.equal(RuleBlocks.formatarValor(false), 'falso');
    assert.equal(RuleBlocks.formatarValor(['a', 1, null]), '[a, 1, nulo]');
    assert.equal(RuleBlocks.formatarValor({ a: 'é', b: [1] }), '{"a":"é","b":[1]}');
});

test('contarComparacoes não desce nos lados', () => {
    const cmp = (atendido) => ({ tipo: 'comparacao', atendido, esquerda: { tipo: 'comparacao', atendido: true } });
    const arvore = { tipo: 'logico', filhos: [cmp(true), { tipo: 'nao', filho: cmp(false) }] };
    assert.deepEqual(RuleBlocks.contarComparacoes(arvore), { atendidas: 1, total: 2 });
});

// DOM mínimo: suficiente para render() (createElement, setAttribute, textContent, appendChild).
function documentoFalso() {
    function criar(tag) {
        return {
            tag,
            atributos: {},
            filhos: [],
            textContent: '',
            className: '',
            ownerDocument: null,
            get firstChild() {
                return this.filhos[0] || null;
            },
            setAttribute(k, v) {
                this.atributos[k] = v;
            },
            appendChild(f) {
                this.filhos.push(f);
                return f;
            },
            removeChild(f) {
                this.filhos.splice(this.filhos.indexOf(f), 1);
            },
        };
    }
    const doc = { createElement: criar };
    return doc;
}

test('render limpa o alvo e monta o DOM com textContent', () => {
    const doc = documentoFalso();
    const alvo = doc.createElement('div');
    alvo.ownerDocument = doc;
    alvo.appendChild(doc.createElement('p'));
    const caso = casos.find((c) => c.nome === 'matriculas');
    const raiz = RuleBlocks.render(alvo, caso.explicacao);
    assert.equal(alvo.filhos.length, 1);
    assert.equal(raiz.className, 'dre-blocos dre-nao');
    const cabeca = raiz.filhos[0].filhos[0];
    assert.equal(cabeca.className, 'dre-cabeca');
    assert.equal(cabeca.filhos[0].textContent, '✗');
    assert.equal(cabeca.filhos[0].atributos.title, 'Não atendido');
});
